"""
Defensive date parsing for feed items.

Feeds observed in the wild emit at least three shapes:
  - ISO-8601 with UTC offset:   "2026-08-20T14:03:00+00:00" / "...Z"
  - Plain ISO date/datetime:    "2026-08-20" / "2026-08-20T14:03:00"
  - US-style m/d/Y:             "8/20/2026"

A silent parsing failure here can quietly de-weight every item in a feed
(recency_weight() would treat an unparseable date as "infinitely old" or
crash) without ever surfacing an error, which is why this has its own
module and its own test (test_date_parsing.py) instead of being inlined
into each fetcher.

parse_item_date raises DateParseError on failure -- callers must not
swallow this silently; they should log it and skip the item, which is
different from treating the item as neutral/zero-weight.
"""

from __future__ import annotations

from datetime import datetime, timezone


class DateParseError(ValueError):
    pass


_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%m/%d/%Y",
    "%m/%d/%y",
)


def parse_item_date(raw: str) -> datetime:
    """Parse a feed-supplied date string into a timezone-aware UTC datetime.

    Naive results (no offset in the source string) are assumed UTC, which
    is a deliberate, documented assumption -- these sources (SEC EDGAR,
    House Clerk XML, RSS pubDate) are US-filed and predominantly UTC or
    US-Eastern; UTC is the safer default for a "how stale is this" check
    since it never makes an item look fresher than it is by more than the
    ET/UTC offset.
    """
    if not raw or not raw.strip():
        raise DateParseError("empty date string")
    s = raw.strip()

    # Normalize trailing 'Z' (Zulu/UTC) to an explicit offset for strptime.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Last resort: fromisoformat handles a few extra ISO variants
    # (e.g. "2026-08-20T14:03:00+00:00" with colon-separated offsets it
    # already covers above, but this also picks up some edge cases like
    # "2026-08-20T14:03" without seconds).
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        pass

    raise DateParseError(f"unparseable date: {raw!r}")
