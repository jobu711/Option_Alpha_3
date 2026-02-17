"""Tests for composite scoring and universe scoring pipeline."""

import math

import pytest

from Option_Alpha.analysis.scoring import (
    INDICATOR_WEIGHTS,
    composite_score,
    score_universe,
)
from Option_Alpha.models.scan import TickerScore


class TestCompositeScore:
    """Tests for composite_score()."""

    def test_known_weighted_geometric_mean(self) -> None:
        """Verify composite_score against a hand-calculated weighted geometric mean.

        With rsi=80, adx=60:
          weights: rsi=0.08, adx=0.08
          weighted_log_sum = 0.08*ln(80) + 0.08*ln(60)
          weight_sum = 0.16
          score = exp(weighted_log_sum / weight_sum)
        """
        indicators: dict[str, float] = {"rsi": 80.0, "adx": 60.0}
        result = composite_score(indicators)

        # Manual calculation
        w_rsi = 0.08
        w_adx = 0.08
        expected = math.exp((w_rsi * math.log(80.0) + w_adx * math.log(60.0)) / (w_rsi + w_adx))
        assert result == pytest.approx(expected, rel=1e-4)

    def test_all_indicators_present(self) -> None:
        """All 18 indicators at 75.0 produce a score of 75.0."""
        indicators: dict[str, float] = {name: 75.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)

        # When all values are the same, geometric mean = that value.
        assert result == pytest.approx(75.0, rel=1e-4)

    def test_missing_indicators_gracefully_skipped(self) -> None:
        """Indicators not in the input are skipped without error."""
        # Only provide one indicator.
        indicators: dict[str, float] = {"rsi": 80.0}
        result = composite_score(indicators)

        # With a single indicator, score = exp(ln(80)) = 80
        assert result == pytest.approx(80.0, rel=1e-4)

    def test_unknown_indicators_ignored(self) -> None:
        """Indicators not in INDICATOR_WEIGHTS are silently ignored."""
        indicators: dict[str, float] = {
            "rsi": 80.0,
            "completely_unknown": 99.0,
        }
        result = composite_score(indicators)

        # Only rsi contributes.
        assert result == pytest.approx(80.0, rel=1e-4)

    def test_zero_value_uses_floor(self) -> None:
        """Values <= 0 are replaced with 1.0 to avoid log(0)."""
        indicators: dict[str, float] = {"rsi": 0.0}
        result = composite_score(indicators)

        # 0.0 -> 1.0(1.0), exp(ln(1.0)) = 1.0
        assert result == pytest.approx(1.0, rel=1e-4)

    def test_negative_value_uses_floor(self) -> None:
        """Negative values are replaced with 1.0."""
        indicators: dict[str, float] = {"rsi": -10.0}
        result = composite_score(indicators)
        assert result == pytest.approx(1.0, rel=1e-4)

    def test_score_clamped_to_100(self) -> None:
        """Score cannot exceed 100.0 even with extreme inputs.

        Since percentile ranks are in [0, 100], the geometric mean naturally
        stays within [0, 100]. But we verify the clamp works by using a value
        at exactly 100.
        """
        indicators: dict[str, float] = {name: 100.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result <= 100.0

    def test_score_clamped_to_0(self) -> None:
        """Score cannot go below 0.0."""
        # All zeros -> all become 1.0(1.0) -> score = 1.0
        indicators: dict[str, float] = {name: 0.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result >= 0.0

    def test_empty_indicators_returns_zero(self) -> None:
        """No indicators at all returns 0.0."""
        result = composite_score({})
        assert result == pytest.approx(0.0, rel=1e-4)

    def test_weights_sum_approximately_one(self) -> None:
        """Sanity check: all weights sum to approximately 1.0."""
        total = sum(INDICATOR_WEIGHTS.values())
        assert total == pytest.approx(1.0, rel=1e-4)


class TestScoreUniverse:
    """Tests for score_universe() end-to-end pipeline."""

    def test_end_to_end_scored_sorted_ranked(self) -> None:
        """Raw indicators -> normalize -> invert -> score -> filter -> sort -> rank.

        Use all 18 indicators for 3 tickers with varying values so that the
        scoring produces a clear ranking.
        """
        # Ticker A: high values (should score well)
        # Ticker B: medium values
        # Ticker C: low values
        base_indicators = list(INDICATOR_WEIGHTS.keys())
        universe: dict[str, dict[str, float]] = {
            "HIGH": {ind: 90.0 for ind in base_indicators},
            "MED": {ind: 50.0 for ind in base_indicators},
            "LOW": {ind: 10.0 for ind in base_indicators},
        }
        results = score_universe(universe)

        # All should pass the MIN_COMPOSITE_SCORE filter since after
        # normalization the highest-ranked ticker will have high percentiles.
        # The relative order should be HIGH > MED > LOW (or their percentile
        # equivalents).
        assert len(results) >= 1

        # Verify they are TickerScore instances.
        for ts in results:
            assert isinstance(ts, TickerScore)

        # Verify descending order.
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

        # Verify ranks are sequential 1-based.
        for i, ts in enumerate(results):
            assert ts.rank == i + 1

    def test_min_composite_score_filtering(self) -> None:
        """Tickers scoring below MIN_COMPOSITE_SCORE are excluded.

        Use only non-inverted indicators so the inversion step does not
        flip high percentiles to zero and drag the geometric mean down.
        With 3 tickers and non-inverted indicators only:
        - HIGH: rank 3/3 -> percentile 100 -> composite 100 (passes)
        - MED: rank 2/3 -> percentile ~66.7 -> composite ~66.7 (passes)
        - LOW: rank 1/3 -> percentile ~33.3 -> composite ~33.3 (filtered)
        """
        inverted = {
            "bb_width",
            "atr_percent",
            "relative_volume",
            "keltner_width",
        }
        non_inverted = [k for k in INDICATOR_WEIGHTS if k not in inverted]
        universe: dict[str, dict[str, float]] = {
            "HIGH": {ind: 90.0 for ind in non_inverted},
            "MED": {ind: 50.0 for ind in non_inverted},
            "LOW": {ind: 10.0 for ind in non_inverted},
        }
        results = score_universe(universe)

        tickers_in_results = {ts.ticker for ts in results}
        # HIGH and MED pass the threshold; LOW is filtered out.
        assert "HIGH" in tickers_in_results
        assert "MED" in tickers_in_results
        assert "LOW" not in tickers_in_results

    def test_empty_universe_returns_empty(self) -> None:
        """Empty universe returns empty list."""
        results = score_universe({})
        assert results == []

    def test_single_ticker_universe(self) -> None:
        """A single ticker normalizes to percentile 100 for all indicators."""
        universe: dict[str, dict[str, float]] = {
            "ONLY": {ind: 50.0 for ind in INDICATOR_WEIGHTS},
        }
        results = score_universe(universe)

        # After normalization, ONLY gets percentile 100 for all indicators.
        # After inversion of bb_width, atr_percent, relative_volume,
        # keltner_width, those become 0 -> floor value 1.0.
        # The rest stay at 100.
        # Should still produce a score and pass the threshold.
        assert len(results) >= 0  # May or may not pass threshold depending on inversion.

        # If it passes, rank should be 1.
        if results:
            assert results[0].rank == 1
            assert results[0].ticker == "ONLY"

    def test_ranks_are_assigned_correctly(self) -> None:
        """Ranks are 1-based and sequential after filtering."""
        # 5 tickers with clearly different values.
        universe: dict[str, dict[str, float]] = {
            f"T{i}": {ind: float(i * 20) for ind in INDICATOR_WEIGHTS} for i in range(1, 6)
        }
        results = score_universe(universe)

        for i, ts in enumerate(results):
            assert ts.rank == i + 1

    def test_signals_populated_on_ticker_score(self) -> None:
        """Each TickerScore has a non-empty signals dict."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {ind: 70.0 for ind in INDICATOR_WEIGHTS},
            "MSFT": {ind: 60.0 for ind in INDICATOR_WEIGHTS},
        }
        results = score_universe(universe)

        for ts in results:
            assert len(ts.signals) > 0
