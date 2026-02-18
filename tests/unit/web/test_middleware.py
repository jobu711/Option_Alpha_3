"""Tests for domain exception handlers and request logging middleware.

Verifies that each domain exception type maps to the correct HTTP status code
and returns a JSON response with a detail message.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from Option_Alpha.utils.exceptions import (
    DataFetchError,
    DataSourceUnavailableError,
    InsufficientDataError,
    RateLimitExceededError,
    TickerNotFoundError,
)
from Option_Alpha.web.middleware import (
    RequestLoggingMiddleware,
    _data_fetch_error_handler,
    _data_source_unavailable_handler,
    _insufficient_data_handler,
    _rate_limit_exceeded_handler,
    _ticker_not_found_handler,
    register_exception_handlers,
)


def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with exception handlers for testing."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/raise-ticker-not-found")
    async def raise_ticker_not_found() -> None:
        raise TickerNotFoundError("ZZZZ not found", ticker="ZZZZ", source="yfinance")

    @app.get("/raise-insufficient-data")
    async def raise_insufficient_data() -> None:
        raise InsufficientDataError("Not enough data for AAPL", ticker="AAPL", source="yfinance")

    @app.get("/raise-data-source-unavailable")
    async def raise_data_source_unavailable() -> None:
        raise DataSourceUnavailableError("yfinance is down", ticker="AAPL", source="yfinance")

    @app.get("/raise-rate-limit")
    async def raise_rate_limit() -> None:
        raise RateLimitExceededError("Rate limit hit", ticker="AAPL", source="yfinance")

    @app.get("/raise-data-fetch-error")
    async def raise_data_fetch_error() -> None:
        raise DataFetchError("Generic fetch error", ticker="AAPL", source="yfinance")

    return app


class TestExceptionHandlers:
    """Test that domain exceptions map to correct HTTP status codes."""

    def setup_method(self) -> None:
        """Create test client with exception handlers registered."""
        self.app = _make_test_app()
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_ticker_not_found_returns_404(self) -> None:
        """TickerNotFoundError should map to HTTP 404."""
        response = self.client.get("/raise-ticker-not-found")
        assert response.status_code == 404
        body = response.json()
        assert "detail" in body
        assert "ZZZZ" in body["detail"]

    def test_insufficient_data_returns_422(self) -> None:
        """InsufficientDataError should map to HTTP 422."""
        response = self.client.get("/raise-insufficient-data")
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body

    def test_data_source_unavailable_returns_503(self) -> None:
        """DataSourceUnavailableError should map to HTTP 503."""
        response = self.client.get("/raise-data-source-unavailable")
        assert response.status_code == 503
        body = response.json()
        assert "detail" in body

    def test_rate_limit_exceeded_returns_429(self) -> None:
        """RateLimitExceededError should map to HTTP 429."""
        response = self.client.get("/raise-rate-limit")
        assert response.status_code == 429
        body = response.json()
        assert "detail" in body

    def test_data_fetch_error_returns_502(self) -> None:
        """DataFetchError (base) should map to HTTP 502."""
        response = self.client.get("/raise-data-fetch-error")
        assert response.status_code == 502
        body = response.json()
        assert "detail" in body

    def test_exception_detail_contains_message(self) -> None:
        """Response detail should contain the exception message string."""
        response = self.client.get("/raise-ticker-not-found")
        body = response.json()
        assert body["detail"] == "ZZZZ not found"


class TestHandlerFunctions:
    """Test individual handler functions return correct JSONResponse."""

    @pytest.mark.asyncio
    async def test_ticker_not_found_handler(self) -> None:
        """_ticker_not_found_handler returns 404 JSONResponse."""
        exc = TickerNotFoundError("Not found", ticker="XYZ", source="test")
        # Create a mock request — handlers don't use the request object
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope=scope)
        result = await _ticker_not_found_handler(request, exc)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_insufficient_data_handler(self) -> None:
        """_insufficient_data_handler returns 422 JSONResponse."""
        exc = InsufficientDataError("No data", ticker="XYZ", source="test")
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope=scope)
        result = await _insufficient_data_handler(request, exc)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 422

    @pytest.mark.asyncio
    async def test_data_source_unavailable_handler(self) -> None:
        """_data_source_unavailable_handler returns 503 JSONResponse."""
        exc = DataSourceUnavailableError("Down", ticker="XYZ", source="test")
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope=scope)
        result = await _data_source_unavailable_handler(request, exc)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 503

    @pytest.mark.asyncio
    async def test_rate_limit_handler(self) -> None:
        """_rate_limit_exceeded_handler returns 429 JSONResponse."""
        exc = RateLimitExceededError("Throttled", ticker="XYZ", source="test")
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope=scope)
        result = await _rate_limit_exceeded_handler(request, exc)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 429

    @pytest.mark.asyncio
    async def test_data_fetch_error_handler(self) -> None:
        """_data_fetch_error_handler returns 502 JSONResponse."""
        exc = DataFetchError("Fetch failed", ticker="XYZ", source="test")
        scope = {"type": "http", "method": "GET", "path": "/test"}
        request = Request(scope=scope)
        result = await _data_fetch_error_handler(request, exc)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 502


class TestRequestLoggingMiddleware:
    """Test request logging middleware integration."""

    def test_middleware_logs_request(self, caplog: pytest.LogCaptureFixture) -> None:
        """RequestLoggingMiddleware should log method, path, status, and duration."""
        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)

        @app.get("/test-log")
        async def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        with caplog.at_level("INFO", logger="Option_Alpha.web.middleware"):
            response = client.get("/test-log")

        assert response.status_code == 200
        # Check that the log message contains method, path, and status
        assert any(
            "GET" in record.message and "/test-log" in record.message and "200" in record.message
            for record in caplog.records
        )
