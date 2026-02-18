"""FastAPI application factory with lifespan, CORS, and router registration.

Creates and configures the FastAPI instance used by the Option Alpha web layer.
The lifespan context manager handles Database setup/teardown. CORS is restricted
to localhost origins (Vite dev server on 5173, FastAPI on 8000).
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Option_Alpha.data.database import Database
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.web.middleware import RequestLoggingMiddleware, register_exception_handlers
from Option_Alpha.web.routes.debate import router as debate_router
from Option_Alpha.web.routes.health import router as health_router
from Option_Alpha.web.routes.report import router as report_router
from Option_Alpha.web.routes.scan import router as scan_router
from Option_Alpha.web.routes.settings import router as settings_router
from Option_Alpha.web.routes.ticker import router as ticker_router
from Option_Alpha.web.routes.universe import router as universe_router
from Option_Alpha.web.routes.watchlist import router as watchlist_router

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure application logging.

    Sets the Option_Alpha namespace to INFO level so scan progress,
    request timing, and lifecycle events are visible in the terminal.
    Uses basicConfig to ensure a root handler exists (uvicorn provides
    one when running under ``uvicorn``, but tests and bare invocations
    may not).
    """
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        level=logging.WARNING,
    )
    logging.getLogger("Option_Alpha").setLevel(logging.INFO)


# Database path used by the lifespan context manager
_DB_PATH = "data/option_alpha.db"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan: connect Database on startup, close on shutdown."""
    db = Database(_DB_PATH)
    await db.connect()
    app.state.database = db

    # Shared singletons — rate limiter and cache must persist across requests
    # so that rate limiting actually works and cached data is reused.
    app.state.rate_limiter = RateLimiter()
    app.state.cache = ServiceCache()

    logger.info("Application startup complete — database connected.")
    try:
        yield
    finally:
        await db.close()
        logger.info("Application shutdown complete — database closed.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A fully configured FastAPI instance with CORS, exception handlers,
        request logging middleware, and all routers registered.
    """
    _configure_logging()

    app = FastAPI(
        title="Option Alpha",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=_lifespan,
    )

    # CORS — restricted to localhost origins only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Domain exception -> HTTP status handlers
    register_exception_handlers(app)

    # Routers — all under /api prefix
    app.include_router(health_router, prefix="/api")
    app.include_router(scan_router, prefix="/api")
    app.include_router(debate_router, prefix="/api")
    app.include_router(ticker_router, prefix="/api")
    app.include_router(watchlist_router, prefix="/api")
    app.include_router(universe_router, prefix="/api")
    app.include_router(report_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")

    return app
