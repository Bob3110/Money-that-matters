"""
Refresh orchestrator. This is what /api/refresh and the background scheduler
(see main.py's lifespan) actually call. It's the piece that was a stub
before — this wires the real fetchers to real storage.

Design:
  - Run all four source fetchers concurrently (asyncio.gather with
    return_exceptions=True) so one broken source degrades only its own
    tab, per the build spec.
  - A failed fetch never overwrites good cached data -- record_feed_failure
    only touches last_attempt_at/error, never the stored items.
  - After Market News + Insiders succeed, recompute per-ticker leans into
    the `ticker_leans` collection, which is what the money_match router
    reads. Congress is deliberately excluded from this -- filing-level
    rows carry no ticker, so it can never vote (see scoring.py docstring).
  - Egypt News is stored but never touches ticker_leans -- it powers the
    Egypt tab only, per the strict separation required by the spec.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from . import db
from .dates import parse_item_date
from .fetchers import congress as congress_fetcher
from .fetchers import egypt_news as egypt_fetcher
from .fetchers import insiders as insiders_fetcher
from .fetchers import market_news as market_news_fetcher
from .scoring import SourceName, recency_weight, weighted_lean
from .universe import tracked_universe

logger = logging.getLogger("mtm.refresh")

RECENCY_HALF_LIFE_DAYS = {
    SourceName.MARKET_NEWS: 3.0,   # headlines matter less after a few days
    SourceName.INSIDERS: 14.0,     # filings stay meaningful longer
}


async def _run_source(name: str, coro, timeout_seconds: float) -> tuple[str, list | Exception]:
    """Wrap one fetcher so a single failing OR HANGING source doesn't
    block the others. Each fetcher already sets its own httpx-level
    timeout, but that alone isn't a sufficient guarantee -- a slow trickle
    of bytes can keep individual read operations under their own timeout
    while the overall call runs far longer than intended (this is exactly
    what happened with the Congress fetcher's first live run: it never
    raised, it just never finished). wait_for is the actual hard ceiling."""
    try:
        result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        return name, result
    except asyncio.TimeoutError:
        logger.warning("Fetcher %s exceeded %.0fs hard timeout, aborting", name, timeout_seconds)
        return name, TimeoutError(f"{name} exceeded {timeout_seconds:.0f}s hard timeout")
    except Exception as exc:  # noqa: BLE001 - deliberately broad, isolated per-source
        logger.warning("Fetcher %s failed: %s", name, exc)
        return name, exc


# Per-source hard ceilings. Congress gets the longest budget since it
# downloads and parses a full year's disclosure index; the others are
# bounded RSS/API calls that should complete in seconds under normal
# conditions.
SOURCE_TIMEOUTS_SECONDS = {
    "market_news": 30.0,
    # ~500 tickers x (1 submissions.json + up to 2 XML fetches for tickers
    # with recent Form 4s) against a shared 10 req/s SEC budget can run
    # several minutes in the worst case. This is a real tradeoff: the
    # manual /api/refresh endpoint blocks on this, so a full sweep will
    # feel slow from the frontend's Refresh button. Moving to a proper
    # background job queue (rather than blocking the request) is the
    # right fix if this becomes a UX problem -- documented here rather
    # than silently living with it.
    "insiders": 240.0,
    "congress": 60.0,
    "egypt_news": 45.0,
}


async def refresh_all() -> dict:
    """Entry point called by /api/refresh and the periodic background task.
    Returns a summary dict; never raises -- individual source failures
    (including hangs, via the wait_for ceiling in _run_source) are
    captured and reported, not propagated."""
    results = await asyncio.gather(
        _run_source("market_news", market_news_fetcher.fetch_market_news(), SOURCE_TIMEOUTS_SECONDS["market_news"]),
        _run_source("insiders", _fetch_insiders_for_tracked_universe(), SOURCE_TIMEOUTS_SECONDS["insiders"]),
        _run_source(
            "congress",
            congress_fetcher.fetch_house_clerk_index(datetime.now(timezone.utc).year),
            SOURCE_TIMEOUTS_SECONDS["congress"],
        ),
        _run_source("egypt_news", egypt_fetcher.fetch_egypt_news(), SOURCE_TIMEOUTS_SECONDS["egypt_news"]),
        return_exceptions=False,  # _run_source already isolates exceptions
    )

    summary = {}
    market_news_items = None
    insider_items = None

    for name, result in results:
        if isinstance(result, Exception):
            await db.record_feed_failure(name, str(result))
            summary[name] = {"status": "failed", "error": str(result)}
            continue

        summary[name] = {"status": "ok", "count": len(result)}
        await _store_items(name, result)
        await db.record_feed_success(name)
        logger.info("Fetcher %s succeeded: %d items", name, len(result))

        if name == "market_news":
            market_news_items = result
        elif name == "insiders":
            insider_items = result

    # Only recompute scoring inputs if at least one of the two scoring
    # sources actually succeeded this cycle -- a failed fetch must not
    # erase yesterday's still-valid leans just because today's run failed.
    if market_news_items is not None or insider_items is not None:
        await _recompute_ticker_leans(market_news_items, insider_items)

    return summary


async def _fetch_insiders_for_tracked_universe() -> list:
    """Sweep per-ticker for every ticker in the tracked universe, plus a
    market-wide catch-all, per the build spec. Per-ticker sweeps are
    prioritized; the market-wide sweep supplements them."""
    tickers = sorted(tracked_universe.all())

    # Resolve the ticker->CIK map exactly once before fanning out to ~500
    # concurrent per-ticker calls. Without this, a single transient failure
    # on the very first lookup meant every one of those callers
    # independently retried the same failing request for the rest of the
    # sweep's time budget -- see insiders.py's _get_ticker_to_cik_map
    # docstring for the full story; this is the fix on the caller side.
    resolved_count = await insiders_fetcher.prewarm_ticker_cik_map()
    logger.info("CIK map prewarm resolved %d tickers before per-ticker sweep", resolved_count)

    per_ticker_results = []

    # Bound concurrency so we don't blow past SEC's 10 req/s limit --
    # the shared rate limiter in rate_limiter.py enforces the hard limit
    # regardless, this just avoids scheduling hundreds of coroutines that
    # all immediately block on the limiter.
    sem = asyncio.Semaphore(8)

    async def bounded_fetch(ticker: str) -> list:
        async with sem:
            try:
                return await insiders_fetcher.fetch_insiders_for_ticker(ticker)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Insider fetch failed for %s: %s", ticker, exc)
                return []

    if tickers:
        batches = await asyncio.gather(*(bounded_fetch(t) for t in tickers))
        for batch in batches:
            per_ticker_results.extend(batch)
    ticker_sweep_stats = insiders_fetcher.reset_and_snapshot_parse_stats()
    logger.info(
        "Per-ticker sweep: %d tickers checked, %d usable transactions found, reject reasons: %s",
        len(tickers), len(per_ticker_results), ticker_sweep_stats,
    )

    try:
        market_wide = await insiders_fetcher.fetch_insiders_market_wide()
        market_wide_stats = insiders_fetcher.reset_and_snapshot_parse_stats()
        logger.info("Market-wide sweep reject reasons: %s", market_wide_stats)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Market-wide insider sweep failed: %s", exc)
        market_wide = []

    # De-dupe by (ticker, insider_name, filed_at, shares) in case the
    # market-wide sweep and a per-ticker sweep both caught the same filing.
    seen = set()
    deduped = []
    for item in per_ticker_results + market_wide:
        key = (item["ticker"], item["insider_name"], item["filed_at"], item["shares"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


async def _store_items(source: str, items: list) -> None:
    database = db.get_db()
    collection_map = {
        "market_news": "market_news_items",
        "insiders": "insider_transactions",
        "congress": "congress_disclosures",
        "egypt_news": "egypt_news_items",
    }
    collection = database[collection_map[source]]

    for item in items:
        # Upsert on a natural key per source so re-running refresh doesn't
        # duplicate rows. Never overwrite with fewer fields than a prior
        # successful write had -- partial data beats fake data, but a
        # later *complete* record should still win over an earlier partial
        # one, so a plain $set is correct here.
        if source == "market_news":
            key = {"source_url": item["source_url"]}
        elif source == "insiders":
            key = {"ticker": item["ticker"], "insider_name": item["insider_name"], "filed_at": item["filed_at"], "shares": item["shares"]}
        elif source == "congress":
            key = {"document_id": item["document_id"]}
        else:  # egypt_news
            key = {"source_url": item["source_url"]}

        await collection.update_one(key, {"$set": item}, upsert=True)


async def _recompute_ticker_leans(market_news_items: list | None, insider_items: list | None) -> None:
    """Rebuild the ticker_leans collection the money_match router reads.
    Congress is never included here -- see module docstring."""
    now = datetime.now(timezone.utc)
    database = db.get_db()

    by_ticker: dict[str, dict[str, list[tuple[float, float]]]] = {}

    def add(ticker: str, source_key: str, lean_value: float, item_date: datetime, half_life: float):
        if not ticker:
            return
        weight = recency_weight(item_date, now, half_life)
        by_ticker.setdefault(ticker, {}).setdefault(source_key, []).append((lean_value, weight))

    lean_map = {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}

    if market_news_items is not None:
        for item in market_news_items:
            if not item.get("ticker"):
                continue
            add(
                item["ticker"],
                SourceName.MARKET_NEWS.value,
                lean_map.get(item["lean"], 0.0),
                item["published_at"],
                RECENCY_HALF_LIFE_DAYS[SourceName.MARKET_NEWS],
            )

    if insider_items is not None:
        for item in insider_items:
            # Insider "lean" isn't tagged bullish/bearish directly -- buys
            # lean bullish, sells lean bearish, scaled down since sells
            # dominate insider activity structurally (compensation/
            # liquidity, not signal) and shouldn't swamp the score.
            lean_value = 0.6 if item["transaction"] == "buy" else -0.3
            add(
                item["ticker"],
                SourceName.INSIDERS.value,
                lean_value,
                item["filed_at"],
                RECENCY_HALF_LIFE_DAYS[SourceName.INSIDERS],
            )

    # Only touch tickers we actually have fresh data for this cycle --
    # leave other tickers' stored leans alone so a partial refresh doesn't
    # wipe out unrelated tickers' still-valid data.
    for ticker, sources in by_ticker.items():
        leans = {
            source_key: weighted_lean(pairs)
            for source_key, pairs in sources.items()
        }
        await database.ticker_leans.update_one(
            {"ticker": ticker},
            {"$set": {"ticker": ticker, "leans": leans, "updated_at": now}},
            upsert=True,
        )
