"""Health routes — service dependency status page with HTMX recheck."""

import logging

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse

from Option_Alpha.data.database import Database
from Option_Alpha.services.health import HealthService
from Option_Alpha.web.app import get_db, templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_class=HTMLResponse)
async def health_page(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the health status page with current service checks."""
    service = HealthService(database=db)
    try:
        status = await service.check_all()
    finally:
        await service.aclose()
    return templates.TemplateResponse(
        "pages/health.html",
        {"request": request, "active_page": "health", "status": status},
    )


@router.post("/health/recheck", response_class=HTMLResponse)
async def recheck(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Re-run all health checks and return the status partial for HTMX swap."""
    service = HealthService(database=db)
    try:
        status = await service.check_all()
    finally:
        await service.aclose()
    logger.info("Health recheck completed")
    return templates.TemplateResponse(
        "partials/health_status.html",
        {"request": request, "status": status},
    )
