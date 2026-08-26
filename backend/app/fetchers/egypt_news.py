"""
Egypt News feed: EGX-relevant news (earnings, CBE announcements, currency/
macro, regional events). Powers the Egypt tab ONLY -- this module never
writes into universe.tracked_universe and is never checked against
Insiders/Congress, matching the strict separation required by the spec.

Uses GDELT's sourcecountry:EG filter to scope the query before the two
gates run (source allow-list + subject gate), which fixes most noise before
it ever reaches the gate logic. Mubasher has no public API/RSS -- kept as a
manual/semi-automated input rather than a scraper, since Mubasher's terms
of use don't visibly address automated pulls and that needs a direct check
before shipping anything commercial.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any

import httpx

from ..allowlist import source_gate_egypt
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import passes_egypt_subject_gate
from ..sentiment import classify

logger = logging.getLogger("mtm.fetchers.egypt_news")

# Same pattern as insiders.py's _parse_stats and market_news.py's
# _reject_stats -- one summary line per fetch instead of either
# per-item log spam or, as happened here before this existed, zero
# visibility into whether "0 items" meant "GDELT genuinely returned
# nothing" or "articles came back but the allow-list/subject gates
# rejected all of them" (a very real possibility given this app's Egypt
# allow-list is a curated ~17-outlet list, and GDELT's sourcecountry:EG
# filter surfaces every Egyptian domain it knows about, most of which
# are correctly NOT on that list by design).
_reject_stats: Counter = Counter()


def reset_and_snapshot_reject_stats() -> dict[str, int]:
    global _reject_stats
    snapshot = dict(_reject_stats)
    _reject_stats = Counter()
    return snapshot

# Aggregate rejection-reason counts, same pattern as insiders.py and
# market_news.py's counters -- exists because this exact "succeeded with
# 0 items, zero visibility into why" shape has now happened on three
# separate sources in this app, and every time the real cause was only
# findable once a reason-coded counter existed.
_reject_stats: Counter = Counter()


def reset_and_snapshot_reject_stats() -> dict[str, int]:
    global _reject_stats
    snapshot = dict(_reject_stats)
    _reject_stats = Counter()
    return snapshot

GDELT_HOST = "api.gdeltproject.org"
GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

NATIVE_EGYPTIAN_OUTLETS = {
    "The Egyptian Exchange (EGX)", "Central Bank of Egypt", "CAPMAS",
    "Enterprise", "Mubasher", "Al-Mal", "Al-Borsa", "Al-Masry Al-Youm",
    "Al-Shorouk", "Al-Ahram", "Daily News Egypt",
}


async def _fetch_gdelt(query: str) -> dict[str, Any]:
    await throttle(GDELT_HOST)
    params = {
        "query": f"{query} sourcecountry:EG",
        "mode": "artlist",
        "format": "json",
        "maxrecords": "75",
    }
    # GDELT's DOC API is documented as returning spurious 429s to
    # non-browser User-Agent strings even under quota -- confirmed via a
    # maintainer-acknowledged issue on the gdelt-doc-api client. This is
    # not an attempt to impersonate a browser for scraping purposes; it's
    # matching a documented, publicly-known quirk of this specific free
    # API to get the request treated the same as any other legitimate
    # client.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    # GDELT's real-world 429 behavior (per multiple independent reports)
    # is stickier than a simple rate limit: bursts can trigger blocks
    # lasting well beyond a single Retry-After window, and hammering it
    # with immediate retries makes it worse, not better. So: try once,
    # and if 429'd, respect Retry-After if given, otherwise back off for
    # a full extra rate-limit period once and try exactly one more time.
    # Beyond that, give up cleanly for this cycle -- the next scheduled
    # refresh (30 min later) is a more realistic recovery point than
    # anything this function can force within a single call.
    last_exc: Exception | None = None
    for attempt in range(2):
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.get(GDELT_DOC_API, params=params, headers=headers)
            except httpx.HTTPError as exc:
                # Broadened from just (TimeoutException, ConnectError) --
                # confirmed live that a second, different httpx exception
                # subtype (httpx has ~10: ReadTimeout, PoolTimeout,
                # RemoteProtocolError, etc., several of which also have
                # empty str() by design) still slipped through the
                # narrower catch and surfaced as feed_status.error == "".
                # httpx.HTTPError is the common base class for all of
                # them, and refresh.py's error formatting now always
                # prepends the exception type name regardless, so this is
                # the last place this class of bug can hide.
                # These raise from client.get() itself, before any status
                # code exists to check -- the 429-only retry logic above
                # never saw this class of failure at all. Confirmed live:
                # egypt_news failed with an empty error message, which is
                # httpx.TimeoutException's actual str() representation
                # (its __str__ returns "" by design), making the failure
                # look unexplained in logs until named explicitly here.
                last_exc = exc
                logger.warning("GDELT request failed (attempt %d/2): %s: %s", attempt + 1, type(exc).__name__, exc)
                if attempt == 0:
                    await asyncio.sleep(3.0)
                    continue
                raise
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 5.0
                # Cap the wait regardless of what GDELT asks for -- this
                # function runs inside refresh.py's 45s hard timeout for
                # egypt_news; a large Retry-After value plus two request
                # round-trips could otherwise blow that budget and get
                # cancelled mid-sleep, which is strictly worse than just
                # giving up after a bounded wait.
                wait_seconds = min(wait_seconds, 15.0)
                last_exc = httpx.HTTPStatusError(
                    f"429 from GDELT (attempt {attempt + 1}/2)", request=resp.request, response=resp
                )
                if attempt == 0:
                    await asyncio.sleep(wait_seconds)
                    continue
                raise last_exc
            resp.raise_for_status()
            # GDELT's DOC API returns a genuinely empty body (not even
            # '{}') with a 200 status when a query matches zero articles
            # -- confirmed live: raise_for_status() passed, but
            # resp.json() then raised "Expecting value: line 1 column 1
            # (char 0)". An empty body on a successful response means
            # zero results, not a fetch failure -- treat it as such
            # rather than letting the whole source get marked failed.
            if not resp.text.strip():
                return {"articles": []}
            try:
                return resp.json()
            except ValueError:
                # Any other non-JSON 200 body (e.g. an HTML error page
                # GDELT sometimes serves instead of JSON) -- same
                # reasoning: don't crash the whole fetch over one
                # malformed response, but do keep it visible.
                return {"articles": []}
    raise last_exc  # unreachable given the loop above, but keeps type-checkers happy


def process_article(raw: dict[str, Any]) -> dict[str, Any] | None:
    headline = raw.get("title", "")
    url = raw.get("url", "")
    published_raw = raw.get("seendate")

    # Check field presence BEFORE calling the source gate on a possibly-
    # empty url -- matches the fix already applied in market_news.py's
    # process_feed_entry, where the reverse order silently discarded
    # every item when a field came back empty from an endpoint switch.
    # GDELT's field names (url/title/seendate) are confirmed correct
    # against the API's documented response shape, but this ordering is
    # still the more defensive, correct pattern regardless.
    if not headline:
        _reject_stats["no_headline"] += 1
        return None
    if not url:
        _reject_stats["no_url"] += 1
        return None
    if not published_raw:
        _reject_stats["no_date"] += 1
        return None

    outlet_name = source_gate_egypt(url)
    if outlet_name is None:
        _reject_stats["source_gate"] += 1
        return None

    try:
        published_at = parse_item_date(published_raw)
    except ValueError:
        _reject_stats["unparseable_date"] += 1
        return None

    is_native = outlet_name in NATIVE_EGYPTIAN_OUTLETS
    mentions_egypt = "egypt" in headline.lower() or "egx" in headline.lower() or "مصر" in headline

    if not passes_egypt_subject_gate(
        headline=headline,
        outlet_is_native_egyptian=is_native,
        mentions_egypt_or_egx=mentions_egypt or is_native,
    ):
        _reject_stats["subject_gate"] += 1
        return None

    lean_value = classify(headline)
    lean = "bullish" if lean_value > 0.15 else "bearish" if lean_value < -0.15 else "neutral"

    _reject_stats["accepted"] += 1
    return {
        "ticker": None,  # market-wide unless a specific EGX ticker/company is separately resolved
        "headline": headline,
        "outlet": outlet_name,
        "source_url": url,
        "published_at": published_at,
        "lean": lean,
    }


async def fetch_egypt_news() -> list[dict[str, Any]]:
    raw = await _fetch_gdelt("EGX OR \"Central Bank of Egypt\" OR Egyptian pound")
    articles = raw.get("articles", [])
    results = []
    for article in articles:
        parsed = process_article(article)
        if parsed is not None:
            results.append(parsed)
    logger.info(
        "GDELT: fetched %d raw articles, %d passed all gates, reject reasons: %s",
        len(articles), len(results), reset_and_snapshot_reject_stats(),
    )
    return results
