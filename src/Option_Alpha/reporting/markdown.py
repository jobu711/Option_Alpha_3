"""Markdown report generator producing GitHub-Flavored Markdown.

Generates a complete analysis report with all 8 sections. Tables use GFM
pipe syntax. Disclaimer is always the final section, imported from
``disclaimer.py``.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.models.enums import OptionType
from Option_Alpha.models.options import OptionContract
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT
from Option_Alpha.reporting.formatters import (
    build_report_filename,
    detect_conflicting_signals,
    format_greek_impact,
    group_indicators_by_category,
)

logger = logging.getLogger(__name__)

# Default output directory (relative to project root)
DEFAULT_REPORTS_DIR: str = "reports"


def _section_header(
    thesis: TradeThesis,
    context: MarketContext,
    contract: OptionContract | None,
) -> str:
    """Section 1: Report header with ticker, option details, and timestamp."""
    lines: list[str] = []

    title_parts = [f"**{context.ticker}**"]
    if contract is not None:
        type_str = contract.option_type.value.upper()
        title_parts.append(f"${contract.strike} {type_str}")
        title_parts.append(f"Exp: {contract.expiration.isoformat()}")
        title_parts.append(f"{contract.dte} DTE")

    lines.append(f"# Options Analysis: {' | '.join(title_parts)}")
    lines.append("")

    timestamp_str = context.data_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"*Generated: {timestamp_str}*")
    lines.append("")

    return "\n".join(lines)


def _section_market_snapshot(
    context: MarketContext,
    contract: OptionContract | None,
    signals: dict[str, float] | None,
) -> str:
    """Section 2: Market snapshot with price, IV, Greeks, and indicators."""
    lines: list[str] = []
    lines.append("## Market Snapshot")
    lines.append("")

    # Price info table
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Price | ${context.current_price} |")
    lines.append(f"| 52W High | ${context.price_52w_high} |")
    lines.append(f"| 52W Low | ${context.price_52w_low} |")
    lines.append(f"| IV Rank | {context.iv_rank:.1f} |")
    lines.append(f"| IV Percentile | {context.iv_percentile:.1f} |")
    lines.append(f"| RSI (14) | {context.rsi_14:.1f} |")
    lines.append(f"| MACD Signal | {context.macd_signal} |")
    lines.append(f"| Put/Call Ratio | {context.put_call_ratio:.2f} |")

    if context.next_earnings is not None:
        lines.append(f"| Next Earnings | {context.next_earnings.isoformat()} |")

    lines.append("")

    # Greeks table
    if contract is not None and contract.greeks is not None:
        lines.append("### Greeks")
        lines.append("")
        lines.append("| Greek | Value | What It Means |")
        lines.append("|-------|-------|---------------|")

        rows = format_greek_impact(contract.greeks, contract.greeks_source)
        for name, value, interpretation in rows:
            lines.append(f"| {name} | {value} | {interpretation} |")

        lines.append("")

    # Indicator readings by category
    if signals:
        lines.append("### Indicators")
        lines.append("")
        grouped = group_indicators_by_category(signals)
        for category, items in grouped.items():
            parts: list[str] = []
            for ind_name, ind_value, interpretation in items:
                parts.append(f"{ind_name} {ind_value:.1f} ({interpretation})")
            lines.append(f"**{category}**: {', '.join(parts)}")

        conflicts = detect_conflicting_signals(signals)
        if conflicts:
            lines.append("")
            for conflict in conflicts:
                lines.append(f"> **Warning**: {conflict}")

        lines.append("")

    return "\n".join(lines)


def _section_strategy_summary(thesis: TradeThesis, context: MarketContext) -> str:
    """Section 3: Strategy summary with recommended position."""
    lines: list[str] = []
    lines.append("## Strategy Summary")
    lines.append("")
    lines.append(f"- **Direction**: {thesis.direction.value.upper()}")
    lines.append(f"- **Conviction**: {thesis.conviction:.0%}")
    lines.append(f"- **Recommended Action**: {thesis.recommended_action}")
    lines.append("")

    return "\n".join(lines)


def _section_debate_summary(thesis: TradeThesis) -> str:
    """Section 4: Debate summary with bull/bear cases and verdict."""
    lines: list[str] = []
    lines.append("## Debate Summary")
    lines.append("")

    lines.append("### Bull Case")
    lines.append("")
    lines.append(thesis.bull_summary)
    lines.append("")

    lines.append("### Bear Case")
    lines.append("")
    lines.append(thesis.bear_summary)
    lines.append("")

    lines.append(
        f"**Verdict**: {thesis.direction.value.upper()} (conviction: {thesis.conviction:.0%})"
    )
    lines.append("")

    return "\n".join(lines)


def _section_key_factors(thesis: TradeThesis) -> str:
    """Section 5: Key factors driving the verdict."""
    lines: list[str] = []
    lines.append("## Key Factors")
    lines.append("")
    lines.append(thesis.entry_rationale)
    lines.append("")

    return "\n".join(lines)


def _section_risk_assessment(thesis: TradeThesis) -> str:
    """Section 6: Risk assessment with identified risks."""
    lines: list[str] = []
    lines.append("## Risk Assessment")
    lines.append("")

    if thesis.risk_factors:
        for i, risk in enumerate(thesis.risk_factors, start=1):
            lines.append(f"{i}. {risk}")
    else:
        lines.append("No specific risk factors identified.")

    lines.append("")

    return "\n".join(lines)


def _section_metadata(thesis: TradeThesis, context: MarketContext) -> str:
    """Section 7: Metadata block with model info, tokens, and duration."""
    lines: list[str] = []
    lines.append("## Metadata")
    lines.append("")
    lines.append("```")

    timestamp_str = context.data_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    lines.append(f"Ticker: {context.ticker} | ${context.target_strike} | {context.sector}")
    lines.append("Data Source: yfinance")
    lines.append(f"Data Timestamp: {timestamp_str}")
    lines.append(f"AI Model: {thesis.model_used}")
    lines.append(f"Total Tokens: {thesis.total_tokens:,}")
    lines.append(f"Analysis Duration: {thesis.duration_ms / 1000:.1f}s")

    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def _section_disclaimer() -> str:
    """Section 8: Legal disclaimer. Always last. Always present."""
    lines: list[str] = []
    lines.append("---")
    lines.append("")
    lines.append(f"> {DISCLAIMER_TEXT}")
    lines.append("")

    return "\n".join(lines)


def generate_markdown_report(
    thesis: TradeThesis,
    context: MarketContext,
    contract: OptionContract | None = None,
    signals: dict[str, float] | None = None,
) -> str:
    """Generate a complete GitHub-Flavored Markdown analysis report.

    Includes all 8 sections in order:
    1. Header, 2. Market Snapshot, 3. Strategy Summary,
    4. Debate Summary, 5. Key Factors, 6. Risk Assessment,
    7. Metadata, 8. Disclaimer.

    Args:
        thesis: Final trade thesis from the debate system.
        context: Market data snapshot used for the analysis.
        contract: Optional option contract being analyzed.
        signals: Optional indicator signals from :class:`TickerScore`.

    Returns:
        Complete markdown string ready for file output.
    """
    sections: list[str] = [
        _section_header(thesis, context, contract),
        _section_market_snapshot(context, contract, signals),
        _section_strategy_summary(thesis, context),
        _section_debate_summary(thesis),
        _section_key_factors(thesis),
        _section_risk_assessment(thesis),
        _section_metadata(thesis, context),
        _section_disclaimer(),
    ]

    return "\n".join(sections)


def save_report(
    content: str,
    ticker: str,
    strike: Decimal,
    option_type: OptionType,
) -> Path:
    """Save a markdown report to the reports directory.

    Creates the ``reports/`` directory if it does not exist. Uses
    :func:`build_report_filename` to generate the filename.

    Args:
        content: Full markdown content to write.
        ticker: Uppercase ticker symbol.
        strike: Option strike price.
        option_type: CALL or PUT.

    Returns:
        Path to the written report file.
    """
    filename = build_report_filename(ticker, strike, option_type, ext="md")
    reports_dir = Path(DEFAULT_REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    filepath = reports_dir / filename
    filepath.write_text(content, encoding="utf-8")

    logger.info("Report saved to %s", filepath)
    return filepath
