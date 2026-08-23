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
  - Per-ticker: resolves ticker -> CIK via
    https://www.sec.gov/files/company_tickers.json (cached in-process),
    then queries https://data.sec.gov/submissions/CIK{cik}.json for that
    company's recent filings, filters to Form 4, and fetches+parses each
    filing's actual XML document for the transaction detail. Bounded to
    MAX_FILINGS_PER_TICKER per ticker to keep the full ~500-ticker sweep's
    request count tractable under SEC's shared 10 req/s limit.

This was written against the documented shapes of these endpoints without
the ability to make a live call from the build sandbox. Railway's runtime
has real network access, so runtime logs from an actual deploy are the
first real signal on whether the parsing here matches reality -- treat
early failures here as expected debugging, not a design failure.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import feedparser
import httpx

from ..config import SEC_USER_AGENT
from ..dates import parse_item_date
from ..rate_limiter import throttle
from ..relevance import is_valid_us_ticker

logger = logging.getLogger("mtm.fetchers.insiders")

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

# Cap how many filings we open per market-wide sweep -- each filing costs
# two extra requests (index page + XML doc) on top of the atom feed itself,
# and SEC's 10 req/s limit is shared across every fetcher hitting sec.gov
# (see rate_limiter.py), so an unbounded sweep would starve Market News's
# 8-K pulls on the same host.
MAX_FILINGS_PER_SWEEP = 20

# Cap per ticker in the per-ticker sweep. With ~500 tickers in the tracked
# universe, even 1 filing/ticker is ~1000 requests (1 submissions.json +
# up to N XML fetches per ticker) against a shared 10 req/s budget --
# multiplying this up scales runtime linearly, so keep it small and let
# successive refresh cycles pick up anything missed rather than trying to
# fetch everything in one pass.
MAX_FILINGS_PER_TICKER = 2

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


_company_tickers_cache: dict[str, str] | None = None
_company_tickers_cache_failed = False


async def _get_ticker_to_cik_map() -> dict[str, str]:
    """Resolve ticker -> zero-padded 10-digit CIK via SEC's official
    company_tickers.json (no key required). Cached in-process for the life
    of the container -- this file changes rarely and re-fetching it on
    every ticker lookup would waste a meaningful fraction of the 10 req/s
    budget shared with every other sec.gov call.

    Also caches FAILURE, not just success. Without this, a single bad
    fetch (network blip, transient 5xx) meant every one of ~500 concurrent
    per-ticker callers would independently retry the same failing request
    for the rest of the refresh cycle -- burning the entire per-ticker
    sweep's time budget on one endpoint and silently producing zero
    results everywhere, which is exactly what the first live run showed.
    A failed resolution now fails fast and loud instead."""
    global _company_tickers_cache, _company_tickers_cache_failed
    if _company_tickers_cache is not None:
        return _company_tickers_cache
    if _company_tickers_cache_failed:
        return {}

    try:
        data = await _fetch_json("https://www.sec.gov/files/company_tickers.json", SEC_BROWSE_HOST)
    except httpx.HTTPError as exc:
        _company_tickers_cache_failed = True
        logger.error("Failed to resolve ticker->CIK map, insiders per-ticker sweep will return nothing this cycle: %s", exc)
        return {}

    mapping: dict[str, str] = {}
    for entry in data.values():
        ticker = str(entry.get("ticker", "")).strip().upper()
        cik = entry.get("cik_str")
        if ticker and cik is not None:
            mapping[ticker] = str(cik).zfill(10)
    _company_tickers_cache = mapping
    logger.info("Resolved ticker->CIK map: %d entries", len(mapping))
    return mapping


async def prewarm_ticker_cik_map() -> int:
    """Public entry point for callers (refresh.py) that want to resolve
    the CIK map exactly once, up front, rather than lazily from inside
    hundreds of concurrent per-ticker callers. Returns the number of
    tickers resolved (0 means resolution failed -- see logs)."""
    mapping = await _get_ticker_to_cik_map()
    return len(mapping)


async def fetch_insiders_for_ticker(ticker: str) -> list[dict[str, Any]]:
    """Real implementation: resolve CIK, pull that company's recent filing
    index from data.sec.gov/submissions (which lists form types directly,
    no atom-feed indirection needed for this part), filter to Form 4, then
    fetch+parse each filing's actual XML for the transaction detail.
    Bounded to the most recent MAX_FILINGS_PER_TICKER per ticker to keep
    the full-universe sweep's total request count tractable under SEC's
    shared 10 req/s limit -- see refresh.py's SOURCE_TIMEOUTS_SECONDS for
    how this is budgeted against the overall insiders timeout."""
    cik_map = await _get_ticker_to_cik_map()
    cik = cik_map.get(ticker.strip().upper())
    if cik is None:
        return []  # not in SEC's list under this exact symbol -- honest empty, not a guess

    try:
        data = await _fetch_json(f"https://{SEC_SUBMISSIONS_HOST}/submissions/CIK{cik}.json", SEC_SUBMISSIONS_HOST)
    except httpx.HTTPError:
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    form4_indices = [i for i, f in enumerate(forms) if f == "4"][:MAX_FILINGS_PER_TICKER]

    results: list[dict[str, Any]] = []
    cik_int = str(int(cik))
    for i in form4_indices:
        accession_nodash = accessions[i].replace("-", "")
        doc_url = f"https://{SEC_BROWSE_HOST}/Archives/edgar/data/{cik_int}/{accession_nodash}/{primary_docs[i]}"
        await throttle(SEC_BROWSE_HOST)
        headers = {"User-Agent": SEC_USER_AGENT}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(doc_url, headers=headers)
                resp.raise_for_status()
                parsed = parse_form4_xml(resp.content, source_url=doc_url)
        except (httpx.HTTPError, ET.ParseError):
            continue  # one bad filing shouldn't abort this ticker's whole sweep
        if parsed is not None:
            results.append(parsed)
    return results


async def fetch_insiders_market_wide() -> list[dict[str, Any]]:
    feed = await _fetch_atom(
        f"https://{SEC_BROWSE_HOST}/cgi-bin/browse-edgar?action=getcurrent&type=4&output=atom",
        SEC_BROWSE_HOST,
    )
    entries = feed.get("entries", [])
    logger.info("Market-wide Form 4 atom feed returned %d entries (parsing up to %d)", len(entries), MAX_FILINGS_PER_SWEEP)
    results: list[dict[str, Any]] = []
    for entry in entries[:MAX_FILINGS_PER_SWEEP]:
        link = entry.get("link")
        if not link:
            continue
        try:
            parsed = await _fetch_and_parse_filing(link)
        except (httpx.HTTPError, ET.ParseError) as exc:
            logger.debug("Skipping one market-wide filing (%s): %s", link, exc)
            continue  # one bad filing shouldn't abort the whole sweep
        if parsed is not None:
            results.append(parsed)
    logger.info("Market-wide sweep parsed %d usable transactions from %d entries", len(results), len(entries))
    return results
