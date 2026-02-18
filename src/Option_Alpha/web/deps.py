"""Dependency injection providers for FastAPI route handlers.

All shared resources (Database, Repository, services) are provided via
FastAPI's ``Depends()`` mechanism. Route handlers never construct these
directly — they declare dependencies and FastAPI injects them.
"""

import logging
import re
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Request

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.services.health import HealthService
from Option_Alpha.services.market_data import MarketDataService
from Option_Alpha.services.options_data import OptionsDataService
from Option_Alpha.services.universe import UniverseService

logger = logging.getLogger(__name__)

# Ticker symbol validation pattern: 1-5 uppercase alphanumeric characters
_TICKER_PATTERN = re.compile(r"^[A-Z0-9]{1,5}$")


async def get_database(request: Request) -> AsyncGenerator[Database]:
    """Yield the Database instance from application state.

    The Database is created during application lifespan startup and stored
    in ``app.state.database``. This dependency yields it for the duration
    of the request.
    """
    db: Database = request.app.state.database
    yield db


async def get_repository(
    db: Annotated[Database, Depends(get_database)],
) -> Repository:
    """Return a Repository backed by the request-scoped Database."""
    return Repository(db)


async def get_market_data_service(request: Request) -> MarketDataService:
    """Return a MarketDataService using the app-wide rate limiter and cache.

    The shared RateLimiter and ServiceCache are created once during lifespan
    startup and stored on ``app.state`` so that rate limiting is effective
    and cached data persists across requests.
    """
    return MarketDataService(
        rate_limiter=request.app.state.rate_limiter,
        cache=request.app.state.cache,
    )


async def get_options_data_service(request: Request) -> OptionsDataService:
    """Return an OptionsDataService using the app-wide rate limiter and cache."""
    return OptionsDataService(
        rate_limiter=request.app.state.rate_limiter,
        cache=request.app.state.cache,
    )


async def get_health_service(
    db: Annotated[Database, Depends(get_database)],
) -> HealthService:
    """Return a HealthService with the request-scoped Database."""
    return HealthService(database=db)


async def get_universe_service(request: Request) -> UniverseService:
    """Return a UniverseService using the app-wide rate limiter and cache."""
    return UniverseService(
        cache=request.app.state.cache,
        rate_limiter=request.app.state.rate_limiter,
    )


async def validate_ticker_symbol(
    symbol: Annotated[str, Path(description="Ticker symbol (1-5 uppercase alphanumeric)")],
) -> str:
    """Validate and normalize a ticker symbol path parameter.

    Converts to uppercase and validates against the pattern ``^[A-Z0-9]{1,5}$``.
    Raises HTTP 422 if the symbol is invalid.

    Returns:
        The validated uppercase ticker symbol.
    """
    normalized = symbol.upper()
    if not _TICKER_PATTERN.match(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid ticker symbol: '{symbol}'. Must be 1-5 alphanumeric characters.",
        )
    return normalized
