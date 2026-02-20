"""Signal direction classification based on technical indicators.

Determines BULLISH, BEARISH, or NEUTRAL direction by scoring ADX trend
strength, RSI momentum, and SMA alignment signals.
"""

import logging

from Option_Alpha.models.enums import SignalDirection

logger = logging.getLogger(__name__)

# --- Thresholds ---
ADX_TREND_THRESHOLD: float = 20.0
RSI_OVERBOUGHT: float = 70.0
RSI_OVERSOLD: float = 30.0
SMA_BULLISH_THRESHOLD: float = 0.5
SMA_BEARISH_THRESHOLD: float = -0.5
RSI_MIDPOINT: float = 50.0

# --- Internal scoring weights ---
_STRONG_SIGNAL_WEIGHT: float = 1.0
_MILD_SIGNAL_WEIGHT: float = 0.5


def determine_direction(
    adx: float,
    rsi: float,
    sma_alignment: float,
) -> SignalDirection:
    """Classify market direction from technical indicator values.

    Args:
        adx: Average Directional Index value. Below ADX_TREND_THRESHOLD means
            no clear trend (returns NEUTRAL).
        rsi: Relative Strength Index (0-100).
        sma_alignment: SMA alignment score. Positive values indicate bullish
            alignment, negative values bearish.

    Returns:
        SignalDirection.BULLISH, BEARISH, or NEUTRAL based on weighted scoring.
    """
    if adx < ADX_TREND_THRESHOLD:
        logger.debug(
            "ADX %.2f < threshold %.2f — returning NEUTRAL",
            adx,
            ADX_TREND_THRESHOLD,
        )
        return SignalDirection.NEUTRAL

    bullish_score: float = 0.0
    bearish_score: float = 0.0

    # RSI scoring
    if rsi < RSI_OVERSOLD:
        bullish_score += _STRONG_SIGNAL_WEIGHT
    elif rsi < RSI_MIDPOINT:
        # RSI between 30 and 50 — mild bullish
        bullish_score += _MILD_SIGNAL_WEIGHT
    elif rsi > RSI_OVERBOUGHT:
        bearish_score += _STRONG_SIGNAL_WEIGHT
    elif rsi > RSI_MIDPOINT:
        # RSI between 50 and 70 — mild bearish
        bearish_score += _MILD_SIGNAL_WEIGHT

    # SMA alignment scoring
    if sma_alignment > SMA_BULLISH_THRESHOLD:
        bullish_score += _STRONG_SIGNAL_WEIGHT
    elif sma_alignment < SMA_BEARISH_THRESHOLD:
        bearish_score += _STRONG_SIGNAL_WEIGHT

    logger.debug(
        "Direction scoring — bullish=%.2f, bearish=%.2f (ADX=%.2f, RSI=%.2f, SMA=%.4f)",
        bullish_score,
        bearish_score,
        adx,
        rsi,
        sma_alignment,
    )

    if bullish_score > bearish_score:
        return SignalDirection.BULLISH
    if bearish_score > bullish_score:
        return SignalDirection.BEARISH

    # Tiebreaker: when scores are equal and both > 0, use SMA alignment
    # direction as the deciding factor (underlying trend is more fundamental
    # than RSI's overbought/oversold momentum signal).
    if bullish_score > 0 and bullish_score == bearish_score:
        if sma_alignment > 0:
            return SignalDirection.BULLISH
        if sma_alignment < 0:
            return SignalDirection.BEARISH

    return SignalDirection.NEUTRAL
