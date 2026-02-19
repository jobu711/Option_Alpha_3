"""Watchlist routes — CRUD for watchlists and their tickers via HTMX."""

import logging

from fastapi import APIRouter, Depends, Form, Request
from starlette.responses import HTMLResponse

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.web.app import get_db, templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/watchlists", response_class=HTMLResponse)
async def watchlists_page(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the watchlists management page."""
    repo = Repository(db)
    watchlists = await repo.list_watchlists()
    return templates.TemplateResponse(
        "pages/watchlists.html",
        {"request": request, "active_page": "watchlists", "watchlists": watchlists},
    )


@router.post("/watchlists", response_class=HTMLResponse)
async def create_watchlist(
    request: Request,
    name: str = Form(...),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Create a new watchlist and return the updated list partial."""
    repo = Repository(db)
    await repo.create_watchlist(name)
    watchlists = await repo.list_watchlists()
    logger.info("Created watchlist '%s'", name)
    return templates.TemplateResponse(
        "partials/watchlist_list.html",
        {"request": request, "watchlists": watchlists},
    )


@router.delete("/watchlists/{watchlist_id}", response_class=HTMLResponse)
async def delete_watchlist(
    request: Request,
    watchlist_id: int,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Delete a watchlist and return the updated list partial."""
    repo = Repository(db)
    await repo.delete_watchlist(watchlist_id)
    watchlists = await repo.list_watchlists()
    logger.info("Deleted watchlist id=%d", watchlist_id)
    return templates.TemplateResponse(
        "partials/watchlist_list.html",
        {"request": request, "watchlists": watchlists},
    )


@router.get("/watchlists/{watchlist_id}/tickers", response_class=HTMLResponse)
async def watchlist_tickers(
    request: Request,
    watchlist_id: int,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Return the ticker list partial for a single watchlist."""
    repo = Repository(db)
    tickers = await repo.get_watchlist_tickers(watchlist_id)
    return templates.TemplateResponse(
        "partials/watchlist_list.html",
        {"request": request, "tickers": tickers, "watchlist_id": watchlist_id},
    )


@router.post("/watchlists/{watchlist_id}/tickers", response_class=HTMLResponse)
async def add_ticker(
    request: Request,
    watchlist_id: int,
    ticker: str = Form(...),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Add a ticker to a watchlist and return the updated ticker list partial."""
    repo = Repository(db)
    await repo.add_tickers_to_watchlist(watchlist_id, [ticker.upper()])
    tickers = await repo.get_watchlist_tickers(watchlist_id)
    logger.info("Added ticker '%s' to watchlist id=%d", ticker.upper(), watchlist_id)
    return templates.TemplateResponse(
        "partials/watchlist_list.html",
        {"request": request, "tickers": tickers, "watchlist_id": watchlist_id},
    )


@router.delete("/watchlists/{watchlist_id}/tickers/{ticker}", response_class=HTMLResponse)
async def remove_ticker(
    request: Request,
    watchlist_id: int,
    ticker: str,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Remove a ticker from a watchlist and return the updated ticker list partial."""
    repo = Repository(db)
    await repo.remove_tickers_from_watchlist(watchlist_id, [ticker])
    tickers = await repo.get_watchlist_tickers(watchlist_id)
    logger.info("Removed ticker '%s' from watchlist id=%d", ticker, watchlist_id)
    return templates.TemplateResponse(
        "partials/watchlist_list.html",
        {"request": request, "tickers": tickers, "watchlist_id": watchlist_id},
    )
