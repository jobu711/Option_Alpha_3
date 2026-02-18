"""Tests for the /api/debate endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
All services and repositories are mocked — no real network calls.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_market_data_service, get_repository


def _mock_trade_thesis() -> TradeThesis:
    """Create a realistic TradeThesis for testing."""
    return TradeThesis(
        direction=SignalDirection.BULLISH,
        conviction=0.72,
        entry_rationale="RSI at 35 suggests oversold conditions.",
        risk_factors=["High IV rank", "Earnings in 2 weeks"],
        recommended_action="Buy 45 DTE call spread",
        bull_summary="Strong technical oversold signal with volume confirmation.",
        bear_summary="Elevated IV suggests expensive premiums.",
        model_used="llama3.1:8b",
        total_tokens=1500,
        duration_ms=5000,
        disclaimer="This is not investment advice.",
    )


def _create_test_app() -> FastAPI:
    """Create a FastAPI app with mocked dependencies for testing."""
    app = create_app()

    mock_repo = AsyncMock()
    mock_repo.get_debate_by_id = AsyncMock(return_value=_mock_trade_thesis())
    mock_repo.list_debates = AsyncMock(return_value=[_mock_trade_thesis()])

    async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
        return mock_repo

    mock_market_service = AsyncMock()

    async def mock_get_market_data_service() -> AsyncMock:  # type: ignore[type-arg]
        return mock_market_service

    app.dependency_overrides[get_repository] = mock_get_repository
    app.dependency_overrides[get_market_data_service] = mock_get_market_data_service

    return app


class TestListDebates:
    """Test GET /api/debate — list recent debates."""

    @pytest.mark.asyncio
    async def test_list_debates_returns_200(self) -> None:
        """GET /api/debate should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_debates_returns_list(self) -> None:
        """GET /api/debate should return a JSON array of TradeThesis objects."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/")
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["direction"] == "bullish"

    @pytest.mark.asyncio
    async def test_list_debates_pagination(self) -> None:
        """GET /api/debate?limit=5&offset=0 passes pagination params."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/?limit=5&offset=0")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_debates_empty(self) -> None:
        """GET /api/debate returns empty list when no debates exist."""
        app = _create_test_app()

        mock_repo = AsyncMock()
        mock_repo.list_debates = AsyncMock(return_value=[])

        async def mock_get_repo() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repo

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/")
        assert response.status_code == 200
        assert response.json() == []


class TestGetDebate:
    """Test GET /api/debate/{id} — get a specific debate result."""

    @pytest.mark.asyncio
    async def test_get_debate_returns_200(self) -> None:
        """GET /api/debate/{id} should return HTTP 200 for existing debate."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_debate_returns_thesis(self) -> None:
        """GET /api/debate/{id} should return a TradeThesis shape."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/1")
        body = response.json()
        assert body["direction"] == "bullish"
        assert body["conviction"] == pytest.approx(0.72, abs=0.01)
        assert body["model_used"] == "llama3.1:8b"

    @pytest.mark.asyncio
    async def test_get_debate_not_found(self) -> None:
        """GET /api/debate/{id} should return 404 for non-existent debate."""
        app = _create_test_app()

        mock_repo = AsyncMock()
        mock_repo.get_debate_by_id = AsyncMock(return_value=None)

        async def mock_get_repo() -> AsyncMock:  # type: ignore[type-arg]
            return mock_repo

        app.dependency_overrides[get_repository] = mock_get_repo

        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_debate_thesis_fields(self) -> None:
        """GET /api/debate/{id} response should contain all TradeThesis fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/debate/1")
        body = response.json()
        expected_fields = [
            "direction",
            "conviction",
            "entry_rationale",
            "risk_factors",
            "recommended_action",
            "bull_summary",
            "bear_summary",
            "model_used",
            "total_tokens",
            "duration_ms",
            "disclaimer",
        ]
        for field in expected_fields:
            assert field in body, f"Missing field: {field}"


class TestStartDebate:
    """Test POST /api/debate/{ticker} — start a new debate."""

    @pytest.mark.asyncio
    async def test_start_debate_returns_202(self) -> None:
        """POST /api/debate/{ticker} should return HTTP 202 Accepted."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/debate/AAPL")
        assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_start_debate_returns_started_response(self) -> None:
        """POST /api/debate/{ticker} should return a DebateStarted response."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/debate/AAPL")
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["status"] == "running"
        assert "message" in body

    @pytest.mark.asyncio
    async def test_start_debate_normalizes_ticker(self) -> None:
        """POST /api/debate/{ticker} should normalize ticker to uppercase."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/debate/aapl")
        body = response.json()
        assert body["ticker"] == "AAPL"

    @pytest.mark.asyncio
    async def test_start_debate_invalid_ticker(self) -> None:
        """POST /api/debate/{ticker} should return 422 for invalid ticker."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/debate/TOOLONGTICKER")
        assert response.status_code == 422
