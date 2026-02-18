"""Tests for the /api/universe endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
UniverseService is mocked — no real CBOE downloads or network calls.
"""

import datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.market_data import TickerInfo, UniverseStats
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_universe_service


def _mock_universe_stats() -> UniverseStats:
    """Create a realistic UniverseStats for testing."""
    return UniverseStats(
        total=500,
        active=480,
        inactive=20,
        by_tier={"large_cap": 200, "mid_cap": 250, "etf": 50},
        by_sector={"Information Technology": 80, "Health Care": 60, "Financials": 55},
    )


def _mock_ticker_info(symbol: str, name: str = "") -> TickerInfo:
    """Create a TickerInfo for testing."""
    return TickerInfo(
        symbol=symbol,
        name=name or symbol,
        sector="Information Technology",
        market_cap_tier="large_cap",
        asset_type="equity",
        source="cboe",
        tags=["optionable"],
        status="active",
        discovered_at=datetime.datetime(2025, 1, 1, tzinfo=datetime.UTC),
    )


def _create_test_app(
    tickers: list[TickerInfo] | None = None,
    stats: UniverseStats | None = None,
) -> FastAPI:
    """Create a FastAPI app with mocked UniverseService for testing."""
    app = create_app()

    mock_svc = AsyncMock()
    mock_svc.get_stats = AsyncMock(return_value=stats or _mock_universe_stats())
    mock_svc.get_universe = AsyncMock(return_value=tickers or [])
    mock_svc.refresh = AsyncMock(return_value=tickers or [])
    mock_svc.aclose = AsyncMock()

    async def mock_get_universe_service() -> AsyncMock:  # type: ignore[type-arg]
        return mock_svc

    app.dependency_overrides[get_universe_service] = mock_get_universe_service

    return app


class TestListUniverse:
    """Tests for GET /api/universe."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """GET /api/universe should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_stats_and_tickers(self) -> None:
        """Response should contain stats, tickers, pagination fields."""
        tickers = [_mock_ticker_info("AAPL"), _mock_ticker_info("MSFT")]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe")

        body = response.json()
        assert "stats" in body
        assert "tickers" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert body["total"] == 2
        assert len(body["tickers"]) == 2

    @pytest.mark.asyncio
    async def test_pagination_limit(self) -> None:
        """Pagination should respect the limit parameter."""
        tickers = [_mock_ticker_info(f"T{i}") for i in range(10)]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe?limit=3")

        body = response.json()
        assert len(body["tickers"]) == 3
        assert body["total"] == 10
        assert body["limit"] == 3

    @pytest.mark.asyncio
    async def test_pagination_offset(self) -> None:
        """Pagination should respect the offset parameter."""
        tickers = [_mock_ticker_info(f"T{i}") for i in range(5)]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe?offset=3&limit=50")

        body = response.json()
        assert len(body["tickers"]) == 2  # 5 - 3 = 2 remaining
        assert body["offset"] == 3

    @pytest.mark.asyncio
    async def test_query_filter(self) -> None:
        """The q parameter should filter tickers by symbol."""
        tickers = [
            _mock_ticker_info("AAPL"),
            _mock_ticker_info("AMZN"),
            _mock_ticker_info("MSFT"),
        ]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe?q=A")

        body = response.json()
        assert body["total"] == 2  # AAPL, AMZN
        symbols = [t["symbol"] for t in body["tickers"]]
        assert "AAPL" in symbols
        assert "AMZN" in symbols

    @pytest.mark.asyncio
    async def test_empty_universe(self) -> None:
        """An empty universe should return zero tickers."""
        app = _create_test_app(tickers=[])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe")

        body = response.json()
        assert body["total"] == 0
        assert body["tickers"] == []


class TestRefreshUniverse:
    """Tests for POST /api/universe/refresh."""

    @pytest.mark.asyncio
    async def test_returns_202(self) -> None:
        """POST /api/universe/refresh should return HTTP 202 Accepted."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/universe/refresh")
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_returns_enqueued_status(self) -> None:
        """Response should indicate the refresh is enqueued."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/universe/refresh")

        body = response.json()
        assert body["status"] == "refresh_enqueued"


class TestSearchUniverse:
    """Tests for GET /api/universe/search."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """GET /api/universe/search?q=A should return HTTP 200."""
        tickers = [_mock_ticker_info("AAPL", "Apple Inc.")]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe/search?q=A")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_search_by_symbol(self) -> None:
        """Search should match by symbol."""
        tickers = [
            _mock_ticker_info("AAPL", "Apple Inc."),
            _mock_ticker_info("MSFT", "Microsoft Corp."),
        ]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe/search?q=AAPL")

        body = response.json()
        assert body["count"] == 1
        assert body["results"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_search_by_name(self) -> None:
        """Search should match by company name (case-insensitive)."""
        tickers = [
            _mock_ticker_info("AAPL", "Apple Inc."),
            _mock_ticker_info("MSFT", "Microsoft Corp."),
        ]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe/search?q=apple")

        body = response.json()
        assert body["count"] == 1
        assert body["results"][0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_search_no_results(self) -> None:
        """Search with no matches should return empty results."""
        tickers = [_mock_ticker_info("AAPL", "Apple Inc.")]
        app = _create_test_app(tickers=tickers)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe/search?q=ZZZZZ")

        body = response.json()
        assert body["count"] == 0
        assert body["results"] == []

    @pytest.mark.asyncio
    async def test_search_returns_query(self) -> None:
        """Response should echo the search query."""
        app = _create_test_app(tickers=[_mock_ticker_info("AAPL")])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/universe/search?q=AAPL")

        body = response.json()
        assert body["query"] == "AAPL"
