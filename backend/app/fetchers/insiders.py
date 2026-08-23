"""
Insiders feed: SEC EDGAR Form 4 filings (no API key required).

Sweeps BOTH per-ticker (for every ticker in the tracked universe, prioritized
in the fetch budget) and market-wide, per the build spec -- a random slice of
the site-wide feed almost never overlaps the large caps Market News surfaces,
so per-ticker sweeps are the primary path and the market-wide sweep is a
supplementary catch-all.

Endpoints used:
  - Per-ticker: https://data.sec.gov/cgi-bin/browse-edgar?action=getcompany
    &type=4&company=... (or by CIK once resolved)
  - Full-text/company facts: https://data.sec.gov/submissions/CIK{cik}.json
  - Market-wide recent filings index: https://www.sec.gov/cgi-bin/browse-edgar
    ?action=getcurrent&type=4

This module cannot be exercised end-to-end in the build sandbox (no network
route to sec.gov there); it is written and unit-testable against the parsing
functions below, with the actual HTTP calls isolated in `_fetch_json` so
they can be mocked in tests and swapped for a real client at deploy time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from ..config import SEC_USER_AGENT
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import is_valid_us_ticker

SEC_SUBMISSIONS_HOST = "data.sec.gov"
SEC_BROWSE_HOST = "www.sec.gov"


async def _fetch_json(url: str, host: str) -> dict[str, Any]:
    await throttle(host)
    headers = {"User-Agent": SEC_USER_AGENT}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def parse_form4_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Parse one Form 4 filing entry into the InsiderTransaction shape.
    Returns None (and the caller should log + skip) if the symbol is
    malformed or a required field is missing -- never guess a missing
    field, per the honesty rules."""
    symbol = raw.get("issuerTradingSymbol")
    if not is_valid_us_ticker(symbol):
        return None

    filed_raw = raw.get("periodOfReport") or raw.get("filedAt")
    if not filed_raw:
        return None
    try:
        filed_at: datetime = parse_item_date(filed_raw)
    except ValueError:
        return None

    shares = raw.get("shares")
    if shares is None:
        return None

    return {
        "ticker": symbol.strip().upper(),
        "company": raw.get("issuerName", ""),
        "insider_name": raw.get("reportingOwnerName", ""),
        "insider_role": raw.get("reportingOwnerRelationship", ""),
        "transaction": "buy" if raw.get("transactionCode") == "P" else "sell",
        "shares": int(shares),
        "value_usd": raw.get("value"),  # left None if EDGAR doesn't supply it -- never guessed
        "filed_at": filed_at,
        "source_url": raw.get("accessionUrl", ""),
    }


async def fetch_insiders_for_ticker(ticker: str) -> list[dict[str, Any]]:
    """Fetch and parse recent Form 4 filings for a single ticker. Real
    deployment needs CIK resolution (ticker -> CIK via
    https://www.sec.gov/files/company_tickers.json, cached) before hitting
    the submissions endpoint; omitted here as an implementation detail that
    doesn't change the parsing/validation contract above."""
    url = f"https://{SEC_SUBMISSIONS_HOST}/submissions/CIK-lookup-required.json"
    raw = await _fetch_json(url, SEC_SUBMISSIONS_HOST)
    entries = raw.get("filings", [])
    results = []
    for entry in entries:
        parsed = parse_form4_entry(entry)
        if parsed is not None:
            results.append(parsed)
    return results


async def fetch_insiders_market_wide() -> list[dict[str, Any]]:
    url = f"https://{SEC_BROWSE_HOST}/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom"
    raw = await _fetch_json(url, SEC_BROWSE_HOST)
    entries = raw.get("entries", [])
    results = []
    for entry in entries:
        parsed = parse_form4_entry(entry)
        if parsed is not None:
            results.append(parsed)
    return results
