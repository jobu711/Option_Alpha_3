"""Shared scan pipeline — async generator yielding progress events.

Extracted from ``cli.py`` so that both the CLI (rich terminal output) and
the web layer (SSE progress) can consume the same 5-phase pipeline without
duplicating business logic.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import pandas as pd

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.models.scan import ScanRun, TickerScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Progress / completion event types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanProgress:
    """A progress event emitted by the scan pipeline."""

    phase: int
    phase_name: str
    message: str
    current: int
    total: int


@dataclass(frozen=True)
class ScanComplete:
    """Terminal event emitted when the scan finishes successfully."""

    scan_run: ScanRun
    scores: list[TickerScore]
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Default constants (shared with cli.py)
# ---------------------------------------------------------------------------

DEFAULT_TOP_N: int = 50
DEFAULT_MIN_SCORE: float = 50.0
DEFAULT_DB_PATH: str = "data/options.db"
DEFAULT_OHLCV_PERIOD: str = "2y"


# ---------------------------------------------------------------------------
# Pipeline generator
# ---------------------------------------------------------------------------


async def run_scan_pipeline(
    db: Database,
    *,
    preset: str = "full",
    sector_list: list[str] | None = None,
    top_n: int = DEFAULT_TOP_N,
    min_score: float = DEFAULT_MIN_SCORE,
    cancelled: CancelFlag | None = None,
) -> AsyncGenerator[ScanProgress | ScanComplete]:
    """Execute the 5-phase scan pipeline, yielding progress events.

    Args:
        db: An already-connected Database instance.
        preset: Universe preset filter.
        sector_list: Optional GICS sector filter list.
        top_n: Number of top tickers to fetch options for.
        min_score: Minimum composite score threshold.
        cancelled: Optional cancellation flag checked between phases.

    Yields:
        ScanProgress for intermediate updates, ScanComplete when done.
    """
    # Lazy imports to avoid heavy startup cost
    from Option_Alpha.analysis import (
        apply_catalyst_adjustment,
        catalyst_proximity_score,
        determine_direction,
        recommend_contract,
        score_universe,
    )
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
    from Option_Alpha.models import SignalDirection
    from Option_Alpha.models.market_data import OHLCV, TickerInfo
    from Option_Alpha.services import (
        MarketDataService,
        OptionsDataService,
        RateLimiter,
        ServiceCache,
        UniverseService,
    )

    effective_sectors = sector_list or []
    scan_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.UTC)

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
        yield ScanProgress(
            phase=1,
            phase_name="Loading universe",
            message="Loading universe and fetching market data",
            current=0,
            total=5,
        )

        universe: list[TickerInfo] = await universe_service.get_universe(preset=preset)
        if not universe:
            logger.warning("Universe empty for preset '%s', attempting refresh", preset)
            universe = await universe_service.refresh()
            universe = await universe_service.get_universe(preset=preset)

        if effective_sectors:
            filtered_tickers: list[TickerInfo] = []
            for sector_name in effective_sectors:
                sector_tickers = await universe_service.filter_by_sector(
                    universe, sector=sector_name
                )
                filtered_tickers.extend(sector_tickers)
            universe = filtered_tickers

        if not universe:
            logger.error("No tickers found for preset=%s sectors=%s", preset, effective_sectors)
            return

        ticker_symbols = [t.symbol for t in universe]

        yield ScanProgress(
            phase=1,
            phase_name="Loading universe",
            message=f"Fetching OHLCV for {len(ticker_symbols)} tickers",
            current=0,
            total=len(ticker_symbols),
        )

        batch_results = await market_service.fetch_batch_ohlcv(ticker_symbols)

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
            logger.warning("%d tickers failed OHLCV fetch", len(fetch_failures))

        if not ohlcv_data:
            logger.error("No OHLCV data retrieved. Aborting scan.")
            return

        yield ScanProgress(
            phase=1,
            phase_name="Loading universe",
            message=f"Fetched data for {len(ohlcv_data)} tickers",
            current=1,
            total=5,
        )

        if cancelled is not None and cancelled.is_set:
            return

        # ---------------------------------------------------------------
        # Phase 2: Compute indicators, normalize, score, direction
        # ---------------------------------------------------------------
        yield ScanProgress(
            phase=2,
            phase_name="Computing indicators",
            message="Computing indicators and scoring",
            current=0,
            total=len(ohlcv_data),
        )

        universe_indicators: dict[str, dict[str, float]] = {}
        processed_count = 0

        for ticker_sym, bars in ohlcv_data.items():
            try:
                close_prices = pd.Series([float(bar.close) for bar in bars], dtype=float)
                high_prices = pd.Series([float(bar.high) for bar in bars], dtype=float)
                low_prices = pd.Series([float(bar.low) for bar in bars], dtype=float)
                volume_series = pd.Series([float(bar.volume) for bar in bars], dtype=float)

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

                if indicators:
                    universe_indicators[ticker_sym] = indicators
            except Exception as exc:  # noqa: BLE001
                logger.warning("Indicator computation failed for %s: %s", ticker_sym, exc)
                continue

            processed_count += 1
            if processed_count % 50 == 0:
                yield ScanProgress(
                    phase=2,
                    phase_name="Computing indicators",
                    message=f"Processed {processed_count}/{len(ohlcv_data)} tickers",
                    current=processed_count,
                    total=len(ohlcv_data),
                )

        if not universe_indicators:
            logger.error("No indicators computed. Aborting scan.")
            return

        # Score universe
        scored_tickers = score_universe(universe_indicators)
        scored_tickers = [t for t in scored_tickers if t.score >= min_score]

        if not scored_tickers:
            logger.warning("No tickers scored above threshold (%s).", min_score)
            return

        # Determine direction for each scored ticker
        ticker_directions: dict[str, SignalDirection] = {}
        for ts in scored_tickers:
            adx_val = ts.signals.get("adx", 0.0)
            rsi_val = ts.signals.get("rsi", 50.0)
            sma_val = ts.signals.get("sma_alignment", 0.0)
            ticker_directions[ts.ticker] = determine_direction(
                adx=adx_val, rsi=rsi_val, sma_alignment=sma_val
            )

        yield ScanProgress(
            phase=2,
            phase_name="Computing indicators",
            message=f"Scored {len(scored_tickers)} tickers above threshold",
            current=2,
            total=5,
        )

        if cancelled is not None and cancelled.is_set:
            return

        # ---------------------------------------------------------------
        # Phase 3: Catalyst proximity scoring
        # ---------------------------------------------------------------
        yield ScanProgress(
            phase=3,
            phase_name="Evaluating catalysts",
            message="Evaluating earnings catalysts",
            current=0,
            total=len(scored_tickers),
        )

        today = datetime.date.today()
        try:
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

            # Re-sort and re-rank
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

        yield ScanProgress(
            phase=3,
            phase_name="Evaluating catalysts",
            message=f"Catalyst adjustment applied to {len(scored_tickers)} tickers",
            current=3,
            total=5,
        )

        if cancelled is not None and cancelled.is_set:
            return

        # ---------------------------------------------------------------
        # Phase 4: Fetch option chains for top N
        # ---------------------------------------------------------------
        yield ScanProgress(
            phase=4,
            phase_name="Fetching options",
            message=f"Fetching option chains (top {top_n})",
            current=0,
            total=min(top_n, len(scored_tickers)),
        )

        top_tickers = scored_tickers[:top_n]

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
                        recommend_contract(contracts, direction)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Options fetch failed for %s: %s", ts.ticker, exc)
                    continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Options phase failed (continuing): %s", exc)

        yield ScanProgress(
            phase=4,
            phase_name="Fetching options",
            message=f"Options fetched for top {min(top_n, len(scored_tickers))} tickers",
            current=4,
            total=5,
        )

        if cancelled is not None and cancelled.is_set:
            return

        # ---------------------------------------------------------------
        # Phase 5: Persist results
        # ---------------------------------------------------------------
        yield ScanProgress(
            phase=5,
            phase_name="Persisting results",
            message="Persisting results to database",
            current=0,
            total=1,
        )

        completed_at = datetime.datetime.now(datetime.UTC)
        scan_run = ScanRun(
            id=scan_id,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            preset=preset,
            sectors=effective_sectors,
            ticker_count=len(scored_tickers),
            top_n=top_n,
        )

        try:
            await repo.save_scan_run(scan_run)
            await repo.save_ticker_scores(scan_id, scored_tickers)
            logger.info("Scan results persisted: %d tickers", len(scored_tickers))
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to persist scan results: %s", exc)

        elapsed = (completed_at - started_at).total_seconds()

        yield ScanComplete(
            scan_run=scan_run,
            scores=scored_tickers,
            elapsed_seconds=elapsed,
        )

    finally:
        await universe_service.aclose()


# ---------------------------------------------------------------------------
# Cancellation flag (simple mutable wrapper)
# ---------------------------------------------------------------------------


class CancelFlag:
    """Thread-safe-ish cancellation flag for the scan pipeline."""

    def __init__(self) -> None:
        self._cancelled: bool = False

    @property
    def is_set(self) -> bool:
        """Return True if cancellation has been requested."""
        return self._cancelled

    def set(self) -> None:
        """Request cancellation."""
        self._cancelled = True

    def reset(self) -> None:
        """Clear the cancellation flag."""
        self._cancelled = False
