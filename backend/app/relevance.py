"""
Subject-gate relevance filters. Passing the source allow-list only proves an
outlet is credible; it says nothing about whether a given item is actually
about something that could move a stock. These filters are the second gate
described in the build spec for both Market News and Egypt News.
"""

from __future__ import annotations

import re

# Terms that indicate market/business-desk relevance for a general index/sector
# style story (used when a story doesn't name a specific tracked ticker).
MARKET_TERMS = (
    "index", "indices", "sector", "central bank", "federal reserve", "fed",
    "interest rate", "rate decision", "rate cut", "rate hike", "trade deal",
    "tariff", "earnings", "gdp", "inflation", "cpi", "treasury", "bond yield",
)

EGYPT_FINANCE_TERMS = (
    # English
    "egx", "bourse", "central bank", "cbe", "pound", "egp", "inflation",
    "interest rate", "earnings", "ipo", "listing", "capmas", "gdp", "reserves",
    "devaluation", "treasury bill", "t-bill",
    # Arabic finance/economy terms
    "البورصة", "البنك المركزي", "الجنيه", "التضخم", "الفائدة", "الناتج المحلي",
    "الاحتياطي", "طرح", "أسهم", "سندات",
)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def passes_us_subject_gate(
    *,
    headline: str,
    tracked_tickers: set[str],
    mentioned_tickers: set[str],
    is_markets_business_desk: bool,
) -> bool:
    """A US market-news item passes if it names a tracked ticker/company, OR
    it's specifically from the outlet's markets/business desk AND names an
    index/sector/central-bank/rate-or-trade-decision term. General world news
    (a war, a referendum, an infrastructure story) fails here even from an
    allow-listed outlet, even if it happens to mention a country also in the
    news for other reasons."""
    if mentioned_tickers & tracked_tickers:
        return True
    if is_markets_business_desk and _contains_any(headline, MARKET_TERMS):
        return True
    return False


def passes_egypt_subject_gate(
    *,
    headline: str,
    outlet_is_native_egyptian: bool,
    mentions_egypt_or_egx: bool,
) -> bool:
    """A native Egyptian outlet's beat is Egypt by definition, so it only
    needs a finance/economy term (their sports coverage is not market news).
    An international wire must explicitly name Egypt or the EGX, or general
    market copy about any other country would sail straight through."""
    if outlet_is_native_egyptian:
        return _contains_any(headline, EGYPT_FINANCE_TERMS)
    return mentions_egypt_or_egx and _contains_any(headline, EGYPT_FINANCE_TERMS + ("egypt", "egx", "مصر"))


# ---------------------------------------------------------------------------
# Symbol validation for SEC EDGAR Form 4 data (Insiders feed)
# ---------------------------------------------------------------------------

_VALID_TICKER_RE = re.compile(r"^[A-Z]{1,5}$")
_KNOWN_PLACEHOLDERS = {"NONE", "N/A", "NA", "-", ""}


def is_valid_us_ticker(symbol: str | None) -> bool:
    """Reject malformed symbols leaking out of SEC data: foreign dual-listings
    like 'ASX:LNW' (has a colon/exchange prefix -- can never match a US-only
    tracked universe) and placeholders like 'NONE'."""
    if symbol is None:
        return False
    s = symbol.strip().upper()
    if s in _KNOWN_PLACEHOLDERS:
        return False
    if ":" in s or "." in s:  # exchange-prefixed or dual-listing notation
        return False
    return bool(_VALID_TICKER_RE.match(s))
