"""Data-driven fallback thesis when Ollama is unavailable.

Produces a ``TradeThesis`` from composite score + indicator values alone,
without any AI debate.  This ensures the pipeline always returns a result
even when the LLM backend is down.
"""

from __future__ import annotations

import logging

from Option_Alpha.models import SignalDirection, TradeThesis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STRONG_SCORE_THRESHOLD: float = 70.0
_MODERATE_SCORE_THRESHOLD: float = 50.0

_RSI_OVERBOUGHT_WARN: float = 65.0
_RSI_OVERSOLD_WARN: float = 35.0
_RSI_OVERBOUGHT: float = 70.0
_RSI_OVERSOLD: float = 30.0

_IV_RANK_HIGH: float = 70.0
_IV_RANK_LOW: float = 20.0

_ADX_WEAK_TREND: float = 20.0


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* to the inclusive range [low, high]."""
    return max(low, min(value, high))


def _build_risk_factors(
    *,
    iv_rank: float,
    rsi_14: float,
    adx: float | None,
    direction: SignalDirection,
) -> list[str]:
    """Generate a list of risk factors from indicator values."""
    factors: list[str] = []

    # RSI risks
    if rsi_14 >= _RSI_OVERBOUGHT:
        factors.append(f"RSI overbought at {rsi_14:.0f}")
    elif rsi_14 >= _RSI_OVERBOUGHT_WARN:
        factors.append(f"RSI approaching overbought at {rsi_14:.0f}")
    elif rsi_14 <= _RSI_OVERSOLD:
        factors.append(f"RSI oversold at {rsi_14:.0f}")
    elif rsi_14 <= _RSI_OVERSOLD_WARN:
        factors.append(f"RSI approaching oversold at {rsi_14:.0f}")

    # IV rank risks
    if iv_rank >= _IV_RANK_HIGH:
        factors.append(f"IV rank elevated at {iv_rank:.0f} -- potential IV crush risk")
    elif iv_rank <= _IV_RANK_LOW:
        factors.append(f"IV rank low at {iv_rank:.0f} -- limited premium selling opportunity")

    # ADX / trend strength risks
    if adx is not None:
        if adx < _ADX_WEAK_TREND:
            factors.append(f"ADX at {adx:.0f} indicates weak/no trend")
    else:
        factors.append("ADX unavailable -- trend strength unknown")

    # Direction-specific risks
    if direction == SignalDirection.BULLISH:
        factors.append("Bullish thesis carries downside risk if momentum reverses")
    elif direction == SignalDirection.BEARISH:
        factors.append("Bearish thesis risks rally or short squeeze")

    return factors


def _determine_direction(
    composite_score: float,
    direction: SignalDirection,
) -> tuple[SignalDirection, str]:
    """Determine the thesis direction and strength label."""
    if composite_score >= _STRONG_SCORE_THRESHOLD and direction == SignalDirection.BULLISH:
        return SignalDirection.BULLISH, "strong"
    if composite_score >= _MODERATE_SCORE_THRESHOLD and direction == SignalDirection.BULLISH:
        return SignalDirection.BULLISH, "moderate"
    if composite_score >= _STRONG_SCORE_THRESHOLD and direction == SignalDirection.BEARISH:
        return SignalDirection.BEARISH, "strong"
    if composite_score >= _MODERATE_SCORE_THRESHOLD and direction == SignalDirection.BEARISH:
        return SignalDirection.BEARISH, "moderate"
    return SignalDirection.NEUTRAL, "weak"


async def build_fallback_thesis(
    ticker: str,
    composite_score: float,
    direction: SignalDirection,
    *,
    iv_rank: float,
    rsi_14: float,
    adx: float | None = None,
) -> TradeThesis:
    """Build a data-driven trade thesis without AI debate.

    Parameters
    ----------
    ticker:
        Ticker symbol (e.g. ``"AAPL"``).
    composite_score:
        Overall score from the scoring engine (0-100).
    direction:
        Signal direction from the scoring engine.
    iv_rank:
        Current IV rank (0-100).
    rsi_14:
        14-period RSI value.
    adx:
        Average Directional Index value, or ``None`` if unavailable.

    Returns
    -------
    TradeThesis
        A complete thesis with ``model_used="data-driven-fallback"``.
    """
    logger.info(
        "Building fallback thesis for %s: score=%.1f direction=%s",
        ticker,
        composite_score,
        direction.value,
    )

    final_direction, strength = _determine_direction(composite_score, direction)
    conviction = _clamp(composite_score / 100.0, 0.0, 1.0)

    adx_str = f"ADX {adx:.0f}" if adx is not None else "ADX N/A"
    entry_rationale = (
        f"{final_direction.value.upper()} "
        f"({composite_score:.0f}/100 composite, "
        f"{strength} trend alignment, "
        f"RSI {rsi_14:.0f}, {adx_str})"
    )

    risk_factors = _build_risk_factors(
        iv_rank=iv_rank,
        rsi_14=rsi_14,
        adx=adx,
        direction=final_direction,
    )

    # Direction-specific summaries
    if final_direction == SignalDirection.BULLISH:
        bull_summary = (
            f"Data-driven bullish signal for {ticker}: "
            f"composite score {composite_score:.0f}/100, RSI {rsi_14:.0f}, "
            f"IV rank {iv_rank:.0f}. {strength.capitalize()} conviction."
        )
        bear_summary = (
            f"No AI bear argument generated. "
            f"Risk factors: {', '.join(risk_factors[:2]) if risk_factors else 'none identified'}."
        )
        recommended_action = (
            f"Consider bullish position on {ticker} "
            f"with {strength} conviction based on composite scoring."
        )
    elif final_direction == SignalDirection.BEARISH:
        bull_summary = (
            f"No AI bull argument generated. "
            f"Risk factors: {', '.join(risk_factors[:2]) if risk_factors else 'none identified'}."
        )
        bear_summary = (
            f"Data-driven bearish signal for {ticker}: "
            f"composite score {composite_score:.0f}/100, RSI {rsi_14:.0f}, "
            f"IV rank {iv_rank:.0f}. {strength.capitalize()} conviction."
        )
        recommended_action = (
            f"Consider bearish position on {ticker} "
            f"with {strength} conviction based on composite scoring."
        )
    else:
        bull_summary = (
            f"Insufficient signal strength for {ticker}. "
            f"Composite score {composite_score:.0f}/100 does not favor bulls."
        )
        bear_summary = (
            f"Insufficient signal strength for {ticker}. "
            f"Composite score {composite_score:.0f}/100 does not favor bears."
        )
        recommended_action = (
            f"Hold/no action on {ticker}. "
            f"Composite score {composite_score:.0f}/100 is below threshold."
        )

    return TradeThesis(
        direction=final_direction,
        conviction=conviction,
        entry_rationale=entry_rationale,
        risk_factors=risk_factors,
        recommended_action=recommended_action,
        bull_summary=bull_summary,
        bear_summary=bear_summary,
        model_used="data-driven-fallback",
        total_tokens=0,
        duration_ms=0,
    )
