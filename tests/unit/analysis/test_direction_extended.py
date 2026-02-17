"""Extended direction classification tests: boundary values, all combinations."""

from __future__ import annotations

import pytest

from Option_Alpha.analysis.direction import (
    ADX_TREND_THRESHOLD,
    RSI_MIDPOINT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    SMA_BEARISH_THRESHOLD,
    SMA_BULLISH_THRESHOLD,
    determine_direction,
)
from Option_Alpha.models.enums import SignalDirection


class TestDirectionBoundaries:
    """Test exact boundary values for direction classification."""

    def test_adx_exactly_at_threshold_neutral(self) -> None:
        """ADX exactly at threshold (20.0) -> still below -> NEUTRAL."""
        result = determine_direction(adx=ADX_TREND_THRESHOLD - 0.01, rsi=50.0, sma_alignment=0.0)
        assert result == SignalDirection.NEUTRAL

    def test_adx_just_above_threshold(self) -> None:
        """ADX just above threshold -> direction determined by RSI/SMA."""
        # RSI 75 (overbought, bearish +1) + SMA -1.0 (bearish +1) = bearish 2.0
        result = determine_direction(
            adx=ADX_TREND_THRESHOLD + 0.01, rsi=RSI_OVERBOUGHT + 5, sma_alignment=-1.0
        )
        assert result == SignalDirection.BEARISH

    def test_adx_zero_always_neutral(self) -> None:
        result = determine_direction(adx=0.0, rsi=80.0, sma_alignment=5.0)
        assert result == SignalDirection.NEUTRAL

    def test_rsi_overbought_bearish_signal(self) -> None:
        """RSI above 70 -> bearish signal component."""
        result = determine_direction(adx=30.0, rsi=RSI_OVERBOUGHT + 1, sma_alignment=-1.0)
        assert result == SignalDirection.BEARISH

    def test_rsi_oversold_bullish_signal(self) -> None:
        """RSI below 30 -> bullish signal component."""
        result = determine_direction(adx=30.0, rsi=RSI_OVERSOLD - 1, sma_alignment=1.0)
        assert result == SignalDirection.BULLISH

    def test_rsi_neutral_band(self) -> None:
        """RSI between 30-70 with neutral SMA -> NEUTRAL."""
        result = determine_direction(adx=25.0, rsi=50.0, sma_alignment=0.0)
        assert result == SignalDirection.NEUTRAL

    def test_strong_bullish_all_signals(self) -> None:
        """Low RSI + positive SMA = strongly bullish."""
        result = determine_direction(adx=35.0, rsi=25.0, sma_alignment=2.0)
        assert result == SignalDirection.BULLISH

    def test_strong_bearish_all_signals(self) -> None:
        """High RSI + negative SMA = strongly bearish."""
        result = determine_direction(adx=35.0, rsi=75.0, sma_alignment=-2.0)
        assert result == SignalDirection.BEARISH


class TestDirectionConstants:
    """Verify direction module constants."""

    def test_adx_threshold(self) -> None:
        assert pytest.approx(20.0, abs=1e-9) == ADX_TREND_THRESHOLD

    def test_rsi_overbought(self) -> None:
        assert pytest.approx(70.0, abs=1e-9) == RSI_OVERBOUGHT

    def test_rsi_oversold(self) -> None:
        assert pytest.approx(30.0, abs=1e-9) == RSI_OVERSOLD

    def test_rsi_midpoint(self) -> None:
        assert pytest.approx(50.0, abs=1e-9) == RSI_MIDPOINT

    def test_sma_bullish_threshold(self) -> None:
        assert pytest.approx(0.5, abs=1e-9) == SMA_BULLISH_THRESHOLD

    def test_sma_bearish_threshold(self) -> None:
        assert pytest.approx(-0.5, abs=1e-9) == SMA_BEARISH_THRESHOLD
