"""Extended model tests: UniverseStats, Quote edge cases, OHLCV edge cases.

Covers models that had no dedicated test class (UniverseStats) and
additional edge cases for existing models.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo, UniverseStats

# ---------------------------------------------------------------------------
# UniverseStats
# ---------------------------------------------------------------------------


class TestUniverseStats:
    """Unit tests for the UniverseStats model."""

    def test_valid_construction(self) -> None:
        stats = UniverseStats(
            total=100,
            active=80,
            inactive=20,
            by_tier={"large_cap": 40, "mid_cap": 30, "etf": 10},
            by_sector={"Technology": 25, "Healthcare": 15, "Financials": 10},
        )
        assert stats.total == 100
        assert stats.active == 80
        assert stats.inactive == 20
        assert stats.by_tier["large_cap"] == 40
        assert stats.by_sector["Technology"] == 25

    def test_json_roundtrip(self) -> None:
        original = UniverseStats(
            total=50,
            active=45,
            inactive=5,
            by_tier={"mega": 10, "large_cap": 20, "mid_cap": 15},
            by_sector={"Energy": 5, "Utilities": 3},
        )
        restored = UniverseStats.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_frozen_immutability(self) -> None:
        stats = UniverseStats(
            total=100,
            active=80,
            inactive=20,
            by_tier={},
            by_sector={},
        )
        with pytest.raises(ValidationError, match="frozen"):
            stats.total = 200  # type: ignore[misc]

    def test_empty_dicts_valid(self) -> None:
        stats = UniverseStats(
            total=0,
            active=0,
            inactive=0,
            by_tier={},
            by_sector={},
        )
        assert stats.by_tier == {}
        assert stats.by_sector == {}

    def test_zero_universe(self) -> None:
        stats = UniverseStats(
            total=0,
            active=0,
            inactive=0,
            by_tier={},
            by_sector={},
        )
        assert stats.total == 0

    def test_all_sectors_represented(self) -> None:
        sectors = {
            "Energy": 5,
            "Materials": 3,
            "Industrials": 8,
            "Consumer Discretionary": 12,
            "Consumer Staples": 6,
            "Health Care": 10,
            "Financials": 9,
            "Information Technology": 15,
            "Communication Services": 7,
            "Utilities": 4,
            "Real Estate": 3,
        }
        stats = UniverseStats(
            total=82,
            active=82,
            inactive=0,
            by_tier={"large_cap": 82},
            by_sector=sectors,
        )
        assert len(stats.by_sector) == 11

    def test_multiple_tiers(self) -> None:
        stats = UniverseStats(
            total=200,
            active=180,
            inactive=20,
            by_tier={"mega": 20, "large_cap": 60, "mid_cap": 50, "etf": 50},
            by_sector={"Technology": 200},
        )
        assert sum(stats.by_tier.values()) == 180


# ---------------------------------------------------------------------------
# Quote edge cases
# ---------------------------------------------------------------------------


class TestQuoteEdgeCases:
    """Additional Quote model edge cases."""

    def test_equal_bid_ask_zero_spread(self) -> None:
        q = Quote(
            ticker="AAPL",
            bid=Decimal("186.50"),
            ask=Decimal("186.50"),
            last=Decimal("186.50"),
            volume=1_000_000,
            timestamp=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert q.spread == Decimal("0")
        assert q.mid == Decimal("186.50")

    def test_wide_spread_illiquid(self) -> None:
        q = Quote(
            ticker="ILLIQ",
            bid=Decimal("10.00"),
            ask=Decimal("15.00"),
            last=Decimal("12.50"),
            volume=100,
            timestamp=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert q.spread == Decimal("5.00")
        assert q.mid == Decimal("12.50")


# ---------------------------------------------------------------------------
# TickerInfo edge cases
# ---------------------------------------------------------------------------


class TestTickerInfoEdgeCases:
    """Additional TickerInfo edge cases."""

    def test_no_last_scanned(self) -> None:
        info = TickerInfo(
            symbol="NEW",
            name="New Corp",
            sector="Technology",
            market_cap_tier="mid_cap",
            asset_type="equity",
            source="cboe",
            tags=[],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        )
        assert info.last_scanned_at is None
        assert info.consecutive_misses == 0

    def test_json_roundtrip(self) -> None:
        original = TickerInfo(
            symbol="MSFT",
            name="Microsoft Corporation",
            sector="Technology",
            market_cap_tier="mega",
            asset_type="equity",
            source="yfinance",
            tags=["tech", "cloud"],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
            last_scanned_at=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
            consecutive_misses=1,
        )
        restored = TickerInfo.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_empty_tags(self) -> None:
        info = TickerInfo(
            symbol="XYZ",
            name="XYZ Corp",
            sector="Financials",
            market_cap_tier="small_cap",
            asset_type="equity",
            source="cboe",
            tags=[],
            status="inactive",
            discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        )
        assert info.tags == []


# ---------------------------------------------------------------------------
# OHLCV edge cases
# ---------------------------------------------------------------------------


class TestOHLCVEdgeCases:
    """Additional OHLCV model edge cases."""

    def test_high_equals_low_flat_bar(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("100.00"),
            low=Decimal("100.00"),
            close=Decimal("100.00"),
            volume=0,
        )
        assert bar.high == bar.low

    def test_zero_volume(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=0,
        )
        assert bar.volume == 0

    def test_decimal_precision_json_roundtrip(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("185.42"),
            high=Decimal("187.25"),
            low=Decimal("184.10"),
            close=Decimal("186.75"),
            volume=52_340_000,
        )
        json_str = bar.model_dump_json()
        assert "185.42" in json_str
        restored = OHLCV.model_validate_json(json_str)
        assert restored.open == Decimal("185.42")
