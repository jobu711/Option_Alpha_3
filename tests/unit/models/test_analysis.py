"""Tests for analysis models: MarketContext, AgentResponse, TradeThesis.

Covers:
- JSON roundtrip for all models
- MarketContext is flat (all expected fields present, no nested objects)
- Conviction validation: values > 1.0 or < 0.0 rejected
- Decimal fields survive JSON roundtrip
- TradeThesis has mandatory disclaimer field
- SignalDirection enum used correctly in TradeThesis
"""

import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from Option_Alpha.models.analysis import AgentResponse, MarketContext, TradeThesis
from Option_Alpha.models.enums import SignalDirection


class TestMarketContext:
    """Tests for the MarketContext (flat snapshot for debate agents)."""

    def test_valid_construction(self, sample_market_context: MarketContext) -> None:
        """MarketContext can be constructed with valid data."""
        assert sample_market_context.ticker == "AAPL"
        assert sample_market_context.current_price == Decimal("186.75")
        assert sample_market_context.iv_rank == pytest.approx(45.2, rel=1e-3)
        assert sample_market_context.rsi_14 == pytest.approx(55.3, rel=1e-3)
        assert sample_market_context.sector == "Technology"

    def test_json_roundtrip(self, sample_market_context: MarketContext) -> None:
        """MarketContext survives a full JSON serialize/deserialize cycle."""
        json_str = sample_market_context.model_dump_json()
        restored = MarketContext.model_validate_json(json_str)
        assert restored == sample_market_context

    def test_is_flat_no_nested_objects(self, sample_market_context: MarketContext) -> None:
        """MarketContext is flat -- all fields are primitives, no nested models.

        This is intentional: agents handle flat key-value pairs better than
        deeply nested objects when parsing prompt text.
        """
        dumped = sample_market_context.model_dump()
        for key, value in dumped.items():
            assert not isinstance(value, dict), (
                f"MarketContext.{key} is a dict -- model should be flat"
            )
            assert not isinstance(value, list), (
                f"MarketContext.{key} is a list -- model should be flat"
            )

    def test_all_expected_fields_present(self) -> None:
        """MarketContext has all expected fields for the debate agents."""
        expected_fields = {
            "ticker",
            "current_price",
            "price_52w_high",
            "price_52w_low",
            "iv_rank",
            "iv_percentile",
            "atm_iv_30d",
            "rsi_14",
            "macd_signal",
            "put_call_ratio",
            "next_earnings",
            "dte_target",
            "target_strike",
            "target_delta",
            "sector",
            "data_timestamp",
        }
        actual_fields = set(MarketContext.model_fields.keys())
        assert expected_fields == actual_fields

    def test_decimal_fields_survive_roundtrip(self, sample_market_context: MarketContext) -> None:
        """Decimal fields maintain precision through JSON roundtrip."""
        json_str = sample_market_context.model_dump_json()
        restored = MarketContext.model_validate_json(json_str)
        assert restored.current_price == Decimal("186.75")
        assert restored.price_52w_high == Decimal("199.62")
        assert restored.price_52w_low == Decimal("164.08")
        assert restored.target_strike == Decimal("185.00")

    def test_frozen_immutability(self, sample_market_context: MarketContext) -> None:
        """MarketContext is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_market_context.ticker = "MSFT"  # type: ignore[misc]

    def test_next_earnings_none(self) -> None:
        """next_earnings can be None when earnings date is unknown."""
        ctx = MarketContext(
            ticker="TSLA",
            current_price=Decimal("250.00"),
            price_52w_high=Decimal("300.00"),
            price_52w_low=Decimal("150.00"),
            iv_rank=60.0,
            iv_percentile=65.0,
            atm_iv_30d=0.45,
            rsi_14=48.0,
            macd_signal="bearish_crossover",
            put_call_ratio=1.2,
            next_earnings=None,
            dte_target=30,
            target_strike=Decimal("245.00"),
            target_delta=0.40,
            sector="Consumer Discretionary",
            data_timestamp=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert ctx.next_earnings is None


class TestAgentResponse:
    """Tests for AgentResponse from debate agents."""

    def test_valid_construction(self, sample_agent_response: AgentResponse) -> None:
        """AgentResponse can be constructed with valid data."""
        assert sample_agent_response.agent_role == "bull"
        assert sample_agent_response.conviction == pytest.approx(0.72, abs=0.01)
        assert len(sample_agent_response.key_points) == 2
        assert sample_agent_response.model_used == "claude-sonnet-4-5-20250929"

    def test_json_roundtrip(self, sample_agent_response: AgentResponse) -> None:
        """AgentResponse survives a full JSON serialize/deserialize cycle."""
        json_str = sample_agent_response.model_dump_json()
        restored = AgentResponse.model_validate_json(json_str)
        assert restored.agent_role == sample_agent_response.agent_role
        assert restored.conviction == pytest.approx(sample_agent_response.conviction, abs=0.01)
        assert restored.key_points == sample_agent_response.key_points
        assert restored.contracts_referenced == sample_agent_response.contracts_referenced
        assert restored.greeks_cited == sample_agent_response.greeks_cited

    def test_conviction_above_max_rejected(self) -> None:
        """Conviction > 1.0 is rejected."""
        with pytest.raises(ValidationError, match="conviction"):
            AgentResponse(
                agent_role="bull",
                analysis="Strong bullish case",
                key_points=["Point 1"],
                conviction=1.01,
                contracts_referenced=["AAPL 185C"],
                greeks_cited={"delta": 0.45},
                model_used="test-model",
                input_tokens=100,
                output_tokens=50,
            )

    def test_conviction_below_min_rejected(self) -> None:
        """Conviction < 0.0 is rejected."""
        with pytest.raises(ValidationError, match="conviction"):
            AgentResponse(
                agent_role="bear",
                analysis="Weak bearish case",
                key_points=["Point 1"],
                conviction=-0.01,
                contracts_referenced=["AAPL 180P"],
                greeks_cited={"delta": -0.30},
                model_used="test-model",
                input_tokens=100,
                output_tokens=50,
            )

    def test_conviction_at_boundaries(self) -> None:
        """Conviction at 0.0 and 1.0 are both valid."""
        response_zero = AgentResponse(
            agent_role="bull",
            analysis="No conviction",
            key_points=[],
            conviction=0.0,
            contracts_referenced=[],
            greeks_cited={},
            model_used="test-model",
            input_tokens=100,
            output_tokens=50,
        )
        assert response_zero.conviction == pytest.approx(0.0, abs=0.01)

        response_one = AgentResponse(
            agent_role="bear",
            analysis="Maximum conviction",
            key_points=["Overwhelming evidence"],
            conviction=1.0,
            contracts_referenced=["SPY 450P"],
            greeks_cited={"delta": -0.90},
            model_used="test-model",
            input_tokens=100,
            output_tokens=50,
        )
        assert response_one.conviction == pytest.approx(1.0, abs=0.01)

    def test_frozen_immutability(self, sample_agent_response: AgentResponse) -> None:
        """AgentResponse is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_agent_response.agent_role = "bear"  # type: ignore[misc]

    def test_greeks_cited_dict(self, sample_agent_response: AgentResponse) -> None:
        """greeks_cited maps Greek names to float values."""
        assert "delta" in sample_agent_response.greeks_cited
        assert sample_agent_response.greeks_cited["delta"] == pytest.approx(0.45, rel=1e-4)

    def test_empty_contracts_and_greeks(self) -> None:
        """Empty contracts_referenced and greeks_cited lists are valid."""
        response = AgentResponse(
            agent_role="bull",
            analysis="General outlook only",
            key_points=["Macro trend positive"],
            conviction=0.50,
            contracts_referenced=[],
            greeks_cited={},
            model_used="test-model",
            input_tokens=100,
            output_tokens=50,
        )
        assert response.contracts_referenced == []
        assert response.greeks_cited == {}


class TestTradeThesis:
    """Tests for TradeThesis -- the final debate output."""

    def test_valid_construction(self, sample_trade_thesis: TradeThesis) -> None:
        """TradeThesis can be constructed with valid data."""
        assert sample_trade_thesis.direction is SignalDirection.BULLISH
        assert sample_trade_thesis.conviction == pytest.approx(0.72, abs=0.01)
        assert len(sample_trade_thesis.risk_factors) == 2
        assert sample_trade_thesis.disclaimer != ""

    def test_json_roundtrip(self, sample_trade_thesis: TradeThesis) -> None:
        """TradeThesis survives a full JSON serialize/deserialize cycle."""
        json_str = sample_trade_thesis.model_dump_json()
        restored = TradeThesis.model_validate_json(json_str)
        assert restored == sample_trade_thesis

    def test_conviction_above_max_rejected(self) -> None:
        """Conviction > 1.0 is rejected on TradeThesis."""
        with pytest.raises(ValidationError, match="conviction"):
            TradeThesis(
                direction=SignalDirection.BULLISH,
                conviction=1.5,
                entry_rationale="Overbought",
                risk_factors=[],
                recommended_action="Buy",
                bull_summary="Strong",
                bear_summary="Weak",
                model_used="test",
                total_tokens=100,
                duration_ms=1000,
                disclaimer="Educational only.",
            )

    def test_conviction_below_min_rejected(self) -> None:
        """Conviction < 0.0 is rejected on TradeThesis."""
        with pytest.raises(ValidationError, match="conviction"):
            TradeThesis(
                direction=SignalDirection.BEARISH,
                conviction=-0.1,
                entry_rationale="Oversold",
                risk_factors=[],
                recommended_action="Sell",
                bull_summary="Weak",
                bear_summary="Strong",
                model_used="test",
                total_tokens=100,
                duration_ms=1000,
                disclaimer="Educational only.",
            )

    def test_conviction_at_boundaries(self) -> None:
        """Conviction at 0.0 and 1.0 are both valid on TradeThesis."""
        thesis_zero = TradeThesis(
            direction=SignalDirection.NEUTRAL,
            conviction=0.0,
            entry_rationale="No signal",
            risk_factors=[],
            recommended_action="Hold",
            bull_summary="None",
            bear_summary="None",
            model_used="test",
            total_tokens=100,
            duration_ms=1000,
            disclaimer="Educational only.",
        )
        assert thesis_zero.conviction == pytest.approx(0.0, abs=0.01)

        thesis_one = TradeThesis(
            direction=SignalDirection.BULLISH,
            conviction=1.0,
            entry_rationale="Extreme signal",
            risk_factors=["High conviction carries risk"],
            recommended_action="Buy aggressively",
            bull_summary="All indicators aligned",
            bear_summary="No bear case",
            model_used="test",
            total_tokens=100,
            duration_ms=1000,
            disclaimer="Educational only.",
        )
        assert thesis_one.conviction == pytest.approx(1.0, abs=0.01)

    def test_disclaimer_is_mandatory(self) -> None:
        """TradeThesis requires a disclaimer field.

        Every verdict must include a disclaimer populated from reporting/disclaimer.py.
        """
        # Disclaimer is a required field -- omitting it raises ValidationError
        with pytest.raises(ValidationError):
            TradeThesis(
                direction=SignalDirection.BULLISH,
                conviction=0.70,
                entry_rationale="RSI bounce",
                risk_factors=["Earnings risk"],
                recommended_action="Buy call",
                bull_summary="Momentum",
                bear_summary="Caution",
                model_used="test",
                total_tokens=100,
                duration_ms=1000,
                # disclaimer intentionally omitted
            )  # type: ignore[call-arg]

    def test_signal_direction_enum_values(self) -> None:
        """All SignalDirection values work in TradeThesis.direction."""
        for direction in SignalDirection:
            thesis = TradeThesis(
                direction=direction,
                conviction=0.50,
                entry_rationale="Test",
                risk_factors=[],
                recommended_action="Hold",
                bull_summary="N/A",
                bear_summary="N/A",
                model_used="test",
                total_tokens=100,
                duration_ms=1000,
                disclaimer="Educational only.",
            )
            assert thesis.direction is direction

    def test_frozen_immutability(self, sample_trade_thesis: TradeThesis) -> None:
        """TradeThesis is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_trade_thesis.conviction = 0.99  # type: ignore[misc]

    def test_risk_factors_list(self, sample_trade_thesis: TradeThesis) -> None:
        """risk_factors is a list of strings."""
        assert isinstance(sample_trade_thesis.risk_factors, list)
        for factor in sample_trade_thesis.risk_factors:
            assert isinstance(factor, str)
