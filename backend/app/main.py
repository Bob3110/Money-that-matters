from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import feeds, money_match

app = FastAPI(
    title="Money that matters API",
    description=(
        "Backend for the Money that matters dashboard. Public-filings data. "
        "Not financial advice. Congressional trades are disclosed on a "
        "legal delay."
    ),
)

# Wide-open CORS below is a development default only -- see DEPLOYMENT.md
# for locking this to the real deployed frontend origin before going live.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(money_match.router)
app.include_router(feeds.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/refresh")
async def manual_refresh():
    """Triggered by the frontend's Refresh button. Real implementation
    kicks off the four fetchers concurrently (asyncio.gather with
    return_exceptions=True) so one broken source degrades only its own
    tab, then returns immediately with a job id while fetches run in the
    background -- left as a TODO wired to a task queue at deploy time
    rather than blocking this request for the duration of four external
    fetches."""
    return {"status": "refresh_triggered"}
