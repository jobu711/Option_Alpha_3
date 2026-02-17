"""Tests for StrEnum types in the options domain.

Covers:
- Value roundtrip: enum -> string -> enum
- All members have correct values
- Serialization in JSON via a Pydantic model
- Invalid values rejected
"""

from enum import StrEnum

import pytest
from pydantic import BaseModel, ValidationError

from Option_Alpha.models.enums import (
    GreeksSource,
    OptionType,
    PositionSide,
    SignalDirection,
    SpreadType,
)


class _EnumTestModel(BaseModel):
    """Helper model for testing enum JSON serialization."""

    option_type: OptionType
    position_side: PositionSide
    signal_direction: SignalDirection
    greeks_source: GreeksSource
    spread_type: SpreadType


class TestOptionType:
    """Tests for OptionType enum."""

    def test_call_value(self) -> None:
        assert OptionType.CALL == "call"

    def test_put_value(self) -> None:
        assert OptionType.PUT == "put"

    def test_value_roundtrip_call(self) -> None:
        """OptionType.CALL -> 'call' -> OptionType('call') == OptionType.CALL."""
        as_string = str(OptionType.CALL)
        restored = OptionType(as_string)
        assert restored is OptionType.CALL

    def test_value_roundtrip_put(self) -> None:
        as_string = str(OptionType.PUT)
        restored = OptionType(as_string)
        assert restored is OptionType.PUT

    def test_is_strenum(self) -> None:
        assert issubclass(OptionType, StrEnum)

    def test_member_count(self) -> None:
        assert len(OptionType) == 2

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="is not a valid"):
            OptionType("butterfly")


class TestPositionSide:
    """Tests for PositionSide enum."""

    def test_long_value(self) -> None:
        assert PositionSide.LONG == "long"

    def test_short_value(self) -> None:
        assert PositionSide.SHORT == "short"

    def test_roundtrip(self) -> None:
        for member in PositionSide:
            assert PositionSide(str(member)) is member

    def test_member_count(self) -> None:
        assert len(PositionSide) == 2

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="is not a valid"):
            PositionSide("flat")


class TestSignalDirection:
    """Tests for SignalDirection enum."""

    def test_bullish_value(self) -> None:
        assert SignalDirection.BULLISH == "bullish"

    def test_bearish_value(self) -> None:
        assert SignalDirection.BEARISH == "bearish"

    def test_neutral_value(self) -> None:
        assert SignalDirection.NEUTRAL == "neutral"

    def test_roundtrip(self) -> None:
        for member in SignalDirection:
            assert SignalDirection(str(member)) is member

    def test_member_count(self) -> None:
        assert len(SignalDirection) == 3

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="is not a valid"):
            SignalDirection("sideways")


class TestGreeksSource:
    """Tests for GreeksSource enum."""

    def test_market_value(self) -> None:
        assert GreeksSource.MARKET == "market"

    def test_calculated_value(self) -> None:
        assert GreeksSource.CALCULATED == "calculated"

    def test_model_value(self) -> None:
        assert GreeksSource.MODEL == "model"

    def test_roundtrip(self) -> None:
        for member in GreeksSource:
            assert GreeksSource(str(member)) is member

    def test_member_count(self) -> None:
        assert len(GreeksSource) == 3


class TestSpreadType:
    """Tests for SpreadType enum."""

    EXPECTED_VALUES = {
        "VERTICAL": "vertical",
        "CALENDAR": "calendar",
        "IRON_CONDOR": "iron_condor",
        "STRADDLE": "straddle",
        "STRANGLE": "strangle",
        "BUTTERFLY": "butterfly",
    }

    def test_all_member_values(self) -> None:
        for name, expected_value in self.EXPECTED_VALUES.items():
            member = SpreadType[name]
            assert member == expected_value

    def test_roundtrip(self) -> None:
        for member in SpreadType:
            assert SpreadType(str(member)) is member

    def test_member_count(self) -> None:
        assert len(SpreadType) == 6

    def test_invalid_value_rejected(self) -> None:
        with pytest.raises(ValueError, match="is not a valid"):
            SpreadType("ratio_spread")


class TestEnumJsonSerialization:
    """Tests for enum serialization through Pydantic models."""

    def test_json_roundtrip(self) -> None:
        """Enum values survive a full JSON serialize/deserialize cycle."""
        model = _EnumTestModel(
            option_type=OptionType.CALL,
            position_side=PositionSide.LONG,
            signal_direction=SignalDirection.BULLISH,
            greeks_source=GreeksSource.MARKET,
            spread_type=SpreadType.IRON_CONDOR,
        )
        json_str = model.model_dump_json()
        restored = _EnumTestModel.model_validate_json(json_str)

        assert restored.option_type is OptionType.CALL
        assert restored.position_side is PositionSide.LONG
        assert restored.signal_direction is SignalDirection.BULLISH
        assert restored.greeks_source is GreeksSource.MARKET
        assert restored.spread_type is SpreadType.IRON_CONDOR

    def test_json_contains_string_values(self) -> None:
        """JSON output contains lowercase string values, not enum names."""
        model = _EnumTestModel(
            option_type=OptionType.PUT,
            position_side=PositionSide.SHORT,
            signal_direction=SignalDirection.BEARISH,
            greeks_source=GreeksSource.CALCULATED,
            spread_type=SpreadType.STRADDLE,
        )
        json_str = model.model_dump_json()
        assert '"put"' in json_str
        assert '"short"' in json_str
        assert '"bearish"' in json_str
        assert '"calculated"' in json_str
        assert '"straddle"' in json_str

    def test_invalid_enum_in_model_rejected(self) -> None:
        """Pydantic rejects invalid enum values during model construction."""
        with pytest.raises(ValidationError):
            _EnumTestModel(
                option_type="invalid",  # type: ignore[arg-type]
                position_side=PositionSide.LONG,
                signal_direction=SignalDirection.BULLISH,
                greeks_source=GreeksSource.MARKET,
                spread_type=SpreadType.VERTICAL,
            )
