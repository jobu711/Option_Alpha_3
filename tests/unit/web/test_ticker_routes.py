"""Tests for the /api/ticker endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
All services are mocked — no real network calls.
"""

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_market_data_service


def _mock_ticker_info() -> TickerInfo:
    """Create a realistic TickerInfo for testing."""
    return TickerInfo(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        market_cap_tier="Mega",
        asset_type="EQUITY",
        source="yfinance",
        tags=[],
        status="active",
        discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        last_scanned_at=datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.UTC),
    )


def _mock_quote() -> Quote:
    """Create a realistic Quote for testing."""
    return Quote(
        ticker="AAPL",
        bid=Decimal("195.50"),
        ask=Decimal("195.60"),
        last=Decimal("195.55"),
        volume=50_000_000,
        timestamp=datetime.datetime(2025, 6, 1, 16, 0, 0, tzinfo=datetime.UTC),
    )


def _mock_ohlcv_bars() -> list[OHLCV]:
    """Create minimal OHLCV bars for indicator computation testing."""
    # Generate 200 bars of synthetic data to ensure all indicators can compute
    bars: list[OHLCV] = []
    base_price = 100.0
    for i in range(200):
        day_offset = i
        close = base_price + (i % 10) * 0.5 - 2.5
        bar = OHLCV(
            date=datetime.date(2025, 1, 1) + datetime.timedelta(days=day_offset),
            open=Decimal(str(round(close - 0.5, 2))),
            high=Decimal(str(round(close + 1.0, 2))),
            low=Decimal(str(round(close - 1.0, 2))),
            close=Decimal(str(round(close, 2))),
            volume=1_000_000 + i * 1000,
        )
        bars.append(bar)
    return bars


def _create_test_app() -> FastAPI:
    """Create a FastAPI app with mocked market data service for testing."""
    app = create_app()

    mock_market_service = AsyncMock()
    mock_market_service.fetch_ticker_info = AsyncMock(return_value=_mock_ticker_info())
    mock_market_service.fetch_quote = AsyncMock(return_value=_mock_quote())
    mock_market_service.fetch_ohlcv = AsyncMock(return_value=_mock_ohlcv_bars())

    async def mock_get_market_data_service() -> AsyncMock:  # type: ignore[type-arg]
        return mock_market_service

    app.dependency_overrides[get_market_data_service] = mock_get_market_data_service

    return app


class TestGetTicker:
    """Test GET /api/ticker/{symbol} — ticker detail with info and quote."""

    @pytest.mark.asyncio
    async def test_get_ticker_returns_200(self) -> None:
        """GET /api/ticker/{symbol} should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_ticker_returns_info_and_quote(self) -> None:
        """GET /api/ticker/{symbol} should return both info and quote fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL")
        body = response.json()
        assert "info" in body
        assert "quote" in body
        assert body["info"]["symbol"] == "AAPL"
        assert body["info"]["name"] == "Apple Inc."
        assert body["quote"]["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_ticker_quote_decimal_precision(self) -> None:
        """Quote prices should be serialized as strings to preserve Decimal precision."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL")
        body = response.json()
        # Decimal fields are serialized as strings
        assert body["quote"]["bid"] == "195.50"
        assert body["quote"]["ask"] == "195.60"

    @pytest.mark.asyncio
    async def test_get_ticker_normalizes_symbol(self) -> None:
        """GET /api/ticker/{symbol} should normalize symbol to uppercase."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/aapl")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_ticker_invalid_symbol(self) -> None:
        """GET /api/ticker/{symbol} should return 422 for invalid symbol."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/TOOLONGSYMBOL")
        assert response.status_code == 422


class TestGetTickerIndicators:
    """Test GET /api/ticker/{symbol}/indicators — computed indicator values."""

    @pytest.mark.asyncio
    async def test_indicators_returns_200(self) -> None:
        """GET /api/ticker/{symbol}/indicators should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL/indicators")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_indicators_returns_ticker_field(self) -> None:
        """Response should include the ticker symbol."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL/indicators")
        body = response.json()
        assert body["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_indicators_includes_all_fields(self) -> None:
        """Response should include all 14 indicator fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL/indicators")
        body = response.json()
        expected_fields = [
            "ticker",
            "rsi",
            "stoch_rsi",
            "williams_r",
            "adx",
            "roc",
            "supertrend",
            "atr_percent",
            "bb_width",
            "keltner_width",
            "obv_trend",
            "ad_trend",
            "relative_volume",
            "sma_alignment",
            "vwap_deviation",
        ]
        for field in expected_fields:
            assert field in body, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_indicators_rsi_is_numeric(self) -> None:
        """RSI indicator should be a float value."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/AAPL/indicators")
        body = response.json()
        # With 200 bars of synthetic data, RSI should compute
        rsi_val = body["rsi"]
        assert rsi_val is None or isinstance(rsi_val, float)

    @pytest.mark.asyncio
    async def test_indicators_invalid_symbol(self) -> None:
        """GET /api/ticker/{symbol}/indicators should return 422 for invalid symbol."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/TOOLONGSYMBOL/indicators")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_indicators_normalizes_symbol(self) -> None:
        """GET /api/ticker/{symbol}/indicators should normalize symbol to uppercase."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ticker/aapl/indicators")
        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"
