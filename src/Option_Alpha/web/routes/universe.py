"""Universe browsing, search, and refresh endpoints.

Provides access to the CBOE optionable ticker universe via the existing
UniverseService. Supports paginated listing, text search, and background
refresh from the CBOE source.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict

from Option_Alpha.models.market_data import TickerInfo, UniverseStats
from Option_Alpha.services.universe import UniverseService
from Option_Alpha.web.deps import get_universe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/universe", tags=["universe"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class UniverseListResponse(BaseModel):
    """Paginated universe listing with summary statistics."""

    model_config = ConfigDict(frozen=True)

    stats: UniverseStats
    tickers: list[TickerInfo]
    total: int
    limit: int
    offset: int


class UniverseRefreshResponse(BaseModel):
    """Acknowledgement that a universe refresh has been enqueued."""

    model_config = ConfigDict(frozen=True)

    status: str


class UniverseSearchResponse(BaseModel):
    """Search results from the universe."""

    model_config = ConfigDict(frozen=True)

    query: str
    results: list[TickerInfo]
    count: int


# ---------------------------------------------------------------------------
# Background task helper
# ---------------------------------------------------------------------------


async def _refresh_universe(svc: UniverseService) -> None:
    """Execute the universe refresh in the background."""
    try:
        tickers = await svc.refresh()
        logger.info("Background universe refresh complete: %d tickers.", len(tickers))
    except Exception:
        logger.exception("Background universe refresh failed.")
    finally:
        await svc.aclose()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=UniverseListResponse)
async def list_universe(
    svc: Annotated[UniverseService, Depends(get_universe_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: Annotated[str, Query(max_length=10)] = "",
) -> UniverseListResponse:
    """Return universe stats and a paginated slice of tickers.

    Use ``?q=AAPL`` to filter by symbol prefix. Pagination via
    ``?limit=50&offset=0``.
    """
    stats = await svc.get_stats()
    all_tickers = await svc.get_universe(preset="full")

    # Apply optional text filter
    if q:
        query_upper = q.upper()
        all_tickers = [t for t in all_tickers if query_upper in t.symbol]

    total = len(all_tickers)
    page = all_tickers[offset : offset + limit]

    logger.info(
        "Universe list: total=%d, offset=%d, limit=%d, q=%r",
        total,
        offset,
        limit,
        q,
    )

    return UniverseListResponse(
        stats=stats,
        tickers=page,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/refresh",
    response_model=UniverseRefreshResponse,
    status_code=202,
)
async def refresh_universe(
    svc: Annotated[UniverseService, Depends(get_universe_service)],
    background_tasks: BackgroundTasks,
) -> UniverseRefreshResponse:
    """Trigger a CBOE universe refresh as a background task.

    Returns 202 Accepted immediately. The refresh runs asynchronously.
    """
    background_tasks.add_task(_refresh_universe, svc)
    logger.info("Universe refresh enqueued.")
    return UniverseRefreshResponse(status="refresh_enqueued")


@router.get("/search", response_model=UniverseSearchResponse)
async def search_universe(
    svc: Annotated[UniverseService, Depends(get_universe_service)],
    q: Annotated[str, Query(min_length=1, max_length=10, description="Search query")],
) -> UniverseSearchResponse:
    """Search universe tickers by symbol or name substring.

    Performs case-insensitive matching against both ``symbol`` and ``name``
    fields of the ticker universe.
    """
    all_tickers = await svc.get_universe(preset="full")

    query_upper = q.upper()
    query_lower = q.lower()
    results = [t for t in all_tickers if query_upper in t.symbol or query_lower in t.name.lower()]

    logger.info("Universe search q=%r: %d results", q, len(results))

    return UniverseSearchResponse(
        query=q,
        results=results,
        count=len(results),
    )
