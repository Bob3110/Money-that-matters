"""
Insiders feed: SEC EDGAR Form 4 filings (no API key required).

Sweeps BOTH per-ticker (for every ticker in the tracked universe, prioritized
in the fetch budget) and market-wide, per the build spec -- a random slice of
the site-wide feed almost never overlaps the large caps Market News surfaces,
so per-ticker sweeps are the primary path and the market-wide sweep is a
supplementary catch-all.

Endpoints used:
  - Market-wide recent filings index: https://www.sec.gov/cgi-bin/browse-edgar
    ?action=getcurrent&type=4&output=atom -- an Atom/XML feed, NOT JSON. An
    earlier version of this module assumed JSON here; that was wrong and
    would have raised on first real use. Fixed to parse Atom via feedparser,
    consistent with market_news.py's approach.
  - Per-ticker: requires resolving ticker -> CIK first (via
    https://www.sec.gov/files/company_tickers.json, cached), then querying
    https://data.sec.gov/submissions/CIK{cik}.json for that company's recent
    filings and filtering to Form 4. NOT YET IMPLEMENTED -- see
    fetch_insiders_for_ticker below, which is a documented stub rather than
    a silently-broken implementation. Until this lands, only the
    market-wide sweep runs; per-ticker coverage is a known gap.

This was written against the documented shapes of these endpoints without
the ability to make a live call from the build sandbox. Railway's runtime
has real network access, so runtime logs from an actual deploy are the
first real signal on whether the parsing here matches reality -- treat
early failures here as expected debugging, not a design failure.
"""

from __future__ import annotations

from typing import Any

import feedparser
import httpx

from ..config import SEC_USER_AGENT
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import is_valid_us_ticker

SEC_SUBMISSIONS_HOST = "data.sec.gov"
SEC_BROWSE_HOST = "www.sec.gov"


async def _fetch_atom(url: str, host: str) -> feedparser.FeedParserDict:
    await throttle(host)
    headers = {"User-Agent": SEC_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return feedparser.parse(resp.text)


async def _fetch_json(url: str, host: str) -> dict[str, Any]:
    await throttle(host)
    headers = {"User-Agent": SEC_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


import re
import xml.etree.ElementTree as ET

# Cap how many filings we open per market-wide sweep -- each filing costs
# two extra requests (index page + XML doc) on top of the atom feed itself,
# and SEC's 10 req/s limit is shared across every fetcher hitting sec.gov
# (see rate_limiter.py), so an unbounded sweep would starve Market News's
# 8-K pulls on the same host.
MAX_FILINGS_PER_SWEEP = 20

_XML_LINK_RE = re.compile(r'href="([^"]+\.xml)"', re.IGNORECASE)


def _ns_strip(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_form4_xml(raw_xml: bytes, source_url: str) -> dict[str, Any] | None:
    """Parse a single Form 4 ownershipDocument XML into the
    InsiderTransaction shape. Returns None if a required field is
    genuinely absent -- never guesses a missing field. Only the first
    non-derivative transaction is used if multiple are present; Form 4s
    with only derivative transactions (options, RSUs vesting) are skipped
    for now rather than misrepresented as open-market buys/sells."""
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return None

    def find_text(path: str) -> str | None:
        el = root.find(path)
        return el.text.strip() if el is not None and el.text else None

    symbol = find_text(".//issuer/issuerTradingSymbol")
    if not is_valid_us_ticker(symbol):
        return None

    company = find_text(".//issuer/issuerName") or ""
    insider_name = find_text(".//reportingOwner/reportingOwnerId/rptOwnerName")
    if not insider_name:
        return None

    role_parts = []
    rel = root.find(".//reportingOwner/reportingOwnerRelationship")
    if rel is not None:
        for tag, label in (
            ("isDirector", "Director"),
            ("isOfficer", "Officer"),
            ("isTenPercentOwner", "10% Owner"),
        ):
            el = rel.find(tag)
            if el is not None and (el.text or "").strip() == "1":
                role_parts.append(label)
        officer_title = rel.find("officerTitle")
        if officer_title is not None and officer_title.text:
            role_parts.append(officer_title.text.strip())
    insider_role = ", ".join(role_parts) if role_parts else "Unspecified"

    txn = root.find(".//nonDerivativeTable/nonDerivativeTransaction")
    if txn is None:
        return None  # derivative-only filing (options/RSUs) -- skipped, not misrepresented

    filed_raw = find_text(".//nonDerivativeTransaction/transactionDate/value") or find_text(
        ".//periodOfReport"
    )
    if not filed_raw:
        return None
    try:
        filed_at = parse_item_date(filed_raw)
    except ValueError:
        return None

    code = find_text(".//nonDerivativeTransaction/transactionCoding/transactionCode")
    shares_raw = find_text(".//nonDerivativeTransaction/transactionAmounts/transactionShares/value")
    price_raw = find_text(".//nonDerivativeTransaction/transactionAmounts/transactionPricePerShare/value")

    if code is None or shares_raw is None:
        return None
    try:
        shares = int(float(shares_raw))
    except ValueError:
        return None

    value_usd = None
    if price_raw is not None:
        try:
            value_usd = round(float(price_raw) * shares, 2)
        except ValueError:
            value_usd = None  # left None rather than guessed

    return {
        "ticker": symbol.strip().upper(),
        "company": company,
        "insider_name": insider_name,
        "insider_role": insider_role,
        "transaction": "buy" if code == "P" else "sell",
        "shares": shares,
        "value_usd": value_usd,
        "filed_at": filed_at,
        "source_url": source_url,
    }


async def _find_form4_xml_url(index_page_url: str, host: str) -> str | None:
    """The atom feed's entry link points at a filing's index HTML page, not
    the Form 4 XML document itself. Fetch that page and pull out the first
    linked .xml file -- SEC's convention names it '<accession>.xml' or
    'xslF345X0*/<accession>.xml', but the exact name varies, so we parse
    the page rather than guess the filename."""
    await throttle(host)
    headers = {"User-Agent": SEC_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(index_page_url, headers=headers)
        resp.raise_for_status()
        match = _XML_LINK_RE.search(resp.text)
        if not match:
            return None
        href = match.group(1)
        if href.startswith("http"):
            return href
        base = index_page_url.rsplit("/", 1)[0]
        return f"{base}/{href.lstrip('/')}"


async def _fetch_and_parse_filing(index_page_url: str) -> dict[str, Any] | None:
    xml_url = await _find_form4_xml_url(index_page_url, SEC_BROWSE_HOST)
    if xml_url is None:
        return None
    await throttle(SEC_BROWSE_HOST)
    headers = {"User-Agent": SEC_USER_AGENT}
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(xml_url, headers=headers)
        resp.raise_for_status()
        return parse_form4_xml(resp.content, source_url=xml_url)


async def fetch_insiders_for_ticker(ticker: str) -> list[dict[str, Any]]:
    """NOT YET IMPLEMENTED. Requires resolving ticker -> CIK first (via
    https://www.sec.gov/files/company_tickers.json, cached) before this can
    query a specific company's filing history. Returns an empty list rather
    than raising, so callers treat 'no per-ticker coverage yet' the same as
    'no filings found' -- both correctly show nothing rather than crashing
    the whole Insiders refresh. This is a known, documented gap, not a
    silent failure: see refresh_job.py, which currently only calls
    fetch_insiders_market_wide()."""
    return []


async def fetch_insiders_market_wide() -> list[dict[str, Any]]:
    feed = await _fetch_atom(
        f"https://{SEC_BROWSE_HOST}/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom",
        SEC_BROWSE_HOST,
    )
    results: list[dict[str, Any]] = []
    for entry in feed.get("entries", [])[:MAX_FILINGS_PER_SWEEP]:
        link = entry.get("link")
        if not link:
            continue
        try:
            parsed = await _fetch_and_parse_filing(link)
        except (httpx.HTTPError, ET.ParseError):
            continue  # one bad filing shouldn't abort the whole sweep
        if parsed is not None:
            results.append(parsed)
    return results
