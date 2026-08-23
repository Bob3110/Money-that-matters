"""
Thin read endpoints for the four raw feeds. Each returns cached Mongo data
plus the feed's current mode (live/stale/empty) so the frontend can render
the honest state described in the build spec -- never invented rows, and a
"waiting for first sync" state when mode == empty.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..db import get_db, get_feed_mode

router = APIRouter(prefix="/api", tags=["feeds"])


async def _feed_response(collection: str, source_key: str, sort_field: str, limit: int = 200):
    db = get_db()
    mode, last_success = await get_feed_mode(source_key)
    items = []
    if mode.value != "empty":
        cursor = db[collection].find({}).sort(sort_field, -1).limit(limit)
        items = [doc async for doc in cursor]
        for item in items:
            item.pop("_id", None)
    return {
        "mode": mode.value,
        "last_success_at": last_success.isoformat() if last_success else None,
        "items": items,
    }


@router.get("/market-news")
async def get_market_news():
    return await _feed_response("market_news_items", "market_news", "published_at")


@router.get("/insiders")
async def get_insiders(buys_only: bool = False):
    resp = await _feed_response("insider_transactions", "insiders", "filed_at")
    if buys_only:
        resp["items"] = [i for i in resp["items"] if i.get("transaction") == "buy"]
    return resp


@router.get("/congress")
async def get_congress():
    resp = await _feed_response("congress_disclosures", "congress", "filing_date")
    # Filing-level rows have no ticker/buy-sell -- deliberately no
    # asset-type or buys-only filter params here, since applying them would
    # silently empty the list (there is nothing to filter on). The
    # frontend must hide those filter controls on this tab, not just this
    # endpoint refusing to support them.
    resp["legal_notice"] = (
        "Financial Disclosure Reports may not be obtained or used for any "
        "commercial purpose other than by news and communications media for "
        "public dissemination, per U.S. Senate Ethics Committee rules. "
        "Consult a lawyer before monetizing this data."
    )
    return resp


@router.get("/egypt-news")
async def get_egypt_news():
    return await _feed_response("egypt_news_items", "egypt_news", "published_at")
