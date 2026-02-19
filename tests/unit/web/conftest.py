"""Shared fixtures for web route tests.

Provides a test FastAPI app, TestClient, and mock database/repository objects
so that route tests never hit real databases or external services.
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncGenerator
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Option_Alpha.data.database import Database
from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.models.health import HealthStatus
from Option_Alpha.models.market_data import OHLCV, TickerInfo, UniverseStats
from Option_Alpha.models.scan import (
    ScanRun,
    TickerScore,
    UniversePreset,
    WatchlistSummary,
)
from Option_Alpha.web.app import create_app, get_db


@pytest.fixture()
def mock_db() -> AsyncMock:
    """Mock Database instance with a stubbed connection."""
    db = AsyncMock(spec=Database)
    db.connect = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture()
def app(mock_db: AsyncMock) -> FastAPI:
    """Create a test app with database dependency overridden."""
    test_app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncMock]:
        yield mock_db

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    """Create a synchronous test client for the app."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_scan_run() -> ScanRun:
    """A completed scan run for testing."""
    return ScanRun(
        id="scan-20250115-001",
        started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
        completed_at=datetime.datetime(2025, 1, 15, 9, 35, 0, tzinfo=datetime.UTC),
        status="completed",
        preset="high_iv",
        sectors=["Technology", "Healthcare"],
        ticker_count=50,
        top_n=10,
    )


@pytest.fixture()
def sample_ticker_scores() -> list[TickerScore]:
    """A list of scored tickers for testing result tables."""
    return [
        TickerScore(
            ticker="AAPL",
            score=82.5,
            signals={"rsi": 55.0, "adx": 30.0, "iv_rank": 45.2},
            rank=1,
        ),
        TickerScore(
            ticker="MSFT",
            score=78.3,
            signals={"rsi": 48.0, "adx": 25.0, "iv_rank": 40.0},
            rank=2,
        ),
        TickerScore(
            ticker="NVDA",
            score=75.0,
            signals={"rsi": 62.0, "adx": 35.0, "iv_rank": 55.0},
            rank=3,
        ),
        TickerScore(
            ticker="TSLA",
            score=70.2,
            signals={"rsi": 42.0, "adx": 28.0, "iv_rank": 60.0},
            rank=4,
        ),
        TickerScore(
            ticker="AMZN",
            score=68.1,
            signals={"rsi": 50.0, "adx": 22.0, "iv_rank": 38.0},
            rank=5,
        ),
    ]


@pytest.fixture()
def sample_trade_thesis() -> TradeThesis:
    """A valid TradeThesis for debate page testing."""
    return TradeThesis(
        direction=SignalDirection.BULLISH,
        conviction=0.72,
        entry_rationale="RSI at 55 with bullish MACD crossover suggests upward momentum.",
        risk_factors=["Earnings in 30 days", "IV rank elevated at 45%"],
        recommended_action="Buy 185 call expiring Feb 21",
        bull_summary="Technical momentum favors upside with support at 184.",
        bear_summary="Elevated IV may compress post-earnings, capping gains.",
        model_used="llama3.1:8b",
        total_tokens=1500,
        duration_ms=3200,
    )


@pytest.fixture()
def sample_health_status() -> HealthStatus:
    """A healthy HealthStatus for testing."""
    return HealthStatus(
        ollama_available=True,
        anthropic_available=True,
        yfinance_available=True,
        sqlite_available=True,
        ollama_models=["llama3.1:8b", "mistral:7b"],
        last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_health_status_degraded() -> HealthStatus:
    """A degraded HealthStatus with some services offline."""
    return HealthStatus(
        ollama_available=False,
        anthropic_available=False,
        yfinance_available=True,
        sqlite_available=True,
        ollama_models=[],
        last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_ohlcv_bars() -> list[OHLCV]:
    """A short list of OHLCV bars for chart endpoint testing."""
    return [
        OHLCV(
            date=datetime.date(2025, 1, 13),
            open=Decimal("184.00"),
            high=Decimal("186.00"),
            low=Decimal("183.50"),
            close=Decimal("185.50"),
            volume=40_000_000,
        ),
        OHLCV(
            date=datetime.date(2025, 1, 14),
            open=Decimal("185.50"),
            high=Decimal("187.25"),
            low=Decimal("184.10"),
            close=Decimal("186.75"),
            volume=52_340_000,
        ),
        OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("186.75"),
            high=Decimal("188.00"),
            low=Decimal("185.90"),
            close=Decimal("187.20"),
            volume=45_000_000,
        ),
    ]


@pytest.fixture()
def sample_watchlists() -> list[WatchlistSummary]:
    """Sample watchlist summaries for testing."""
    return [
        WatchlistSummary(id=1, name="Tech Growth", created_at="2025-01-10T10:00:00Z"),
        WatchlistSummary(id=2, name="Earnings Watch", created_at="2025-01-12T14:00:00Z"),
    ]


@pytest.fixture()
def sample_presets() -> list[UniversePreset]:
    """Sample universe presets for testing."""
    return [
        UniversePreset(
            id=1,
            name="Large Tech",
            filters='{"sectors": ["Technology"], "tiers": ["large_cap"]}',
            created_at="2025-01-05T08:00:00Z",
        ),
        UniversePreset(
            id=2,
            name="All Sectors",
            filters='{"sectors": [], "tiers": []}',
            created_at="2025-01-06T09:00:00Z",
        ),
    ]


@pytest.fixture()
def sample_ticker_infos() -> list[TickerInfo]:
    """Sample ticker info for universe page testing."""
    return [
        TickerInfo(
            symbol="AAPL",
            name="Apple Inc.",
            sector="Technology",
            market_cap_tier="large_cap",
            asset_type="equity",
            source="cboe",
            tags=["tech", "mega-cap"],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        ),
        TickerInfo(
            symbol="MSFT",
            name="Microsoft Corporation",
            sector="Technology",
            market_cap_tier="large_cap",
            asset_type="equity",
            source="cboe",
            tags=["tech", "mega-cap"],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        ),
        TickerInfo(
            symbol="JNJ",
            name="Johnson & Johnson",
            sector="Health Care",
            market_cap_tier="large_cap",
            asset_type="equity",
            source="cboe",
            tags=["healthcare"],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        ),
    ]


@pytest.fixture()
def sample_universe_stats() -> UniverseStats:
    """Sample universe statistics for testing."""
    return UniverseStats(
        total=500,
        active=480,
        inactive=20,
        by_tier={"large_cap": 200, "mid_cap": 150, "small_cap": 100, "etf": 50},
        by_sector={"Technology": 80, "Health Care": 60, "Financials": 70},
    )
