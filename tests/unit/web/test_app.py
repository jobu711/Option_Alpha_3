"""Tests for the FastAPI application factory.

Verifies create_app returns a properly configured FastAPI instance with
CORS middleware, exception handlers, and all expected routers registered.
"""

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from Option_Alpha.web.app import create_app


class TestCreateApp:
    """Test the create_app() factory function."""

    def test_returns_fastapi_instance(self) -> None:
        """create_app() should return a FastAPI instance."""
        app = create_app()
        assert isinstance(app, FastAPI)

    def test_app_title(self) -> None:
        """Application title should be 'Option Alpha'."""
        app = create_app()
        assert app.title == "Option Alpha"

    def test_app_version(self) -> None:
        """Application version should be '0.1.0'."""
        app = create_app()
        assert app.version == "0.1.0"

    def test_docs_url(self) -> None:
        """Swagger docs should be at /docs."""
        app = create_app()
        assert app.docs_url == "/docs"

    def test_redoc_disabled(self) -> None:
        """ReDoc should be disabled (None)."""
        app = create_app()
        assert app.redoc_url is None

    def test_cors_middleware_present(self) -> None:
        """CORS middleware should be registered on the app."""
        app = create_app()
        # FastAPI wraps middleware in a middleware stack; check for CORSMiddleware
        middleware_classes = [m.cls for m in app.user_middleware]
        assert CORSMiddleware in middleware_classes

    def test_cors_origins(self) -> None:
        """CORS should allow localhost:5173 and localhost:8000."""
        app = create_app()
        cors_middleware = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
        origins = cors_middleware.kwargs.get("allow_origins", [])
        assert "http://localhost:5173" in origins
        assert "http://localhost:8000" in origins

    def test_health_route_registered(self) -> None:
        """The /api/health route should be registered."""
        app = create_app()
        route_paths = [route.path for route in app.routes]  # type: ignore[union-attr]
        assert "/api/health" in route_paths

    def test_exception_handlers_registered(self) -> None:
        """Domain exception handlers should be registered."""
        from Option_Alpha.utils.exceptions import (
            DataFetchError,
            DataSourceUnavailableError,
            InsufficientDataError,
            RateLimitExceededError,
            TickerNotFoundError,
        )

        app = create_app()
        handlers = app.exception_handlers
        assert TickerNotFoundError in handlers
        assert InsufficientDataError in handlers
        assert DataSourceUnavailableError in handlers
        assert RateLimitExceededError in handlers
        assert DataFetchError in handlers
