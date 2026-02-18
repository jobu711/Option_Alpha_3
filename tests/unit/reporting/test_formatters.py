"""Tests for shared formatting utilities.

Covers Greek impact formatting, indicator category grouping,
conflict detection, and report filename generation.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from Option_Alpha.models.enums import GreeksSource, OptionType
from Option_Alpha.models.options import OptionGreeks
from Option_Alpha.reporting.formatters import (
    build_report_filename,
    detect_conflicting_signals,
    format_greek_impact,
    group_indicators_by_category,
)

# ---------------------------------------------------------------------------
# format_greek_impact
# ---------------------------------------------------------------------------


class TestFormatGreekImpact:
    """Tests for format_greek_impact()."""

    def test_returns_five_tuples(self, sample_option_greeks: OptionGreeks) -> None:
        """Must return exactly 5 tuples (one per Greek)."""
        result = format_greek_impact(sample_option_greeks, GreeksSource.MARKET)
        assert len(result) == 5

    def test_tuple_structure(self, sample_option_greeks: OptionGreeks) -> None:
        """Each result element must be a 3-tuple of strings."""
        result = format_greek_impact(sample_option_greeks, GreeksSource.MARKET)
        for name, value, interpretation in result:
            assert isinstance(name, str)
            assert isinstance(value, str)
            assert isinstance(interpretation, str)

    def test_greek_names_in_order(self, sample_option_greeks: OptionGreeks) -> None:
        """Tuples must be ordered: Delta, Gamma, Theta, Vega, Rho."""
        result = format_greek_impact(sample_option_greeks, GreeksSource.MARKET)
        names = [r[0] for r in result]
        assert names == ["Delta", "Gamma", "Theta", "Vega", "Rho"]

    def test_theta_dollar_impact(self, sample_option_greeks: OptionGreeks) -> None:
        """Theta interpretation must show dollar impact (theta * 100)."""
        result = format_greek_impact(sample_option_greeks, None)
        theta_row = result[2]
        # theta = -0.08, dollar impact = abs(-0.08 * 100) = $8
        assert "$8" in theta_row[2]
        assert "day" in theta_row[2].lower()

    def test_vega_dollar_impact(self, sample_option_greeks: OptionGreeks) -> None:
        """Vega interpretation must show dollar impact (vega * 100)."""
        result = format_greek_impact(sample_option_greeks, None)
        vega_row = result[3]
        # vega = 0.12, dollar impact = 0.12 * 100 = $12
        assert "$12" in vega_row[2]
        assert "IV" in vega_row[2]

    def test_delta_dollar_impact(self, sample_option_greeks: OptionGreeks) -> None:
        """Delta interpretation must show dollar P&L per $1 move."""
        result = format_greek_impact(sample_option_greeks, None)
        delta_row = result[0]
        # delta = 0.45, dollar impact = abs(0.45) * 100 = $45
        assert "$45" in delta_row[2]
        assert "$1 move" in delta_row[2]

    def test_source_label_included_when_provided(self, sample_option_greeks: OptionGreeks) -> None:
        """When a source is provided, the label should appear in delta interpretation."""
        result = format_greek_impact(sample_option_greeks, GreeksSource.MARKET)
        delta_interp = result[0][2]
        assert "(market)" in delta_interp

    def test_source_label_bsm(self, sample_option_greeks: OptionGreeks) -> None:
        """BSM source should be flagged as (calculated)."""
        result = format_greek_impact(sample_option_greeks, GreeksSource.CALCULATED)
        delta_interp = result[0][2]
        assert "(calculated)" in delta_interp

    def test_source_label_none(self, sample_option_greeks: OptionGreeks) -> None:
        """When source is None, no parenthetical label appears."""
        result = format_greek_impact(sample_option_greeks, None)
        delta_interp = result[0][2]
        assert "(market)" not in delta_interp
        assert "(calculated)" not in delta_interp

    def test_negative_theta_shows_losing(self) -> None:
        """Negative theta should use 'Losing' language."""
        greeks = OptionGreeks(delta=0.5, gamma=0.03, theta=-0.10, vega=0.15, rho=0.01)
        result = format_greek_impact(greeks, None)
        theta_interp = result[2][2]
        assert "Losing" in theta_interp

    def test_positive_theta_shows_gaining(self) -> None:
        """Positive theta (short position) should use 'Gaining' language."""
        greeks = OptionGreeks(delta=-0.5, gamma=0.03, theta=0.05, vega=0.15, rho=0.01)
        result = format_greek_impact(greeks, None)
        theta_interp = result[2][2]
        assert "Gaining" in theta_interp

    def test_rho_minimal_for_small_value(self) -> None:
        """Rho < 0.05 should show 'Minimal interest rate sensitivity'."""
        greeks = OptionGreeks(delta=0.45, gamma=0.03, theta=-0.08, vega=0.12, rho=0.01)
        result = format_greek_impact(greeks, None)
        rho_interp = result[4][2]
        assert "Minimal" in rho_interp

    def test_rho_dollar_impact_for_large_value(self) -> None:
        """Rho >= 0.05 should show dollar impact."""
        greeks = OptionGreeks(delta=0.45, gamma=0.03, theta=-0.08, vega=0.12, rho=0.10)
        result = format_greek_impact(greeks, None)
        rho_interp = result[4][2]
        assert "$10" in rho_interp
        assert "rate" in rho_interp.lower()

    def test_formatted_value_precision(self, sample_option_greeks: OptionGreeks) -> None:
        """Formatted values should use 3 decimal places."""
        result = format_greek_impact(sample_option_greeks, None)
        # delta = 0.45 -> "0.450"
        assert result[0][1] == "0.450"
        # gamma = 0.05 -> "0.050"
        assert result[1][1] == "0.050"


# ---------------------------------------------------------------------------
# group_indicators_by_category
# ---------------------------------------------------------------------------


class TestGroupIndicatorsByCategory:
    """Tests for group_indicators_by_category()."""

    def test_groups_trend_indicators(self) -> None:
        """ADX and ROC should be grouped under Trend."""
        signals = {"adx": 30.0, "roc": 5.2}
        result = group_indicators_by_category(signals)
        assert "Trend" in result
        names = [item[0] for item in result["Trend"]]
        assert "adx" in names
        assert "roc" in names

    def test_groups_momentum_indicators(self) -> None:
        """RSI and stoch_rsi should be grouped under Momentum."""
        signals = {"rsi": 55.0, "stoch_rsi": 60.0}
        result = group_indicators_by_category(signals)
        assert "Momentum" in result
        names = [item[0] for item in result["Momentum"]]
        assert "rsi" in names
        assert "stoch_rsi" in names

    def test_groups_volatility_indicators(self) -> None:
        """IV rank, bb_width should be grouped under Volatility."""
        signals = {"iv_rank": 72.0, "bb_width": 45.0}
        result = group_indicators_by_category(signals)
        assert "Volatility" in result
        names = [item[0] for item in result["Volatility"]]
        assert "iv_rank" in names
        assert "bb_width" in names

    def test_groups_volume_indicators(self) -> None:
        """obv_trend and put_call_ratio should be grouped under Volume."""
        signals = {"obv_trend": 1.5, "put_call_ratio": 0.85}
        result = group_indicators_by_category(signals)
        assert "Volume" in result
        names = [item[0] for item in result["Volume"]]
        assert "obv_trend" in names
        assert "put_call_ratio" in names

    def test_empty_signals_returns_empty(self) -> None:
        """Empty signals dict should return empty categories."""
        result = group_indicators_by_category({})
        assert result == {}

    def test_unknown_indicator_goes_to_other(self) -> None:
        """Indicators not in any known category should go to Other."""
        signals = {"unknown_indicator": 42.0}
        result = group_indicators_by_category(signals)
        assert "Other" in result
        assert result["Other"][0][0] == "unknown_indicator"

    def test_interpretation_added_for_rsi(self) -> None:
        """RSI indicators should have interpretation strings."""
        signals = {"rsi": 75.0}
        result = group_indicators_by_category(signals)
        rsi_item = result["Momentum"][0]
        assert rsi_item[2] == "overbought"

    def test_interpretation_for_rsi_oversold(self) -> None:
        """RSI below 30 should interpret as oversold."""
        signals = {"rsi": 25.0}
        result = group_indicators_by_category(signals)
        rsi_item = result["Momentum"][0]
        assert rsi_item[2] == "oversold"

    def test_interpretation_for_rsi_neutral(self) -> None:
        """RSI between 30 and 70 should interpret as neutral."""
        signals = {"rsi": 50.0}
        result = group_indicators_by_category(signals)
        rsi_item = result["Momentum"][0]
        assert rsi_item[2] == "neutral"

    def test_interpretation_for_adx_strong(self) -> None:
        """ADX above 25 should interpret as strong trend."""
        signals = {"adx": 30.0}
        result = group_indicators_by_category(signals)
        adx_item = result["Trend"][0]
        assert adx_item[2] == "strong trend"

    def test_interpretation_for_adx_weak(self) -> None:
        """ADX below 25 should interpret as weak trend."""
        signals = {"adx": 20.0}
        result = group_indicators_by_category(signals)
        adx_item = result["Trend"][0]
        assert adx_item[2] == "weak trend"

    def test_interpretation_for_iv_rank_high(self) -> None:
        """IV rank above 75 should interpret as high."""
        signals = {"iv_rank": 80.0}
        result = group_indicators_by_category(signals)
        item = result["Volatility"][0]
        assert item[2] == "high"

    def test_interpretation_for_iv_rank_elevated(self) -> None:
        """IV rank between 50 and 75 should interpret as elevated."""
        signals = {"iv_rank": 60.0}
        result = group_indicators_by_category(signals)
        item = result["Volatility"][0]
        assert item[2] == "elevated"

    def test_interpretation_for_iv_rank_low(self) -> None:
        """IV rank below 50 should interpret as low."""
        signals = {"iv_rank": 30.0}
        result = group_indicators_by_category(signals)
        item = result["Volatility"][0]
        assert item[2] == "low"

    def test_interpretation_for_put_call_bullish(self) -> None:
        """Put/call ratio below 0.7 should interpret as bullish."""
        signals = {"put_call_ratio": 0.5}
        result = group_indicators_by_category(signals)
        item = result["Volume"][0]
        assert item[2] == "bullish"

    def test_interpretation_for_put_call_bearish(self) -> None:
        """Put/call ratio above 1.3 should interpret as bearish."""
        signals = {"put_call_ratio": 1.5}
        result = group_indicators_by_category(signals)
        item = result["Volume"][0]
        assert item[2] == "bearish"

    def test_only_nonempty_categories_returned(self) -> None:
        """Categories with no indicators should not appear."""
        signals = {"rsi": 55.0}  # Only momentum
        result = group_indicators_by_category(signals)
        assert "Trend" not in result
        assert "Volatility" not in result
        assert "Volume" not in result
        assert "Momentum" in result

    def test_tuple_values_match_input(self) -> None:
        """The value in each tuple must match the input signal value."""
        signals = {"rsi": 55.0, "adx": 30.0}
        result = group_indicators_by_category(signals)
        rsi_item = result["Momentum"][0]
        assert rsi_item[1] == pytest.approx(55.0)
        adx_item = result["Trend"][0]
        assert adx_item[1] == pytest.approx(30.0)

    def test_sorted_output_within_category(self) -> None:
        """Indicators should be sorted alphabetically within category."""
        signals = {"williams_r": -50.0, "rsi": 55.0, "stoch_rsi": 60.0}
        result = group_indicators_by_category(signals)
        names = [item[0] for item in result["Momentum"]]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# detect_conflicting_signals
# ---------------------------------------------------------------------------


class TestDetectConflictingSignals:
    """Tests for detect_conflicting_signals()."""

    def test_no_conflicts_when_empty(self) -> None:
        """Empty signals dict should return no conflicts."""
        result = detect_conflicting_signals({})
        assert result == []

    def test_no_conflicts_when_no_contradiction(self) -> None:
        """Non-conflicting signals should return empty list."""
        signals = {"rsi": 55.0, "adx": 20.0}
        result = detect_conflicting_signals(signals)
        assert result == []

    def test_rsi_overbought_with_strong_adx(self) -> None:
        """RSI overbought + strong ADX should be flagged."""
        signals = {"rsi": 75.0, "adx": 30.0}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "overbought" in result[0].lower()
        assert "trend" in result[0].lower()

    def test_rsi_oversold_with_bearish_sma(self) -> None:
        """RSI oversold + bearish SMA alignment should detect value trap."""
        signals = {"rsi": 25.0, "sma_alignment": -0.8}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "value trap" in result[0].lower()

    def test_rsi_overbought_stoch_rsi_oversold(self) -> None:
        """RSI overbought + Stochastic RSI oversold should detect mixed momentum."""
        signals = {"rsi": 75.0, "stoch_rsi": 15.0}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "mixed momentum" in result[0].lower()

    def test_rsi_oversold_stoch_rsi_overbought(self) -> None:
        """RSI oversold + Stochastic RSI overbought should detect mixed momentum."""
        signals = {"rsi": 25.0, "stoch_rsi": 85.0}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "mixed momentum" in result[0].lower()

    def test_iv_rank_high_put_call_bullish(self) -> None:
        """IV rank high + bullish put/call should detect expensive options contradiction."""
        signals = {"iv_rank": 80.0, "put_call_ratio": 0.5}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "expensive" in result[0].lower()

    def test_obv_declining_rsi_overbought(self) -> None:
        """OBV declining while RSI overbought should detect bearish volume divergence."""
        signals = {"obv_trend": -1.0, "rsi": 75.0}
        result = detect_conflicting_signals(signals)
        assert len(result) == 1
        assert "divergence" in result[0].lower()

    def test_multiple_conflicts_detected(self) -> None:
        """Multiple conflicts can fire simultaneously."""
        signals = {
            "rsi": 75.0,
            "adx": 30.0,
            "stoch_rsi": 15.0,
            "obv_trend": -1.0,
        }
        result = detect_conflicting_signals(signals)
        # rsi+adx, rsi+stoch_rsi, obv+rsi = 3 conflicts
        assert len(result) == 3

    def test_partial_indicator_data(self) -> None:
        """Missing indicators should not cause errors."""
        signals = {"rsi": 55.0}  # Only RSI, no ADX
        result = detect_conflicting_signals(signals)
        assert result == []

    def test_returns_list_of_strings(self) -> None:
        """All conflict descriptions must be strings."""
        signals = {"rsi": 75.0, "adx": 30.0}
        result = detect_conflicting_signals(signals)
        for item in result:
            assert isinstance(item, str)


# ---------------------------------------------------------------------------
# build_report_filename
# ---------------------------------------------------------------------------


class _FakeDate(datetime.date):
    """A date subclass that overrides today() for deterministic tests."""

    _frozen: datetime.date | None = None

    @classmethod
    def today(cls) -> datetime.date:  # type: ignore[override]
        if cls._frozen is not None:
            return cls._frozen
        return super().today()


class TestBuildReportFilename:
    """Tests for build_report_filename()."""

    def _patch_today(self, year: int, month: int, day: int) -> patch:
        """Return a context-manager that freezes datetime.date.today()."""
        frozen = datetime.date(year, month, day)

        class Frozen(_FakeDate):
            _frozen = frozen

        return patch("Option_Alpha.reporting.formatters.datetime.date", Frozen)

    def test_call_option_format(self) -> None:
        """Call option should use 'C' suffix."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="AAPL",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
            )
        assert result == "AAPL_2025-03-15_185C_analysis.md"

    def test_put_option_format(self) -> None:
        """Put option should use 'P' suffix."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="TSLA",
                strike=Decimal("250.50"),
                option_type=OptionType.PUT,
            )
        assert result == "TSLA_2025-03-15_250.5P_analysis.md"

    def test_includes_current_date(self) -> None:
        """Filename must contain today's date."""
        with self._patch_today(2025, 6, 20):
            result = build_report_filename(
                ticker="SPY",
                strike=Decimal("450"),
                option_type=OptionType.CALL,
            )
        assert "2025-06-20" in result

    def test_custom_extension(self) -> None:
        """Custom extension should replace .md."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="AAPL",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
                ext="html",
            )
        assert result.endswith("_analysis.html")

    def test_ticker_is_uppercased(self) -> None:
        """Ticker should be uppercased in the filename."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="aapl",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
            )
        assert result.startswith("AAPL_")

    def test_strike_trailing_zeros_stripped(self) -> None:
        """Strike like 185.00 should be rendered as 185."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="AAPL",
                strike=Decimal("185.00"),
                option_type=OptionType.CALL,
            )
        assert "185C" in result
        assert "185.00" not in result

    def test_strike_zero_does_not_produce_empty_string(self) -> None:
        """Decimal('0') must produce '0' in filename, not empty string."""
        with self._patch_today(2025, 3, 15):
            result = build_report_filename(
                ticker="AAPL",
                strike=Decimal("0"),
                option_type=OptionType.CALL,
            )
        assert "_0C_" in result
