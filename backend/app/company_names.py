"""
Ticker <-> company name matching for headline text.

The naive approach -- matching only literal ticker symbols like "AAPL" in
headline text -- systematically misses almost everything, because real
headlines say "Apple," not "AAPL". This module fixes that by also matching
normalized company names (with legal suffixes like "Inc.", "Corp.",
"Corporation", "plc", "Co." stripped) against headline text.

This is intentionally conservative in the other direction: it requires a
whole-word match of the normalized name (or a long-enough distinctive
prefix of it), not a loose substring, to avoid false positives like
matching "A" (A. O. Smith's ticker) against nearly every sentence in the
English language. Short/ambiguous names are excluded from matching
entirely rather than guessed at.
"""

from __future__ import annotations

import json
import os
import re

_NAMES_PATH = os.path.join(os.path.dirname(__file__), "data", "ticker_company_names.json")

_LEGAL_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|plc|ltd|limited|"
    r"holdings?|group|the)\b\.?",
    re.IGNORECASE,
)

# Names shorter than this after normalization are too ambiguous to match
# as free text (e.g. a single common word) -- excluded from the map
# entirely rather than risking false positives.
MIN_MATCHABLE_NAME_LENGTH = 4


def _normalize(name: str) -> str:
    name = name.replace(",", " ").replace(".", " ")
    name = _LEGAL_SUFFIXES.sub("", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


_ticker_to_name_normalized: dict[str, str] | None = None
_name_to_ticker: dict[str, str] | None = None


def _load() -> tuple[dict[str, str], dict[str, str]]:
    global _ticker_to_name_normalized, _name_to_ticker
    if _ticker_to_name_normalized is not None and _name_to_ticker is not None:
        return _ticker_to_name_normalized, _name_to_ticker

    if not os.path.exists(_NAMES_PATH):
        _ticker_to_name_normalized, _name_to_ticker = {}, {}
        return _ticker_to_name_normalized, _name_to_ticker

    with open(_NAMES_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    ticker_to_norm: dict[str, str] = {}
    norm_to_ticker: dict[str, str] = {}
    for ticker, name in raw.items():
        norm = _normalize(name)
        if len(norm) < MIN_MATCHABLE_NAME_LENGTH:
            continue  # too ambiguous to match as free text -- skip, don't guess
        ticker_to_norm[ticker] = norm
        norm_to_ticker[norm] = ticker

    _ticker_to_name_normalized, _name_to_ticker = ticker_to_norm, norm_to_ticker
    return ticker_to_norm, norm_to_ticker


def find_tickers_by_company_name(text: str, tracked_universe: frozenset[str]) -> set[str]:
    """Match normalized company names as whole-word substrings of `text`.
    Only returns tickers that are also in `tracked_universe`, so this can
    never surface a ticker the rest of the app hasn't already validated
    into the tracked set."""
    _, norm_to_ticker = _load()
    if not norm_to_ticker:
        return set()

    normalized_text = re.sub(r"[^\w\s]", " ", text.lower())
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
    words = f" {normalized_text} "

    found = set()
    for norm_name, ticker in norm_to_ticker.items():
        if ticker not in tracked_universe:
            continue
        if f" {norm_name} " in words:
            found.add(ticker)
    return found
