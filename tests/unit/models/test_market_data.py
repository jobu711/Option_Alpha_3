"""Tests for market data models: OHLCV, Quote, TickerInfo.

Covers:
- JSON roundtrip: model_validate_json(m.model_dump_json()) == m
- Decimal precision survives serialization
- Frozen immutability
- Computed fields (mid, spread on Quote)
- Valid construction with all required fields
- Edge cases: zero volume, max values
"""

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo


class TestOHLCV:
    """Tests for the OHLCV (price bar) model."""

    def test_valid_construction(self, sample_ohlcv: OHLCV) -> None:
        """OHLCV can be constructed with valid data."""
        assert sample_ohlcv.date == datetime.date(2025, 1, 15)
        assert sample_ohlcv.open == Decimal("185.50")
        assert sample_ohlcv.high == Decimal("187.25")
        assert sample_ohlcv.low == Decimal("184.10")
        assert sample_ohlcv.close == Decimal("186.75")
        assert sample_ohlcv.volume == 52_340_000

    def test_json_roundtrip(self, sample_ohlcv: OHLCV) -> None:
        """OHLCV survives a full JSON serialize/deserialize cycle."""
        json_str = sample_ohlcv.model_dump_json()
        restored = OHLCV.model_validate_json(json_str)
        assert restored == sample_ohlcv

    def test_decimal_precision_survives_serialization(self) -> None:
        """Decimal('1.05') does NOT become 1.0500000000000000444 after JSON roundtrip."""
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("1.05"),
            high=Decimal("1.10"),
            low=Decimal("1.00"),
            close=Decimal("1.07"),
            volume=100,
        )
        json_str = bar.model_dump_json()
        restored = OHLCV.model_validate_json(json_str)
        # Decimal precision must survive -- no float artifacts
        assert restored.open == Decimal("1.05")
        assert "1.050000000000000" not in json_str

    def test_frozen_immutability(self, sample_ohlcv: OHLCV) -> None:
        """Assigning to a frozen model field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_ohlcv.close = Decimal("999.99")  # type: ignore[misc]

    def test_zero_volume(self) -> None:
        """Zero volume is valid (e.g., holiday bars or low-liquidity stocks)."""
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("100.00"),
            low=Decimal("100.00"),
            close=Decimal("100.00"),
            volume=0,
        )
        assert bar.volume == 0

    def test_large_volume(self) -> None:
        """Very large volume values are handled correctly."""
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("100.00"),
            low=Decimal("100.00"),
            close=Decimal("100.00"),
            volume=999_999_999_999,
        )
        assert bar.volume == 999_999_999_999

    def test_date_serialization(self, sample_ohlcv: OHLCV) -> None:
        """Date field is correctly serialized to and from JSON."""
        json_str = sample_ohlcv.model_dump_json()
        restored = OHLCV.model_validate_json(json_str)
        assert restored.date == datetime.date(2025, 1, 15)


class TestQuote:
    """Tests for the Quote (real-time snapshot) model."""

    def test_valid_construction(self, sample_quote: Quote) -> None:
        """Quote can be constructed with valid data."""
        assert sample_quote.ticker == "AAPL"
        assert sample_quote.bid == Decimal("186.50")
        assert sample_quote.ask == Decimal("186.55")
        assert sample_quote.last == Decimal("186.52")
        assert sample_quote.volume == 35_120_000

    def test_json_roundtrip(self, sample_quote: Quote) -> None:
        """Quote survives a full JSON serialize/deserialize cycle.

        Note: mid and spread are Python properties (not computed_field),
        so they are not included in JSON serialization. We compare the
        serialized fields only.
        """
        json_str = sample_quote.model_dump_json()
        restored = Quote.model_validate_json(json_str)
        assert restored == sample_quote

    def test_decimal_precision_survives_serialization(self) -> None:
        """Decimal values maintain precision through JSON roundtrip."""
        quote = Quote(
            ticker="TEST",
            bid=Decimal("1.05"),
            ask=Decimal("1.07"),
            last=Decimal("1.06"),
            volume=100,
            timestamp=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
        )
        json_str = quote.model_dump_json()
        restored = Quote.model_validate_json(json_str)
        assert restored.bid == Decimal("1.05")
        assert restored.ask == Decimal("1.07")
        assert "1.050000000000000" not in json_str

    def test_mid_price_computation(self, sample_quote: Quote) -> None:
        """Mid price is (bid + ask) / 2."""
        expected_mid = (Decimal("186.50") + Decimal("186.55")) / 2
        assert sample_quote.mid == expected_mid

    def test_spread_computation(self, sample_quote: Quote) -> None:
        """Spread is ask - bid."""
        expected_spread = Decimal("186.55") - Decimal("186.50")
        assert sample_quote.spread == expected_spread

    def test_frozen_immutability(self, sample_quote: Quote) -> None:
        """Assigning to a frozen model field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_quote.bid = Decimal("999.99")  # type: ignore[misc]

    def test_zero_volume(self) -> None:
        """Zero volume is valid for pre-market or low-liquidity instruments."""
        quote = Quote(
            ticker="RARE",
            bid=Decimal("50.00"),
            ask=Decimal("50.10"),
            last=Decimal("50.05"),
            volume=0,
            timestamp=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
        )
        assert quote.volume == 0

    def test_wide_spread(self) -> None:
        """Quote with wide bid-ask spread is valid (illiquid stock)."""
        quote = Quote(
            ticker="ILLIQ",
            bid=Decimal("10.00"),
            ask=Decimal("15.00"),
            last=Decimal("12.50"),
            volume=50,
            timestamp=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
        )
        assert quote.spread == Decimal("5.00")

    def test_timestamp_with_timezone(self, sample_quote: Quote) -> None:
        """Timestamp with UTC timezone is preserved."""
        assert sample_quote.timestamp.tzinfo == datetime.UTC


class TestTickerInfo:
    """Tests for the TickerInfo (ticker metadata) model."""

    def test_valid_construction(self, sample_ticker_info: TickerInfo) -> None:
        """TickerInfo can be constructed with valid data."""
        assert sample_ticker_info.symbol == "AAPL"
        assert sample_ticker_info.name == "Apple Inc."
        assert sample_ticker_info.sector == "Technology"
        assert sample_ticker_info.market_cap_tier == "mega"
        assert sample_ticker_info.asset_type == "equity"
        assert sample_ticker_info.source == "yfinance"
        assert sample_ticker_info.tags == ["faang", "tech", "mega-cap"]
        assert sample_ticker_info.status == "active"

    def test_json_roundtrip(self, sample_ticker_info: TickerInfo) -> None:
        """TickerInfo survives a full JSON serialize/deserialize cycle."""
        json_str = sample_ticker_info.model_dump_json()
        restored = TickerInfo.model_validate_json(json_str)
        assert restored == sample_ticker_info

    def test_frozen_immutability(self, sample_ticker_info: TickerInfo) -> None:
        """Assigning to a frozen model field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_ticker_info.symbol = "MSFT"  # type: ignore[misc]

    def test_last_scanned_at_defaults_to_none(self) -> None:
        """last_scanned_at is optional and defaults to None."""
        info = TickerInfo(
            symbol="NEW",
            name="New Corp",
            sector="Technology",
            market_cap_tier="small",
            asset_type="equity",
            source="scan",
            tags=[],
            status="pending",
            discovered_at=datetime.datetime(2025, 1, 15, 0, 0, 0, tzinfo=datetime.UTC),
        )
        assert info.last_scanned_at is None

    def test_consecutive_misses_defaults_to_zero(self) -> None:
        """consecutive_misses defaults to 0."""
        info = TickerInfo(
            symbol="NEW",
            name="New Corp",
            sector="Technology",
            market_cap_tier="small",
            asset_type="equity",
            source="scan",
            tags=[],
            status="pending",
            discovered_at=datetime.datetime(2025, 1, 15, 0, 0, 0, tzinfo=datetime.UTC),
        )
        assert info.consecutive_misses == 0

    def test_empty_tags_list(self) -> None:
        """Empty tags list is valid."""
        info = TickerInfo(
            symbol="TEST",
            name="Test Corp",
            sector="Unknown",
            market_cap_tier="micro",
            asset_type="equity",
            source="manual",
            tags=[],
            status="active",
            discovered_at=datetime.datetime(2025, 1, 15, 0, 0, 0, tzinfo=datetime.UTC),
        )
        assert info.tags == []
