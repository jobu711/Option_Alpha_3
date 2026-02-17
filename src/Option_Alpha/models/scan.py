"""Scan models: tracking scan runs, ticker scoring, and watchlist metadata."""

import datetime

from pydantic import BaseModel, ConfigDict


class WatchlistSummary(BaseModel):
    """Summary of a saved watchlist."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    created_at: str


class ScanRun(BaseModel):
    """Metadata for a single scan execution.

    Tracks timing, configuration, and completion status of a scan
    that evaluates tickers against scoring criteria.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    started_at: datetime.datetime
    completed_at: datetime.datetime | None = None
    status: str
    preset: str
    sectors: list[str]
    ticker_count: int
    top_n: int


class TickerScore(BaseModel):
    """Scored ticker from a scan run with signal breakdown.

    Each signal contributes a float score; the overall score is the
    aggregate used for ranking.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    score: float
    signals: dict[str, float]
    rank: int
