"""Dashboard routes — latest scan summary and quick-action navigation."""

import logging

from fastapi import APIRouter, Depends, Request
from starlette.responses import HTMLResponse

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.web.app import get_db, templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Database = Depends(get_db)) -> HTMLResponse:  # noqa: B008
    """Render the dashboard page with latest scan summary."""
    repo = Repository(db)
    scan = await repo.get_latest_scan()
    scores = await repo.get_scores_for_scan(scan.id) if scan else []
    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "active_page": "dashboard",
            "scan": scan,
            "scores": scores[:5],
        },
    )
