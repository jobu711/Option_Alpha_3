"""Scan API routes.

POST /api/scan       — Start a new scan pipeline (202 Accepted).
GET  /api/scan       — List recent scan runs (paginated).
GET  /api/scan/{id}  — Get a single scan run with ticker scores.
GET  /api/scan/{id}/stream — SSE stream of scan progress events.
"""

import asyncio
import datetime
import logging
import uuid
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from Option_Alpha.data.repository import Repository
from Option_Alpha.models.market_data import OHLCV
from Option_Alpha.models.scan import ScanRun, TickerScore
from Option_Alpha.web.deps import get_repository
from Option_Alpha.web.sse import ScanProgressEvent, create_sse_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scan", tags=["scan"])

# Active scan tasks keyed by scan_id. Storing references prevents
# fire-and-forget tasks from being garbage-collected and allows exception logging.
_scan_tasks: dict[str, asyncio.Task[None]] = {}

# ---------------------------------------------------------------------------
# Request / response models (web-layer input schemas)
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    """Input schema for starting a new scan."""

    model_config = ConfigDict(frozen=True)

    tickers: list[str] | None = None  # None = full universe
    top_n: int = 10


class ScanRunWithScores(BaseModel):
    """A scan run together with its associated ticker scores."""

    model_config = ConfigDict(frozen=True)

    scan_run: ScanRun
    scores: list[TickerScore]


# ---------------------------------------------------------------------------
# In-memory progress tracking for SSE
# ---------------------------------------------------------------------------

# Maps scan_id -> list of progress events queued for SSE consumers.
_scan_progress: dict[str, asyncio.Queue[ScanProgressEvent | None]] = {}


def _emit_progress(scan_id: str, phase: str, current: int, total: int) -> None:
    """Push a progress event to the queue for SSE consumers."""
    queue = _scan_progress.get(scan_id)
    if queue is not None:
        pct = (current / total * 100.0) if total > 0 else 0.0
        event = ScanProgressEvent(phase=phase, current=current, total=total, pct=pct)
        queue.put_nowait(event)


# ---------------------------------------------------------------------------
# Scan pipeline (runs as background task)
# ---------------------------------------------------------------------------


async def _run_scan_pipeline(
    scan_id: str,
    request: ScanRequest,
    repo: Repository,
) -> None:
    """Execute the 5-phase scan pipeline in the background.

    Mirrors the logic from ``cli.py._scan_async`` but reports progress
    via the in-memory SSE queue rather than rich console output.
    """
    from Option_Alpha.analysis import (
        apply_catalyst_adjustment,
        catalyst_proximity_score,
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
    from Option_Alpha.services import MarketDataService, RateLimiter, ServiceCache

    started_at = datetime.datetime.now(datetime.UTC)

    try:
        rate_limiter = RateLimiter()
        cache = ServiceCache()
        market_service = MarketDataService(rate_limiter=rate_limiter, cache=cache)

        # Phase 1: determine tickers and fetch OHLCV
        if request.tickers:
            ticker_symbols = [t.upper().strip() for t in request.tickers]
            logger.info(
                "Scan %s | Phase 1/5 UNIVERSE | %d tickers from request: %s",
                scan_id[:8],
                len(ticker_symbols),
                ", ".join(ticker_symbols),
            )
        else:
            from Option_Alpha.services import UniverseService

            universe_service = UniverseService(cache=cache, rate_limiter=rate_limiter)
            try:
                logger.info("Scan %s | Phase 1/5 UNIVERSE | Loading full universe...", scan_id[:8])
                universe = await universe_service.get_universe(preset="full")
                if not universe:
                    logger.info(
                        "Scan %s | Phase 1/5 UNIVERSE | Cache empty, refreshing...", scan_id[:8]
                    )
                    universe = await universe_service.refresh()
                    universe = await universe_service.get_universe(preset="full")
                ticker_symbols = [t.symbol for t in universe]
                logger.info(
                    "Scan %s | Phase 1/5 UNIVERSE | %d tickers loaded",
                    scan_id[:8],
                    len(ticker_symbols),
                )
            finally:
                await universe_service.aclose()

        total_tickers = len(ticker_symbols)
        _emit_progress(scan_id, "fetch_prices", 0, total_tickers)

        logger.info(
            "Scan %s | Phase 2/5 FETCH    | Fetching OHLCV for %d tickers...",
            scan_id[:8],
            total_tickers,
        )
        batch_results = await market_service.fetch_batch_ohlcv(ticker_symbols)

        ohlcv_data: dict[str, list[OHLCV]] = {}
        failed_tickers: list[str] = []
        for ticker_sym, result in batch_results.items():
            if not isinstance(result, Exception):
                ohlcv_data[ticker_sym] = result
            else:
                failed_tickers.append(ticker_sym)

        _emit_progress(scan_id, "fetch_prices", total_tickers, total_tickers)

        logger.info(
            "Scan %s | Phase 2/5 FETCH    | %d succeeded, %d failed",
            scan_id[:8],
            len(ohlcv_data),
            len(failed_tickers),
        )
        if failed_tickers:
            logger.warning(
                "Scan %s | Phase 2/5 FETCH    | Failed: %s",
                scan_id[:8],
                ", ".join(failed_tickers[:20]),
            )

        if not ohlcv_data:
            logger.warning("Scan %s: no OHLCV data retrieved, aborting", scan_id[:8])
            await _finalize_scan(repo, scan_id, started_at, "failed", 0, request.top_n)
            return

        # Phase 3: compute indicators and score
        logger.info(
            "Scan %s | Phase 3/5 INDICATE | Computing indicators for %d tickers...",
            scan_id[:8],
            len(ohlcv_data),
        )
        _emit_progress(scan_id, "compute_indicators", 0, len(ohlcv_data))

        universe_indicators: dict[str, dict[str, float]] = {}
        indicator_failures = 0

        for idx, (ticker_sym, bars) in enumerate(ohlcv_data.items(), start=1):
            try:
                close_prices = pd.Series([float(bar.close) for bar in bars], dtype=float)
                high_prices = pd.Series([float(bar.high) for bar in bars], dtype=float)
                low_prices = pd.Series([float(bar.low) for bar in bars], dtype=float)
                volume_series = pd.Series([float(bar.volume) for bar in bars], dtype=float)

                indicators: dict[str, float] = {}

                rsi_s = rsi(close_prices)
                if not rsi_s.dropna().empty:
                    indicators["rsi"] = float(rsi_s.dropna().iloc[-1])

                stoch_s = stoch_rsi(close_prices)
                if not stoch_s.dropna().empty:
                    indicators["stoch_rsi"] = float(stoch_s.dropna().iloc[-1])

                wr_s = williams_r(high_prices, low_prices, close_prices)
                if not wr_s.dropna().empty:
                    indicators["williams_r"] = float(wr_s.dropna().iloc[-1])

                adx_s = adx(high_prices, low_prices, close_prices)
                if not adx_s.dropna().empty:
                    indicators["adx"] = float(adx_s.dropna().iloc[-1])

                roc_s = roc(close_prices)
                if not roc_s.dropna().empty:
                    indicators["roc"] = float(roc_s.dropna().iloc[-1])

                st_s = supertrend(high_prices, low_prices, close_prices)
                if not st_s.dropna().empty:
                    indicators["supertrend"] = float(st_s.dropna().iloc[-1])

                atr_s = atr_percent(high_prices, low_prices, close_prices)
                if not atr_s.dropna().empty:
                    indicators["atr_percent"] = float(atr_s.dropna().iloc[-1])

                bb_s = bb_width(close_prices)
                if not bb_s.dropna().empty:
                    indicators["bb_width"] = float(bb_s.dropna().iloc[-1])

                kw_s = keltner_width(high_prices, low_prices, close_prices)
                if not kw_s.dropna().empty:
                    indicators["keltner_width"] = float(kw_s.dropna().iloc[-1])

                obv_s = obv_trend(close_prices, volume_series)
                if not obv_s.dropna().empty:
                    indicators["obv_trend"] = float(obv_s.dropna().iloc[-1])

                ad_s = ad_trend(high_prices, low_prices, close_prices, volume_series)
                if not ad_s.dropna().empty:
                    indicators["ad_trend"] = float(ad_s.dropna().iloc[-1])

                rv_s = relative_volume(volume_series)
                if not rv_s.dropna().empty:
                    indicators["relative_volume"] = float(rv_s.dropna().iloc[-1])

                sma_s = sma_alignment(close_prices)
                if not sma_s.dropna().empty:
                    indicators["sma_alignment"] = float(sma_s.dropna().iloc[-1])

                vwap_s = vwap_deviation(close_prices, volume_series)
                if not vwap_s.dropna().empty:
                    indicators["vwap_deviation"] = float(vwap_s.dropna().iloc[-1])

                if indicators:
                    universe_indicators[ticker_sym] = indicators
            except Exception as exc:  # noqa: BLE001
                indicator_failures += 1
                logger.warning("Scan %s | INDICATE | %s failed: %s", scan_id[:8], ticker_sym, exc)

            if idx % 50 == 0 or idx == len(ohlcv_data):
                logger.info(
                    "Scan %s | Phase 3/5 INDICATE | %d/%d tickers processed",
                    scan_id[:8],
                    idx,
                    len(ohlcv_data),
                )
            _emit_progress(scan_id, "compute_indicators", idx, len(ohlcv_data))

        logger.info(
            "Scan %s | Phase 3/5 INDICATE | Done — %d with indicators, %d failed",
            scan_id[:8],
            len(universe_indicators),
            indicator_failures,
        )

        if not universe_indicators:
            logger.warning("Scan %s: no indicators computed, aborting", scan_id[:8])
            await _finalize_scan(repo, scan_id, started_at, "failed", 0, request.top_n)
            return

        # Score universe
        logger.info(
            "Scan %s | Phase 4/5 SCORING  | Scoring %d tickers...",
            scan_id[:8],
            len(universe_indicators),
        )
        scored_tickers = score_universe(universe_indicators)
        _emit_progress(scan_id, "scoring", len(scored_tickers), len(scored_tickers))

        # Phase 4b: catalyst adjustment
        logger.info("Scan %s | Phase 4/5 CATALYST | Applying catalyst adjustments...", scan_id[:8])
        _emit_progress(scan_id, "catalysts", 0, len(scored_tickers))
        today = datetime.date.today()
        try:
            scored_tickers = [
                TickerScore(
                    ticker=t.ticker,
                    score=apply_catalyst_adjustment(
                        t.score,
                        catalyst_proximity_score(next_earnings=None, reference_date=today),
                    ),
                    signals=t.signals,
                    rank=t.rank,
                )
                for t in scored_tickers
            ]
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

        _emit_progress(scan_id, "catalysts", len(scored_tickers), len(scored_tickers))
        logger.info("Scan %s | Phase 4/5 CATALYST | Done", scan_id[:8])

        # Phase 5: persist
        logger.info(
            "Scan %s | Phase 5/5 PERSIST  | Saving top %d of %d scored tickers...",
            scan_id[:8],
            min(request.top_n, len(scored_tickers)),
            len(scored_tickers),
        )
        _emit_progress(scan_id, "persisting", 0, 1)

        completed_at = datetime.datetime.now(datetime.UTC)
        scan_run = ScanRun(
            id=scan_id,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            preset="api",
            sectors=[],
            ticker_count=len(scored_tickers),
            top_n=request.top_n,
        )

        await repo.save_scan_run(scan_run)
        await repo.save_ticker_scores(scan_id, scored_tickers[: request.top_n])

        _emit_progress(scan_id, "persisting", 1, 1)
        _emit_progress(scan_id, "complete", 1, 1)

        elapsed = (completed_at - started_at).total_seconds()
        logger.info(
            "Scan %s | COMPLETE | %d tickers scored, top %d saved (%.1fs elapsed)",
            scan_id[:8],
            len(scored_tickers),
            min(request.top_n, len(scored_tickers)),
            elapsed,
        )
        # Log the top results
        for ts in scored_tickers[: request.top_n]:
            logger.info(
                "Scan %s |  #%-3d %s  score=%.4f",
                scan_id[:8],
                ts.rank,
                ts.ticker.ljust(5),
                ts.score,
            )

    except Exception:
        logger.exception("Scan %s | FAILED   | Unexpected error", scan_id[:8])
        try:
            await _finalize_scan(repo, scan_id, started_at, "failed", 0, request.top_n)
        except Exception:
            logger.exception("Scan %s | FAILED   | Could not persist failure record", scan_id[:8])
    finally:
        # Signal SSE consumers that the stream is done
        queue = _scan_progress.get(scan_id)
        if queue is not None:
            queue.put_nowait(None)


async def _finalize_scan(
    repo: Repository,
    scan_id: str,
    started_at: datetime.datetime,
    status: str,
    ticker_count: int,
    top_n: int,
) -> None:
    """Persist a final scan run record (for failed/aborted scans)."""
    completed_at = datetime.datetime.now(datetime.UTC)
    scan_run = ScanRun(
        id=scan_id,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        preset="api",
        sectors=[],
        ticker_count=ticker_count,
        top_n=top_n,
    )
    await repo.save_scan_run(scan_run)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/", status_code=202, response_model=ScanRun)
async def start_scan(
    request: ScanRequest,
    repo: Annotated[Repository, Depends(get_repository)],
) -> ScanRun:
    """Start a new scan pipeline.

    Creates a ScanRun record and kicks off the scan as a background task.
    Returns the ScanRun immediately with its ID for polling or SSE streaming.
    """
    scan_id = str(uuid.uuid4())
    started_at = datetime.datetime.now(datetime.UTC)

    scan_run = ScanRun(
        id=scan_id,
        started_at=started_at,
        completed_at=None,
        status="running",
        preset="api",
        sectors=[],
        ticker_count=0,
        top_n=request.top_n,
    )

    # Persist the initial "running" state so GET /scan/{id} works immediately
    await repo.save_scan_run(scan_run)

    # Create SSE progress queue
    _scan_progress[scan_id] = asyncio.Queue()

    # Launch pipeline as background task with reference tracking
    task = asyncio.create_task(_run_scan_pipeline(scan_id, request, repo))
    _scan_tasks[scan_id] = task

    def _on_scan_done(t: asyncio.Task[None], *, _scan_id: str = scan_id) -> None:
        """Clean up task reference and log any unhandled exception."""
        _scan_tasks.pop(_scan_id, None)
        exc = t.exception() if not t.cancelled() else None
        if exc is not None:
            logger.error("Scan task %s failed: %s", _scan_id, exc)

    task.add_done_callback(_on_scan_done)

    tickers_desc = ", ".join(request.tickers) if request.tickers else "full universe"
    logger.info(
        "Scan %s | STARTED  | top_n=%d, tickers=%s",
        scan_id[:8],
        request.top_n,
        tickers_desc,
    )
    return scan_run


@router.get("/{scan_id}", response_model=ScanRunWithScores)
async def get_scan(
    scan_id: str,
    repo: Annotated[Repository, Depends(get_repository)],
) -> ScanRunWithScores:
    """Return a scan run with its associated ticker scores."""
    scan_run = await repo.get_scan_by_id(scan_id)
    if scan_run is None:
        raise HTTPException(status_code=404, detail=f"Scan run '{scan_id}' not found")

    scores = await repo.get_scores_for_scan(scan_id)
    return ScanRunWithScores(scan_run=scan_run, scores=scores)


@router.get("/{scan_id}/stream")
async def stream_scan_progress(scan_id: str) -> "EventSourceResponse":  # type: ignore[name-defined]  # noqa: F821
    """Stream scan progress events via Server-Sent Events.

    Yields JSON-encoded ScanProgressEvent objects until the scan completes.
    """
    from collections.abc import AsyncGenerator

    async def _progress_generator() -> AsyncGenerator[str]:
        queue = _scan_progress.get(scan_id)
        if queue is None:
            # Scan already completed or never existed — send a single complete event
            done = ScanProgressEvent(phase="complete", current=1, total=1, pct=100.0)
            yield done.model_dump_json()
            return

        while True:
            event = await queue.get()
            if event is None:
                # Stream is done
                break
            yield event.model_dump_json()

        # Clean up
        _scan_progress.pop(scan_id, None)

    return create_sse_response(_progress_generator())


@router.get("/", response_model=list[ScanRun])
async def list_scans(
    repo: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ScanRun]:
    """List recent scan runs with pagination."""
    return await repo.list_scan_runs(limit=limit, offset=offset)
