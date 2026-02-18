"""Tests for the /api/watchlist endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
Repository is mocked — no real database calls.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.scan import WatchlistSummary
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_repository


def _mock_watchlist_summary(
    watchlist_id: int = 1,
    name: str = "default",
) -> WatchlistSummary:
    """Create a realistic WatchlistSummary for testing."""
    return WatchlistSummary(
        id=watchlist_id,
        name=name,
        created_at="2025-06-15T10:00:00Z",
    )


def _create_test_app(
    watchlists: list[WatchlistSummary] | None = None,
    tickers: list[str] | None = None,
) -> FastAPI:
    """Create a FastAPI app with mocked repository for testing."""
    app = create_app()

    mock_repo = AsyncMock()
    wl_list = watchlists if watchlists is not None else [_mock_watchlist_summary()]
    mock_repo.list_watchlists = AsyncMock(return_value=wl_list)
    mock_repo.get_watchlist_tickers = AsyncMock(return_value=tickers or [])
    mock_repo.create_watchlist = AsyncMock(return_value=1)
    mock_repo.add_tickers_to_watchlist = AsyncMock()
    mock_repo.remove_tickers_from_watchlist = AsyncMock()

    async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
        return mock_repo

    app.dependency_overrides[get_repository] = mock_get_repository

    return app


class TestListWatchlist:
    """Tests for GET /api/watchlist."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """GET /api/watchlist should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/watchlist")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_watchlist_shape(self) -> None:
        """Response should contain watchlist metadata and tickers list."""
        app = _create_test_app(tickers=["AAPL", "MSFT"])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/watchlist")

        body = response.json()
        assert "watchlist" in body
        assert "tickers" in body
        assert body["tickers"] == ["AAPL", "MSFT"]
        assert body["watchlist"]["name"] == "default"

    @pytest.mark.asyncio
    async def test_empty_watchlist(self) -> None:
        """An empty watchlist should return an empty ticker list."""
        app = _create_test_app(tickers=[])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/watchlist")

        body = response.json()
        assert body["tickers"] == []

    @pytest.mark.asyncio
    async def test_creates_default_watchlist_if_missing(self) -> None:
        """If no default watchlist exists, one should be created."""
        # Start with no watchlists, then after create_watchlist, return the new one
        app = create_app()
        mock_repo = AsyncMock()

        call_count = 0

        async def dynamic_list_watchlists() -> list[WatchlistSummary]:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return []
            return [_mock_watchlist_summary()]

        mock_repo.list_watchlists = AsyncMock(side_effect=dynamic_list_watchlists)
        mock_repo.create_watchlist = AsyncMock(return_value=1)
        mock_repo.get_watchlist_tickers = AsyncMock(return_value=[])

        async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repository

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/watchlist")

        assert response.status_code == 200
        mock_repo.create_watchlist.assert_called_once_with("default")


class TestAddToWatchlist:
    """Tests for POST /api/watchlist."""

    @pytest.mark.asyncio
    async def test_add_returns_201(self) -> None:
        """POST /api/watchlist should return HTTP 201 on success."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/watchlist",
                json={"ticker": "AAPL"},
            )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_add_returns_ticker(self) -> None:
        """Response should contain the normalized ticker symbol."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/watchlist",
                json={"ticker": "aapl"},
            )

        body = response.json()
        assert body["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_add_normalizes_to_uppercase(self) -> None:
        """Lowercase ticker input should be normalized to uppercase."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/watchlist",
                json={"ticker": "msft"},
            )

        body = response.json()
        assert body["ticker"] == "MSFT"

    @pytest.mark.asyncio
    async def test_add_invalid_ticker_returns_422(self) -> None:
        """Invalid ticker symbols should return HTTP 422."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/watchlist",
                json={"ticker": "TOOLONG"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_empty_ticker_returns_422(self) -> None:
        """Empty ticker should return HTTP 422."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/watchlist",
                json={"ticker": ""},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_add_missing_body_returns_422(self) -> None:
        """Missing request body should return HTTP 422."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/watchlist")
        assert response.status_code == 422


class TestRemoveFromWatchlist:
    """Tests for DELETE /api/watchlist/{ticker}."""

    @pytest.mark.asyncio
    async def test_delete_returns_204(self) -> None:
        """DELETE /api/watchlist/AAPL should return HTTP 204."""
        app = _create_test_app(tickers=["AAPL"])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/watchlist/AAPL")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_no_content_body(self) -> None:
        """DELETE response body should be empty."""
        app = _create_test_app(tickers=["AAPL"])
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/watchlist/AAPL")
        assert response.content == b""

    @pytest.mark.asyncio
    async def test_delete_normalizes_ticker(self) -> None:
        """Lowercase ticker in path should be normalized to uppercase before removal."""
        app = create_app()
        mock_repo = AsyncMock()
        mock_repo.list_watchlists = AsyncMock(return_value=[_mock_watchlist_summary()])
        mock_repo.remove_tickers_from_watchlist = AsyncMock()

        async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repository

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/watchlist/aapl")

        assert response.status_code == 204
        mock_repo.remove_tickers_from_watchlist.assert_called_once_with(1, ["AAPL"])

    @pytest.mark.asyncio
    async def test_delete_invalid_ticker_returns_422(self) -> None:
        """Invalid ticker symbols in DELETE path should return HTTP 422."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/watchlist/TOOLONG")
        assert response.status_code == 422
