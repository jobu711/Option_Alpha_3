"""Tests for the /api/scan endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
All services and repositories are mocked — no real network calls.
"""

import datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.scan import ScanRun, TickerScore
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_repository


def _mock_scan_run(
    *,
    scan_id: str = "test-scan-1",
    status: str = "completed",
) -> ScanRun:
    """Create a realistic ScanRun for testing."""
    return ScanRun(
        id=scan_id,
        started_at=datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.UTC),
        completed_at=datetime.datetime(2025, 6, 1, 12, 5, 0, tzinfo=datetime.UTC),
        status=status,
        preset="api",
        sectors=[],
        ticker_count=10,
        top_n=10,
    )


def _mock_ticker_scores() -> list[TickerScore]:
    """Create realistic TickerScore objects for testing."""
    return [
        TickerScore(ticker="AAPL", score=75.0, signals={"rsi": 45.0, "adx": 30.0}, rank=1),
        TickerScore(ticker="MSFT", score=70.0, signals={"rsi": 50.0, "adx": 25.0}, rank=2),
    ]


def _create_test_app() -> FastAPI:
    """Create a FastAPI app with mocked dependencies for testing."""
    app = create_app()

    mock_repo = AsyncMock()
    mock_repo.get_scan_by_id = AsyncMock(return_value=_mock_scan_run())
    mock_repo.get_scores_for_scan = AsyncMock(return_value=_mock_ticker_scores())
    mock_repo.list_scan_runs = AsyncMock(return_value=[_mock_scan_run()])
    mock_repo.save_scan_run = AsyncMock()
    mock_repo.save_ticker_scores = AsyncMock()

    async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
        return mock_repo

    app.dependency_overrides[get_repository] = mock_get_repository

    return app


class TestListScans:
    """Test GET /api/scan — list recent scan runs."""

    @pytest.mark.asyncio
    async def test_list_scans_returns_200(self) -> None:
        """GET /api/scan should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_scans_returns_list(self) -> None:
        """GET /api/scan should return a JSON array of scan runs."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/")
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["id"] == "test-scan-1"

    @pytest.mark.asyncio
    async def test_list_scans_pagination(self) -> None:
        """GET /api/scan?limit=5&offset=0 passes pagination params."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/?limit=5&offset=0")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_scans_empty(self) -> None:
        """GET /api/scan returns empty list when no scans exist."""
        app = _create_test_app()
        # Override to return empty
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[])

        async def mock_get_repo() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repo

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/")
        assert response.status_code == 200
        assert response.json() == []


class TestGetScan:
    """Test GET /api/scan/{id} — get a specific scan run with scores."""

    @pytest.mark.asyncio
    async def test_get_scan_returns_200(self) -> None:
        """GET /api/scan/{id} should return HTTP 200 for existing scan."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/test-scan-1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_scan_returns_scan_with_scores(self) -> None:
        """GET /api/scan/{id} should include scan_run and scores."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/test-scan-1")
        body = response.json()
        assert "scan_run" in body
        assert "scores" in body
        assert body["scan_run"]["id"] == "test-scan-1"
        assert len(body["scores"]) == 2
        assert body["scores"][0]["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_scan_not_found(self) -> None:
        """GET /api/scan/{id} should return 404 for non-existent scan."""
        app = _create_test_app()

        mock_repo = AsyncMock()
        mock_repo.get_scan_by_id = AsyncMock(return_value=None)

        async def mock_get_repo() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repo

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/scan/nonexistent-id")
        assert response.status_code == 404


class TestStartScan:
    """Test POST /api/scan — start a new scan pipeline."""

    @pytest.mark.asyncio
    async def test_start_scan_returns_202(self) -> None:
        """POST /api/scan should return HTTP 202 Accepted."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/scan/", json={"top_n": 5})
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_start_scan_returns_scan_run(self) -> None:
        """POST /api/scan should return a ScanRun with running status."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/scan/", json={"top_n": 10})
        body = response.json()
        assert body["status"] == "running"
        assert "id" in body

    @pytest.mark.asyncio
    async def test_start_scan_with_tickers(self) -> None:
        """POST /api/scan with specific tickers should return 202."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/scan/",
                json={"tickers": ["AAPL", "MSFT"], "top_n": 5},
            )
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_start_scan_default_body(self) -> None:
        """POST /api/scan with empty body uses defaults (full universe, top_n=10)."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/scan/", json={})
        assert response.status_code == 202
        body = response.json()
        assert body["top_n"] == 10
