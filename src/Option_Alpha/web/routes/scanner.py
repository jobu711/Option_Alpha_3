"""Scanner routes — scan history, results table, and SSE scan execution."""

import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse
from starlette.responses import HTMLResponse

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.web.app import get_db, templates
from Option_Alpha.web.scan_pipeline import ScanComplete, ScanProgress, run_scan_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/scanner", response_class=HTMLResponse)
async def scanner_page(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the scanner page with scan history and latest results."""
    repo = Repository(db)
    scans = await repo.list_scan_runs()
    latest = await repo.get_latest_scan()
    scores = await repo.get_scores_for_scan(latest.id) if latest else []
    return templates.TemplateResponse(
        "pages/scanner.html",
        {
            "request": request,
            "active_page": "scanner",
            "scans": scans,
            "latest_scan": latest,
            "scores": scores,
        },
    )


@router.get("/scanner/results", response_class=HTMLResponse)
async def scanner_results(
    request: Request,
    scan_id: str | None = None,
    sort: str = "score",
    direction: str = "desc",
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Return sorted scan results as an HTMX partial.

    Supports server-side sorting by any column. The ``sort`` parameter
    names the column and ``direction`` is ``asc`` or ``desc``.
    """
    repo = Repository(db)

    if scan_id:
        scores = await repo.get_scores_for_scan(scan_id)
    else:
        latest = await repo.get_latest_scan()
        scores = await repo.get_scores_for_scan(latest.id) if latest else []

    # Server-side sorting
    reverse = direction == "desc"
    if sort == "ticker":
        scores = sorted(scores, key=lambda s: s.ticker, reverse=reverse)
    elif sort == "rank":
        scores = sorted(scores, key=lambda s: s.rank, reverse=reverse)
    elif sort == "rsi":
        scores = sorted(scores, key=lambda s: s.signals.get("rsi", 0.0), reverse=reverse)
    elif sort == "adx":
        scores = sorted(scores, key=lambda s: s.signals.get("adx", 0.0), reverse=reverse)
    else:
        # Default: sort by score
        scores = sorted(scores, key=lambda s: s.score, reverse=reverse)

    return templates.TemplateResponse(
        "partials/scan_table.html",
        {
            "request": request,
            "scores": scores,
            "sort": sort,
            "direction": direction,
        },
    )


@router.get("/scanner/run")
async def run_scan(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> EventSourceResponse:
    """Run a scan and stream progress via Server-Sent Events."""

    async def event_generator() -> AsyncGenerator[dict[str, str]]:
        async for event in run_scan_pipeline(db):
            if isinstance(event, ScanComplete):
                html = templates.get_template("partials/scan_table.html").render(
                    {
                        "scores": event.scores,
                        "sort": "score",
                        "direction": "desc",
                    }
                )
                yield {"event": "complete", "data": html}
            elif isinstance(event, ScanProgress):
                html = templates.get_template("partials/scan_progress.html").render(
                    {"progress": event}
                )
                yield {"event": "progress", "data": html}

    return EventSourceResponse(event_generator())
