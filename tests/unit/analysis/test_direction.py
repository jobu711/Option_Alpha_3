"""Tests for direction signal classification.

Verifies determine_direction() scoring logic across ADX thresholds,
RSI zones, SMA alignment boundaries, and mixed-signal scenarios.
"""

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


class TestDetermineDirectionADXGating:
    """ADX below threshold always returns NEUTRAL regardless of other signals."""

    @pytest.mark.parametrize(
        ("adx", "rsi", "sma_alignment"),
        [
            (0.0, 20.0, 1.0),  # strongly bullish signals, but no trend
            (10.0, 80.0, -1.0),  # strongly bearish signals, but no trend
            (14.9, 50.0, 0.0),  # just below threshold, neutral signals
            (14.99, 25.0, 0.8),  # barely below threshold, bullish signals
        ],
        ids=[
            "adx_zero_bullish_signals",
            "adx_low_bearish_signals",
            "adx_just_below_threshold",
            "adx_barely_below_threshold",
        ],
    )
    def test_adx_below_threshold_returns_neutral(
        self,
        adx: float,
        rsi: float,
        sma_alignment: float,
    ) -> None:
        result = determine_direction(adx, rsi, sma_alignment)
        assert result == SignalDirection.NEUTRAL

    def test_adx_exactly_at_threshold_is_not_neutral(self) -> None:
        """ADX == 15.0 is NOT below threshold, so scoring proceeds."""
        # RSI < 30 (bullish +1) and SMA > 0.5 (bullish +1) -> BULLISH
        result = determine_direction(adx=ADX_TREND_THRESHOLD, rsi=25.0, sma_alignment=0.8)
        assert result == SignalDirection.BULLISH


class TestDetermineDirectionBullish:
    """Bullish direction when bullish score exceeds bearish score."""

    @pytest.mark.parametrize(
        ("adx", "rsi", "sma_alignment", "description"),
        [
            (25.0, 20.0, 0.8, "RSI oversold + SMA bullish"),
            (30.0, 15.0, 0.0, "RSI strongly oversold, SMA neutral"),
            (25.0, 40.0, 0.9, "RSI mild bullish + SMA bullish"),
            (25.0, 29.99, 0.1, "RSI just below oversold, SMA in neutral zone"),
        ],
        ids=[
            "strong_bullish_both",
            "rsi_oversold_only",
            "mild_rsi_plus_sma",
            "rsi_oversold_sma_neutral",
        ],
    )
    def test_bullish_scenarios(
        self,
        adx: float,
        rsi: float,
        sma_alignment: float,
        description: str,
    ) -> None:
        result = determine_direction(adx, rsi, sma_alignment)
        assert result == SignalDirection.BULLISH, description


class TestDetermineDirectionBearish:
    """Bearish direction when bearish score exceeds bullish score."""

    @pytest.mark.parametrize(
        ("adx", "rsi", "sma_alignment", "description"),
        [
            (25.0, 80.0, -0.8, "RSI overbought + SMA bearish"),
            (30.0, 85.0, 0.0, "RSI strongly overbought, SMA neutral"),
            (25.0, 60.0, -0.9, "RSI mild bearish + SMA bearish"),
            (25.0, 70.01, -0.1, "RSI just above overbought, SMA in neutral zone"),
        ],
        ids=[
            "strong_bearish_both",
            "rsi_overbought_only",
            "mild_rsi_plus_sma",
            "rsi_overbought_sma_neutral",
        ],
    )
    def test_bearish_scenarios(
        self,
        adx: float,
        rsi: float,
        sma_alignment: float,
        description: str,
    ) -> None:
        result = determine_direction(adx, rsi, sma_alignment)
        assert result == SignalDirection.BEARISH, description


class TestDetermineDirectionNeutral:
    """NEUTRAL when ADX passes but bullish_score == bearish_score."""

    @pytest.mark.parametrize(
        ("adx", "rsi", "sma_alignment", "description"),
        [
            (25.0, 50.0, 0.0, "RSI at midpoint + SMA neutral -> both scores 0"),
            (25.0, 50.0, 0.3, "RSI at midpoint + SMA in neutral band -> both scores 0"),
            (25.0, 50.0, -0.3, "RSI at midpoint + SMA in neutral band -> both scores 0"),
        ],
        ids=[
            "all_neutral_zero_scores",
            "rsi_midpoint_sma_positive_neutral",
            "rsi_midpoint_sma_negative_neutral",
        ],
    )
    def test_neutral_balanced_signals(
        self,
        adx: float,
        rsi: float,
        sma_alignment: float,
        description: str,
    ) -> None:
        result = determine_direction(adx, rsi, sma_alignment)
        assert result == SignalDirection.NEUTRAL, description

    def test_mild_bullish_rsi_vs_strong_bearish_sma_is_bearish(self) -> None:
        """Mild bullish RSI (+0.5) vs strong bearish SMA (+1.0) -> BEARISH, not NEUTRAL."""
        result = determine_direction(adx=25.0, rsi=40.0, sma_alignment=-0.8)
        assert result == SignalDirection.BEARISH

    def test_mild_bearish_rsi_vs_strong_bullish_sma_is_bullish(self) -> None:
        """Mild bearish RSI (+0.5) vs strong bullish SMA (+1.0) -> BULLISH, not NEUTRAL."""
        result = determine_direction(adx=25.0, rsi=60.0, sma_alignment=0.8)
        assert result == SignalDirection.BULLISH


class TestDetermineDirectionBoundaryValues:
    """Boundary value tests for RSI and SMA thresholds."""

    def test_rsi_exactly_at_oversold_boundary(self) -> None:
        """RSI == 30.0 is NOT < 30, so it enters the mild bullish zone (30-50)."""
        result = determine_direction(adx=25.0, rsi=RSI_OVERSOLD, sma_alignment=0.0)
        # RSI == 30 -> mild bullish +0.5, bearish 0 -> BULLISH
        assert result == SignalDirection.BULLISH

    def test_rsi_exactly_at_overbought_boundary(self) -> None:
        """RSI == 70.0 is NOT > 70, so it enters the mild bearish zone (50-70)."""
        result = determine_direction(adx=25.0, rsi=RSI_OVERBOUGHT, sma_alignment=0.0)
        # RSI == 70 -> mild bearish +0.5, bullish 0 -> BEARISH
        assert result == SignalDirection.BEARISH

    def test_rsi_exactly_at_midpoint(self) -> None:
        """RSI == 50.0: not < 50 and not > 50, so no RSI signal at all."""
        result = determine_direction(adx=25.0, rsi=RSI_MIDPOINT, sma_alignment=0.0)
        # RSI == 50 -> no signal, SMA neutral -> no signal -> NEUTRAL
        assert result == SignalDirection.NEUTRAL

    def test_rsi_just_above_midpoint_is_mild_bearish(self) -> None:
        """RSI = 50.01 > 50 enters the mild bearish zone."""
        result = determine_direction(adx=25.0, rsi=50.01, sma_alignment=0.0)
        # RSI 50.01 -> mild bearish +0.5, bullish 0 -> BEARISH
        assert result == SignalDirection.BEARISH

    def test_rsi_just_below_midpoint_is_mild_bullish(self) -> None:
        """RSI = 49.99 < 50 enters the mild bullish zone."""
        result = determine_direction(adx=25.0, rsi=49.99, sma_alignment=0.0)
        # RSI 49.99 -> mild bullish +0.5, bearish 0 -> BULLISH
        assert result == SignalDirection.BULLISH

    def test_sma_exactly_at_bullish_threshold(self) -> None:
        """SMA == 0.5 is NOT > 0.5, so no bullish SMA signal."""
        # Use RSI that produces a clear bearish signal to avoid NEUTRAL
        result = determine_direction(adx=25.0, rsi=75.0, sma_alignment=SMA_BULLISH_THRESHOLD)
        # RSI 75 -> bearish +1.0, SMA == 0.5 -> no signal -> BEARISH
        assert result == SignalDirection.BEARISH

    def test_sma_exactly_at_bearish_threshold(self) -> None:
        """SMA == -0.5 is NOT < -0.5, so no bearish SMA signal."""
        # Use RSI that produces a clear bullish signal to avoid NEUTRAL
        result = determine_direction(adx=25.0, rsi=25.0, sma_alignment=SMA_BEARISH_THRESHOLD)
        # RSI 25 -> bullish +1.0, SMA == -0.5 -> no signal -> BULLISH
        assert result == SignalDirection.BULLISH

    def test_sma_just_above_bullish_threshold(self) -> None:
        """SMA = 0.51 > 0.5 triggers bullish SMA signal."""
        result = determine_direction(adx=25.0, rsi=RSI_MIDPOINT, sma_alignment=0.51)
        # RSI == 50 -> no signal, SMA -> bullish +1.0
        # bullish 1.0 > bearish 0 -> BULLISH
        assert result == SignalDirection.BULLISH

    def test_sma_just_below_bearish_threshold(self) -> None:
        """SMA = -0.51 < -0.5 triggers bearish SMA signal."""
        result = determine_direction(adx=25.0, rsi=RSI_MIDPOINT, sma_alignment=-0.51)
        # RSI == 50 -> no signal, SMA -> bearish +1.0
        # bearish 1.0 > bullish 0 -> BEARISH
        assert result == SignalDirection.BEARISH


class TestDetermineDirectionConflictingSignals:
    """When RSI and SMA signals conflict, the stronger aggregate wins."""

    def test_strong_rsi_bullish_vs_strong_sma_bearish(self) -> None:
        """RSI < 30 (+1 bull) vs SMA < -0.5 (+1 bear) -> tie -> SMA tiebreaker -> BEARISH."""
        result = determine_direction(adx=25.0, rsi=20.0, sma_alignment=-0.8)
        assert result == SignalDirection.BEARISH

    def test_strong_rsi_bearish_vs_strong_sma_bullish(self) -> None:
        """RSI > 70 (+1 bear) vs SMA > 0.5 (+1 bull) -> tie -> SMA tiebreaker -> BULLISH."""
        result = determine_direction(adx=25.0, rsi=80.0, sma_alignment=0.8)
        assert result == SignalDirection.BULLISH

    def test_mild_rsi_bullish_vs_strong_sma_bearish(self) -> None:
        """RSI in (30,50) (+0.5 bull) vs SMA < -0.5 (+1 bear) -> BEARISH."""
        result = determine_direction(adx=25.0, rsi=40.0, sma_alignment=-0.8)
        assert result == SignalDirection.BEARISH

    def test_strong_rsi_bullish_vs_no_sma_signal(self) -> None:
        """RSI < 30 (+1 bull) vs SMA in neutral zone -> BULLISH."""
        result = determine_direction(adx=25.0, rsi=20.0, sma_alignment=0.0)
        assert result == SignalDirection.BULLISH

    def test_tiebreaker_uses_sma_sign_not_threshold(self) -> None:
        """Tiebreaker resolves via SMA sign: positive SMA -> BULLISH on tie."""
        # RSI > 70 (+1 bear) + SMA > 0.5 (+1 bull) -> tie at 1.0 each
        # SMA alignment = 0.8 > 0 -> tiebreaker selects BULLISH
        result = determine_direction(adx=25.0, rsi=80.0, sma_alignment=0.8)
        assert result == SignalDirection.BULLISH
        # Confirm the inverse: negative SMA -> BEARISH on tie
        result2 = determine_direction(adx=25.0, rsi=20.0, sma_alignment=-0.8)
        assert result2 == SignalDirection.BEARISH

    def test_zero_scores_tie_returns_neutral(self) -> None:
        """Both scores zero (RSI at midpoint + SMA neutral) -> no tiebreaker -> NEUTRAL."""
        result = determine_direction(adx=25.0, rsi=50.0, sma_alignment=0.0)
        assert result == SignalDirection.NEUTRAL
