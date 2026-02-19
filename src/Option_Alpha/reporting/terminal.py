"""Rich-based terminal output for analysis reports, scan results, and health checks.

Uses ``rich.console.Console`` for all output. Color scheme:
green = bullish, red = bearish, yellow = caution.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.models.health import HealthStatus
from Option_Alpha.models.options import OptionContract
from Option_Alpha.models.scan import TickerScore
from Option_Alpha.reporting.formatters import (
    detect_conflicting_signals,
    format_greek_impact,
    group_indicators_by_category,
)

logger = logging.getLogger(__name__)

# Shared console instance for terminal output
console = Console()

# --- Color scheme ---
COLOR_BULLISH: str = "green"
COLOR_BEARISH: str = "red"
COLOR_NEUTRAL: str = "yellow"
COLOR_HEADER: str = "bold cyan"
COLOR_MUTED: str = "dim"


def _direction_color(direction: SignalDirection) -> str:
    """Map a signal direction to its terminal color."""
    if direction == SignalDirection.BULLISH:
        return COLOR_BULLISH
    if direction == SignalDirection.BEARISH:
        return COLOR_BEARISH
    return COLOR_NEUTRAL


def _render_header(
    thesis: TradeThesis,
    context: MarketContext,
    contract: OptionContract | None,
) -> None:
    """Section 1: Header with ticker, option details, and timestamp."""
    title_parts = [f"[bold]{context.ticker}[/bold]"]
    if contract is not None:
        type_str = contract.option_type.value.upper()
        title_parts.append(f"${contract.strike} {type_str}")
        title_parts.append(f"Exp: {contract.expiration.isoformat()}")
        title_parts.append(f"{contract.dte} DTE")

    title = " | ".join(title_parts)
    timestamp_str = context.data_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    console.print()
    console.print(
        Panel(
            f"{title}\nTimestamp: {timestamp_str}",
            title="Options Analysis Report",
            style=COLOR_HEADER,
        )
    )


def _render_market_snapshot(
    context: MarketContext,
    contract: OptionContract | None,
    signals: dict[str, float] | None,
) -> None:
    """Section 2: Market snapshot with price, IV, Greeks, and indicators."""
    console.print("\n[bold]Market Snapshot[/bold]", style=COLOR_HEADER)

    # Price info table
    price_table = Table(show_header=False, box=None, padding=(0, 2))
    price_table.add_column("Metric", style="bold")
    price_table.add_column("Value")

    price_table.add_row("Price", f"${context.current_price}")
    price_table.add_row("52W High", f"${context.price_52w_high}")
    price_table.add_row("52W Low", f"${context.price_52w_low}")
    price_table.add_row("IV Rank", f"{context.iv_rank:.1f}")
    price_table.add_row("IV Percentile", f"{context.iv_percentile:.1f}")
    price_table.add_row("RSI (14)", f"{context.rsi_14:.1f}")
    price_table.add_row("MACD Signal", context.macd_signal)
    price_table.add_row("Put/Call Ratio", f"{context.put_call_ratio:.2f}")

    if context.next_earnings is not None:
        price_table.add_row("Next Earnings", context.next_earnings.isoformat())

    console.print(price_table)

    # Greeks table (if contract has them)
    if contract is not None and contract.greeks is not None:
        console.print()
        greeks_table = Table(title="Greeks", show_lines=True)
        greeks_table.add_column("Greek", style="bold")
        greeks_table.add_column("Value", justify="right")
        greeks_table.add_column("What It Means")

        rows = format_greek_impact(contract.greeks, contract.greeks_source)
        for name, value, interpretation in rows:
            greeks_table.add_row(name, value, interpretation)

        console.print(greeks_table)

    # Indicator readings
    if signals:
        console.print()
        grouped = group_indicators_by_category(signals)
        for category, items in grouped.items():
            parts: list[str] = []
            for ind_name, ind_value, interpretation in items:
                parts.append(f"{ind_name}: {ind_value:.1f} ({interpretation})")
            console.print(f"  [bold]{category}[/bold]: {', '.join(parts)}")

        conflicts = detect_conflicting_signals(signals)
        for conflict in conflicts:
            console.print(f"  [yellow]Warning: {conflict}[/yellow]")


def _render_strategy_summary(thesis: TradeThesis, context: MarketContext) -> None:
    """Section 3: Strategy summary with recommended action."""
    console.print("\n[bold]Strategy Summary[/bold]", style=COLOR_HEADER)

    direction_color = _direction_color(thesis.direction)
    console.print(
        f"  Direction: [{direction_color}]{thesis.direction.value.upper()}[/{direction_color}]"
    )
    console.print(f"  Conviction: {thesis.conviction:.0%}")
    console.print(f"  Recommended Action: {thesis.recommended_action}")


def _render_debate_summary(thesis: TradeThesis) -> None:
    """Section 4: Debate summary with bull/bear cases and verdict."""
    console.print("\n[bold]Debate Summary[/bold]", style=COLOR_HEADER)

    # Bull case
    console.print(f"\n  [{COLOR_BULLISH}]Bull Case:[/{COLOR_BULLISH}]")
    console.print(f"  {thesis.bull_summary}")

    # Bear case
    console.print(f"\n  [{COLOR_BEARISH}]Bear Case:[/{COLOR_BEARISH}]")
    console.print(f"  {thesis.bear_summary}")

    # Verdict
    direction_color = _direction_color(thesis.direction)
    console.print(
        f"\n  Verdict: [{direction_color}]{thesis.direction.value.upper()}"
        f"[/{direction_color}] (conviction: {thesis.conviction:.0%})"
    )


def _render_key_factors(thesis: TradeThesis) -> None:
    """Section 5: Key factors driving the verdict."""
    console.print("\n[bold]Key Factors[/bold]", style=COLOR_HEADER)
    console.print(f"  {thesis.entry_rationale}")


def _render_risk_assessment(thesis: TradeThesis) -> None:
    """Section 6: Risk assessment with identified risk factors."""
    console.print("\n[bold]Risk Assessment[/bold]", style=COLOR_HEADER)

    if thesis.risk_factors:
        for i, risk in enumerate(thesis.risk_factors, start=1):
            console.print(f"  {i}. [{COLOR_NEUTRAL}]{risk}[/{COLOR_NEUTRAL}]")
    else:
        console.print(f"  [{COLOR_MUTED}]No specific risk factors identified.[/{COLOR_MUTED}]")


def _render_metadata(thesis: TradeThesis, context: MarketContext) -> None:
    """Section 7: Metadata block with model info, token usage, and duration."""
    console.print("\n[bold]Metadata[/bold]", style=COLOR_HEADER)

    meta_table = Table(show_header=False, box=None, padding=(0, 2))
    meta_table.add_column("Key", style="dim")
    meta_table.add_column("Value")

    timestamp_str = context.data_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

    meta_table.add_row("Ticker", f"{context.ticker} | ${context.target_strike} | {context.sector}")
    meta_table.add_row("Data Source", "yfinance")
    meta_table.add_row("Data Timestamp", timestamp_str)
    meta_table.add_row("AI Model", thesis.model_used)
    meta_table.add_row("Total Tokens", f"{thesis.total_tokens:,}")
    meta_table.add_row("Duration", f"{thesis.duration_ms / 1000:.1f}s")

    console.print(meta_table)


def render_report(
    thesis: TradeThesis,
    context: MarketContext,
    contract: OptionContract | None = None,
    signals: dict[str, float] | None = None,
) -> None:
    """Render a full analysis report to the terminal using Rich.

    Prints all 7 report sections in order:
    1. Header, 2. Market Snapshot, 3. Strategy Summary,
    4. Debate Summary, 5. Key Factors, 6. Risk Assessment,
    7. Metadata.

    Args:
        thesis: Final trade thesis from the debate system.
        context: Market data snapshot used for the analysis.
        contract: Optional option contract being analyzed.
        signals: Optional indicator signals from :class:`TickerScore`.
    """
    _render_header(thesis, context, contract)
    _render_market_snapshot(context, contract, signals)
    _render_strategy_summary(thesis, context)
    _render_debate_summary(thesis)
    _render_key_factors(thesis)
    _render_risk_assessment(thesis)
    _render_metadata(thesis, context)


def render_scan_results(
    scores: list[TickerScore],
    verbose: bool = False,
) -> None:
    """Render scan results in compact terminal format.

    Compact format: ``#1 AAPL 87.3 BULLISH | RSI:72 ADX:34 BB:tight IV-R:62``
    Verbose mode adds a full table with all signal values.

    Args:
        scores: List of scored tickers, assumed pre-sorted by rank.
        verbose: If True, display a detailed table instead of compact lines.
    """
    if not scores:
        console.print("[dim]No tickers met the scoring threshold.[/dim]")
        return

    if verbose:
        table = Table(title="Scan Results", show_lines=True)
        table.add_column("#", justify="right", style="bold")
        table.add_column("Ticker", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Signals")

        for ts in scores:
            signal_parts: list[str] = []
            for name, value in sorted(ts.signals.items()):
                signal_parts.append(f"{name}:{value:.1f}")
            table.add_row(
                str(ts.rank),
                ts.ticker,
                f"{ts.score:.1f}",
                " ".join(signal_parts),
            )

        console.print(table)
    else:
        console.print(f"\n[bold]Top {len(scores)} Candidates[/bold]\n")
        for ts in scores:
            # Build compact signal summary from key indicators
            key_signals: list[str] = []
            for key in ("rsi", "adx", "bb_width", "iv_rank"):
                signal_value = ts.signals.get(key)
                if signal_value is not None:
                    label = key.upper().replace("_", "-")
                    if key == "bb_width":
                        label = "BB"
                        interp = (
                            "tight"
                            if signal_value < 30
                            else "wide"
                            if signal_value > 70
                            else "normal"
                        )
                        key_signals.append(f"{label}:{interp}")
                    else:
                        key_signals.append(f"{label}:{signal_value:.0f}")

            signal_str = " ".join(key_signals)
            console.print(f"  #{ts.rank:<3} {ts.ticker:<6} {ts.score:>5.1f} | {signal_str}")


def render_health(status: HealthStatus) -> None:
    """Render system health check status to the terminal.

    Displays green checkmarks for available services and red X marks
    for unavailable ones.

    Args:
        status: Health status from the health check service.
    """
    console.print("\n[bold]System Health Check[/bold]\n")

    checks: list[tuple[str, bool]] = [
        ("Ollama", status.ollama_available),
        ("Anthropic", status.anthropic_available),
        ("Yahoo Finance", status.yfinance_available),
        ("SQLite", status.sqlite_available),
    ]

    for name, available in checks:
        if available:
            console.print(f"  [green][OK][/green]  {name}")
        else:
            console.print(f"  [red][FAIL][/red] {name}")

    if status.ollama_models:
        console.print(f"\n  Ollama models: {', '.join(status.ollama_models)}")
    else:
        console.print(f"\n  [{COLOR_MUTED}]No Ollama models available[/{COLOR_MUTED}]")

    last_check_str = status.last_check.strftime("%Y-%m-%dT%H:%M:%SZ")
    console.print(f"\n  Last check: {last_check_str}")
