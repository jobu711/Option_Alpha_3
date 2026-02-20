"""CLI entry point for Option Alpha — AI-powered options analysis tool.

Provides the ``option-alpha`` command with subcommands for scanning the ticker
universe, running AI debates, generating reports, and managing watchlists.

This is the ONLY module where ``print()`` is allowed. All other modules use
``logging``. Async internals are bridged to typer's synchronous interface via
``asyncio.run()``.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import logging.handlers
import signal
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from Option_Alpha.models import (
    MarketContext,
    OptionContract,
    SignalDirection,
    TickerScore,
    TradeThesis,
)
from Option_Alpha.models.market_data import OHLCV, TickerInfo
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT

# ---------------------------------------------------------------------------
# Typer app and sub-apps
# ---------------------------------------------------------------------------

app = typer.Typer(name="option-alpha", help="AI-powered options analysis tool")
universe_app = typer.Typer(help="Manage the optionable ticker universe")
watchlist_app = typer.Typer(help="Manage watchlists")
app.add_typer(universe_app, name="universe")
app.add_typer(watchlist_app, name="watchlist")

# Rich console for formatted output
console = Console()

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

_LOG_FORMAT: str = "%(levelname)s: %(message)s"
_FILE_LOG_FORMAT: str = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_LOG_FILE: Path = Path("data/logs/option_alpha.log")


def _configure_logging(
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """Configure the root logger based on verbosity flags.

    Console output respects ``--verbose`` / ``--quiet``.  A rotating file
    handler always captures DEBUG-level output to ``data/logs/option_alpha.log``
    for post-hoc review.

    Args:
        verbose: Show DEBUG-level messages on the console.
        quiet: Show only WARNING and above on the console.
    """
    level = logging.DEBUG if verbose else logging.WARNING if quiet else logging.INFO
    logging.basicConfig(level=level, format=_LOG_FORMAT, force=True)

    # Add a persistent file handler (DEBUG, regardless of console level)
    root = logging.getLogger()
    already_has_file_handler = any(
        isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers
    )
    if not already_has_file_handler:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5_242_880,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FILE_LOG_FORMAT))
        root.addHandler(file_handler)
        # Ensure root logger level allows DEBUG through to the file handler
        if root.level > logging.DEBUG:
            root.setLevel(logging.DEBUG)
        # Silence noisy third-party loggers
        logging.getLogger("aiosqlite").setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Scan cancellation via Ctrl+C
# ---------------------------------------------------------------------------

_scan_cancelled: bool = False


def _handle_sigint(signum: int, frame: object) -> None:
    """Handle SIGINT (Ctrl+C) by setting the cancellation flag.

    Does not call ``sys.exit()`` — the pipeline checks
    ``_scan_cancelled`` between phases and exits cleanly.
    """
    global _scan_cancelled  # noqa: PLW0603
    _scan_cancelled = True
    console.print("\n[yellow]Scan cancellation requested. Finishing current phase...[/yellow]")


# ---------------------------------------------------------------------------
# Async scan lock
# ---------------------------------------------------------------------------

_scan_lock = asyncio.Lock()

# ---------------------------------------------------------------------------
# Default constants
# ---------------------------------------------------------------------------

DEFAULT_TOP_N: int = 50
DEFAULT_MIN_SCORE: float = 50.0
DEFAULT_DB_PATH: str = "data/options.db"
DEFAULT_OHLCV_PERIOD: str = "1y"

# ---------------------------------------------------------------------------
# scan command
# ---------------------------------------------------------------------------


@app.command()
def scan(
    preset: Annotated[
        str, typer.Option(help="Universe preset: full, sp500, midcap, smallcap, etfs")
    ] = "full",
    sectors: Annotated[str, typer.Option(help="Comma-separated GICS sectors to filter")] = "",
    top_n: Annotated[
        int, typer.Option(help="Number of top tickers to fetch options for")
    ] = DEFAULT_TOP_N,
    min_score: Annotated[
        float, typer.Option(help="Minimum composite score threshold")
    ] = DEFAULT_MIN_SCORE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info logging")] = False,
) -> None:
    """Run the 5-phase scan pipeline on the ticker universe."""
    _configure_logging(verbose=verbose, quiet=quiet)

    sector_list = [s.strip() for s in sectors.split(",") if s.strip()] if sectors else []

    # Install SIGINT handler for clean abort
    original_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handle_sigint)
    try:
        asyncio.run(
            _scan_async(
                preset=preset,
                sector_list=sector_list,
                top_n=top_n,
                min_score=min_score,
            )
        )
    finally:
        signal.signal(signal.SIGINT, original_handler)


async def _scan_async(
    *,
    preset: str,
    sector_list: list[str],
    top_n: int,
    min_score: float,
) -> None:
    """Execute the 5-phase scan pipeline asynchronously.

    Phases:
        1. Load universe and batch-fetch OHLCV data.
        2. Compute indicators, normalize, score, and determine direction.
        3. Fetch earnings catalysts and apply adjustments.
        4. Fetch option chains for top tickers.
        5. Persist ScanRun and ticker scores.
    """
    global _scan_cancelled  # noqa: PLW0603
    _scan_cancelled = False

    if _scan_lock.locked():
        console.print("[red]A scan is already in progress.[/red]")
        raise typer.Exit(code=1)

    async with _scan_lock:
        # Lazy imports to avoid heavy startup cost when running other commands
        from Option_Alpha.analysis import (
            apply_catalyst_adjustment,
            catalyst_proximity_score,
            determine_direction,
            filter_liquid_tickers,
            recommend_contract,
            score_universe,
        )
        from Option_Alpha.data import Database, Repository
        from Option_Alpha.indicators import (
            ad_trend,
            adx,
            atr_percent,
            bb_width,
            keltner_width,
            obv_trend,
            relative_volume,
            roc,
            rsi,
            sma_alignment,
            stoch_rsi,
            supertrend,
            vwap_deviation,
            williams_r,
        )
        from Option_Alpha.services import (
            MarketDataService,
            OptionsDataService,
            RateLimiter,
            ServiceCache,
            UniverseService,
        )

        logger = logging.getLogger(__name__)
        scan_id = str(uuid.uuid4())
        started_at = datetime.datetime.now(datetime.UTC)

        async with Database(DEFAULT_DB_PATH) as db:
            cache = ServiceCache(database=db)
            rate_limiter = RateLimiter()
            repo = Repository(db)
            market_service = MarketDataService(rate_limiter=rate_limiter, cache=cache)
            options_service = OptionsDataService(rate_limiter=rate_limiter, cache=cache)
            universe_service = UniverseService(cache=cache, rate_limiter=rate_limiter)

            try:
                # ---------------------------------------------------------------
                # Phase 1: Load universe and fetch OHLCV
                # ---------------------------------------------------------------
                console.print(
                    "\n[bold cyan]Phase 1/5: Loading universe and fetching market data[/bold cyan]"
                )

                universe = await universe_service.get_universe(preset=preset)
                if not universe:
                    logger.warning("Universe empty for preset '%s', attempting refresh", preset)
                    universe = await universe_service.refresh()
                    universe = await universe_service.get_universe(preset=preset)

                if sector_list:
                    filtered_tickers: list[TickerInfo] = []
                    for sector_name in sector_list:
                        sector_tickers = await universe_service.filter_by_sector(
                            universe, sector=sector_name
                        )
                        filtered_tickers.extend(sector_tickers)
                    universe = filtered_tickers

                if not universe:
                    console.print(
                        "[red]No tickers found for the given preset/sector filters.[/red]"
                    )
                    raise typer.Exit(code=1)

                ticker_symbols = [t.symbol for t in universe]
                console.print(f"  Loaded {len(ticker_symbols)} tickers")

                with Progress(
                    SpinnerColumn(spinner_name="line"),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        f"Fetching OHLCV for {len(ticker_symbols)} tickers...",
                        total=None,
                    )
                    batch_results = await market_service.fetch_batch_ohlcv(ticker_symbols)
                    progress.update(task, completed=1)

                # Separate successes and failures
                ohlcv_data: dict[str, list[OHLCV]] = {}
                fetch_failures: list[str] = []
                for ticker_sym, result in batch_results.items():
                    if isinstance(result, Exception):
                        fetch_failures.append(ticker_sym)
                        logger.warning("OHLCV fetch failed for %s: %s", ticker_sym, result)
                    else:
                        ohlcv_data[ticker_sym] = result

                if fetch_failures:
                    fail_count = len(fetch_failures)
                    console.print(
                        f"  [yellow]Warning: {fail_count} tickers failed OHLCV fetch[/yellow]"
                    )

                if not ohlcv_data:
                    console.print("[red]No OHLCV data retrieved. Aborting scan.[/red]")
                    raise typer.Exit(code=1)

                console.print(f"  Fetched data for {len(ohlcv_data)} tickers")

                if _scan_cancelled:
                    console.print("[yellow]Scan cancelled after Phase 1.[/yellow]")
                    raise typer.Exit(code=0)

                # ---------------------------------------------------------------
                # Phase 2: Compute indicators, normalize, score, direction
                # ---------------------------------------------------------------
                console.print(
                    "\n[bold cyan]Phase 2/5: Computing indicators and scoring[/bold cyan]"
                )

                universe_indicators: dict[str, dict[str, float]] = {}

                for ticker_sym, bars in ohlcv_data.items():
                    try:
                        # Convert OHLCV models to pandas Series for indicators
                        close_prices = pd.Series(
                            [float(bar.close) for bar in bars],
                            dtype=float,
                        )
                        high_prices = pd.Series(
                            [float(bar.high) for bar in bars],
                            dtype=float,
                        )
                        low_prices = pd.Series(
                            [float(bar.low) for bar in bars],
                            dtype=float,
                        )
                        volume_series = pd.Series(
                            [float(bar.volume) for bar in bars],
                            dtype=float,
                        )

                        indicators: dict[str, float] = {}

                        # Oscillators
                        rsi_series = rsi(close_prices)
                        if not rsi_series.dropna().empty:
                            indicators["rsi"] = float(rsi_series.dropna().iloc[-1])

                        stoch_series = stoch_rsi(close_prices)
                        if not stoch_series.dropna().empty:
                            indicators["stoch_rsi"] = float(stoch_series.dropna().iloc[-1])

                        wr_series = williams_r(high_prices, low_prices, close_prices)
                        if not wr_series.dropna().empty:
                            indicators["williams_r"] = float(wr_series.dropna().iloc[-1])

                        # Trend
                        adx_series = adx(high_prices, low_prices, close_prices)
                        if not adx_series.dropna().empty:
                            indicators["adx"] = float(adx_series.dropna().iloc[-1])

                        roc_series = roc(close_prices)
                        if not roc_series.dropna().empty:
                            indicators["roc"] = float(roc_series.dropna().iloc[-1])

                        st_series = supertrend(high_prices, low_prices, close_prices)
                        if not st_series.dropna().empty:
                            indicators["supertrend"] = float(st_series.dropna().iloc[-1])

                        # Volatility
                        atr_series = atr_percent(high_prices, low_prices, close_prices)
                        if not atr_series.dropna().empty:
                            indicators["atr_percent"] = float(atr_series.dropna().iloc[-1])

                        bb_series = bb_width(close_prices)
                        if not bb_series.dropna().empty:
                            indicators["bb_width"] = float(bb_series.dropna().iloc[-1])

                        kw_series = keltner_width(high_prices, low_prices, close_prices)
                        if not kw_series.dropna().empty:
                            indicators["keltner_width"] = float(kw_series.dropna().iloc[-1])

                        # Volume
                        obv_series = obv_trend(close_prices, volume_series)
                        if not obv_series.dropna().empty:
                            indicators["obv_trend"] = float(obv_series.dropna().iloc[-1])

                        ad_series = ad_trend(high_prices, low_prices, close_prices, volume_series)
                        if not ad_series.dropna().empty:
                            indicators["ad_trend"] = float(ad_series.dropna().iloc[-1])

                        rv_series = relative_volume(volume_series)
                        if not rv_series.dropna().empty:
                            indicators["relative_volume"] = float(rv_series.dropna().iloc[-1])

                        # Moving averages
                        sma_series = sma_alignment(close_prices)
                        if not sma_series.dropna().empty:
                            indicators["sma_alignment"] = float(sma_series.dropna().iloc[-1])

                        vwap_series = vwap_deviation(close_prices, volume_series)
                        if not vwap_series.dropna().empty:
                            indicators["vwap_deviation"] = float(vwap_series.dropna().iloc[-1])

                        # Options-specific indicators (iv_rank, iv_percentile,
                        # put_call_ratio, max_pain) are omitted here because they
                        # require historical IV / options chain data not available
                        # from basic OHLCV.  The normalization pipeline assigns
                        # DEFAULT_PERCENTILE (50.0) to any missing indicator
                        # automatically, which is cleaner than hard-coding placeholders
                        # that would be indistinguishable from real data.

                        if indicators:
                            universe_indicators[ticker_sym] = indicators
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Indicator computation failed for %s: %s",
                            ticker_sym,
                            exc,
                        )
                        continue

                if not universe_indicators:
                    console.print("[red]No indicators computed. Aborting scan.[/red]")
                    raise typer.Exit(code=1)

                # Score universe: normalize, invert, composite score, filter, rank
                scored_tickers = score_universe(universe_indicators)

                # Filter by min_score
                scored_tickers = [t for t in scored_tickers if t.score >= min_score]

                if not scored_tickers:
                    console.print(
                        f"[yellow]No tickers scored above threshold ({min_score}).[/yellow]"
                    )
                    raise typer.Exit(code=0)

                # Determine direction using RAW indicator values (not percentile-
                # normalized values from ts.signals).  determine_direction()
                # expects raw ADX (0-100 scale), raw RSI (0-100), and raw SMA
                # alignment (small float, typically -5 to +5).
                ticker_directions: dict[str, SignalDirection] = {}
                for ts in scored_tickers:
                    raw = universe_indicators.get(ts.ticker, {})
                    adx_val = raw.get("adx", 0.0)
                    rsi_val = raw.get("rsi", 50.0)
                    sma_val = raw.get("sma_alignment", 0.0)
                    ticker_directions[ts.ticker] = determine_direction(
                        adx=adx_val, rsi=rsi_val, sma_alignment=sma_val
                    )

                console.print(f"  Scored {len(scored_tickers)} tickers above threshold")

                if _scan_cancelled:
                    console.print("[yellow]Scan cancelled after Phase 2.[/yellow]")
                    raise typer.Exit(code=0)

                # ---------------------------------------------------------------
                # Phase 3: Catalyst proximity scoring
                # ---------------------------------------------------------------
                console.print("\n[bold cyan]Phase 3/5: Evaluating earnings catalysts[/bold cyan]")

                today = datetime.date.today()
                try:
                    # Apply catalyst adjustment to all tickers.
                    # Without a real earnings calendar, use neutral proximity.
                    scored_tickers = [
                        TickerScore(
                            ticker=t.ticker,
                            score=apply_catalyst_adjustment(
                                t.score,
                                catalyst_proximity_score(
                                    next_earnings=None,
                                    reference_date=today,
                                ),
                            ),
                            signals=t.signals,
                            rank=t.rank,
                        )
                        for t in scored_tickers
                    ]

                    # Re-sort and re-rank after catalyst adjustment
                    scored_tickers.sort(key=lambda t: t.score, reverse=True)
                    scored_tickers = [
                        TickerScore(
                            ticker=t.ticker,
                            score=t.score,
                            signals=t.signals,
                            rank=rank,
                        )
                        for rank, t in enumerate(scored_tickers, start=1)
                    ]
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Catalyst scoring failed (continuing): %s", exc)

                console.print(f"  Catalyst adjustment applied to {len(scored_tickers)} tickers")

                if _scan_cancelled:
                    console.print("[yellow]Scan cancelled after Phase 3.[/yellow]")
                    raise typer.Exit(code=0)

                # ---------------------------------------------------------------
                # Phase 4: Fetch option chains for top N
                # ---------------------------------------------------------------
                console.print(
                    f"\n[bold cyan]Phase 4/5: Fetching option chains (top {top_n})[/bold cyan]"
                )

                top_tickers = filter_liquid_tickers(scored_tickers, ohlcv_data, top_n)
                options_results: dict[str, OptionContract] = {}

                try:
                    for ts in top_tickers:
                        direction = ticker_directions.get(ts.ticker, SignalDirection.NEUTRAL)
                        if direction == SignalDirection.NEUTRAL:
                            continue
                        try:
                            contracts = await options_service.fetch_option_chain(
                                ts.ticker, direction=direction
                            )
                            if contracts:
                                # Estimate spot from last OHLCV close for BSM fallback
                                ticker_bars = ohlcv_data.get(ts.ticker)
                                spot_price: float | None = None
                                if ticker_bars:
                                    spot_price = float(ticker_bars[-1].close)
                                recommended = recommend_contract(
                                    contracts, direction, spot=spot_price
                                )
                                if recommended is not None:
                                    options_results[ts.ticker] = recommended
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("Options fetch failed for %s: %s", ts.ticker, exc)
                            continue
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Options phase failed (continuing): %s", exc)

                console.print(f"  Found option recommendations for {len(options_results)} tickers")

                if _scan_cancelled:
                    console.print("[yellow]Scan cancelled after Phase 4.[/yellow]")
                    raise typer.Exit(code=0)

                # ---------------------------------------------------------------
                # Phase 5: Persist results
                # ---------------------------------------------------------------
                console.print("\n[bold cyan]Phase 5/5: Persisting results[/bold cyan]")

                from Option_Alpha.models.scan import ScanRun

                completed_at = datetime.datetime.now(datetime.UTC)
                scan_run = ScanRun(
                    id=scan_id,
                    started_at=started_at,
                    completed_at=completed_at,
                    status="completed",
                    preset=preset,
                    sectors=sector_list,
                    ticker_count=len(scored_tickers),
                    top_n=top_n,
                )

                try:
                    await repo.save_scan_run(scan_run)
                    await repo.save_ticker_scores(scan_id, scored_tickers)
                    console.print("  Results persisted to database")
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to persist scan results: %s", exc)
                    console.print("[yellow]Warning: Failed to persist results[/yellow]")

                # ---------------------------------------------------------------
                # Display results
                # ---------------------------------------------------------------
                _render_scan_results(scored_tickers[:top_n], ticker_directions, options_results)

                elapsed = (completed_at - started_at).total_seconds()
                console.print(
                    f"\n[green]Scan complete: {len(scored_tickers)} tickers scored "
                    f"in {elapsed:.1f}s[/green]"
                )
                console.print(f"\n[dim]{DISCLAIMER_TEXT}[/dim]")

            finally:
                await universe_service.aclose()


def _render_scan_results(
    scores: list[TickerScore],
    directions: dict[str, SignalDirection],
    options: dict[str, OptionContract],
) -> None:
    """Render scan results as a rich table to the console.

    Args:
        scores: Scored and ranked tickers to display.
        directions: Direction classification for each ticker.
        options: Recommended contracts (OptionContract) keyed by ticker.
    """
    if not scores:
        console.print("[yellow]No results to display.[/yellow]")
        return

    table = Table(title="Scan Results", show_lines=False)
    table.add_column("Rank", justify="right", style="dim", width=5)
    table.add_column("Ticker", style="bold", width=8)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Direction", width=10)
    table.add_column("RSI", justify="right", width=7)
    table.add_column("ADX", justify="right", width=7)
    table.add_column("Option", width=25)

    for ts in scores:
        direction = directions.get(ts.ticker, SignalDirection.NEUTRAL)
        direction_style = {
            SignalDirection.BULLISH: "[green]BULLISH[/green]",
            SignalDirection.BEARISH: "[red]BEARISH[/red]",
            SignalDirection.NEUTRAL: "[yellow]NEUTRAL[/yellow]",
        }.get(direction, "[dim]---[/dim]")

        rsi_val = ts.signals.get("rsi")
        adx_val = ts.signals.get("adx")
        rsi_str = f"{rsi_val:.1f}" if rsi_val is not None else "---"
        adx_str = f"{adx_val:.1f}" if adx_val is not None else "---"

        option_rec = options.get(ts.ticker)
        if option_rec is not None:
            # Display strike and type from the OptionContract
            option_str = (
                f"${option_rec.strike} {option_rec.option_type.value.upper()} ({option_rec.dte}d)"
            )
        else:
            option_str = "---"

        table.add_row(
            str(ts.rank),
            ts.ticker,
            f"{ts.score:.1f}",
            direction_style,
            rsi_str,
            adx_str,
            option_str,
        )

    console.print(table)


# ---------------------------------------------------------------------------
# debate command
# ---------------------------------------------------------------------------


@app.command()
def debate(
    ticker: Annotated[str, typer.Argument(help="Ticker symbol to debate")],
    strike: Annotated[str | None, typer.Option(help="Strike price (e.g., '185.00')")] = None,
    expiration: Annotated[str | None, typer.Option(help="Expiration date (YYYY-MM-DD)")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info logging")] = False,
) -> None:
    """Run an AI debate for a specific ticker."""
    _configure_logging(verbose=verbose, quiet=quiet)

    strike_decimal = Decimal(strike) if strike else None
    expiration_date = datetime.date.fromisoformat(expiration) if expiration else None

    asyncio.run(
        _debate_async(
            ticker=ticker.upper().strip(),
            strike_price=strike_decimal,
            expiration_date=expiration_date,
        )
    )


async def _debate_async(
    *,
    ticker: str,
    strike_price: Decimal | None,
    expiration_date: datetime.date | None,
) -> None:
    """Execute the debate pipeline asynchronously.

    Builds a MarketContext from live data, then runs the
    DebateOrchestrator for a Bull -> Bear -> Risk debate flow.
    """
    from Option_Alpha.agents import DebateOrchestrator, LLMClient
    from Option_Alpha.data import Database, Repository
    from Option_Alpha.indicators import adx as compute_adx
    from Option_Alpha.indicators import rsi as compute_rsi
    from Option_Alpha.services import (
        MarketDataService,
        RateLimiter,
        ServiceCache,
    )

    logger = logging.getLogger(__name__)

    async with Database(DEFAULT_DB_PATH) as db:
        cache = ServiceCache(database=db)
        rate_limiter = RateLimiter()
        repo = Repository(db)
        market_service = MarketDataService(rate_limiter=rate_limiter, cache=cache)

        console.print(f"\n[bold]Preparing debate for {ticker}...[/bold]")

        # Fetch OHLCV data
        try:
            bars = await market_service.fetch_ohlcv(ticker)
        except Exception as exc:
            console.print(f"[red]Failed to fetch market data for {ticker}: {exc}[/red]")
            raise typer.Exit(code=1) from exc

        # Compute key indicators from OHLCV
        close_prices = pd.Series([float(bar.close) for bar in bars], dtype=float)
        high_prices = pd.Series([float(bar.high) for bar in bars], dtype=float)
        low_prices = pd.Series([float(bar.low) for bar in bars], dtype=float)

        rsi_series = compute_rsi(close_prices)
        rsi_val = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else 50.0

        adx_series = compute_adx(high_prices, low_prices, close_prices)
        adx_val = float(adx_series.dropna().iloc[-1]) if not adx_series.dropna().empty else None

        # Get current price and quote
        try:
            quote = await market_service.fetch_quote(ticker)
            current_price = quote.last
        except Exception:
            # Fallback to last close from OHLCV
            current_price = bars[-1].close
            logger.warning("Quote fetch failed, using last OHLCV close for %s", ticker)

        # Fetch ticker info for sector
        try:
            ticker_info = await market_service.fetch_ticker_info(ticker)
            sector = ticker_info.sector
        except Exception:
            sector = "Unknown"
            logger.warning("Ticker info fetch failed for %s, using Unknown sector", ticker)

        # Select expiration and strike if not provided
        target_strike = strike_price or current_price
        target_dte = 45

        if expiration_date is not None:
            target_dte = max(1, (expiration_date - datetime.date.today()).days)

        # Determine 52-week high/low from OHLCV
        all_highs = [float(bar.high) for bar in bars]
        all_lows = [float(bar.low) for bar in bars]
        price_52w_high = Decimal(str(max(all_highs)))
        price_52w_low = Decimal(str(min(all_lows)))

        # Build MarketContext
        now_utc = datetime.datetime.now(datetime.UTC)
        context = MarketContext(
            ticker=ticker,
            current_price=current_price,
            price_52w_high=price_52w_high,
            price_52w_low=price_52w_low,
            iv_rank=50.0,  # Default when no IV history available
            iv_percentile=50.0,
            atm_iv_30d=0.25,  # Reasonable default
            rsi_14=rsi_val,
            macd_signal="neutral",
            put_call_ratio=1.0,
            next_earnings=None,
            dte_target=target_dte,
            target_strike=target_strike,
            target_delta=0.35,
            sector=sector,
            data_timestamp=now_utc,
        )

        # Run debate
        llm_client = LLMClient()
        orchestrator = DebateOrchestrator(llm_client=llm_client, repository=repo)

        console.print("[bold]Running AI debate (Bull -> Bear -> Risk)...[/bold]")

        with Progress(
            SpinnerColumn(spinner_name="line"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Debating...", total=None)
            thesis = await orchestrator.run_debate(
                context,
                composite_score=50.0,
                iv_rank=context.iv_rank,
                rsi_14=rsi_val,
                adx=adx_val,
            )
            progress.update(task, completed=1)

        # Display results
        _render_debate_report(ticker, thesis, context)


def _render_debate_report(
    ticker: str,
    thesis: TradeThesis,
    context: MarketContext,
) -> None:
    """Render the debate thesis as a rich console display.

    Args:
        ticker: The ticker symbol debated.
        thesis: The final trade thesis output.
        context: Market context used for the debate.
    """
    console.print(f"\n[bold underline]Debate Report: {ticker}[/bold underline]\n")

    # Direction and conviction
    direction_colors = {
        SignalDirection.BULLISH: "green",
        SignalDirection.BEARISH: "red",
        SignalDirection.NEUTRAL: "yellow",
    }
    color = direction_colors.get(thesis.direction, "white")
    console.print(f"Direction: [{color}]{thesis.direction.value.upper()}[/{color}]")
    console.print(f"Conviction: {thesis.conviction:.0%}")
    console.print(f"Model: {thesis.model_used}")
    if thesis.total_tokens > 0:
        console.print(f"Tokens: {thesis.total_tokens:,}")
    if thesis.duration_ms > 0:
        console.print(f"Duration: {thesis.duration_ms / 1000:.1f}s")

    # Rationale
    console.print(f"\n[bold]Entry Rationale:[/bold]\n{thesis.entry_rationale}")

    # Bull case
    console.print(f"\n[green][bold]Bull Case:[/bold][/green]\n{thesis.bull_summary}")

    # Bear case
    console.print(f"\n[red][bold]Bear Case:[/bold][/red]\n{thesis.bear_summary}")

    # Risk factors
    if thesis.risk_factors:
        console.print("\n[yellow][bold]Risk Factors:[/bold][/yellow]")
        for factor in thesis.risk_factors:
            console.print(f"  - {factor}")

    # Recommended action
    console.print(f"\n[bold]Recommended Action:[/bold]\n{thesis.recommended_action}")

    # Market context summary
    console.print(
        f"\n[dim]Price: ${context.current_price} | "
        f"RSI: {context.rsi_14:.1f} | "
        f"Sector: {context.sector}[/dim]"
    )

    # Disclaimer
    console.print(f"\n[dim]{thesis.disclaimer}[/dim]")
    console.print(f"[dim]{DISCLAIMER_TEXT}[/dim]")


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


@app.command()
def report(
    ticker: Annotated[str, typer.Argument(help="Ticker symbol to report on")],
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: terminal or md")
    ] = "terminal",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Suppress info logging")] = False,
) -> None:
    """Generate a report from the latest debate history for a ticker."""
    _configure_logging(verbose=verbose, quiet=quiet)
    asyncio.run(_report_async(ticker=ticker.upper().strip(), output_format=output_format))


async def _report_async(*, ticker: str, output_format: str) -> None:
    """Generate a report from debate history.

    Args:
        ticker: The ticker symbol.
        output_format: Either ``"terminal"`` or ``"md"``.
    """
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        theses = await repo.get_debate_history(ticker, limit=1)

        if not theses:
            console.print(f"[yellow]No debate history found for {ticker}.[/yellow]")
            raise typer.Exit(code=1)

        thesis = theses[0]

        if output_format == "md":
            _render_markdown_report(ticker, thesis)
        else:
            _render_terminal_report(ticker, thesis)


def _render_terminal_report(ticker: str, thesis: TradeThesis) -> None:
    """Render a debate thesis to the terminal using rich formatting.

    Args:
        ticker: Ticker symbol.
        thesis: Trade thesis to render.
    """
    console.print(f"\n[bold underline]Report: {ticker}[/bold underline]\n")

    direction_colors = {
        SignalDirection.BULLISH: "green",
        SignalDirection.BEARISH: "red",
        SignalDirection.NEUTRAL: "yellow",
    }
    color = direction_colors.get(thesis.direction, "white")
    console.print(f"Direction: [{color}]{thesis.direction.value.upper()}[/{color}]")
    console.print(f"Conviction: {thesis.conviction:.0%}")

    console.print(f"\n[bold]Entry Rationale:[/bold]\n{thesis.entry_rationale}")
    console.print(f"\n[green][bold]Bull Summary:[/bold][/green]\n{thesis.bull_summary}")
    console.print(f"\n[red][bold]Bear Summary:[/bold][/red]\n{thesis.bear_summary}")

    if thesis.risk_factors:
        console.print("\n[yellow][bold]Risk Factors:[/bold][/yellow]")
        for factor in thesis.risk_factors:
            console.print(f"  - {factor}")

    console.print(f"\n[bold]Recommended Action:[/bold]\n{thesis.recommended_action}")
    console.print(f"\n[dim]{thesis.disclaimer}[/dim]")
    console.print(f"[dim]{DISCLAIMER_TEXT}[/dim]")


def _render_markdown_report(ticker: str, thesis: TradeThesis) -> None:
    """Render a debate thesis as markdown and save to a file.

    Args:
        ticker: Ticker symbol.
        thesis: Trade thesis to render.
    """
    from pathlib import Path

    date_str = datetime.date.today().isoformat()
    filename = f"{ticker}_{date_str}_analysis.md"
    report_dir = Path("reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    filepath = report_dir / filename

    lines: list[str] = [
        f"# Analysis Report: {ticker}",
        "",
        f"**Date:** {date_str}",
        f"**Direction:** {thesis.direction.value.upper()}",
        f"**Conviction:** {thesis.conviction:.0%}",
        f"**Model:** {thesis.model_used}",
        "",
        "## Entry Rationale",
        "",
        thesis.entry_rationale,
        "",
        "## Bull Summary",
        "",
        thesis.bull_summary,
        "",
        "## Bear Summary",
        "",
        thesis.bear_summary,
        "",
    ]

    if thesis.risk_factors:
        lines.append("## Risk Factors")
        lines.append("")
        for factor in thesis.risk_factors:
            lines.append(f"- {factor}")
        lines.append("")

    lines.extend(
        [
            "## Recommended Action",
            "",
            thesis.recommended_action,
            "",
            "---",
            "",
            f"> {thesis.disclaimer}",
            "",
            f"> {DISCLAIMER_TEXT}",
            "",
        ]
    )

    content = "\n".join(lines)
    filepath.write_text(content, encoding="utf-8")
    console.print(f"[green]Report saved to {filepath}[/green]")


# ---------------------------------------------------------------------------
# health command
# ---------------------------------------------------------------------------


@app.command()
def health(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
) -> None:
    """Check the health of all external dependencies."""
    _configure_logging(verbose=verbose)
    asyncio.run(_health_async())


async def _health_async() -> None:
    """Run all health checks and display results."""
    from Option_Alpha.data import Database
    from Option_Alpha.services import HealthService

    db: Database | None = None
    try:
        db = Database(DEFAULT_DB_PATH)
        await db.connect()
    except Exception:
        db = None
        logging.getLogger(__name__).warning("Database connection failed for health check")

    health_service = HealthService(database=db)

    try:
        console.print("\n[bold]Running health checks...[/bold]\n")
        status = await health_service.check_all()

        table = Table(title="Health Status")
        table.add_column("Service", style="bold", width=15)
        table.add_column("Status", width=12)
        table.add_column("Details", width=40)

        # Ollama
        ollama_status = "[green]OK[/green]" if status.ollama_available else "[red]DOWN[/red]"
        models_str = ", ".join(status.ollama_models) if status.ollama_models else "none"
        table.add_row("Ollama", ollama_status, f"Models: {models_str}")

        # Anthropic
        anthropic_status = "[green]OK[/green]" if status.anthropic_available else "[red]DOWN[/red]"
        table.add_row(
            "Anthropic",
            anthropic_status,
            "API key configured"
            if status.anthropic_available
            else "Not configured or unreachable",
        )

        # yfinance
        yf_status = "[green]OK[/green]" if status.yfinance_available else "[red]DOWN[/red]"
        table.add_row("yfinance", yf_status, "SPY canary check")

        # SQLite
        sqlite_status = "[green]OK[/green]" if status.sqlite_available else "[red]DOWN[/red]"
        table.add_row("SQLite", sqlite_status, DEFAULT_DB_PATH)

        console.print(table)
        console.print(f"\n[dim]Last check: {status.last_check.isoformat()}[/dim]")

    finally:
        await health_service.aclose()
        if db is not None:
            await db.close()


# ---------------------------------------------------------------------------
# universe subcommands
# ---------------------------------------------------------------------------


@universe_app.command("refresh")
def universe_refresh(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
) -> None:
    """Refresh the CBOE optionable ticker universe."""
    _configure_logging(verbose=verbose)
    asyncio.run(_universe_refresh_async())


async def _universe_refresh_async() -> None:
    """Download and parse the latest CBOE optionable list."""
    from Option_Alpha.data import Database
    from Option_Alpha.services import RateLimiter, ServiceCache, UniverseService

    async with Database(DEFAULT_DB_PATH) as db:
        cache = ServiceCache(database=db)
        rate_limiter = RateLimiter()
        universe_service = UniverseService(cache=cache, rate_limiter=rate_limiter)

        try:
            console.print("[bold]Refreshing universe from CBOE...[/bold]")
            with Progress(
                SpinnerColumn(spinner_name="line"),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading...", total=None)
                tickers = await universe_service.refresh()
                progress.update(task, completed=1)

            console.print(f"[green]Universe refreshed: {len(tickers)} tickers loaded.[/green]")
        finally:
            await universe_service.aclose()


@universe_app.command("list")
def universe_list(
    sector: Annotated[str | None, typer.Option(help="Filter by GICS sector")] = None,
    preset: Annotated[
        str, typer.Option(help="Universe preset: full, sp500, midcap, smallcap, etfs")
    ] = "full",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
) -> None:
    """List tickers in the universe."""
    _configure_logging(verbose=verbose)
    asyncio.run(_universe_list_async(sector=sector, preset=preset))


async def _universe_list_async(
    *,
    sector: str | None,
    preset: str,
) -> None:
    """Display the ticker universe filtered by preset and/or sector."""
    from Option_Alpha.data import Database
    from Option_Alpha.services import RateLimiter, ServiceCache, UniverseService

    async with Database(DEFAULT_DB_PATH) as db:
        cache = ServiceCache(database=db)
        rate_limiter = RateLimiter()
        universe_service = UniverseService(cache=cache, rate_limiter=rate_limiter)

        try:
            universe = await universe_service.get_universe(preset=preset)

            if sector:
                universe = await universe_service.filter_by_sector(universe, sector=sector)

            if not universe:
                console.print("[yellow]No tickers found.[/yellow]")
                return

            table = Table(title=f"Universe: {preset}" + (f" / {sector}" if sector else ""))
            table.add_column("Symbol", style="bold", width=8)
            table.add_column("Name", width=30)
            table.add_column("Sector", width=25)
            table.add_column("Tier", width=12)
            table.add_column("Type", width=8)

            for t in universe[:100]:  # Cap at 100 for terminal readability
                table.add_row(t.symbol, t.name, t.sector, t.market_cap_tier, t.asset_type)

            console.print(table)

            if len(universe) > 100:
                console.print(f"[dim]... and {len(universe) - 100} more[/dim]")

            console.print(f"\n[dim]Total: {len(universe)} tickers[/dim]")
        finally:
            await universe_service.aclose()


@universe_app.command("stats")
def universe_stats(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
) -> None:
    """Display universe summary statistics."""
    _configure_logging(verbose=verbose)
    asyncio.run(_universe_stats_async())


async def _universe_stats_async() -> None:
    """Fetch and display universe statistics."""
    from Option_Alpha.data import Database
    from Option_Alpha.services import RateLimiter, ServiceCache, UniverseService

    async with Database(DEFAULT_DB_PATH) as db:
        cache = ServiceCache(database=db)
        rate_limiter = RateLimiter()
        universe_service = UniverseService(cache=cache, rate_limiter=rate_limiter)

        try:
            stats = await universe_service.get_stats()

            console.print("\n[bold underline]Universe Statistics[/bold underline]\n")
            console.print(f"Total:    {stats.total}")
            console.print(f"Active:   {stats.active}")
            console.print(f"Inactive: {stats.inactive}")

            if stats.by_tier:
                console.print("\n[bold]By Market Cap Tier:[/bold]")
                tier_table = Table(show_header=False)
                tier_table.add_column("Tier", width=15)
                tier_table.add_column("Count", justify="right", width=8)
                for tier, count in sorted(stats.by_tier.items()):
                    tier_table.add_row(tier, str(count))
                console.print(tier_table)

            if stats.by_sector:
                console.print("\n[bold]By Sector:[/bold]")
                sector_table = Table(show_header=False)
                sector_table.add_column("Sector", width=30)
                sector_table.add_column("Count", justify="right", width=8)
                for sector_name, count in sorted(
                    stats.by_sector.items(), key=lambda kv: kv[1], reverse=True
                ):
                    sector_table.add_row(sector_name, str(count))
                console.print(sector_table)
        finally:
            await universe_service.aclose()


# ---------------------------------------------------------------------------
# watchlist subcommands
# ---------------------------------------------------------------------------


@watchlist_app.command("create")
def watchlist_create(
    name: Annotated[str, typer.Argument(help="Name for the new watchlist")],
) -> None:
    """Create a new watchlist."""
    asyncio.run(_watchlist_create_async(name=name))


async def _watchlist_create_async(*, name: str) -> None:
    """Create a watchlist in the database."""
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        watchlist_id = await repo.create_watchlist(name)
        console.print(f"[green]Watchlist '{name}' created (ID: {watchlist_id})[/green]")


@watchlist_app.command("add")
def watchlist_add(
    watchlist_id: Annotated[int, typer.Argument(help="Watchlist ID")],
    tickers: Annotated[list[str], typer.Argument(help="Ticker symbols to add")],
) -> None:
    """Add tickers to a watchlist."""
    asyncio.run(
        _watchlist_add_async(
            watchlist_id=watchlist_id,
            tickers=[t.upper().strip() for t in tickers],
        )
    )


async def _watchlist_add_async(*, watchlist_id: int, tickers: list[str]) -> None:
    """Add tickers to a watchlist in the database."""
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        await repo.add_tickers_to_watchlist(watchlist_id, tickers)
        console.print(f"[green]Added {len(tickers)} ticker(s) to watchlist {watchlist_id}[/green]")


@watchlist_app.command("remove")
def watchlist_remove(
    watchlist_id: Annotated[int, typer.Argument(help="Watchlist ID")],
    tickers: Annotated[list[str], typer.Argument(help="Ticker symbols to remove")],
) -> None:
    """Remove tickers from a watchlist."""
    asyncio.run(
        _watchlist_remove_async(
            watchlist_id=watchlist_id,
            tickers=[t.upper().strip() for t in tickers],
        )
    )


async def _watchlist_remove_async(*, watchlist_id: int, tickers: list[str]) -> None:
    """Remove tickers from a watchlist in the database."""
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        await repo.remove_tickers_from_watchlist(watchlist_id, tickers)
        console.print(
            f"[green]Removed {len(tickers)} ticker(s) from watchlist {watchlist_id}[/green]"
        )


@watchlist_app.command("list")
def watchlist_list() -> None:
    """List all watchlists."""
    asyncio.run(_watchlist_list_async())


async def _watchlist_list_async() -> None:
    """Display all watchlists with their tickers."""
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        watchlists = await repo.list_watchlists()

        if not watchlists:
            console.print("[yellow]No watchlists found.[/yellow]")
            return

        table = Table(title="Watchlists")
        table.add_column("ID", justify="right", width=5)
        table.add_column("Name", style="bold", width=25)
        table.add_column("Created", width=20)
        table.add_column("Tickers", width=40)

        for wl in watchlists:
            tickers = await repo.get_watchlist_tickers(wl.id)
            tickers_str = ", ".join(tickers[:10])
            if len(tickers) > 10:
                tickers_str += f" ... (+{len(tickers) - 10} more)"
            elif not tickers:
                tickers_str = "(empty)"
            table.add_row(str(wl.id), wl.name, wl.created_at, tickers_str)

        console.print(table)


@watchlist_app.command("delete")
def watchlist_delete(
    watchlist_id: Annotated[int, typer.Argument(help="Watchlist ID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a watchlist and all its ticker associations."""
    if not force:
        confirm = typer.confirm(f"Delete watchlist {watchlist_id}? This cannot be undone")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(code=0)

    asyncio.run(_watchlist_delete_async(watchlist_id=watchlist_id))


async def _watchlist_delete_async(*, watchlist_id: int) -> None:
    """Delete a watchlist from the database."""
    from Option_Alpha.data import Database, Repository

    async with Database(DEFAULT_DB_PATH) as db:
        repo = Repository(db)
        await repo.delete_watchlist(watchlist_id)
        console.print(f"[green]Watchlist {watchlist_id} deleted.[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
