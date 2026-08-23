"""
In-house bullish/neutral/bearish classification.

Rationale (from the build spec): dedicated sentiment APIs cap free tiers far
too low to run live across many tickers (Alpha Vantage: 25 requests/day). A
deterministic lexicon is the default -- no key, reproducible, and a score can
be explained after the fact by pointing at which words fired. An LLM
classifier can be swapped in behind USE_LLM_SENTIMENT, but its prompt is kept
as a single reviewable constant below, because prompt quality directly drives
what shows up as a "Strong Match" badge on the home screen.

Output is always presented as an algorithmic lean, never as fact -- callers
must not render this as "this stock IS bullish", only "recent items lean
bullish".
"""

from __future__ import annotations

import os
import re

BULLISH_TERMS = (
    "beats expectations", "beat estimates", "raises guidance", "upgraded",
    "record revenue", "record profit", "surpassed", "outperform", "buyback",
    "strong demand", "accelerating growth", "exceeds forecast", "tops estimates",
    "buy rating", "price target raised", "expansion", "strong quarter",
)

BEARISH_TERMS = (
    "misses expectations", "missed estimates", "cuts guidance", "downgraded",
    "warns", "profit warning", "layoffs", "recall", "investigation", "lawsuit",
    "underperform", "sell rating", "price target cut", "weak demand",
    "declining", "shortfall", "restructuring", "bankruptcy", "delisted",
)

# Kept as a single reviewable constant per the build spec, used only if
# USE_LLM_SENTIMENT is enabled (see classify_llm below).
LLM_SENTIMENT_PROMPT = """You are classifying a single financial news headline for \
directional market sentiment. Read the headline and respond with exactly one word: \
BULLISH, BEARISH, or NEUTRAL.

Rules:
- BULLISH means the news is likely positive for the stock's price.
- BEARISH means the news is likely negative for the stock's price.
- NEUTRAL means no clear directional read, or the headline is purely factual \
  with no evaluative signal (e.g. a routine filing date, a scheduled event).
- Do not guess based on the company's general reputation; classify only what \
  the headline itself states.
- Respond with exactly one word and nothing else.

Headline: {headline}"""


def classify_lexicon(headline: str) -> float:
    """Returns a lean in [-1, 1]. Counts (weighted equally) bullish vs
    bearish term hits and returns the normalized difference. No hits on
    either side -> 0.0 (neutral)."""
    text = headline.lower()
    bull_hits = sum(1 for term in BULLISH_TERMS if term in text)
    bear_hits = sum(1 for term in BEARISH_TERMS if term in text)
    total = bull_hits + bear_hits
    if total == 0:
        return 0.0
    return (bull_hits - bear_hits) / total


def classify(headline: str) -> float:
    """Entry point used by fetchers. Uses the LLM classifier only if
    USE_LLM_SENTIMENT is truthy in the environment; otherwise the
    deterministic lexicon, which is the documented default."""
    if os.environ.get("USE_LLM_SENTIMENT", "").lower() in ("1", "true", "yes"):
        return classify_llm(headline)
    return classify_lexicon(headline)


def classify_llm(headline: str) -> float:  # pragma: no cover - requires network/API access
    """Optional LLM-backed classifier. Not called by default. Left as a
    documented stub: wiring this to a real completion call is an
    infrastructure decision (which model, which endpoint) left to the
    deployer, but the prompt driving it must remain LLM_SENTIMENT_PROMPT
    above so its behavior stays auditable."""
    raise NotImplementedError(
        "USE_LLM_SENTIMENT is enabled but classify_llm() has no model backend "
        "wired up in this environment. Wire this to your chosen completion "
        "API before enabling USE_LLM_SENTIMENT, or unset it to use the "
        "lexicon classifier."
    )


_word_re = re.compile(r"[a-z']+")
