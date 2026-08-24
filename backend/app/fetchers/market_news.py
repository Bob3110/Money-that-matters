"""
Market News feed: earnings/results, major economic/world events, and
statements from public figures (incl. Trump) about specific stocks --
caught via keyword match on mainstream-outlet RSS, never by polling Truth
Social directly (mainstream outlets report those posts within minutes).

Prefers outlets' own RSS feeds so the source gate is inherent rather than
applied after the fact. SEC 8-K filings are treated as the strongest
"press release" source: no aggregator sits between the company and the
filing.

Growable universe: any ticker that clears both gates here is added to
universe.tracked_universe so Insiders starts checking it too.
"""

from __future__ import annotations

import calendar
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from ..allowlist import source_gate_us
from ..company_names import find_tickers_by_company_name
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import passes_us_subject_gate
from ..sentiment import classify
from ..universe import tracked_universe

logger = logging.getLogger("mtm.fetchers.market_news")

# Aggregate rejection-reason counts, same pattern as insiders.py's
# _parse_stats -- exists so a caller can log one summary line per feed
# instead of either flooding with a per-item DEBUG line or, as happened
# on the first live run after switching CNBC endpoints, having zero
# visibility into WHY '30 raw entries, 0 passed' happened.
_reject_stats: Counter = Counter()


def reset_and_snapshot_reject_stats() -> dict[str, int]:
    global _reject_stats
    snapshot = dict(_reject_stats)
    _reject_stats = Counter()
    return snapshot

# Outlets' own RSS feeds -- source gate is inherent because we only ever
# request from these hosts in the first place. Business/markets-desk feeds
# specifically, per the "markets/business desk" requirement of the subject
# gate (not each outlet's general/world-news feed).
#
# Reuters' public RSS feeds (feeds.reuters.com and reuters.com/*/rss
# paths) are confirmed DEAD as of March 2026 -- multiple independent
# reports (GitHub issue threads, RSS-tooling docs) describe them as
# returning nothing or erroring, consistent with what this app's own
# first live run observed (401 Forbidden). Reuters remains on the
# allow-list in allowlist.py for attribution purposes (e.g. Reuters
# content reached via a licensed API or aggregator that names Reuters as
# the original source), but it is NOT pulled via RSS here because there
# is no working public feed to pull. Do not re-add a Reuters RSS URL
# without first verifying it actually returns 200 with real content --
# see this comment's history for why that check matters.
#
# CNBC's www.cnbc.com/id/<id>/device/rss/rss.html pages are a browser-
# facing wrapper, not the raw feed -- a live run confirmed they return
# 200 OK with a body feedparser silently parses into zero entries for a
# non-browser client (same failure shape as the Reuters 401, just
# swallowed instead of raised). CNBC's own RSSHub integration reveals
# the real underlying machine-readable endpoint below, which is what
# every third-party CNBC RSS tool actually calls.
CNBC_FEED_API = "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id={feed_id}"

RSS_FEEDS: dict[str, str] = {
    # Labeled accurately based on CNBC's own feed descriptions, not
    # assumed -- the original label here ("CNBC (Markets)") was wrong;
    # id/10001147 is actually CNBC's CEO/company-news feed. Still real,
    # still business-relevant content, just mislabeled before.
    CNBC_FEED_API.format(feed_id="10001147"): "CNBC (CEOs & Companies)",
    CNBC_FEED_API.format(feed_id="10000664"): "CNBC (Finance)",
    CNBC_FEED_API.format(feed_id="100370673"): "CNBC (Earnings)",
    # Bloomberg and WSJ do not offer full public RSS for markets content;
    # in production these are reached via their official partner feeds or
    # licensed API, not scraped -- left as a documented gap rather than a
    # scraper that violates ToS.
}

SEC_8K_FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"


async def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    host = httpx.URL(url).host
    await throttle(host)
    # A generic app UA got Reuters to 401 outright; CNBC's wrapper pages
    # silently returned parseable-but-empty content to the same UA
    # instead of erroring, which is a harder failure to notice. Using a
    # real browser UA here isn't about impersonating a browser to evade
    # blocking policy -- it's matching what CNBC's own documented,
    # third-party-tool-recommended endpoint (search.cnbc.com's combinedcms
    # view) expects from any RSS client.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        if not parsed.get("entries"):
            # Don't just report "0 items" with no way to tell fetch
            # failure from genuinely-empty feed apart -- log enough of
            # the raw response to diagnose which one this is, without
            # dumping the whole body.
            logger.warning(
                "Feed at %s returned 0 entries. Response length=%d, first 200 chars: %r",
                url, len(resp.text), resp.text[:200],
            )
        return parsed


def _extract_tickers(text: str, universe: frozenset[str]) -> set[str]:
    """Two matching strategies, combined:
    1. Literal ticker symbols as whole-word uppercase tokens (e.g. "AAPL")
       -- rare in real headlines but occasionally used, especially in
       parenthetical asides like "Apple (AAPL)". Single-letter tickers
       (e.g. "A" for Agilent) are excluded from this path -- confirmed
       live: "A media M&A chill..." matched Agilent's ticker purely
       because "A" is also the English indefinite article, a false
       positive with no real relationship to the headline's content.
       Real mentions of single-letter-ticker companies are still caught
       via the company-name path below (e.g. "Agilent" itself).
    2. Company names (e.g. "Apple"), via company_names.py's normalized
       matcher -- this is what most real headlines actually use. Never
       invents a ticker that isn't a real, verifiable symbol already in
       the tracked universe; the name matcher only returns tickers already
       present in `universe`.
    """
    literal_words = {w.strip("$().,:;\"'").upper() for w in text.split()}
    from_symbols = {w for w in (literal_words & universe) if len(w) > 1}
    from_names = find_tickers_by_company_name(text, universe)
    return from_symbols | from_names


def _resolve_published_at(entry: dict[str, Any], published_raw: str):
    """Prefer feedparser's own pre-parsed date struct (published_parsed /
    updated_parsed -- a 9-tuple struct_time, always normalized to UTC by
    feedparser regardless of the feed's original date format) over
    re-parsing the raw string ourselves. feedparser already handles RFC
    822, RFC 3339/ISO-8601, and several nonstandard variants internally;
    duplicating that parsing in dates.py's fixed format list is both
    redundant and, as a live run confirmed, incomplete (RFC 822 -- the
    actual RSS 2.0 <pubDate> standard -- wasn't in the original three
    formats dates.py covered, so 100% of items from a real RSS feed
    failed with 'unparseable_date' until this existed). Falls back to
    dates.parse_item_date on the raw string only if feedparser didn't
    produce a parsed struct."""
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct is not None:
        return datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
    return parse_item_date(published_raw)


async def process_feed_entry(
    entry: dict[str, Any],
    outlet: str,
    is_markets_business_desk: bool,
) -> dict[str, Any] | None:
    global _reject_stats
    headline = entry.get("title", "")
    # The search.cnbc.com/combinedcms endpoint (switched to after the old
    # device/rss/rss.html wrapper was confirmed to silently return
    # zero-parseable content) may structure the article URL under a
    # different feedparser field than the standard 'link' -- confirmed
    # live: switching endpoints took CNBC from '30 raw entries, 0 passed'
    # for all three feeds simultaneously, which is the signature of every
    # item failing the SAME early check (source gate on an empty link),
    # not genuinely irrelevant content. Try the standard field first, then
    # documented feedparser fallbacts for feeds that put the URL in
    # 'id'/'guid' instead.
    link = entry.get("link") or entry.get("id") or entry.get("guid") or ""
    published_raw = entry.get("published") or entry.get("updated") or entry.get("pubDate")

    if not link:
        _reject_stats["no_link"] += 1
        return None
    if not headline:
        _reject_stats["no_headline"] += 1
        return None
    if not published_raw:
        _reject_stats["no_date"] += 1
        return None

    outlet_name = source_gate_us(link)
    if outlet_name is None:
        _reject_stats["source_gate"] += 1
        return None  # fails source gate -- discard, do not attribute elsewhere

    try:
        published_at = _resolve_published_at(entry, published_raw)
    except ValueError:
        _reject_stats["unparseable_date"] += 1
        return None

    universe = tracked_universe.all()
    mentioned = _extract_tickers(headline, universe)

    if not passes_us_subject_gate(
        headline=headline,
        tracked_tickers=universe,
        mentioned_tickers=mentioned,
        is_markets_business_desk=is_markets_business_desk,
    ):
        _reject_stats["subject_gate"] += 1
        return None

    lean_value = classify(headline)
    lean = "bullish" if lean_value > 0.15 else "bearish" if lean_value < -0.15 else "neutral"

    ticker = next(iter(mentioned), None)
    if ticker:
        tracked_universe.add(ticker)  # growable universe -- see universe.py

    _reject_stats["accepted"] += 1
    return {
        "ticker": ticker,
        "headline": headline,
        "outlet": outlet_name,
        "source_url": link,
        "published_at": published_at,
        "lean": lean,
    }


async def fetch_market_news() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    universe_size = len(tracked_universe.all())
    for url, outlet in RSS_FEEDS.items():
        feed = await _fetch_feed(url)
        raw_entries = feed.get("entries", [])
        passed = 0
        for raw_entry in raw_entries:
            parsed = await process_feed_entry(dict(raw_entry), outlet, is_markets_business_desk=True)
            if parsed is not None:
                results.append(parsed)
                passed += 1
        logger.info(
            "%s: fetched %d raw entries, %d passed both gates (tracked universe size: %d), reject reasons: %s",
            outlet, len(raw_entries), passed, universe_size, reset_and_snapshot_reject_stats(),
        )
    return results
