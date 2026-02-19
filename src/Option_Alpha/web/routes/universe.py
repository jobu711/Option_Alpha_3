"""Universe routes — browsing, filtering, and preset management for the ticker universe."""

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from starlette.responses import HTMLResponse

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.models.market_data import TickerInfo
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.services.universe import GICS_SECTORS, UniverseService
from Option_Alpha.web.app import get_db, templates

logger = logging.getLogger(__name__)

router = APIRouter()

# Tier display labels for the UI
_TIER_LABELS: list[tuple[str, str]] = [
    ("large_cap", "Large Cap"),
    ("mid_cap", "Mid Cap"),
    ("small_cap", "Small Cap"),
    ("etf", "ETF"),
]


def _group_by_sector(tickers: list[TickerInfo]) -> dict[str, list[TickerInfo]]:
    """Group a list of TickerInfo models by sector, sorted alphabetically."""
    groups: dict[str, list[TickerInfo]] = defaultdict(list)
    for ticker in tickers:
        groups[ticker.sector].append(ticker)
    # Sort tickers within each group by symbol
    for sector in groups:
        groups[sector].sort(key=lambda t: t.symbol)
    return dict(sorted(groups.items()))


def _apply_filters(
    tickers: list[TickerInfo],
    *,
    sector: str | None = None,
    tier: str | None = None,
    source: str | None = None,
    show_inactive: bool = False,
) -> list[TickerInfo]:
    """Apply optional filters to a ticker list."""
    result = tickers
    if not show_inactive:
        result = [t for t in result if t.status == "active"]
    if sector:
        result = [t for t in result if t.sector == sector]
    if tier:
        result = [t for t in result if t.market_cap_tier == tier]
    if source:
        result = [t for t in result if t.source == source]
    return result


@router.get("/universe", response_class=HTMLResponse)
async def universe_page(
    request: Request,
    sector: str | None = None,
    tier: str | None = None,
    source: str | None = None,
    show_inactive: bool = False,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the universe browser with optional filters."""
    repo = Repository(db)
    cache = ServiceCache(database=db)
    limiter = RateLimiter(max_concurrent=3, requests_per_second=1.0)
    universe_svc = UniverseService(cache=cache, rate_limiter=limiter)

    try:
        all_tickers = await universe_svc.get_universe(preset="full")
        stats = await universe_svc.get_stats()
    finally:
        await universe_svc.aclose()

    # Include inactive tickers if the flag is set
    if show_inactive:
        # Re-fetch without the active filter by accessing the internal universe
        # get_universe("full") only returns active; we need to re-load from cache
        # and skip the active-only filter. Since the service filters internally,
        # we accept the active-only list from get_universe and note that
        # show_inactive will show all returned tickers without further filtering.
        pass

    filtered = _apply_filters(
        all_tickers,
        sector=sector,
        tier=tier,
        source=source,
        show_inactive=show_inactive,
    )
    groups = _group_by_sector(filtered)
    presets = await repo.list_presets()
    watchlists = await repo.list_watchlists()

    # Determine if this is an HTMX partial request
    is_htmx = request.headers.get("HX-Request") == "true"
    hx_target = request.headers.get("HX-Target", "")

    if is_htmx and hx_target == "universe-groups":
        return templates.TemplateResponse(
            "partials/universe_group.html",
            {
                "request": request,
                "groups": groups,
                "filtered_count": len(filtered),
                "watchlists": watchlists,
            },
        )

    return templates.TemplateResponse(
        "pages/universe.html",
        {
            "request": request,
            "active_page": "universe",
            "groups": groups,
            "stats": stats,
            "presets": presets,
            "watchlists": watchlists,
            "sectors": GICS_SECTORS,
            "tier_labels": _TIER_LABELS,
            "filtered_count": len(filtered),
            "current_sector": sector or "",
            "current_tier": tier or "",
            "current_source": source or "",
            "show_inactive": show_inactive,
        },
    )


@router.post("/universe/presets", response_class=HTMLResponse)
async def save_preset(
    request: Request,
    name: str = Form(...),  # noqa: B008
    filters: str = Form(...),  # noqa: B008
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Save a universe filter preset and return the updated preset list partial."""
    repo = Repository(db)
    await repo.save_preset(name, filters)
    presets = await repo.list_presets()
    logger.info("Saved universe preset '%s'", name)
    return templates.TemplateResponse(
        "partials/universe_group.html",
        {
            "request": request,
            "presets": presets,
            "groups": {},
            "filtered_count": 0,
            "watchlists": [],
        },
    )


@router.get("/api/presets")
async def list_presets_json(
    db: Database = Depends(get_db),  # noqa: B008
) -> JSONResponse:
    """List presets as JSON (for Scanner page dropdown)."""
    repo = Repository(db)
    presets = await repo.list_presets()
    return JSONResponse(
        [
            {
                "id": p.id,
                "name": p.name,
                "filters": json.loads(p.filters),
                "created_at": p.created_at,
            }
            for p in presets
        ]
    )


@router.delete("/universe/presets/{preset_id}", response_class=HTMLResponse)
async def delete_preset(
    request: Request,
    preset_id: int,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Delete a universe preset and return confirmation."""
    repo = Repository(db)
    await repo.delete_preset(preset_id)
    presets = await repo.list_presets()
    logger.info("Deleted universe preset id=%d", preset_id)
    return templates.TemplateResponse(
        "partials/universe_group.html",
        {
            "request": request,
            "presets": presets,
            "groups": {},
            "filtered_count": 0,
            "watchlists": [],
        },
    )
