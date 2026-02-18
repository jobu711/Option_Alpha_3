"""Watchlist CRUD endpoints.

Provides list, add, and remove operations for watchlist ticker management.
Delegates all persistence to the Repository layer via dependency injection.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status
from pydantic import BaseModel, ConfigDict

from Option_Alpha.data.repository import Repository
from Option_Alpha.models.scan import WatchlistSummary
from Option_Alpha.web.deps import get_repository, validate_ticker_symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# Default watchlist name used for the single-watchlist API surface.
_DEFAULT_WATCHLIST_NAME = "default"


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class WatchlistAddRequest(BaseModel):
    """Request body for adding a ticker to the watchlist."""

    model_config = ConfigDict(frozen=True)

    ticker: str


class WatchlistItem(BaseModel):
    """A single ticker on the watchlist."""

    model_config = ConfigDict(frozen=True)

    ticker: str


class WatchlistResponse(BaseModel):
    """Full watchlist response with metadata and ticker list."""

    model_config = ConfigDict(frozen=True)

    watchlist: WatchlistSummary
    tickers: list[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _ensure_default_watchlist(repo: Repository) -> WatchlistSummary:
    """Return the default watchlist, creating it if it does not exist.

    The web API exposes a simplified single-watchlist interface.  The
    underlying Repository supports multiple named watchlists; this
    helper transparently manages the "default" one.
    """
    watchlists = await repo.list_watchlists()
    for wl in watchlists:
        if wl.name == _DEFAULT_WATCHLIST_NAME:
            return wl

    watchlist_id = await repo.create_watchlist(_DEFAULT_WATCHLIST_NAME)
    # Re-fetch to get the WatchlistSummary with created_at populated
    watchlists = await repo.list_watchlists()
    for wl in watchlists:
        if wl.id == watchlist_id:
            return wl

    # Fallback — should never happen
    msg = "Failed to retrieve default watchlist after creation."
    raise RuntimeError(msg)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=WatchlistResponse)
async def list_watchlist(
    repo: Annotated[Repository, Depends(get_repository)],
) -> WatchlistResponse:
    """Return all tickers on the default watchlist."""
    wl = await _ensure_default_watchlist(repo)
    tickers = await repo.get_watchlist_tickers(wl.id)
    logger.info("Watchlist retrieved: %d tickers", len(tickers))
    return WatchlistResponse(watchlist=wl, tickers=tickers)


@router.post("", response_model=WatchlistItem, status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    repo: Annotated[Repository, Depends(get_repository)],
) -> WatchlistItem:
    """Add a ticker to the default watchlist.

    The ticker is normalized to uppercase and validated against the
    standard symbol pattern before insertion.
    """
    # Validate / normalize the ticker via the shared validator
    normalized = await validate_ticker_symbol(body.ticker)
    wl = await _ensure_default_watchlist(repo)
    await repo.add_tickers_to_watchlist(wl.id, [normalized])
    logger.info("Ticker %s added to watchlist", normalized)
    return WatchlistItem(ticker=normalized)


@router.delete(
    "/{ticker}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def remove_from_watchlist(
    ticker: Annotated[str, Path(description="Ticker symbol to remove")],
    repo: Annotated[Repository, Depends(get_repository)],
) -> None:
    """Remove a ticker from the default watchlist."""
    normalized = await validate_ticker_symbol(ticker)
    wl = await _ensure_default_watchlist(repo)
    await repo.remove_tickers_from_watchlist(wl.id, [normalized])
    logger.info("Ticker %s removed from watchlist", normalized)
