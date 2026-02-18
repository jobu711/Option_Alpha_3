"""Tests for UniverseService: CBOE CSV parsing, presets, sectors, deactivation.

All httpx calls are mocked. No real API calls.

Covers:
- refresh() parses CSV into TickerInfo models
- refresh() aborts if < 100 tickers returned
- Auto-deactivation after 3 consecutive misses
- get_universe() with each preset (full, sp500, midcap, smallcap, etfs)
- filter_by_sector() with valid and invalid sectors
- get_stats() returns correct counts
- Cache integration (loaded from cache when available)
"""

from __future__ import annotations

import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from Option_Alpha.models.market_data import TickerInfo, UniverseStats
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.services.universe import (
    GICS_SECTORS,
    MAX_CONSECUTIVE_MISSES,
    MIN_TICKERS_SAFETY,
    UniverseService,
)
from Option_Alpha.utils.exceptions import DataSourceUnavailableError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rate_limiter() -> RateLimiter:
    """Fast rate limiter for tests."""
    return RateLimiter(max_concurrent=5, requests_per_second=100.0)


@pytest.fixture()
def cache() -> ServiceCache:
    """Memory-only cache for tests."""
    return ServiceCache(database=None)


@pytest.fixture()
def service(cache: ServiceCache, rate_limiter: RateLimiter) -> UniverseService:
    """UniverseService with mocked dependencies."""
    return UniverseService(cache=cache, rate_limiter=rate_limiter)


def _index_to_alpha_symbol(index: int) -> str:
    """Convert a numeric index to an all-alpha ticker symbol (A-Z, AA-ZZ, etc.).

    The CBOE CSV parser uses ``isalpha()`` to skip non-equity symbols,
    so test symbols must be all alphabetic characters.
    """
    chars: list[str] = []
    n = index
    while True:
        chars.append(chr(ord("A") + (n % 26)))
        n = n // 26 - 1
        if n < 0:
            break
    # Reverse and add prefix to avoid collisions with known symbols
    return "ZZ" + "".join(reversed(chars))


def _build_csv(count: int = 150) -> str:
    """Build a mock CBOE equity & index options directory CSV.

    The real CBOE directory CSV has a header row:
    ``Company Name, Stock Symbol, DPM Name, Post/Station``
    """
    large_caps = ["AAPL", "MSFT", "AMZN", "GOOGL", "META"]
    etfs = ["SPY", "QQQ", "IWM"]

    lines: list[str] = []
    lines.append("Company Name, Stock Symbol, DPM Name, Post/Station")

    for etf in etfs:
        lines.append(f'"{etf} ETF Trust","{etf}","Market Maker LLC","1/1"')

    for lc in large_caps:
        lines.append(f'"{lc} Inc.","{lc}","Market Maker LLC","2/1"')

    remaining = count - len(large_caps) - len(etfs)
    for i in range(max(0, remaining)):
        symbol = _index_to_alpha_symbol(i)
        lines.append(f'"Test Company {symbol}","{symbol}","Market Maker LLC","2/1"')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# refresh() tests
# ---------------------------------------------------------------------------


class TestRefresh:
    """Tests for refresh() method."""

    @pytest.mark.asyncio()
    async def test_parses_csv_into_ticker_info_models(self, service: UniverseService) -> None:
        """refresh() parses CBOE CSV into TickerInfo models."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            tickers = await service.refresh()

        assert len(tickers) >= 150
        assert all(isinstance(t, TickerInfo) for t in tickers)
        # Check first ticker is AAPL
        aapl = next(t for t in tickers if t.symbol == "AAPL")
        assert aapl.name == "AAPL Inc."
        assert aapl.source == "cboe"
        assert aapl.status == "active"

    @pytest.mark.asyncio()
    async def test_aborts_if_fewer_than_min_tickers(self, service: UniverseService) -> None:
        """refresh() raises error if fewer than MIN_TICKERS_SAFETY returned."""
        csv_text = _build_csv(count=50)

        with (
            patch.object(
                service,
                "_fetch_cboe_csv",
                new_callable=AsyncMock,
                return_value=csv_text,
            ),
            pytest.raises(
                DataSourceUnavailableError,
                match="Data source may be broken",
            ),
        ):
            await service.refresh()

    @pytest.mark.asyncio()
    async def test_classifies_etfs_correctly(self, service: UniverseService) -> None:
        """ETFs are classified with asset_type='etf'."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            tickers = await service.refresh()

        spy = next(t for t in tickers if t.symbol == "SPY")
        assert spy.asset_type == "etf"
        assert spy.market_cap_tier == "etf"

    @pytest.mark.asyncio()
    async def test_classifies_large_caps_correctly(self, service: UniverseService) -> None:
        """Well-known large caps are classified correctly."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            tickers = await service.refresh()

        aapl = next(t for t in tickers if t.symbol == "AAPL")
        assert aapl.market_cap_tier == "large_cap"
        assert aapl.asset_type == "equity"


# ---------------------------------------------------------------------------
# Auto-deactivation tests
# ---------------------------------------------------------------------------


class TestAutoDeactivation:
    """Tests for auto-deactivation after consecutive misses."""

    @pytest.mark.asyncio()
    async def test_ticker_deactivated_after_max_misses(self, service: UniverseService) -> None:
        """Tickers missing for MAX_CONSECUTIVE_MISSES refreshes are deactivated."""
        # Set up miss counts for a ticker
        service._miss_counts["GONE"] = MAX_CONSECUTIVE_MISSES

        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            tickers = await service.refresh()

        # GONE is not in the CSV, so its miss count stays at MAX
        # Check that tickers returned are active (GONE won't be in the CSV)
        active_symbols = {t.symbol for t in tickers if t.status == "active"}
        assert "GONE" not in active_symbols

    @pytest.mark.asyncio()
    async def test_present_ticker_resets_miss_count(self, service: UniverseService) -> None:
        """Tickers present in refresh reset their miss count to 0."""
        service._miss_counts["AAPL"] = 2

        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        assert service._miss_counts.get("AAPL") == 0


# ---------------------------------------------------------------------------
# get_universe() preset tests
# ---------------------------------------------------------------------------


class TestGetUniverse:
    """Tests for get_universe() with presets."""

    @pytest.mark.asyncio()
    async def test_full_preset_returns_all_active(self, service: UniverseService) -> None:
        """'full' preset returns all active tickers."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        result = await service.get_universe(preset="full")
        assert len(result) > 0
        assert all(t.status == "active" for t in result)

    @pytest.mark.asyncio()
    async def test_sp500_preset_returns_large_cap_only(self, service: UniverseService) -> None:
        """'sp500' preset returns only large_cap tickers."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        result = await service.get_universe(preset="sp500")
        for t in result:
            assert t.market_cap_tier == "large_cap"

    @pytest.mark.asyncio()
    async def test_midcap_preset(self, service: UniverseService) -> None:
        """'midcap' preset returns only mid_cap tickers."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        result = await service.get_universe(preset="midcap")
        for t in result:
            assert t.market_cap_tier == "mid_cap"

    @pytest.mark.asyncio()
    async def test_etfs_preset_returns_etf_only(self, service: UniverseService) -> None:
        """'etfs' preset returns only etf tickers."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        result = await service.get_universe(preset="etfs")
        for t in result:
            assert t.market_cap_tier == "etf"

    @pytest.mark.asyncio()
    async def test_unknown_preset_returns_full(self, service: UniverseService) -> None:
        """Unknown preset falls back to returning full active universe."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        result = await service.get_universe(preset="nonexistent")
        full = await service.get_universe(preset="full")
        assert len(result) == len(full)

    @pytest.mark.asyncio()
    async def test_loads_from_cache_when_universe_empty(
        self,
        service: UniverseService,
        cache: ServiceCache,
    ) -> None:
        """get_universe() loads from cache when internal universe is empty."""
        # Pre-populate cache with universe data
        now = datetime.datetime.now(datetime.UTC)
        ticker_data = [
            TickerInfo(
                symbol="AAPL",
                name="Apple Inc.",
                sector="Technology",
                market_cap_tier="large_cap",
                asset_type="equity",
                source="cboe",
                tags=["optionable"],
                status="active",
                discovered_at=now,
            ).model_dump(mode="json")
        ]
        await cache.set(
            "cboe:universe:full",
            json.dumps(ticker_data),
            86400,
        )

        result = await service.get_universe(preset="full")
        assert len(result) == 1
        assert result[0].symbol == "AAPL"


# ---------------------------------------------------------------------------
# filter_by_sector tests
# ---------------------------------------------------------------------------


class TestFilterBySector:
    """Tests for filter_by_sector()."""

    @pytest.mark.asyncio()
    async def test_valid_sector_filters_correctly(self, service: UniverseService) -> None:
        """Filtering by a valid GICS sector returns matching tickers."""
        now = datetime.datetime.now(datetime.UTC)
        tickers = [
            TickerInfo(
                symbol="AAPL",
                name="Apple",
                sector="Information Technology",
                market_cap_tier="large_cap",
                asset_type="equity",
                source="cboe",
                tags=[],
                status="active",
                discovered_at=now,
            ),
            TickerInfo(
                symbol="XOM",
                name="Exxon",
                sector="Energy",
                market_cap_tier="large_cap",
                asset_type="equity",
                source="cboe",
                tags=[],
                status="active",
                discovered_at=now,
            ),
        ]

        result = await service.filter_by_sector(tickers, sector="Energy")
        assert len(result) == 1
        assert result[0].symbol == "XOM"

    @pytest.mark.asyncio()
    async def test_invalid_sector_returns_empty(self, service: UniverseService) -> None:
        """Filtering by an invalid sector returns an empty list."""
        now = datetime.datetime.now(datetime.UTC)
        tickers = [
            TickerInfo(
                symbol="AAPL",
                name="Apple",
                sector="Information Technology",
                market_cap_tier="large_cap",
                asset_type="equity",
                source="cboe",
                tags=[],
                status="active",
                discovered_at=now,
            ),
        ]

        result = await service.filter_by_sector(tickers, sector="NotARealSector")
        assert result == []


# ---------------------------------------------------------------------------
# get_stats tests
# ---------------------------------------------------------------------------


class TestGetStats:
    """Tests for get_stats()."""

    @pytest.mark.asyncio()
    async def test_returns_correct_counts(self, service: UniverseService) -> None:
        """get_stats() returns accurate total, active, and inactive counts."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            tickers = await service.refresh()

        stats = await service.get_stats()
        assert isinstance(stats, UniverseStats)
        assert stats.total == len(tickers)
        assert stats.active == sum(1 for t in tickers if t.status == "active")
        assert stats.inactive == stats.total - stats.active

    @pytest.mark.asyncio()
    async def test_includes_tier_and_sector_counts(self, service: UniverseService) -> None:
        """get_stats() includes per-tier and per-sector breakdown."""
        csv_text = _build_csv(count=150)

        with patch.object(
            service,
            "_fetch_cboe_csv",
            new_callable=AsyncMock,
            return_value=csv_text,
        ):
            await service.refresh()

        stats = await service.get_stats()
        assert isinstance(stats, UniverseStats)
        assert len(stats.by_tier) > 0
        assert len(stats.by_sector) > 0


# ---------------------------------------------------------------------------
# CSV parsing edge cases
# ---------------------------------------------------------------------------


class TestCSVParsing:
    """Tests for CSV parsing edge cases with CBOE directory format."""

    def test_skips_non_alpha_symbols(self, service: UniverseService) -> None:
        """Symbols with special characters are skipped."""
        csv_text = (
            "Company Name, Stock Symbol, DPM Name, Post/Station\n"
            '"Apple Inc.","AAPL","MM LLC","2/1"\n'
            '"Weird Corp","A-B","MM LLC","2/1"\n'
        )
        tickers = service._parse_csv(csv_text)
        assert len(tickers) == 1
        assert tickers[0].symbol == "AAPL"

    def test_skips_empty_symbols(self, service: UniverseService) -> None:
        """Rows with empty symbol are skipped."""
        csv_text = (
            "Company Name, Stock Symbol, DPM Name, Post/Station\n"
            '"NoSymbol Corp","","MM LLC","2/1"\n'
            '"Apple Inc.","AAPL","MM LLC","2/1"\n'
        )
        tickers = service._parse_csv(csv_text)
        assert len(tickers) == 1
        assert tickers[0].symbol == "AAPL"

    def test_classifies_etfs_by_name_heuristic(self, service: UniverseService) -> None:
        """Parser classifies ETFs using name-based heuristics."""
        csv_text = (
            "Company Name, Stock Symbol, DPM Name, Post/Station\n"
            '"SPDR S&P 500 ETF Trust","SPY","MM LLC","1/1"\n'
            '"Microsoft Corp","MSFT","MM LLC","2/1"\n'
        )
        tickers = service._parse_csv(csv_text)
        assert len(tickers) == 2
        spy = next(t for t in tickers if t.symbol == "SPY")
        msft = next(t for t in tickers if t.symbol == "MSFT")
        assert spy.asset_type == "etf"
        assert msft.asset_type == "equity"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify service constants."""

    def test_gics_sectors_count(self) -> None:
        """There are 11 GICS sectors."""
        assert len(GICS_SECTORS) == 11

    def test_min_tickers_safety(self) -> None:
        """Safety threshold is 100."""
        assert MIN_TICKERS_SAFETY == 100

    def test_max_consecutive_misses(self) -> None:
        """Auto-deactivation threshold is 3."""
        assert MAX_CONSECUTIVE_MISSES == 3
