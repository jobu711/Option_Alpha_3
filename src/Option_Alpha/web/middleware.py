"""Exception handlers and request logging middleware.

Maps domain exceptions from ``Option_Alpha.utils.exceptions`` to appropriate
HTTP status codes. Provides request logging middleware that logs method, path,
status code, and duration at INFO level.
"""

import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from Option_Alpha.utils.exceptions import (
    DataFetchError,
    DataSourceUnavailableError,
    InsufficientDataError,
    RateLimitExceededError,
    TickerNotFoundError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exception -> HTTP status handlers
# ---------------------------------------------------------------------------


async def _ticker_not_found_handler(request: Request, exc: TickerNotFoundError) -> JSONResponse:
    """Map TickerNotFoundError to HTTP 404."""
    logger.warning("Ticker not found: %s", exc)
    return JSONResponse(status_code=404, content={"detail": str(exc)})


async def _insufficient_data_handler(request: Request, exc: InsufficientDataError) -> JSONResponse:
    """Map InsufficientDataError to HTTP 422."""
    logger.warning("Insufficient data: %s", exc)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def _data_source_unavailable_handler(
    request: Request, exc: DataSourceUnavailableError
) -> JSONResponse:
    """Map DataSourceUnavailableError to HTTP 503."""
    logger.error("Data source unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": str(exc)})


async def _rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """Map RateLimitExceededError to HTTP 429."""
    logger.warning("Rate limit exceeded: %s", exc)
    return JSONResponse(status_code=429, content={"detail": str(exc)})


async def _data_fetch_error_handler(request: Request, exc: DataFetchError) -> JSONResponse:
    """Map base DataFetchError to HTTP 502 (catch-all for data errors)."""
    logger.error("Data fetch error: %s", exc)
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    """Register all domain exception handlers on the FastAPI application.

    More specific exception types must be registered before their base classes
    so FastAPI matches them correctly.
    """
    app.add_exception_handler(TickerNotFoundError, _ticker_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(InsufficientDataError, _insufficient_data_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DataSourceUnavailableError, _data_source_unavailable_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceededError, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DataFetchError, _data_fetch_error_handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request, log timing information, and return response."""
        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response
