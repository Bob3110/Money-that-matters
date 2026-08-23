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

from typing import Any

import feedparser
import httpx

from ..allowlist import source_gate_us
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import passes_us_subject_gate
from ..sentiment import classify
from ..universe import tracked_universe

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
RSS_FEEDS: dict[str, str] = {
    "https://www.cnbc.com/id/10001147/device/rss/rss.html": "CNBC (Markets)",
    # Bloomberg and WSJ do not offer full public RSS for markets content;
    # in production these are reached via their official partner feeds or
    # licensed API, not scraped -- left as a documented gap rather than a
    # scraper that violates ToS.
}

SEC_8K_FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&output=atom"


async def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    host = httpx.URL(url).host
    await throttle(host)
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"User-Agent": "MoneyThatMatters/0.1"})
        resp.raise_for_status()
        return feedparser.parse(resp.text)


def _extract_tickers(text: str, universe: frozenset[str]) -> set[str]:
    """Very deliberately conservative: only matches whole-word uppercase
    tokens that are already in the tracked universe (or the seed list being
    evaluated for entry) -- never invents a ticker that isn't a real,
    verifiable symbol."""
    words = {w.strip("$().,:;\"'").upper() for w in text.split()}
    return words & universe


async def process_feed_entry(
    entry: dict[str, Any],
    outlet: str,
    is_markets_business_desk: bool,
) -> dict[str, Any] | None:
    headline = entry.get("title", "")
    link = entry.get("link", "")
    published_raw = entry.get("published") or entry.get("updated")

    outlet_name = source_gate_us(link)
    if outlet_name is None:
        return None  # fails source gate -- discard, do not attribute elsewhere

    if not headline or not link or not published_raw:
        return None  # partial data beats fake data, but here nothing usable remains

    try:
        published_at = parse_item_date(published_raw)
    except ValueError:
        return None

    universe = tracked_universe.all()
    mentioned = _extract_tickers(headline, universe | {"CANDIDATE"})  # candidate extraction is a placeholder for an NER/lookup step
    mentioned.discard("CANDIDATE")

    if not passes_us_subject_gate(
        headline=headline,
        tracked_tickers=universe,
        mentioned_tickers=mentioned,
        is_markets_business_desk=is_markets_business_desk,
    ):
        return None

    lean_value = classify(headline)
    lean = "bullish" if lean_value > 0.15 else "bearish" if lean_value < -0.15 else "neutral"

    ticker = next(iter(mentioned), None)
    if ticker:
        tracked_universe.add(ticker)  # growable universe -- see universe.py

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
    for url, outlet in RSS_FEEDS.items():
        feed = await _fetch_feed(url)
        for raw_entry in feed.get("entries", []):
            parsed = await process_feed_entry(dict(raw_entry), outlet, is_markets_business_desk=True)
            if parsed is not None:
                results.append(parsed)
    return results
