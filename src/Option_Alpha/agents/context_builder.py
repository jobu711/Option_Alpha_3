"""Convert a MarketContext model into flat key-value text for LLM prompts.

The output is a concise summary (~1,500-2,000 tokens / 6,000-8,000 chars)
with human-readable formatting: dollar signs, percentages, and plain-English
interpretations of IV rank and RSI levels.

No raw JSON is emitted -- agents parse flat text more reliably than nested
structures.
"""

from __future__ import annotations

import datetime

from Option_Alpha.models import MarketContext

# ---------------------------------------------------------------------------
# IV Rank interpretation thresholds
# ---------------------------------------------------------------------------

_IV_RANK_LOW: float = 25.0
_IV_RANK_MODERATE: float = 50.0
_IV_RANK_HIGH: float = 75.0

# ---------------------------------------------------------------------------
# RSI interpretation thresholds
# ---------------------------------------------------------------------------

_RSI_OVERSOLD: float = 30.0
_RSI_OVERBOUGHT: float = 70.0


def _interpret_iv_rank(iv_rank: float) -> str:
    """Return a plain-English label for IV rank."""
    if iv_rank < _IV_RANK_LOW:
        return "low"
    if iv_rank < _IV_RANK_MODERATE:
        return "moderate"
    if iv_rank < _IV_RANK_HIGH:
        return "high"
    return "very high"


def _interpret_rsi(rsi: float) -> str:
    """Return a plain-English label for RSI."""
    if rsi < _RSI_OVERSOLD:
        return "oversold"
    if rsi > _RSI_OVERBOUGHT:
        return "overbought"
    return "neutral"


def _format_earnings(
    next_earnings: datetime.date | None,
    data_timestamp: datetime.datetime,
) -> str:
    """Format the next-earnings date with DTE, or 'N/A'."""
    if next_earnings is None:
        return "N/A"
    dte = (next_earnings - data_timestamp.date()).days
    return f"{next_earnings.isoformat()} ({dte} DTE)"


def build_context_text(context: MarketContext) -> str:
    """Render *context* as flat key-value text suitable for an LLM prompt.

    Parameters
    ----------
    context:
        Fully populated ``MarketContext`` snapshot.

    Returns
    -------
    str
        Multi-line text block with labeled values.  No JSON, no nesting.
    """
    iv_label = _interpret_iv_rank(context.iv_rank)
    rsi_label = _interpret_rsi(context.rsi_14)
    earnings_str = _format_earnings(context.next_earnings, context.data_timestamp)

    # Format the data timestamp as a readable UTC string
    ts = context.data_timestamp
    if ts.tzinfo is not None:
        ts = ts.astimezone(datetime.UTC)
    timestamp_str = ts.strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        f"Ticker: {context.ticker}",
        f"Current Price: ${context.current_price:.2f}",
        f"52-Week Range: ${context.price_52w_low:.2f} - ${context.price_52w_high:.2f}",
        f"IV Rank: {context.iv_rank:.1f} ({iv_label})",
        f"IV Percentile: {context.iv_percentile:.1f}%",
        f"ATM IV (30 DTE): {context.atm_iv_30d * 100:.1f}%",
        f"RSI(14): {context.rsi_14:.1f} ({rsi_label})",
        f"MACD Signal: {context.macd_signal}",
        f"Put/Call Ratio: {context.put_call_ratio:.2f}",
        f"Next Earnings: {earnings_str}",
        f"DTE Target: {context.dte_target}",
        f"Target Strike: ${context.target_strike:.2f}",
        f"Target Delta: {context.target_delta:.2f}",
        f"Sector: {context.sector}",
        f"Data as of: {timestamp_str}",
    ]

    return "\n".join(lines)
