"""Debate API routes.

POST /api/debate/{ticker} — Start a new AI debate (202 Accepted).
GET  /api/debate/{id}      — Get a debate result by ID.
GET  /api/debate            — List recent debates (paginated).
"""

import asyncio
import datetime
import logging
from decimal import Decimal
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from Option_Alpha.data.repository import Repository
from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.services.market_data import MarketDataService
from Option_Alpha.web.deps import (
    get_market_data_service,
    get_repository,
    validate_ticker_symbol,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debate", tags=["debate"])

# ---------------------------------------------------------------------------
# Response models (web-layer output schemas)
# ---------------------------------------------------------------------------


class DebateStarted(BaseModel):
    """Response confirming a debate has been started as a background task."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# Background debate task
# ---------------------------------------------------------------------------


async def _run_debate_task(
    ticker: str,
    market_service: MarketDataService,
    repo: Repository,
) -> None:
    """Execute the full debate pipeline in the background.

    Builds a MarketContext from live data, runs the DebateOrchestrator,
    and persists the result via the repository.
    """
    from Option_Alpha.agents import DebateOrchestrator, LLMClient
    from Option_Alpha.indicators import adx as compute_adx
    from Option_Alpha.indicators import rsi as compute_rsi

    try:
        # Fetch OHLCV data
        bars = await market_service.fetch_ohlcv(ticker)

        # Compute key indicators
        close_prices = pd.Series([float(bar.close) for bar in bars], dtype=float)
        high_prices = pd.Series([float(bar.high) for bar in bars], dtype=float)
        low_prices = pd.Series([float(bar.low) for bar in bars], dtype=float)

        rsi_series = compute_rsi(close_prices)
        rsi_val = float(rsi_series.dropna().iloc[-1]) if not rsi_series.dropna().empty else 50.0

        adx_series = compute_adx(high_prices, low_prices, close_prices)
        adx_val = float(adx_series.dropna().iloc[-1]) if not adx_series.dropna().empty else None

        # Get current price
        try:
            quote = await market_service.fetch_quote(ticker)
            current_price = quote.last
        except Exception:
            current_price = bars[-1].close
            logger.warning("Quote fetch failed, using last OHLCV close for %s", ticker)

        # Get ticker info for sector
        try:
            ticker_info = await market_service.fetch_ticker_info(ticker)
            sector = ticker_info.sector
        except Exception:
            sector = "Unknown"
            logger.warning("Ticker info fetch failed for %s, using Unknown sector", ticker)

        # 52-week high/low from OHLCV
        all_highs = [float(bar.high) for bar in bars]
        all_lows = [float(bar.low) for bar in bars]
        price_52w_high = Decimal(str(max(all_highs)))
        price_52w_low = Decimal(str(min(all_lows)))

        target_dte = 45
        now_utc = datetime.datetime.now(datetime.UTC)

        context = MarketContext(
            ticker=ticker,
            current_price=current_price,
            price_52w_high=price_52w_high,
            price_52w_low=price_52w_low,
            iv_rank=50.0,
            iv_percentile=50.0,
            atm_iv_30d=0.25,
            rsi_14=rsi_val,
            macd_signal="neutral",
            put_call_ratio=1.0,
            next_earnings=None,
            dte_target=target_dte,
            target_strike=current_price,
            target_delta=0.35,
            sector=sector,
            data_timestamp=now_utc,
        )

        llm_client = LLMClient()
        orchestrator = DebateOrchestrator(llm_client=llm_client, repository=repo)

        await orchestrator.run_debate(
            context,
            composite_score=50.0,
            iv_rank=context.iv_rank,
            rsi_14=rsi_val,
            adx=adx_val,
        )

        logger.info("Debate for %s completed and persisted", ticker)

    except Exception:
        logger.exception("Debate for %s failed with unexpected error", ticker)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.post("/{symbol}", status_code=202, response_model=DebateStarted)
async def start_debate(
    symbol: Annotated[str, Depends(validate_ticker_symbol)],
    repo: Annotated[Repository, Depends(get_repository)],
    market_service: Annotated[MarketDataService, Depends(get_market_data_service)],
) -> DebateStarted:
    """Start an AI debate for the given ticker symbol.

    Kicks off the debate pipeline as a background task and returns immediately.
    Poll GET /api/debate or use the ticker's debate history to retrieve results.
    """
    asyncio.create_task(_run_debate_task(symbol, market_service, repo))

    logger.info("Debate started for %s", symbol)
    return DebateStarted(
        ticker=symbol,
        status="running",
        message=f"Debate for {symbol} started. Poll GET /api/debate to check results.",
    )


@router.get("/{debate_id}", response_model=TradeThesis)
async def get_debate(
    debate_id: int,
    repo: Annotated[Repository, Depends(get_repository)],
) -> TradeThesis:
    """Return a debate result (TradeThesis) by its database ID."""
    thesis = await repo.get_debate_by_id(debate_id)
    if thesis is None:
        raise HTTPException(status_code=404, detail=f"Debate {debate_id} not found")
    return thesis


@router.get("/", response_model=list[TradeThesis])
async def list_debates(
    repo: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TradeThesis]:
    """List recent debates with pagination."""
    return await repo.list_debates(limit=limit, offset=offset)
