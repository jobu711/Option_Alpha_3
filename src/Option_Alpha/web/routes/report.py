"""Report download endpoint.

Generates and serves analysis reports for completed debates. Reports are
produced by the existing ``reporting/markdown.py`` module and always include
the mandatory disclaimer from ``reporting/disclaimer.py``.
"""

import datetime
import io
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from Option_Alpha.data.repository import Repository
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT
from Option_Alpha.reporting.markdown import generate_markdown_report
from Option_Alpha.web.deps import get_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{debate_id}")
async def download_report(
    debate_id: Annotated[int, Path(description="AI thesis database ID", ge=1)],
    repo: Annotated[Repository, Depends(get_repository)],
    format: Annotated[str, Query(pattern=r"^md$")] = "md",  # noqa: A002
) -> StreamingResponse:
    """Download a generated analysis report for a debate.

    Currently supports ``?format=md`` (GitHub-Flavored Markdown).
    The report always includes the full legal disclaimer.

    Raises HTTP 404 if the debate_id does not match any stored thesis.
    """
    # Fetch the thesis — the repository method searches by ticker,
    # so we need to look up by the database row ID directly.
    conn = repo._db.connection  # noqa: SLF001
    cursor = await conn.execute(
        "SELECT ticker, full_thesis FROM ai_theses WHERE id = ?",
        (debate_id,),
    )
    row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Debate with id {debate_id} not found.",
        )

    ticker: str = row[0]
    full_thesis_json: str = row[1]

    # Deserialize the thesis
    from Option_Alpha.models.analysis import TradeThesis

    thesis = TradeThesis.model_validate_json(full_thesis_json)

    # Build a minimal MarketContext for the report header.
    # The full_thesis already contains the key analytical content;
    # MarketContext provides ticker and timestamp for the report.
    from decimal import Decimal

    from Option_Alpha.models.analysis import MarketContext

    now = datetime.datetime.now(datetime.UTC)
    context = MarketContext(
        ticker=ticker,
        current_price=Decimal("0"),
        price_52w_high=Decimal("0"),
        price_52w_low=Decimal("0"),
        iv_rank=0.0,
        iv_percentile=0.0,
        atm_iv_30d=0.0,
        rsi_14=50.0,
        macd_signal="neutral",
        put_call_ratio=1.0,
        dte_target=0,
        target_strike=Decimal("0"),
        target_delta=0.0,
        sector="Unknown",
        data_timestamp=now,
    )

    # Generate markdown report (includes disclaimer via generate_markdown_report)
    content = generate_markdown_report(
        thesis=thesis,
        context=context,
    )

    # Verify disclaimer is present (defensive — generate_markdown_report always
    # includes it, but we enforce the invariant at the API boundary)
    if DISCLAIMER_TEXT not in content:
        content += f"\n\n---\n\n> {DISCLAIMER_TEXT}\n"

    # Build filename: {TICKER}_{DATE}_{DIRECTION}.md
    date_str = now.strftime("%Y-%m-%d")
    direction_str = thesis.direction.value
    filename = f"{ticker}_{date_str}_{direction_str}.md"

    media_type = "text/markdown"

    logger.info("Report generated for debate %d: %s", debate_id, filename)

    return StreamingResponse(
        content=io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
