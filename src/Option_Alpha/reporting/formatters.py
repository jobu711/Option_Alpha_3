"""Shared formatting utilities for terminal and markdown reports.

Provides Greek interpretation, indicator grouping, conflict detection,
and report filename generation. All functions accept typed models from
``Option_Alpha.models``, never raw dicts (except ``signals`` which is
``dict[str, float]`` from :class:`TickerScore.signals`).
"""

from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from Option_Alpha.models.enums import GreeksSource, OptionType
from Option_Alpha.models.options import OptionGreeks

logger = logging.getLogger(__name__)

# --- Greek dollar-impact multiplier (1 contract = 100 shares) ---
CONTRACT_MULTIPLIER: int = 100

# --- Indicator category mappings ---
TREND_INDICATORS: frozenset[str] = frozenset(
    {
        "adx",
        "roc",
        "supertrend",
        "sma_alignment",
        "vwap_deviation",
    }
)
MOMENTUM_INDICATORS: frozenset[str] = frozenset(
    {
        "rsi",
        "stoch_rsi",
        "williams_r",
    }
)
VOLATILITY_INDICATORS: frozenset[str] = frozenset(
    {
        "atr_percent",
        "bb_width",
        "keltner_width",
        "iv_rank",
        "iv_percentile",
    }
)
VOLUME_INDICATORS: frozenset[str] = frozenset(
    {
        "obv_trend",
        "ad_trend",
        "relative_volume",
        "put_call_ratio",
        "max_pain",
    }
)

# --- Indicator interpretation thresholds ---
RSI_OVERBOUGHT: float = 70.0
RSI_OVERSOLD: float = 30.0
ADX_STRONG_TREND: float = 25.0
IV_RANK_ELEVATED: float = 50.0
IV_RANK_HIGH: float = 75.0
BB_WIDTH_TIGHT: float = 30.0
BB_WIDTH_WIDE: float = 70.0
PUT_CALL_BULLISH: float = 0.7
PUT_CALL_BEARISH: float = 1.3
STOCH_RSI_OVERBOUGHT: float = 80.0
STOCH_RSI_OVERSOLD: float = 20.0


def format_greek_impact(
    greeks: OptionGreeks,
    source: GreeksSource | None,
) -> list[tuple[str, str, str]]:
    """Format Greeks with dollar-impact interpretations.

    Each tuple contains ``(name, formatted_value, interpretation)``.
    Theta and vega are expressed as dollar impact per contract
    (value * 100).

    Args:
        greeks: Validated option Greeks from a contract.
        source: Where the Greeks originated (market, calculated, model),
            or None if unknown.

    Returns:
        List of 5 tuples, one per Greek, with human-readable interpretation.
    """
    source_label = f" ({source.value})" if source is not None else ""

    theta_dollar = greeks.theta * CONTRACT_MULTIPLIER
    vega_dollar = greeks.vega * CONTRACT_MULTIPLIER

    # Delta interpretation
    delta_dollar = abs(greeks.delta) * CONTRACT_MULTIPLIER
    delta_interp = f"${delta_dollar:.0f} P&L per $1 move in underlying{source_label}"

    # Gamma interpretation
    gamma_interp = f"Delta changes {greeks.gamma:.3f} per $1 move"

    # Theta interpretation: negative = losing money
    if greeks.theta < 0:
        theta_interp = f"Losing ${abs(theta_dollar):.0f}/day to time decay per contract"
    else:
        theta_interp = f"Gaining ${theta_dollar:.0f}/day from time decay per contract"

    # Vega interpretation
    vega_interp = f"${vega_dollar:.0f} P&L per 1% change in IV"

    # Rho interpretation
    if abs(greeks.rho) < 0.05:
        rho_interp = "Minimal interest rate sensitivity"
    else:
        rho_dollar = abs(greeks.rho) * CONTRACT_MULTIPLIER
        rho_interp = f"${rho_dollar:.0f} P&L per 1% rate change"

    return [
        ("Delta", f"{greeks.delta:.3f}", delta_interp),
        ("Gamma", f"{greeks.gamma:.3f}", gamma_interp),
        ("Theta", f"{greeks.theta:.3f}", theta_interp),
        ("Vega", f"{greeks.vega:.3f}", vega_interp),
        ("Rho", f"{greeks.rho:.3f}", rho_interp),
    ]


def _interpret_indicator(name: str, value: float) -> str:
    """Return a short interpretation string for a single indicator value.

    Args:
        name: Indicator key name (e.g. "rsi", "adx", "iv_rank").
        value: The indicator's numeric value.

    Returns:
        Human-readable interpretation in parentheses style.
    """
    if name == "rsi":
        if value > RSI_OVERBOUGHT:
            return "overbought"
        if value < RSI_OVERSOLD:
            return "oversold"
        return "neutral"

    if name == "stoch_rsi":
        if value > STOCH_RSI_OVERBOUGHT:
            return "overbought"
        if value < STOCH_RSI_OVERSOLD:
            return "oversold"
        return "neutral"

    if name == "williams_r":
        # Williams %R is inverted: -20 to 0 = overbought, -100 to -80 = oversold
        if value > -20:
            return "overbought"
        if value < -80:
            return "oversold"
        return "neutral"

    if name == "adx":
        if value > ADX_STRONG_TREND:
            return "strong trend"
        return "weak trend"

    if name in ("iv_rank", "iv_percentile"):
        if value > IV_RANK_HIGH:
            return "high"
        if value > IV_RANK_ELEVATED:
            return "elevated"
        return "low"

    if name == "bb_width":
        if value < BB_WIDTH_TIGHT:
            return "tight"
        if value > BB_WIDTH_WIDE:
            return "wide"
        return "normal"

    if name == "put_call_ratio":
        if value < PUT_CALL_BULLISH:
            return "bullish"
        if value > PUT_CALL_BEARISH:
            return "bearish"
        return "neutral"

    if name in ("obv_trend", "ad_trend"):
        if value > 0:
            return "rising"
        if value < 0:
            return "falling"
        return "flat"

    if name == "sma_alignment":
        if value > 0.5:
            return "bullish alignment"
        if value < -0.5:
            return "bearish alignment"
        return "neutral"

    if name == "supertrend":
        if value > 0:
            return "bullish"
        return "bearish"

    if name == "relative_volume":
        if value > 1.5:
            return "high volume"
        if value < 0.5:
            return "low volume"
        return "average volume"

    # Fallback for unrecognized indicators
    return f"{value:.2f}"


def group_indicators_by_category(
    signals: dict[str, float],
) -> dict[str, list[tuple[str, float, str]]]:
    """Group indicator signals into Trend/Momentum/Volatility/Volume categories.

    Each indicator gets an interpretation string appended. Indicators not
    matching any known category are placed under ``"Other"``.

    Args:
        signals: Indicator name to value mapping from :class:`TickerScore.signals`.

    Returns:
        Mapping of category name to list of ``(indicator_name, value, interpretation)``
        tuples. Only non-empty categories are included.
    """
    categories: dict[str, list[tuple[str, float, str]]] = {}

    for name, value in sorted(signals.items()):
        interpretation = _interpret_indicator(name, value)

        if name in TREND_INDICATORS:
            category = "Trend"
        elif name in MOMENTUM_INDICATORS:
            category = "Momentum"
        elif name in VOLATILITY_INDICATORS:
            category = "Volatility"
        elif name in VOLUME_INDICATORS:
            category = "Volume"
        else:
            category = "Other"

        if category not in categories:
            categories[category] = []
        categories[category].append((name, value, interpretation))

    return categories


def detect_conflicting_signals(signals: dict[str, float]) -> list[str]:
    """Detect and describe conflicting signals in indicator data.

    Looks for specific contradictions such as momentum overbought while
    trend is strong, or volume divergence from price direction.

    Args:
        signals: Indicator name to value mapping from :class:`TickerScore.signals`.

    Returns:
        List of human-readable conflict description strings. Empty if no
        conflicts detected.
    """
    conflicts: list[str] = []

    rsi = signals.get("rsi")
    adx = signals.get("adx")
    sma_alignment = signals.get("sma_alignment")
    stoch_rsi = signals.get("stoch_rsi")
    iv_rank = signals.get("iv_rank")
    put_call = signals.get("put_call_ratio")
    obv_trend = signals.get("obv_trend")

    # Momentum overbought but trend still strong
    if rsi is not None and adx is not None and rsi > RSI_OVERBOUGHT and adx > ADX_STRONG_TREND:
        conflicts.append(
            f"Momentum near overbought (RSI {rsi:.1f}) contradicts strong trend (ADX {adx:.1f})"
        )

    # Momentum oversold but bearish alignment
    if (
        rsi is not None
        and sma_alignment is not None
        and rsi < RSI_OVERSOLD
        and sma_alignment < -0.5
    ):
        conflicts.append(
            f"RSI oversold ({rsi:.1f}) but bearish SMA alignment ({sma_alignment:.2f}) "
            "— potential value trap"
        )

    # Stochastic RSI disagrees with RSI
    if (
        rsi is not None
        and stoch_rsi is not None
        and rsi > RSI_OVERBOUGHT
        and stoch_rsi < STOCH_RSI_OVERSOLD
    ):
        conflicts.append(
            f"RSI overbought ({rsi:.1f}) but Stochastic RSI oversold ({stoch_rsi:.1f}) "
            "— mixed momentum"
        )
    elif (
        rsi is not None
        and stoch_rsi is not None
        and rsi < RSI_OVERSOLD
        and stoch_rsi > STOCH_RSI_OVERBOUGHT
    ):
        conflicts.append(
            f"RSI oversold ({rsi:.1f}) but Stochastic RSI overbought ({stoch_rsi:.1f}) "
            "— mixed momentum"
        )

    # IV elevated but put/call ratio is bullish (cheap options but low demand)
    if (
        iv_rank is not None
        and put_call is not None
        and iv_rank > IV_RANK_HIGH
        and put_call < PUT_CALL_BULLISH
    ):
        conflicts.append(
            f"IV Rank elevated ({iv_rank:.1f}) but put/call ratio bullish ({put_call:.2f}) "
            "— options expensive despite low put demand"
        )

    # Volume divergence: OBV falling but bullish momentum
    if obv_trend is not None and rsi is not None and obv_trend < 0 and rsi > RSI_OVERBOUGHT:
        conflicts.append(
            f"OBV declining while RSI overbought ({rsi:.1f}) — bearish volume divergence"
        )

    return conflicts


def build_report_filename(
    ticker: str,
    strike: Decimal,
    option_type: OptionType,
    ext: str = "md",
) -> str:
    """Build a standardized report filename.

    Format: ``{TICKER}_{DATE}_{STRIKE}{C/P}_analysis.{ext}``
    Example: ``AAPL_2025-03-15_190C_analysis.md``

    Args:
        ticker: Uppercase ticker symbol.
        strike: Option strike price.
        option_type: CALL or PUT.
        ext: File extension without leading dot. Defaults to ``"md"``.

    Returns:
        Formatted filename string.
    """
    date_str = datetime.date.today().isoformat()
    type_char = "C" if option_type == OptionType.CALL else "P"

    # Format strike: remove trailing zeros but keep at least one decimal
    strike_str = f"{strike:f}".rstrip("0").rstrip(".")

    return f"{ticker.upper()}_{date_str}_{strike_str}{type_char}_analysis.{ext}"
