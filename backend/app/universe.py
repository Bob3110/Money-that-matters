"""
Tracked ticker universe for Market News, Insiders, and Congress (US-market
only). Seeded with a baseline (S&P 500 + Nasdaq-100) and grown dynamically:
the moment a ticker clears the Market News source+subject gates, it's added
here so Insiders starts checking it too.

This set is intentionally kept separate from anything Egypt-related. EGX
tickers must never enter this set, and this set must never be checked
against Egypt News -- see egypt/ fetcher, which uses its own allow-list and
never reads from here.
"""

from __future__ import annotations

import json
import os

from .config import TICKER_UNIVERSE_SEED_PATH


class TrackedUniverse:
    def __init__(self, seed_path: str = TICKER_UNIVERSE_SEED_PATH) -> None:
        self._seed_path = seed_path
        self._tickers: set[str] = self._load_seed()

    def _load_seed(self) -> set[str]:
        if not os.path.exists(self._seed_path):
            # Honest empty state rather than a fabricated fallback list --
            # ops must populate data/ticker_universe_seed.json with a real
            # S&P 500 + Nasdaq-100 constituent list before first run.
            return set()
        with open(self._seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {t.strip().upper() for t in data if t and t.strip()}

    def all(self) -> frozenset[str]:
        return frozenset(self._tickers)

    def contains(self, ticker: str) -> bool:
        return ticker.strip().upper() in self._tickers

    def add(self, ticker: str) -> bool:
        """Add a ticker that just cleared the Market News gates. Returns
        True if it was newly added (so Insiders knows to prioritize it on
        the next sweep), False if already tracked."""
        t = ticker.strip().upper()
        if not t or t in self._tickers:
            return False
        self._tickers.add(t)
        return True


# Module-level singleton -- the FastAPI app holds one shared instance so
# growth from a Market News sweep is visible to the next Insiders sweep.
tracked_universe = TrackedUniverse()
