"""
Congress feed: House Clerk's official annual disclosure index
(disclosures-clerk.house.gov, {year}FD.zip) -- free, current, structured
XML, names only real filers.

IMPORTANT, per the build spec:
  - This gives FILINGS, not parsed trades. Ticker/buy-sell/asset-type live
    inside per-filing PDFs with content extraction disabled -- this module
    deliberately does NOT scrape those PDFs to strip that protection.
  - The community S3 mirrors (house-stock-watcher / senate-stock-watcher)
    that used to provide ticker-level detail return AccessDenied and appear
    withdrawn as of the write date. Do not design around their availability;
    `fetch_community_mirror_fallback` below is a best-effort attempt only
    and its failure is expected and handled as FeedMode.EMPTY/STALE, not
    an application error.
  - Senate eFD portal blocks non-browser access -- Senate coverage is
    explicitly out of scope here unless a licensed feed is added.
  - LEGAL: the Senate Ethics Committee holds it unlawful to obtain/use a
    Financial Disclosure Report for commercial purposes other than by news
    and communications media for public dissemination. This must be
    surfaced in the app UI (Congress tab), not just docs -- see
    frontend CongressTab component and DEPLOYMENT.md. Get real legal
    advice before monetizing this tab.

Because filing-level rows carry no ticker, Congress can never vote in the
Money Match score on its own -- see scoring.py and the home-screen banner
in the frontend explaining this plainly rather than leaving the Congress
icon mysteriously dark on every card.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from typing import Any

import httpx

from ..dates import parse_item_date
from ..rate_limiter import throttle

HOUSE_CLERK_HOST = "disclosures-clerk.house.gov"


def _index_url(year: int) -> str:
    return f"https://{HOUSE_CLERK_HOST}/public_disc/financial-pdfs/{year}FD.zip"


async def fetch_house_clerk_index(year: int) -> list[dict[str, Any]]:
    await throttle(HOUSE_CLERK_HOST)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(_index_url(year), headers={"User-Agent": "MoneyThatMatters/0.1"})
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        if not xml_names:
            return []
        with zf.open(xml_names[0]) as f:
            return parse_house_clerk_xml(f.read())


def parse_house_clerk_xml(raw_xml: bytes) -> list[dict[str, Any]]:
    root = ET.fromstring(raw_xml)
    results: list[dict[str, Any]] = []
    for member in root.findall(".//Member"):
        def text(tag: str) -> str | None:
            el = member.find(tag)
            return el.text.strip() if el is not None and el.text else None

        last = text("Last")
        first = text("First")
        district = text("StateDst")
        filing_date_raw = text("FilingDate")
        doc_id = text("DocID")

        if not (last and filing_date_raw and doc_id):
            continue  # never guess a missing required field

        try:
            filing_date: datetime = parse_item_date(filing_date_raw)
        except ValueError:
            continue

        results.append(
            {
                "member_name": f"{first} {last}".strip() if first else last,
                "district": district,
                "filing_date": filing_date,
                "document_id": doc_id,
                "document_url": (
                    f"https://{HOUSE_CLERK_HOST}/public_disc/financial-pdfs/{doc_id}.pdf"
                ),
            }
        )
    return results


async def fetch_community_mirror_fallback() -> list[dict[str, Any]]:
    """Best-effort only. As of the last verification (Aug 2026) the
    house-stock-watcher/senate-stock-watcher S3 mirrors return AccessDenied
    and appear withdrawn. This function is expected to fail; callers must
    treat that failure as an empty/stale result, not surface it as an app
    error, and must NOT fall back to inventing ticker-level data when this
    fails."""
    url = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()
