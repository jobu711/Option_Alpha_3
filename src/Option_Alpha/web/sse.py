"""Server-Sent Events helper for streaming scan progress.

Provides a typed Pydantic model for scan progress events and a helper
function to create SSE responses from async generators.
"""

import logging
from collections.abc import AsyncGenerator

from pydantic import BaseModel, ConfigDict
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)


class ScanProgressEvent(BaseModel):
    """Typed model for scan progress SSE events.

    Sent from server to client during a scan pipeline execution.
    Each event reports the current phase, item progress, and percentage.
    """

    model_config = ConfigDict(frozen=True)

    phase: str
    current: int
    total: int
    pct: float


def create_sse_response(
    generator: AsyncGenerator[str],
    *,
    media_type: str = "text/event-stream",
) -> EventSourceResponse:
    """Create an SSE response from an async generator of JSON strings.

    Args:
        generator: Async generator yielding JSON-encoded event data strings.
        media_type: MIME type for the response (default: text/event-stream).

    Returns:
        An EventSourceResponse suitable for returning from a FastAPI route handler.
    """
    return EventSourceResponse(
        content=generator,
        media_type=media_type,
    )
