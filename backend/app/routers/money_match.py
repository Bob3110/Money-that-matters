from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..db import get_db, get_feed_mode
from ..models import FeedMode as ApiFeedMode
from ..scoring import SourceLean, SourceName, compute_money_match, rank_results
from ..scoring import FeedMode as ScoringFeedMode

router = APIRouter(prefix="/api/money-match", tags=["money-match"])

# Tickers that are ETFs are excluded from scoring (Form 4 filings don't exist
# for funds) but can still appear in feeds and be watchlisted -- enforced at
# the query layer by checking against a maintained ETF exclusion set stored
# in Mongo (etf_exclusions collection), not hardcoded here.


@router.get("")
async def get_money_match():
    db = get_db()

    mn_mode, _ = await get_feed_mode("market_news")
    ins_mode, _ = await get_feed_mode("insiders")
    con_mode, _ = await get_feed_mode("congress")

    mode_map = {
        SourceName.MARKET_NEWS: ScoringFeedMode(mn_mode.value),
        SourceName.INSIDERS: ScoringFeedMode(ins_mode.value),
        SourceName.CONGRESS: ScoringFeedMode(con_mode.value),
    }

    etf_tickers = {doc["ticker"] async for doc in db.etf_exclusions.find({}, {"ticker": 1})}

    tickers_cursor = db.ticker_leans.find({})
    results = []
    async for doc in tickers_cursor:
        ticker = doc["ticker"]
        if ticker in etf_tickers:
            continue
        leans = []
        for source_key, lean_value in doc.get("leans", {}).items():
            source = SourceName(source_key)
            mode = mode_map.get(source, ScoringFeedMode.EMPTY)
            leans.append(SourceLean(source=source, lean=lean_value, mode=mode))
        results.append(compute_money_match(ticker, leans))

    ranked = rank_results(results)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feed_status": {
            "market_news": mn_mode.value,
            "insiders": ins_mode.value,
            "congress": con_mode.value,
            # Congress structurally never votes -- see scoring.py / spec.
            "congress_note": (
                "Congress trades carry no ticker in the free House Clerk data, "
                "so Congress never contributes to Money Match scores. Coverage "
                "caps at two of three sources unless a licensed, ticker-level "
                "feed is added."
            ),
        },
        "tickers": [
            {
                "ticker": r.ticker,
                "score": r.score,
                "sources_fired": r.sources_fired,
                "direction": r.direction,
                "strong_match": r.strong_match,
                "excluded_sources": [s.value for s in r.excluded_sources],
            }
            for r in ranked
        ],
    }
