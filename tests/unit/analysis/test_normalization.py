"""Tests for percentile-rank normalization and indicator inversion."""

import pytest

from Option_Alpha.analysis.normalization import (
    INVERTED_INDICATORS,
    invert_indicators,
    percentile_rank_normalize,
)


class TestPercentileRankNormalize:
    """Tests for percentile_rank_normalize()."""

    def test_three_tickers_three_indicators(self) -> None:
        """Three tickers with three indicators produce correct percentile ranks.

        With 3 values, ranks are 1, 2, 3. Percentiles = (rank/3)*100.
        rank 1 -> 33.33, rank 2 -> 66.67, rank 3 -> 100.0
        """
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 30.0, "adx": 50.0, "obv_trend": 100.0},
            "MSFT": {"rsi": 50.0, "adx": 30.0, "obv_trend": 200.0},
            "GOOG": {"rsi": 70.0, "adx": 70.0, "obv_trend": 150.0},
        }
        result = percentile_rank_normalize(universe)

        # RSI: AAPL(30)=rank1, MSFT(50)=rank2, GOOG(70)=rank3
        assert result["AAPL"]["rsi"] == pytest.approx(100.0 / 3.0, rel=1e-4)
        assert result["MSFT"]["rsi"] == pytest.approx(200.0 / 3.0, rel=1e-4)
        assert result["GOOG"]["rsi"] == pytest.approx(100.0, rel=1e-4)

        # ADX: MSFT(30)=rank1, AAPL(50)=rank2, GOOG(70)=rank3
        assert result["MSFT"]["adx"] == pytest.approx(100.0 / 3.0, rel=1e-4)
        assert result["AAPL"]["adx"] == pytest.approx(200.0 / 3.0, rel=1e-4)
        assert result["GOOG"]["adx"] == pytest.approx(100.0, rel=1e-4)

        # OBV: AAPL(100)=rank1, GOOG(150)=rank2, MSFT(200)=rank3
        assert result["AAPL"]["obv_trend"] == pytest.approx(100.0 / 3.0, rel=1e-4)
        assert result["GOOG"]["obv_trend"] == pytest.approx(200.0 / 3.0, rel=1e-4)
        assert result["MSFT"]["obv_trend"] == pytest.approx(100.0, rel=1e-4)

    def test_missing_indicator_excluded_for_that_ticker(self) -> None:
        """Tickers missing an indicator are excluded from that indicator's output."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 30.0, "adx": 40.0},
            "MSFT": {"rsi": 50.0},  # missing adx
        }
        result = percentile_rank_normalize(universe)

        # MSFT missing adx -> not present in output (skipped, not defaulted)
        assert "adx" not in result["MSFT"]

        # AAPL has adx, and it's the only valid value -> rank 1/1 = 100
        assert result["AAPL"]["adx"] == pytest.approx(100.0, rel=1e-4)

    def test_nan_indicator_excluded_for_that_ticker(self) -> None:
        """NaN indicator values are treated as missing and excluded from output."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 30.0},
            "MSFT": {"rsi": float("nan")},
        }
        result = percentile_rank_normalize(universe)

        # MSFT has NaN rsi -> not present in output (skipped, not defaulted)
        assert "rsi" not in result.get("MSFT", {})

        # AAPL is the only valid value -> rank 1/1 = 100
        assert result["AAPL"]["rsi"] == pytest.approx(100.0, rel=1e-4)

    def test_single_ticker_gets_percentile_100(self) -> None:
        """A single ticker is rank 1 of 1, so percentile = (1/1)*100 = 100."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 45.0, "adx": 25.0},
        }
        result = percentile_rank_normalize(universe)

        assert result["AAPL"]["rsi"] == pytest.approx(100.0, rel=1e-4)
        assert result["AAPL"]["adx"] == pytest.approx(100.0, rel=1e-4)

    def test_empty_universe_returns_empty(self) -> None:
        """An empty universe produces an empty result."""
        result = percentile_rank_normalize({})
        assert result == {}

    def test_tied_values_get_same_rank(self) -> None:
        """Tickers with identical indicator values share the same percentile."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 50.0},
            "MSFT": {"rsi": 50.0},
            "GOOG": {"rsi": 50.0},
        }
        result = percentile_rank_normalize(universe)

        # All tied at rank 2 (average of positions 1,2,3). Percentile = (2/3)*100
        expected = (2.0 / 3.0) * 100.0
        assert result["AAPL"]["rsi"] == pytest.approx(expected, rel=1e-4)
        assert result["MSFT"]["rsi"] == pytest.approx(expected, rel=1e-4)
        assert result["GOOG"]["rsi"] == pytest.approx(expected, rel=1e-4)

    def test_two_tied_one_different(self) -> None:
        """Two tied values and one different produce correct percentiles."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": 30.0},
            "MSFT": {"rsi": 30.0},
            "GOOG": {"rsi": 70.0},
        }
        result = percentile_rank_normalize(universe)

        # AAPL and MSFT tied at rank 1.5 (avg of positions 1,2).
        # Percentile = (1.5/3)*100 = 50.0
        assert result["AAPL"]["rsi"] == pytest.approx(50.0, rel=1e-4)
        assert result["MSFT"]["rsi"] == pytest.approx(50.0, rel=1e-4)

        # GOOG at rank 3. Percentile = (3/3)*100 = 100.0
        assert result["GOOG"]["rsi"] == pytest.approx(100.0, rel=1e-4)

    def test_all_nan_indicator_excluded_entirely(self) -> None:
        """When all tickers have NaN for an indicator, it is excluded from output."""
        universe: dict[str, dict[str, float]] = {
            "AAPL": {"rsi": float("nan")},
            "MSFT": {"rsi": float("nan")},
        }
        result = percentile_rank_normalize(universe)

        # Indicator with no valid values across the universe is excluded
        assert "rsi" not in result.get("AAPL", {})
        assert "rsi" not in result.get("MSFT", {})


class TestInvertIndicators:
    """Tests for invert_indicators()."""

    def test_inverted_indicators_are_flipped(self) -> None:
        """Indicators in INVERTED_INDICATORS get 100 - rank."""
        normalized: dict[str, dict[str, float]] = {
            "AAPL": {
                "bb_width": 80.0,
                "atr_percent": 70.0,
                "relative_volume": 90.0,
                "keltner_width": 60.0,
                "rsi": 55.0,  # not inverted
            },
        }
        result = invert_indicators(normalized)

        assert result["AAPL"]["bb_width"] == pytest.approx(20.0, rel=1e-4)
        assert result["AAPL"]["atr_percent"] == pytest.approx(30.0, rel=1e-4)
        assert result["AAPL"]["relative_volume"] == pytest.approx(10.0, rel=1e-4)
        assert result["AAPL"]["keltner_width"] == pytest.approx(40.0, rel=1e-4)
        assert result["AAPL"]["rsi"] == pytest.approx(55.0, rel=1e-4)

    def test_non_inverted_indicators_unchanged(self) -> None:
        """Indicators not in INVERTED_INDICATORS are returned as-is."""
        normalized: dict[str, dict[str, float]] = {
            "MSFT": {"rsi": 75.0, "adx": 60.0, "iv_rank": 80.0},
        }
        result = invert_indicators(normalized)

        assert result["MSFT"]["rsi"] == pytest.approx(75.0, rel=1e-4)
        assert result["MSFT"]["adx"] == pytest.approx(60.0, rel=1e-4)
        assert result["MSFT"]["iv_rank"] == pytest.approx(80.0, rel=1e-4)

    def test_inverted_indicators_constant_contains_expected_names(self) -> None:
        """INVERTED_INDICATORS contains the four expected indicator names."""
        expected = {"bb_width", "atr_percent", "relative_volume", "keltner_width"}
        assert expected == INVERTED_INDICATORS

    def test_empty_input_returns_empty(self) -> None:
        """Empty normalized dict returns empty result."""
        result = invert_indicators({})
        assert result == {}
