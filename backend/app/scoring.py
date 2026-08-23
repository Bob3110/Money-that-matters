"""
Money Match scoring engine.

FORMULA (do not change without updating tests/test_scoring.py):

    agreement   = |sum of leans| / number_of_sources_that_fired
    coverage    = number_of_sources_that_fired / 3
    money_match = round(100 * agreement * coverage)

Where each source that "fired" for a ticker contributes a single lean value
in [-1, 1] (bearish..bullish), built from that source's recent items for the
ticker, weighted by recency and (where applicable) size.

Design intent, spelled out because it's easy to accidentally break:

- Coverage is a FULL multiplier, not a bonus. A single source, however
  extreme, can contribute at most 1/3 of coverage, so its score caps at
  100 * 1 * (1/3) = 33.3 -> 33. Two agreeing sources cap at 67. Only three
  agreeing sources can approach 100.
- Neutral is not evidence of agreement. A source with a net-neutral lean
  (lean == 0) still counts as "fired" for coverage purposes if it produced
  data, but contributes 0 to the sum inside agreement. This matters: it's
  possible for a source to fire (mode=live, has items) and still land at
  neutral, e.g. equal bullish/bearish weight.
- A STALE source does not vote at all -- it does not count in
  number_of_sources_that_fired and does not contribute to the sum. It is
  excluded, not counted as a neutral/no-signal source. This is why the
  caller must pass only sources whose mode == "live" into
  compute_money_match; stale/empty sources are filtered upstream (see
  build_source_leans) and shown in the UI as "excluded", not "no signal".
- Ties in ranking break on source count: a 3-source 60 outranks a
  1-source 60.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class SourceName(str, Enum):
    MARKET_NEWS = "market_news"
    INSIDERS = "insiders"
    CONGRESS = "congress"


class FeedMode(str, Enum):
    LIVE = "live"
    STALE = "stale"
    EMPTY = "empty"


@dataclass(frozen=True)
class SourceLean:
    """A single source's net directional lean for one ticker.

    lean must be in [-1.0, 1.0]. mode reflects the *feed's* freshness
    (live/stale/empty), not this ticker's data specifically -- a live feed
    with zero items for this ticker simply never appears in the list passed
    to compute_money_match (it didn't "fire").
    """

    source: SourceName
    lean: float
    mode: FeedMode

    def __post_init__(self) -> None:
        if not -1.0 <= self.lean <= 1.0:
            raise ValueError(f"lean must be within [-1, 1], got {self.lean}")


@dataclass(frozen=True)
class MoneyMatchResult:
    ticker: str
    score: int
    sources_fired: int
    direction: str  # "bullish" | "bearish" | "neutral"
    strong_match: bool
    excluded_sources: tuple[SourceName, ...]  # stale, shown as excluded not silent


TOTAL_SOURCES = 3
STRONG_MATCH_THRESHOLD = 60


def compute_money_match(ticker: str, source_leans: Iterable[SourceLean]) -> MoneyMatchResult:
    """Compute the Money Match score for one ticker.

    `source_leans` should contain ONLY sources with mode == LIVE that
    actually produced data for this ticker (i.e. "fired"). Stale sources
    must be filtered out by the caller *before* calling this function, and
    passed separately for display purposes -- see build_source_leans below,
    which does this filtering and returns both lists.
    """
    live = [sl for sl in source_leans if sl.mode == FeedMode.LIVE]
    excluded = tuple(sorted({sl.source for sl in source_leans if sl.mode != FeedMode.LIVE}, key=lambda s: s.value))

    n_fired = len(live)
    if n_fired == 0:
        return MoneyMatchResult(
            ticker=ticker,
            score=0,
            sources_fired=0,
            direction="neutral",
            strong_match=False,
            excluded_sources=excluded,
        )

    lean_sum = sum(sl.lean for sl in live)
    agreement = abs(lean_sum) / n_fired
    coverage = n_fired / TOTAL_SOURCES
    score = round(100 * agreement * coverage)

    if lean_sum > 0:
        direction = "bullish"
    elif lean_sum < 0:
        direction = "bearish"
    else:
        direction = "neutral"

    all_three_present_and_agree = n_fired == TOTAL_SOURCES and (
        all(sl.lean > 0 for sl in live) or all(sl.lean < 0 for sl in live)
    )
    strong_match = all_three_present_and_agree and score >= STRONG_MATCH_THRESHOLD

    return MoneyMatchResult(
        ticker=ticker,
        score=score,
        sources_fired=n_fired,
        direction=direction,
        strong_match=strong_match,
        excluded_sources=excluded,
    )


def rank_results(results: Iterable[MoneyMatchResult]) -> list[MoneyMatchResult]:
    """Rank by score desc, breaking ties by sources_fired desc (a 3-source 60
    outranks a 1-source 60), then ticker asc for full determinism."""
    return sorted(results, key=lambda r: (-r.score, -r.sources_fired, r.ticker))


# ---------------------------------------------------------------------------
# Recency/size weighting used to build a single SourceLean from raw items.
# ---------------------------------------------------------------------------

def recency_weight(item_date: datetime, as_of: datetime, half_life_days: float) -> float:
    """Exponential decay: weight halves every `half_life_days`. Both datetimes
    must be timezone-aware; naive datetimes are treated as UTC by callers via
    parse_item_date (see dates.py) before reaching this function."""
    if item_date.tzinfo is None:
        item_date = item_date.replace(tzinfo=timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (as_of - item_date).total_seconds() / 86400.0)
    return 0.5 ** (age_days / half_life_days)


def weighted_lean(item_leans_and_weights: Iterable[tuple[float, float]]) -> float:
    """item_leans_and_weights: iterable of (lean in [-1,1], weight > 0).
    Returns weighted-average lean clamped to [-1, 1]. Empty input -> 0.0
    (neutral), representing "no directional read" rather than an error --
    callers decide whether zero items means the source didn't fire at all."""
    items = list(item_leans_and_weights)
    if not items:
        return 0.0
    total_weight = sum(w for _, w in items)
    if total_weight == 0:
        return 0.0
    total = sum(lean * w for lean, w in items)
    result = total / total_weight
    return max(-1.0, min(1.0, result))
