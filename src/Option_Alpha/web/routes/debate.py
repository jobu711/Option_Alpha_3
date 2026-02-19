"""Debate routes — ticker debate viewer with AI analysis and price charts."""

import datetime
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from Option_Alpha.agents.llm_client import LLMClient
from Option_Alpha.agents.orchestrator import DebateOrchestrator
from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.market_data import MarketDataService
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
    DataFetchError,
    TickerNotFoundError,
)
from Option_Alpha.web.app import get_db, templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/debate", response_class=HTMLResponse)
async def debate_landing(request: Request) -> HTMLResponse:
    """Render the debate landing page with a ticker search form."""
    return templates.TemplateResponse(
        "pages/debate.html",
        {
            "request": request,
            "active_page": "debate",
            "ticker": None,
            "thesis": None,
            "debates": [],
        },
    )


@router.get("/debate/{ticker}", response_class=HTMLResponse)
async def debate_page(
    request: Request,
    ticker: str,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the debate page for a specific ticker with history."""
    ticker = ticker.upper().strip()
    repo = Repository(db)
    debates = await repo.get_debate_history(ticker)
    latest: TradeThesis | None = debates[0] if debates else None
    return templates.TemplateResponse(
        "pages/debate.html",
        {
            "request": request,
            "active_page": "debate",
            "ticker": ticker,
            "thesis": latest,
            "debates": debates,
        },
    )


@router.post("/debate/{ticker}/run", response_class=HTMLResponse)
async def run_debate(
    request: Request,
    ticker: str,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Run a new AI debate for the ticker and return the result as HTMX partial."""
    ticker = ticker.upper().strip()
    repo = Repository(db)

    # Build services for fetching market data needed by the orchestrator
    rate_limiter = RateLimiter()
    cache = ServiceCache()
    market_service = MarketDataService(rate_limiter=rate_limiter, cache=cache)

    try:
        quote = await market_service.fetch_quote(ticker)
    except (TickerNotFoundError, DataFetchError) as exc:
        logger.warning("Failed to fetch quote for %s: %s", ticker, exc)
        return templates.TemplateResponse(
            "partials/debate_content.html",
            {
                "request": request,
                "ticker": ticker,
                "thesis": None,
                "error": f"Could not fetch market data for {ticker}.",
            },
            status_code=404,
        )

    # Build a minimal MarketContext for the debate
    context = MarketContext(
        ticker=ticker,
        current_price=quote.last,
        price_52w_high=quote.last,
        price_52w_low=quote.last,
        iv_rank=50.0,
        iv_percentile=50.0,
        atm_iv_30d=0.30,
        rsi_14=50.0,
        macd_signal="NEUTRAL",
        put_call_ratio=1.0,
        dte_target=45,
        target_strike=Decimal(str(round(float(quote.last), 0))),
        target_delta=0.30,
        sector="Unknown",
        data_timestamp=datetime.datetime.now(datetime.UTC),
    )

    # Run the debate via the orchestrator
    llm_client = LLMClient()
    orchestrator = DebateOrchestrator(llm_client=llm_client, repository=repo)

    try:
        thesis = await orchestrator.run_debate(context)
    except Exception:
        logger.exception("Debate failed for %s", ticker)
        return templates.TemplateResponse(
            "partials/debate_content.html",
            {
                "request": request,
                "ticker": ticker,
                "thesis": None,
                "error": f"Debate failed for {ticker}. Ollama may be unreachable.",
            },
            status_code=500,
        )

    return templates.TemplateResponse(
        "partials/debate_content.html",
        {
            "request": request,
            "ticker": ticker,
            "thesis": thesis,
            "error": None,
        },
    )


@router.get("/api/ticker/{ticker}/ohlcv")
async def ticker_ohlcv(
    ticker: str,
    period: str = "6mo",
) -> JSONResponse:
    """Return OHLCV data as JSON for Lightweight Charts consumption.

    Converts Decimal prices to float since charts require numeric values.
    """
    ticker = ticker.upper().strip()

    # Validate period parameter
    allowed_periods = {"1mo", "3mo", "6mo", "1y", "2y"}
    if period not in allowed_periods:
        return JSONResponse(
            {"error": f"Invalid period '{period}'. Allowed: {sorted(allowed_periods)}"},
            status_code=400,
        )

    rate_limiter = RateLimiter()
    cache = ServiceCache()
    service = MarketDataService(rate_limiter=rate_limiter, cache=cache)

    try:
        ohlcv_list = await service.fetch_ohlcv(ticker, period=period)
    except TickerNotFoundError:
        return JSONResponse(
            {"error": f"Ticker '{ticker}' not found."},
            status_code=404,
        )
    except DataFetchError as exc:
        logger.warning("OHLCV fetch failed for %s: %s", ticker, exc)
        return JSONResponse(
            {"error": f"Failed to fetch data for {ticker}."},
            status_code=502,
        )

    candles = [
        {
            "time": bar.date.isoformat(),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
        }
        for bar in ohlcv_list
    ]

    volume = [
        {
            "time": bar.date.isoformat(),
            "value": bar.volume,
            "color": "#34d39980" if bar.close >= bar.open else "#f8717180",
        }
        for bar in ohlcv_list
    ]

    return JSONResponse({"candles": candles, "volume": volume})
