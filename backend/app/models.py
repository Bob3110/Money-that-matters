from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class FeedMode(str, Enum):
    LIVE = "live"
    STALE = "stale"
    EMPTY = "empty"


class Lean(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


class MarketNewsItem(BaseModel):
    ticker: str | None = None
    company: str | None = None
    headline: str
    outlet: str
    source_url: str
    published_at: datetime
    lean: Lean


class InsiderTransaction(BaseModel):
    ticker: str
    company: str
    insider_name: str
    insider_role: str
    transaction: str  # "buy" | "sell"
    shares: int
    value_usd: float | None = None
    filed_at: datetime
    source_url: str


class CongressDisclosure(BaseModel):
    member_name: str
    district: str | None = None
    filing_date: datetime
    document_id: str
    document_url: str
    # Deliberately no ticker/transaction_type fields: the House Clerk index
    # gives filings, not parsed trades. Do NOT add these without an actual
    # extraction source -- see fetchers/congress.py.


class EgyptNewsItem(BaseModel):
    ticker: str | None = None  # None means "market-wide"
    company: str | None = None
    headline: str
    outlet: str
    source_url: str
    published_at: datetime
    lean: Lean


class FeedStatus(BaseModel):
    source: str
    mode: FeedMode
    last_success_at: datetime | None
    last_attempt_at: datetime | None
    error: str | None = None


class TickerCard(BaseModel):
    ticker: str
    company: str
    score: int
    direction: Lean
    strong_match: bool
    sources_fired: list[str]
    sources_excluded: list[str]
