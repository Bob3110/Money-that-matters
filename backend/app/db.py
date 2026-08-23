from __future__ import annotations

from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient

from .config import MONGO_DB_NAME, MONGO_URI, STALE_AFTER_HOURS
from .models import FeedMode

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]


async def record_feed_success(source: str) -> None:
    db = get_db()
    now = datetime.now(timezone.utc)
    await db.feed_status.update_one(
        {"source": source},
        {"$set": {"last_success_at": now, "last_attempt_at": now, "error": None}},
        upsert=True,
    )


async def record_feed_failure(source: str, error: str) -> None:
    """A failed fetch must NEVER overwrite good cached data -- this only
    touches last_attempt_at/error, never last_success_at or the cached
    items themselves."""
    db = get_db()
    now = datetime.now(timezone.utc)
    await db.feed_status.update_one(
        {"source": source},
        {"$set": {"last_attempt_at": now, "error": error}},
        upsert=True,
    )


async def get_feed_mode(source: str) -> tuple[FeedMode, datetime | None]:
    db = get_db()
    doc = await db.feed_status.find_one({"source": source})
    if not doc or not doc.get("last_success_at"):
        return FeedMode.EMPTY, None
    last_success: datetime = doc["last_success_at"]
    if last_success.tzinfo is None:
        last_success = last_success.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - last_success
    if age <= timedelta(hours=STALE_AFTER_HOURS):
        return FeedMode.LIVE, last_success
    return FeedMode.STALE, last_success
