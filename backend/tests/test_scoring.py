import pytest

from app.scoring import (
    FeedMode,
    MoneyMatchResult,
    SourceLean,
    SourceName,
    compute_money_match,
    rank_results,
    recency_weight,
    weighted_lean,
)


def live(source, lean):
    return SourceLean(source=source, lean=lean, mode=FeedMode.LIVE)


def stale(source, lean):
    return SourceLean(source=source, lean=lean, mode=FeedMode.STALE)


class TestCoverageCap:
    def test_single_source_caps_at_33_even_at_maximum_extremity(self):
        result = compute_money_match("AAPL", [live(SourceName.INSIDERS, 1.0)])
        assert result.score == 33
        assert result.sources_fired == 1

    def test_single_maximal_source_never_outscores_three_agreeing_sources(self):
        one_source = compute_money_match("AAPL", [live(SourceName.INSIDERS, 1.0)])
        three_sources = compute_money_match(
            "MSFT",
            [
                live(SourceName.MARKET_NEWS, 0.7),
                live(SourceName.INSIDERS, 0.7),
                live(SourceName.CONGRESS, 0.7),
            ],
        )
        assert three_sources.score > one_source.score

    def test_two_agreeing_sources_cap_at_67(self):
        result = compute_money_match(
            "NVDA",
            [live(SourceName.MARKET_NEWS, 1.0), live(SourceName.INSIDERS, 1.0)],
        )
        assert result.score == 67

    def test_three_agreeing_sources_can_approach_100(self):
        result = compute_money_match(
            "GOOGL",
            [
                live(SourceName.MARKET_NEWS, 1.0),
                live(SourceName.INSIDERS, 1.0),
                live(SourceName.CONGRESS, 1.0),
            ],
        )
        assert result.score == 100

    def test_coverage_is_multiplicative_not_additive(self):
        # Two sources at a WEAK lean (0.3) should score lower than one
        # source at max lean (1.0) scaled by coverage -- this guards
        # against an accidental "coverage as bonus" regression where more
        # sources always wins regardless of agreement strength.
        weak_two = compute_money_match(
            "TSLA",
            [live(SourceName.MARKET_NEWS, 0.1), live(SourceName.INSIDERS, 0.1)],
        )
        # agreement=0.1, coverage=2/3 -> 100*0.1*0.667 = 6.7 -> 7
        assert weak_two.score == 7


class TestNeutralAndDisagreement:
    def test_neutral_source_contributes_nothing_to_agreement(self):
        result = compute_money_match(
            "META",
            [live(SourceName.MARKET_NEWS, 0.0), live(SourceName.INSIDERS, 1.0)],
        )
        # sum = 1.0, n_fired = 2 -> agreement = 0.5, coverage = 2/3
        assert result.score == round(100 * 0.5 * (2 / 3))
        assert result.sources_fired == 2  # neutral still "fired" (had data)

    def test_disagreeing_sources_partially_cancel(self):
        result = compute_money_match(
            "AMZN",
            [live(SourceName.MARKET_NEWS, 1.0), live(SourceName.INSIDERS, -1.0)],
        )
        assert result.score == 0
        assert result.direction == "neutral"

    def test_direction_follows_sign_of_sum(self):
        bearish = compute_money_match("XOM", [live(SourceName.MARKET_NEWS, -0.8)])
        assert bearish.direction == "bearish"
        bullish = compute_money_match("XOM", [live(SourceName.MARKET_NEWS, 0.8)])
        assert bullish.direction == "bullish"


class TestStaleSourcesExcludedNotZeroed:
    def test_stale_source_does_not_count_toward_coverage_or_sum(self):
        with_stale = compute_money_match(
            "JPM",
            [live(SourceName.MARKET_NEWS, 1.0), stale(SourceName.INSIDERS, 1.0)],
        )
        without_it = compute_money_match("JPM", [live(SourceName.MARKET_NEWS, 1.0)])
        assert with_stale.score == without_it.score == 33
        assert with_stale.sources_fired == 1

    def test_stale_source_is_reported_as_excluded(self):
        result = compute_money_match(
            "JPM",
            [live(SourceName.MARKET_NEWS, 1.0), stale(SourceName.INSIDERS, 1.0)],
        )
        assert SourceName.INSIDERS in result.excluded_sources

    def test_all_stale_yields_zero_not_a_crash(self):
        result = compute_money_match("JPM", [stale(SourceName.MARKET_NEWS, 1.0)])
        assert result.score == 0
        assert result.sources_fired == 0

    def test_no_sources_at_all(self):
        result = compute_money_match("JPM", [])
        assert result.score == 0
        assert result.sources_fired == 0
        assert result.strong_match is False


class TestStrongMatchBadge:
    def test_requires_all_three_sources_present_and_agreeing(self):
        two_only = compute_money_match(
            "V", [live(SourceName.MARKET_NEWS, 1.0), live(SourceName.INSIDERS, 1.0)]
        )
        assert two_only.strong_match is False  # score is 67 (>=60) but only 2 sources

    def test_fires_when_three_agree_above_threshold(self):
        result = compute_money_match(
            "MA",
            [
                live(SourceName.MARKET_NEWS, 0.8),
                live(SourceName.INSIDERS, 0.8),
                live(SourceName.CONGRESS, 0.8),
            ],
        )
        assert result.strong_match is True
        assert result.score >= 60

    def test_does_not_fire_below_threshold_even_with_three_sources(self):
        result = compute_money_match(
            "PYPL",
            [
                live(SourceName.MARKET_NEWS, 0.2),
                live(SourceName.INSIDERS, 0.2),
                live(SourceName.CONGRESS, 0.2),
            ],
        )
        assert result.strong_match is False
        assert result.score < 60

    def test_does_not_fire_if_three_sources_disagree(self):
        result = compute_money_match(
            "SQ",
            [
                live(SourceName.MARKET_NEWS, 1.0),
                live(SourceName.INSIDERS, 1.0),
                live(SourceName.CONGRESS, -1.0),
            ],
        )
        assert result.strong_match is False


class TestRankingTiebreak:
    def test_three_source_score_outranks_equal_one_source_score(self):
        one_source = MoneyMatchResult("A", 60, 1, "bullish", False, ())
        three_source = MoneyMatchResult("B", 60, 3, "bullish", True, ())
        ranked = rank_results([one_source, three_source])
        assert [r.ticker for r in ranked] == ["B", "A"]

    def test_higher_score_always_ranks_above_lower_regardless_of_source_count(self):
        low_score_more_sources = MoneyMatchResult("A", 40, 3, "bullish", False, ())
        high_score_fewer_sources = MoneyMatchResult("B", 67, 2, "bullish", False, ())
        ranked = rank_results([low_score_more_sources, high_score_fewer_sources])
        assert [r.ticker for r in ranked] == ["B", "A"]


class TestValidation:
    def test_lean_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            SourceLean(source=SourceName.INSIDERS, lean=1.5, mode=FeedMode.LIVE)
        with pytest.raises(ValueError):
            SourceLean(source=SourceName.INSIDERS, lean=-1.1, mode=FeedMode.LIVE)


class TestWeightedLeanHelpers:
    def test_recency_weight_halves_at_half_life(self):
        from datetime import datetime, timedelta, timezone

        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        five_days_ago = now - timedelta(days=5)
        w = recency_weight(five_days_ago, now, half_life_days=5)
        assert abs(w - 0.5) < 1e-9

    def test_recency_weight_is_one_at_zero_age(self):
        from datetime import datetime, timezone

        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        w = recency_weight(now, now, half_life_days=5)
        assert abs(w - 1.0) < 1e-9

    def test_weighted_lean_empty_is_neutral(self):
        assert weighted_lean([]) == 0.0

    def test_weighted_lean_averages_by_weight(self):
        result = weighted_lean([(1.0, 3.0), (-1.0, 1.0)])
        assert abs(result - 0.5) < 1e-9

    def test_weighted_lean_clamped_to_range(self):
        result = weighted_lean([(1.0, 1.0)])
        assert -1.0 <= result <= 1.0
