"""Tests for OHLCV and OptionContract serialization/deserialization helpers.

These module-level functions in market_data.py and options_data.py had no
dedicated test coverage — only exercised indirectly through cache tests.
"""

from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from Option_Alpha.models.enums import GreeksSource, OptionType
from Option_Alpha.models.market_data import OHLCV
from Option_Alpha.models.options import OptionContract, OptionGreeks
from Option_Alpha.services.market_data import (
    _deserialize_ohlcv_list,
    _serialize_ohlcv_list,
)
from Option_Alpha.services.options_data import (
    _deserialize_contract_list,
    _serialize_contract_list,
)

# ---------------------------------------------------------------------------
# OHLCV serialization
# ---------------------------------------------------------------------------


class TestSerializeOHLCVList:
    """Test _serialize_ohlcv_list and _deserialize_ohlcv_list roundtrip."""

    def test_empty_list(self) -> None:
        serialized = _serialize_ohlcv_list([])
        assert serialized == "[]"
        deserialized = _deserialize_ohlcv_list(serialized)
        assert deserialized == []

    def test_single_bar_roundtrip(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("185.42"),
            high=Decimal("187.25"),
            low=Decimal("184.10"),
            close=Decimal("186.75"),
            volume=52_340_000,
        )
        serialized = _serialize_ohlcv_list([bar])
        deserialized = _deserialize_ohlcv_list(serialized)
        assert len(deserialized) == 1
        assert deserialized[0] == bar

    def test_decimal_precision_preserved(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("185.42"),
            high=Decimal("187.25"),
            low=Decimal("184.10"),
            close=Decimal("186.75"),
            volume=52_340_000,
        )
        serialized = _serialize_ohlcv_list([bar])
        # The JSON should contain string representations of decimals
        assert "185.42" in serialized
        deserialized = _deserialize_ohlcv_list(serialized)
        assert deserialized[0].open == Decimal("185.42")

    def test_date_survives_roundtrip(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 6, 30),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=1_000_000,
        )
        serialized = _serialize_ohlcv_list([bar])
        deserialized = _deserialize_ohlcv_list(serialized)
        assert deserialized[0].date == datetime.date(2025, 6, 30)

    def test_multiple_bars_order_preserved(self) -> None:
        bars = [
            OHLCV(
                date=datetime.date(2025, 1, 13),
                open=Decimal("184.00"),
                high=Decimal("185.00"),
                low=Decimal("183.00"),
                close=Decimal("184.50"),
                volume=40_000_000,
            ),
            OHLCV(
                date=datetime.date(2025, 1, 14),
                open=Decimal("184.50"),
                high=Decimal("186.00"),
                low=Decimal("184.00"),
                close=Decimal("185.80"),
                volume=42_000_000,
            ),
            OHLCV(
                date=datetime.date(2025, 1, 15),
                open=Decimal("185.80"),
                high=Decimal("187.00"),
                low=Decimal("185.00"),
                close=Decimal("186.75"),
                volume=45_000_000,
            ),
        ]
        serialized = _serialize_ohlcv_list(bars)
        deserialized = _deserialize_ohlcv_list(serialized)
        assert len(deserialized) == 3
        assert deserialized[0].date == datetime.date(2025, 1, 13)
        assert deserialized[2].date == datetime.date(2025, 1, 15)

    def test_volume_int_preserved(self) -> None:
        bar = OHLCV(
            date=datetime.date(2025, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("101.00"),
            low=Decimal("99.00"),
            close=Decimal("100.50"),
            volume=52_340_000,
        )
        serialized = _serialize_ohlcv_list([bar])
        deserialized = _deserialize_ohlcv_list(serialized)
        assert deserialized[0].volume == 52_340_000
        assert isinstance(deserialized[0].volume, int)


# ---------------------------------------------------------------------------
# OptionContract serialization
# ---------------------------------------------------------------------------


class TestSerializeContractList:
    """Test _serialize_contract_list and _deserialize_contract_list roundtrip."""

    def _make_contract(
        self,
        *,
        greeks: OptionGreeks | None = None,
        greeks_source: GreeksSource | None = None,
    ) -> OptionContract:
        return OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.50"),
            ask=Decimal("4.70"),
            last=Decimal("4.60"),
            volume=1250,
            open_interest=8340,
            implied_volatility=0.28,
            greeks=greeks,
            greeks_source=greeks_source,
        )

    def test_empty_list(self) -> None:
        serialized = _serialize_contract_list([])
        assert serialized == "[]"
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized == []

    def test_contract_without_greeks_roundtrip(self) -> None:
        contract = self._make_contract()
        serialized = _serialize_contract_list([contract])
        deserialized = _deserialize_contract_list(serialized)
        assert len(deserialized) == 1
        assert deserialized[0].ticker == "AAPL"
        assert deserialized[0].greeks is None

    def test_contract_with_greeks_roundtrip(self) -> None:
        greeks = OptionGreeks(delta=0.45, gamma=0.05, theta=-0.08, vega=0.12, rho=0.01)
        contract = self._make_contract(greeks=greeks, greeks_source=GreeksSource.MARKET)
        serialized = _serialize_contract_list([contract])
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized[0].greeks is not None
        assert deserialized[0].greeks.delta == pytest.approx(0.45, rel=1e-4)

    def test_decimal_precision_preserved(self) -> None:
        contract = self._make_contract()
        serialized = _serialize_contract_list([contract])
        assert "185.00" in serialized or "185.0" in serialized
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized[0].strike == Decimal("185.00") or deserialized[0].strike == Decimal(
            "185.0"
        )

    def test_option_type_enum_roundtrip(self) -> None:
        contract = self._make_contract()
        serialized = _serialize_contract_list([contract])
        assert '"call"' in serialized
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized[0].option_type == OptionType.CALL

    def test_expiration_date_roundtrip(self) -> None:
        contract = self._make_contract()
        serialized = _serialize_contract_list([contract])
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized[0].expiration == datetime.date(2025, 2, 21)

    def test_multiple_contracts_order_preserved(self) -> None:
        c1 = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("180.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("8.90"),
            ask=Decimal("9.20"),
            last=Decimal("9.05"),
            volume=3450,
            open_interest=18900,
            implied_volatility=0.27,
        )
        c2 = OptionContract(
            ticker="AAPL",
            option_type=OptionType.PUT,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.80"),
            ask=Decimal("5.10"),
            last=Decimal("4.95"),
            volume=1560,
            open_interest=10200,
            implied_volatility=0.29,
        )
        serialized = _serialize_contract_list([c1, c2])
        deserialized = _deserialize_contract_list(serialized)
        assert len(deserialized) == 2
        assert deserialized[0].option_type == OptionType.CALL
        assert deserialized[1].option_type == OptionType.PUT

    def test_greeks_source_enum_roundtrip(self) -> None:
        greeks = OptionGreeks(delta=0.45, gamma=0.05, theta=-0.08, vega=0.12, rho=0.01)
        contract = self._make_contract(greeks=greeks, greeks_source=GreeksSource.MARKET)
        serialized = _serialize_contract_list([contract])
        deserialized = _deserialize_contract_list(serialized)
        assert deserialized[0].greeks_source == GreeksSource.MARKET
