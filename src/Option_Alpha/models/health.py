"""Health check model: system dependency availability status."""

import datetime

from pydantic import BaseModel, ConfigDict


class HealthStatus(BaseModel):
    """Status of external dependencies the application relies on.

    Used by the CLI to display system readiness before running analysis.
    """

    model_config = ConfigDict(frozen=True)

    ollama_available: bool
    anthropic_available: bool
    yfinance_available: bool
    sqlite_available: bool
    ollama_models: list[str]
    last_check: datetime.datetime
