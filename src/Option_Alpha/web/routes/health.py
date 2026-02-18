"""Health check endpoint.

Returns aggregated health status from all external dependencies
(Ollama, Anthropic, yfinance, SQLite) via the existing HealthService.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from Option_Alpha.models.health import HealthStatus
from Option_Alpha.services.health import HealthService
from Option_Alpha.web.deps import get_health_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health_check(
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthStatus:
    """Return the health status of all external dependencies.

    Checks Ollama, Anthropic, yfinance, and SQLite availability.
    Each check runs independently with its own timeout.
    """
    status = await health_service.check_all()
    logger.info("Health check completed: %s", status)
    return status
