"""Tests for the /health endpoint.

Uses httpx.AsyncClient with ASGITransport for async route testing.
All external service checks are mocked — no real network calls.
"""

import datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.health import HealthStatus
from Option_Alpha.web.app import create_app


def _mock_health_status() -> HealthStatus:
    """Create a realistic HealthStatus for testing."""
    return HealthStatus(
        ollama_available=True,
        anthropic_available=False,
        yfinance_available=True,
        sqlite_available=True,
        ollama_models=["llama3.1:8b"],
        last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


def _create_test_app() -> FastAPI:
    """Create a FastAPI app with mocked health service for testing."""
    app = create_app()

    # Override the health service dependency to avoid real network calls
    from Option_Alpha.web.deps import get_health_service

    mock_health_service = AsyncMock()
    mock_health_service.check_all = AsyncMock(return_value=_mock_health_status())

    async def mock_get_health_service() -> AsyncMock:  # type: ignore[type-arg]
        return mock_health_service

    app.dependency_overrides[get_health_service] = mock_get_health_service

    return app


class TestHealthEndpoint:
    """Test the GET /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self) -> None:
        """GET /health should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_health_status_shape(self) -> None:
        """GET /health should return a JSON body matching HealthStatus fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        body = response.json()
        assert "ollama_available" in body
        assert "anthropic_available" in body
        assert "yfinance_available" in body
        assert "sqlite_available" in body
        assert "ollama_models" in body
        assert "last_check" in body

    @pytest.mark.asyncio
    async def test_health_values_match_mock(self) -> None:
        """GET /health should return values from the mocked health service."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        body = response.json()
        assert body["ollama_available"] is True
        assert body["anthropic_available"] is False
        assert body["yfinance_available"] is True
        assert body["sqlite_available"] is True
        assert body["ollama_models"] == ["llama3.1:8b"]

    @pytest.mark.asyncio
    async def test_health_response_is_valid_health_status(self) -> None:
        """GET /health response should be parseable as a HealthStatus model."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        # Validate the response body round-trips through the Pydantic model
        status = HealthStatus.model_validate(response.json())
        assert status.ollama_available is True
        assert len(status.ollama_models) == 1

    @pytest.mark.asyncio
    async def test_health_endpoint_tagged(self) -> None:
        """The health route should have the 'health' tag for OpenAPI docs."""
        app = _create_test_app()
        # Find the health route and verify its tags
        health_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/health"  # type: ignore[union-attr]
        ]
        assert len(health_routes) == 1
        route = health_routes[0]
        assert "health" in route.tags  # type: ignore[union-attr]
