"""Tests for the MarketContext -> flat text context builder.

Verifies IV rank interpretation, RSI labels, decimal formatting,
earnings handling, and absence of JSON/dict syntax in output.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from Option_Alpha.agents.context_builder import build_context_text
from Option_Alpha.models import MarketContext

# ---------------------------------------------------------------------------
# Helper to build a MarketContext with overrides
# ---------------------------------------------------------------------------


def _make_context(**overrides: object) -> MarketContext:
    """Build a realistic MarketContext, overriding specified fields."""
    defaults = {
        "ticker": "AAPL",
        "current_price": Decimal("186.75"),
        "price_52w_high": Decimal("199.62"),
        "price_52w_low": Decimal("164.08"),
        "iv_rank": 45.2,
        "iv_percentile": 52.8,
        "atm_iv_30d": 0.28,
        "rsi_14": 55.3,
        "macd_signal": "neutral",
        "put_call_ratio": 0.85,
        "next_earnings": datetime.date(2025, 4, 24),
        "dte_target": 37,
        "target_strike": Decimal("185.00"),
        "target_delta": 0.45,
        "sector": "Technology",
        "data_timestamp": datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    }
    defaults.update(overrides)
    return MarketContext(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBuildContextText:
    """Tests for build_context_text() output formatting and labels."""

    def test_basic_output_format(self, sample_market_context: MarketContext) -> None:
        """Output contains all expected key labels."""
        text = build_context_text(sample_market_context)

        expected_keys = [
            "Ticker:",
            "Current Price:",
            "52-Week Range:",
            "IV Rank:",
            "IV Percentile:",
            "ATM IV (30 DTE):",
            "RSI(14):",
            "MACD Signal:",
            "Put/Call Ratio:",
            "Next Earnings:",
            "DTE Target:",
            "Target Strike:",
            "Target Delta:",
            "Sector:",
            "Data as of:",
        ]
        for key in expected_keys:
            assert key in text, f"Missing key: {key}"

    def test_iv_rank_interpretation_low(self) -> None:
        """iv_rank=20 -> '(low)' in output."""
        ctx = _make_context(iv_rank=20.0)
        text = build_context_text(ctx)
        assert "(low)" in text

    def test_iv_rank_interpretation_moderate(self) -> None:
        """iv_rank=40 -> '(moderate)' in output."""
        ctx = _make_context(iv_rank=40.0)
        text = build_context_text(ctx)
        assert "(moderate)" in text

    def test_iv_rank_interpretation_high(self) -> None:
        """iv_rank=60 -> '(high)' in output."""
        ctx = _make_context(iv_rank=60.0)
        text = build_context_text(ctx)
        assert "(high)" in text

    def test_iv_rank_interpretation_very_high(self) -> None:
        """iv_rank=80 -> '(very high)' in output."""
        ctx = _make_context(iv_rank=80.0)
        text = build_context_text(ctx)
        assert "(very high)" in text

    def test_rsi_interpretation_oversold(self) -> None:
        """rsi_14=25 -> '(oversold)' in output."""
        ctx = _make_context(rsi_14=25.0)
        text = build_context_text(ctx)
        assert "(oversold)" in text

    def test_rsi_interpretation_overbought(self) -> None:
        """rsi_14=75 -> '(overbought)' in output."""
        ctx = _make_context(rsi_14=75.0)
        text = build_context_text(ctx)
        assert "(overbought)" in text

    def test_earnings_none(self) -> None:
        """next_earnings=None -> 'N/A' in output."""
        ctx = _make_context(next_earnings=None)
        text = build_context_text(ctx)
        assert "N/A" in text

    def test_decimal_formatting(self) -> None:
        """Prices show $ prefix and 2 decimal places."""
        ctx = _make_context(current_price=Decimal("186.50"))
        text = build_context_text(ctx)
        assert "$186.50" in text

    def test_no_json_in_output(self, sample_market_context: MarketContext) -> None:
        """Output is flat text -- no JSON braces."""
        text = build_context_text(sample_market_context)
        assert "{" not in text
        assert "}" not in text
