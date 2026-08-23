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

from typing import Any

import httpx

from ..allowlist import source_gate_egypt
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import passes_egypt_subject_gate
from ..sentiment import classify

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
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(GDELT_DOC_API, params=params, headers={"User-Agent": "MoneyThatMatters/0.1"})
        resp.raise_for_status()
        return resp.json()


def process_article(raw: dict[str, Any]) -> dict[str, Any] | None:
    headline = raw.get("title", "")
    url = raw.get("url", "")
    published_raw = raw.get("seendate")

    outlet_name = source_gate_egypt(url)
    if outlet_name is None:
        return None

    if not headline or not url or not published_raw:
        return None

    try:
        published_at = parse_item_date(published_raw)
    except ValueError:
        return None

    is_native = outlet_name in NATIVE_EGYPTIAN_OUTLETS
    mentions_egypt = "egypt" in headline.lower() or "egx" in headline.lower() or "مصر" in headline

    if not passes_egypt_subject_gate(
        headline=headline,
        outlet_is_native_egyptian=is_native,
        mentions_egypt_or_egx=mentions_egypt or is_native,
    ):
        return None

    lean_value = classify(headline)
    lean = "bullish" if lean_value > 0.15 else "bearish" if lean_value < -0.15 else "neutral"

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
    results = []
    for article in raw.get("articles", []):
        parsed = process_article(article)
        if parsed is not None:
            results.append(parsed)
    return results
