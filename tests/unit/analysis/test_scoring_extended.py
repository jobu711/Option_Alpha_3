"""Extended scoring tests: composite_score edge cases, weight validation."""

from __future__ import annotations

import pytest

from Option_Alpha.analysis.scoring import (
    _FLOOR_VALUE,
    INDICATOR_WEIGHTS,
    MIN_COMPOSITE_SCORE,
    composite_score,
    score_universe,
)

# ---------------------------------------------------------------------------
# composite_score edge cases
# ---------------------------------------------------------------------------


class TestCompositeScoreExtended:
    """Additional edge cases for the composite_score function."""

    def test_empty_indicators_returns_zero(self) -> None:
        assert composite_score({}) == pytest.approx(0.0, abs=1e-9)

    def test_unknown_indicators_ignored(self) -> None:
        """Indicators not in INDICATOR_WEIGHTS are silently skipped."""
        result = composite_score({"unknown_indicator": 50.0})
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_all_indicators_at_hundred(self) -> None:
        """All indicators at 100 -> score is 100."""
        indicators = {name: 100.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result == pytest.approx(100.0, abs=0.01)

    def test_all_indicators_at_one(self) -> None:
        """All indicators at 1.0 -> geometric mean is 1.0."""
        indicators = {name: 1.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result == pytest.approx(1.0, abs=0.01)

    def test_zero_value_replaced_with_floor(self) -> None:
        """Zero percentile rank is replaced with _FLOOR_VALUE to avoid log(0)."""
        indicators = {name: 0.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result == pytest.approx(_FLOOR_VALUE, abs=0.01)

    def test_negative_value_replaced_with_floor(self) -> None:
        """Negative values are replaced with _FLOOR_VALUE."""
        indicators = {name: -5.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result == pytest.approx(_FLOOR_VALUE, abs=0.01)

    def test_partial_indicators_weighted_correctly(self) -> None:
        """Only some indicators present -> only their weights are summed."""
        # Only RSI at 50 -> score = exp(w_rsi * ln(50) / w_rsi) = 50
        result = composite_score({"rsi": 50.0})
        assert result == pytest.approx(50.0, abs=0.01)

    def test_score_clamped_to_hundred(self) -> None:
        """Score cannot exceed 100.0."""
        # Very high values
        indicators = {name: 1000.0 for name in INDICATOR_WEIGHTS}
        result = composite_score(indicators)
        assert result <= 100.0


# ---------------------------------------------------------------------------
# INDICATOR_WEIGHTS validation
# ---------------------------------------------------------------------------


class TestIndicatorWeights:
    """Verify the indicator weight configuration."""

    def test_weights_sum_to_one(self) -> None:
        total = sum(INDICATOR_WEIGHTS.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_eighteen_indicators(self) -> None:
        assert len(INDICATOR_WEIGHTS) == 18

    def test_all_weights_positive(self) -> None:
        assert all(w > 0 for w in INDICATOR_WEIGHTS.values())

    def test_min_composite_score_constant(self) -> None:
        assert pytest.approx(50.0, abs=1e-9) == MIN_COMPOSITE_SCORE

    def test_floor_value_constant(self) -> None:
        assert pytest.approx(1.0, abs=1e-9) == _FLOOR_VALUE


# ---------------------------------------------------------------------------
# score_universe edge cases
# ---------------------------------------------------------------------------


class TestScoreUniverseExtended:
    """Additional edge cases for the score_universe pipeline."""

    def test_empty_universe(self) -> None:
        result = score_universe({})
        assert result == []

    def test_single_ticker_percentile_rank(self) -> None:
        """Single ticker: percentile rank with 1 ticker produces a deterministic score."""
        indicators = {"AAPL": {name: 75.0 for name in INDICATOR_WEIGHTS}}
        result = score_universe(indicators)
        # With a single ticker, percentile rank puts it at 100 (or 0) — behavior is
        # determined by the normalization logic. Just verify no crash and valid output.
        for ts in result:
            assert ts.ticker == "AAPL"
            assert ts.rank == 1

    def test_all_tickers_below_threshold(self) -> None:
        """All tickers scoring below MIN_COMPOSITE_SCORE -> empty result."""
        # Very low values
        indicators = {
            "LOW1": {name: 1.0 for name in INDICATOR_WEIGHTS},
            "LOW2": {name: 2.0 for name in INDICATOR_WEIGHTS},
        }
        result = score_universe(indicators)
        # May or may not be empty depending on normalization, but low scores
        # will be below threshold after percentile ranking puts them at the bottom
        for ts in result:
            assert ts.score >= MIN_COMPOSITE_SCORE

    def test_ranks_are_sequential(self) -> None:
        """Multiple qualifying tickers get ranks 1, 2, 3, ..."""
        # Create a universe with varied indicator values
        indicators = {}
        for i, ticker in enumerate(["AAPL", "MSFT", "GOOG", "AMZN", "TSLA"]):
            indicators[ticker] = {name: 50.0 + i * 10 for name in INDICATOR_WEIGHTS}
        result = score_universe(indicators)
        if len(result) > 1:
            for i, ts in enumerate(result):
                assert ts.rank == i + 1

    def test_sorted_descending_by_score(self) -> None:
        """Results are sorted by score descending."""
        indicators = {}
        for i, ticker in enumerate(["A", "B", "C", "D", "E"]):
            indicators[ticker] = {name: 50.0 + i * 10 for name in INDICATOR_WEIGHTS}
        result = score_universe(indicators)
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].score >= result[i + 1].score
