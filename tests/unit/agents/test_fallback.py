"""Tests for the data-driven fallback thesis builder.

Verifies direction mapping, conviction clamping, risk factor generation,
model_used string, and disclaimer content -- all without any LLM calls.
"""

from __future__ import annotations

import pytest

from Option_Alpha.agents.fallback import build_fallback_thesis
from Option_Alpha.models import SignalDirection, TradeThesis

# ---------------------------------------------------------------------------
# Direction & conviction
# ---------------------------------------------------------------------------


class TestFallbackDirection:
    """Tests for direction determination and conviction scoring."""

    @pytest.mark.asyncio()
    async def test_strong_bullish(self) -> None:
        """score=78, BULLISH -> direction=BULLISH, conviction ~0.78."""
        thesis = await build_fallback_thesis(
            "AAPL", 78.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.direction == SignalDirection.BULLISH
        assert thesis.conviction == pytest.approx(0.78, abs=0.01)

    @pytest.mark.asyncio()
    async def test_moderate_bullish(self) -> None:
        """score=55, BULLISH -> direction=BULLISH."""
        thesis = await build_fallback_thesis(
            "AAPL", 55.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.direction == SignalDirection.BULLISH

    @pytest.mark.asyncio()
    async def test_strong_bearish(self) -> None:
        """score=75, BEARISH -> direction=BEARISH."""
        thesis = await build_fallback_thesis(
            "AAPL", 75.0, SignalDirection.BEARISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.direction == SignalDirection.BEARISH

    @pytest.mark.asyncio()
    async def test_moderate_bearish(self) -> None:
        """score=55, BEARISH -> direction=BEARISH."""
        thesis = await build_fallback_thesis(
            "AAPL", 55.0, SignalDirection.BEARISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.direction == SignalDirection.BEARISH

    @pytest.mark.asyncio()
    async def test_neutral_low_score(self) -> None:
        """score=30, BULLISH -> direction=NEUTRAL (below moderate threshold)."""
        thesis = await build_fallback_thesis(
            "AAPL", 30.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.direction == SignalDirection.NEUTRAL


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestFallbackMetadata:
    """Tests for model_used, tokens, and disclaimer."""

    @pytest.mark.asyncio()
    async def test_model_used_is_fallback(self) -> None:
        """model_used is always 'data-driven-fallback'."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_tokens_zero(self) -> None:
        """total_tokens=0 and duration_ms=0 for fallback."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.total_tokens == 0
        assert thesis.duration_ms == 0

    @pytest.mark.asyncio()
    async def test_disclaimer_present(self) -> None:
        """disclaimer contains '[DATA-DRIVEN'."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert "[DATA-DRIVEN" in thesis.disclaimer


# ---------------------------------------------------------------------------
# Risk factors
# ---------------------------------------------------------------------------


class TestFallbackRiskFactors:
    """Tests for risk factor generation from indicator values."""

    @pytest.mark.asyncio()
    async def test_risk_factors_rsi_overbought(self) -> None:
        """rsi=75 -> 'RSI overbought' in risk_factors."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=75.0
        )
        assert any("RSI overbought" in f for f in thesis.risk_factors)

    @pytest.mark.asyncio()
    async def test_risk_factors_iv_high(self) -> None:
        """iv_rank=80 -> 'IV rank elevated' in risk_factors."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=80.0, rsi_14=55.0
        )
        assert any("IV rank elevated" in f for f in thesis.risk_factors)

    @pytest.mark.asyncio()
    async def test_conviction_clamped_above(self) -> None:
        """score=150 -> conviction clamped to 1.0."""
        thesis = await build_fallback_thesis(
            "AAPL", 150.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.conviction == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_conviction_clamped_below(self) -> None:
        """score=-10 -> conviction clamped to 0.0."""
        thesis = await build_fallback_thesis(
            "AAPL", -10.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert thesis.conviction == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio()
    async def test_returns_trade_thesis(self) -> None:
        """Fallback always returns a TradeThesis instance."""
        thesis = await build_fallback_thesis(
            "AAPL", 60.0, SignalDirection.BULLISH, iv_rank=40.0, rsi_14=55.0
        )
        assert isinstance(thesis, TradeThesis)
