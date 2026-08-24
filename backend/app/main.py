from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import refresh as refresh_module
from .routers import feeds, money_match

# Without this, Python's root logger defaults to WARNING, which silently
# discards every logger.info() call throughout this app -- including the
# diagnostic counts in refresh.py and the fetchers (CIK map resolution,
# per-source item counts) that are exactly what's needed to debug a live
# deploy. This was missing for the app's first several live runs, which
# is why those runs produced feed_status successes with zero stored items
# and no visible explanation in the logs.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx logs one INFO line per HTTP request by default. At the volume this
# app makes real per-ticker/per-filing calls (hundreds per refresh cycle),
# that completely floods out this app's own diagnostic logs -- which is
# exactly what made the market_news per-feed diagnostic line impossible to
# find in a live deploy's log stream. Quieted to WARNING; this app's own
# loggers (mtm.*) stay at INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("mtm.main")

# How often the background task refreshes all four feeds, in seconds.
# Chosen conservatively: SEC EDGAR and GDELT rate limits (see
# rate_limiter.py) mean a full sweep of ~500 tickers already takes real
# time, and there's no value refreshing faster than sources actually
# publish. 30 minutes balances freshness against not hammering upstreams.
BACKGROUND_REFRESH_INTERVAL_SECONDS = 30 * 60

_background_task: asyncio.Task | None = None


async def _background_refresh_loop() -> None:
    while True:
        try:
            summary = await refresh_module.refresh_all()
            logger.info("Background refresh completed: %s", summary)
        except Exception:  # noqa: BLE001 - never let the loop die
            logger.exception("Background refresh loop hit an unexpected error")
        await asyncio.sleep(BACKGROUND_REFRESH_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _background_task
    _background_task = asyncio.create_task(_background_refresh_loop())
    try:
        yield
    finally:
        if _background_task:
            _background_task.cancel()


app = FastAPI(
    title="Money that matters API",
    description=(
        "Backend for the Money that matters dashboard. Public-filings data. "
        "Not financial advice. Congressional trades are disclosed on a "
        "legal delay."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://money-that-matters.vercel.app",
        "http://localhost:5173",  # local dev
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(money_match.router)
app.include_router(feeds.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/refresh")
async def manual_refresh():
    """Triggered by the frontend's Refresh button. Runs all four fetchers
    concurrently and waits for the result -- a full sweep of the tracked
    universe can take a while (SEC EDGAR's 10 req/s limit alone bounds a
    500-ticker sweep to 50+ seconds), so this is a slow endpoint by
    nature. The frontend shows a spinner for the duration rather than
    polling a job id, since Railway's request timeout is long enough for
    this to complete synchronously."""
    summary = await refresh_module.refresh_all()
    return {"status": "completed", "sources": summary}
