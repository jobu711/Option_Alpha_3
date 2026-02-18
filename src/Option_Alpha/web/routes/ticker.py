"""Ticker detail API routes.

GET /api/ticker/{symbol}             — Ticker info and latest quote.
GET /api/ticker/{symbol}/indicators  — Computed indicator values for a ticker.
"""

import logging
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from Option_Alpha.models.market_data import Quote, TickerInfo
from Option_Alpha.services.market_data import MarketDataService
from Option_Alpha.web.deps import get_market_data_service, validate_ticker_symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ticker", tags=["ticker"])

# ---------------------------------------------------------------------------
# Response models (web-layer output schemas)
# ---------------------------------------------------------------------------


class TickerDetail(BaseModel):
    """Combined ticker info and latest quote snapshot."""

    model_config = ConfigDict(frozen=True)

    info: TickerInfo
    quote: Quote


class IndicatorValues(BaseModel):
    """Computed indicator values for a single ticker.

    Each indicator field is None when insufficient data prevents computation.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    rsi: float | None = None
    stoch_rsi: float | None = None
    williams_r: float | None = None
    adx: float | None = None
    roc: float | None = None
    supertrend: float | None = None
    atr_percent: float | None = None
    bb_width: float | None = None
    keltner_width: float | None = None
    obv_trend: float | None = None
    ad_trend: float | None = None
    relative_volume: float | None = None
    sma_alignment: float | None = None
    vwap_deviation: float | None = None


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


@router.get("/{symbol}", response_model=TickerDetail)
async def get_ticker(
    symbol: Annotated[str, Depends(validate_ticker_symbol)],
    market_service: Annotated[MarketDataService, Depends(get_market_data_service)],
) -> TickerDetail:
    """Return ticker metadata and the latest quote for the given symbol.

    Fetches TickerInfo and Quote via MarketDataService. Domain exceptions
    (TickerNotFoundError, DataSourceUnavailableError) propagate to middleware.
    """
    info = await market_service.fetch_ticker_info(symbol)
    quote = await market_service.fetch_quote(symbol)
    return TickerDetail(info=info, quote=quote)


@router.get("/{symbol}/indicators", response_model=IndicatorValues)
async def get_ticker_indicators(
    symbol: Annotated[str, Depends(validate_ticker_symbol)],
    market_service: Annotated[MarketDataService, Depends(get_market_data_service)],
) -> IndicatorValues:
    """Return computed technical indicator values for the given symbol.

    Fetches OHLCV data via MarketDataService, then computes all 14 available
    technical indicators. Any indicator that cannot be computed (insufficient
    data) is returned as None.
    """
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

    bars = await market_service.fetch_ohlcv(symbol)

    close_prices = pd.Series([float(bar.close) for bar in bars], dtype=float)
    high_prices = pd.Series([float(bar.high) for bar in bars], dtype=float)
    low_prices = pd.Series([float(bar.low) for bar in bars], dtype=float)
    volume_series = pd.Series([float(bar.volume) for bar in bars], dtype=float)

    def _last_or_none(series: "pd.Series[float]") -> float | None:
        """Return the last non-NaN value from a series, or None."""
        clean = series.dropna()
        if clean.empty:
            return None
        return float(clean.iloc[-1])

    return IndicatorValues(
        ticker=symbol,
        rsi=_last_or_none(rsi(close_prices)),
        stoch_rsi=_last_or_none(stoch_rsi(close_prices)),
        williams_r=_last_or_none(williams_r(high_prices, low_prices, close_prices)),
        adx=_last_or_none(adx(high_prices, low_prices, close_prices)),
        roc=_last_or_none(roc(close_prices)),
        supertrend=_last_or_none(supertrend(high_prices, low_prices, close_prices)),
        atr_percent=_last_or_none(atr_percent(high_prices, low_prices, close_prices)),
        bb_width=_last_or_none(bb_width(close_prices)),
        keltner_width=_last_or_none(keltner_width(high_prices, low_prices, close_prices)),
        obv_trend=_last_or_none(obv_trend(close_prices, volume_series)),
        ad_trend=_last_or_none(ad_trend(high_prices, low_prices, close_prices, volume_series)),
        relative_volume=_last_or_none(relative_volume(volume_series)),
        sma_alignment=_last_or_none(sma_alignment(close_prices)),
        vwap_deviation=_last_or_none(vwap_deviation(close_prices, volume_series)),
    )
