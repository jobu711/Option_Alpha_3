"""Extended analysis model tests: GreeksCited, AgentResponse edge cases, TradeThesis edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from Option_Alpha.models.analysis import (
    AgentResponse,
    GreeksCited,
    TradeThesis,
)
from Option_Alpha.models.enums import SignalDirection

# ---------------------------------------------------------------------------
# GreeksCited
# ---------------------------------------------------------------------------


class TestGreeksCited:
    """Unit tests for the GreeksCited model — previously without dedicated class."""

    def test_all_none_default(self) -> None:
        gc = GreeksCited()
        assert gc.delta is None
        assert gc.gamma is None
        assert gc.theta is None
        assert gc.vega is None
        assert gc.rho is None

    def test_partial_fill_delta_only(self) -> None:
        gc = GreeksCited(delta=0.45)
        assert gc.delta == pytest.approx(0.45, rel=1e-4)
        assert gc.gamma is None

    def test_all_fields_populated(self) -> None:
        gc = GreeksCited(delta=0.45, gamma=0.03, theta=-0.08, vega=0.15, rho=0.01)
        assert gc.delta == pytest.approx(0.45, rel=1e-4)
        assert gc.gamma == pytest.approx(0.03, rel=1e-4)
        assert gc.theta == pytest.approx(-0.08, rel=1e-4)
        assert gc.vega == pytest.approx(0.15, rel=1e-4)
        assert gc.rho == pytest.approx(0.01, rel=1e-4)

    def test_json_roundtrip_all_none(self) -> None:
        original = GreeksCited()
        restored = GreeksCited.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_json_roundtrip_partial(self) -> None:
        original = GreeksCited(delta=0.45, theta=-0.08)
        restored = GreeksCited.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_json_roundtrip_all_fields(self) -> None:
        original = GreeksCited(delta=0.45, gamma=0.03, theta=-0.08, vega=0.15, rho=0.01)
        restored = GreeksCited.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_frozen_immutability(self) -> None:
        gc = GreeksCited(delta=0.45)
        with pytest.raises(ValidationError, match="frozen"):
            gc.delta = 0.50  # type: ignore[misc]

    def test_out_of_range_delta_accepted(self) -> None:
        """GreeksCited has NO range validation — it records what agent cited."""
        gc = GreeksCited(delta=2.0)
        assert gc.delta == pytest.approx(2.0, abs=1e-9)

    def test_negative_delta_accepted(self) -> None:
        gc = GreeksCited(delta=-1.5)
        assert gc.delta == pytest.approx(-1.5, abs=1e-9)

    def test_negative_vega_accepted(self) -> None:
        """Unlike OptionGreeks, GreeksCited allows negative vega."""
        gc = GreeksCited(vega=-5.0)
        assert gc.vega == pytest.approx(-5.0, abs=1e-9)

    def test_equality_all_none(self) -> None:
        assert GreeksCited() == GreeksCited()

    def test_inequality(self) -> None:
        a = GreeksCited(delta=0.5)
        b = GreeksCited(delta=0.4)
        assert a != b

    def test_none_fields_serialize_to_null(self) -> None:
        gc = GreeksCited(delta=0.5)
        dumped = gc.model_dump()
        assert dumped["gamma"] is None
        assert dumped["theta"] is None


# ---------------------------------------------------------------------------
# AgentResponse edge cases
# ---------------------------------------------------------------------------


class TestAgentResponseEdgeCases:
    """Additional AgentResponse edge cases."""

    def test_all_greeks_cited_none(self) -> None:
        resp = AgentResponse(
            agent_role="bull",
            analysis="Bullish on AAPL",
            key_points=["RSI oversold"],
            conviction=0.6,
            contracts_referenced=["AAPL 185C 2025-02-21"],
            greeks_cited=GreeksCited(),
            model_used="llama3:8b",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.greeks_cited.delta is None

    def test_conviction_zero_boundary(self) -> None:
        resp = AgentResponse(
            agent_role="bear",
            analysis="Neutral on AAPL",
            key_points=["No edge"],
            conviction=0.0,
            contracts_referenced=[],
            greeks_cited=GreeksCited(),
            model_used="llama3:8b",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.conviction == pytest.approx(0.0, abs=1e-9)

    def test_conviction_one_boundary(self) -> None:
        resp = AgentResponse(
            agent_role="bull",
            analysis="Extremely bullish",
            key_points=["Everything bullish"],
            conviction=1.0,
            contracts_referenced=["AAPL 185C 2025-02-21"],
            greeks_cited=GreeksCited(delta=0.95),
            model_used="llama3:8b",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.conviction == pytest.approx(1.0, abs=1e-9)

    def test_conviction_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError, match="conviction"):
            AgentResponse(
                agent_role="bull",
                analysis="Over-confident",
                key_points=[],
                conviction=1.1,
                contracts_referenced=[],
                greeks_cited=GreeksCited(),
                model_used="llama3:8b",
                input_tokens=100,
                output_tokens=50,
            )

    def test_conviction_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="conviction"):
            AgentResponse(
                agent_role="bear",
                analysis="Negative conviction",
                key_points=[],
                conviction=-0.1,
                contracts_referenced=[],
                greeks_cited=GreeksCited(),
                model_used="llama3:8b",
                input_tokens=100,
                output_tokens=50,
            )

    def test_empty_key_points(self) -> None:
        resp = AgentResponse(
            agent_role="bull",
            analysis="Bullish",
            key_points=[],
            conviction=0.5,
            contracts_referenced=[],
            greeks_cited=GreeksCited(),
            model_used="llama3:8b",
            input_tokens=100,
            output_tokens=50,
        )
        assert resp.key_points == []

    def test_json_roundtrip(self) -> None:
        original = AgentResponse(
            agent_role="bear",
            analysis="Bearish on AAPL due to IV crush risk",
            key_points=["IV elevated", "Earnings approaching"],
            conviction=0.65,
            contracts_referenced=["AAPL 185P 2025-02-21"],
            greeks_cited=GreeksCited(delta=-0.55, vega=0.12),
            model_used="llama3:8b",
            input_tokens=400,
            output_tokens=200,
        )
        restored = AgentResponse.model_validate_json(original.model_dump_json())
        assert restored == original


# ---------------------------------------------------------------------------
# TradeThesis edge cases
# ---------------------------------------------------------------------------


class TestTradeThesisEdgeCases:
    """Additional TradeThesis edge cases."""

    def test_neutral_direction(self) -> None:
        thesis = TradeThesis(
            direction=SignalDirection.NEUTRAL,
            conviction=0.5,
            entry_rationale="Mixed signals",
            risk_factors=["Unclear direction"],
            recommended_action="Stand aside",
            bull_summary="Weak bullish case",
            bear_summary="Weak bearish case",
            model_used="data-driven-fallback",
            total_tokens=0,
            duration_ms=100,
            disclaimer="Not investment advice.",
        )
        assert thesis.direction == SignalDirection.NEUTRAL

    def test_empty_risk_factors(self) -> None:
        thesis = TradeThesis(
            direction=SignalDirection.BULLISH,
            conviction=0.8,
            entry_rationale="Strong bullish setup",
            risk_factors=[],
            recommended_action="Buy calls",
            bull_summary="Strong",
            bear_summary="Weak",
            model_used="llama3:8b",
            total_tokens=1000,
            duration_ms=5000,
            disclaimer="Not investment advice.",
        )
        assert thesis.risk_factors == []

    def test_conviction_boundary_zero(self) -> None:
        thesis = TradeThesis(
            direction=SignalDirection.NEUTRAL,
            conviction=0.0,
            entry_rationale="No edge",
            risk_factors=[],
            recommended_action="Do nothing",
            bull_summary="N/A",
            bear_summary="N/A",
            model_used="data-driven-fallback",
            total_tokens=0,
            duration_ms=0,
            disclaimer="Not investment advice.",
        )
        assert thesis.conviction == pytest.approx(0.0, abs=1e-9)

    def test_conviction_boundary_one(self) -> None:
        thesis = TradeThesis(
            direction=SignalDirection.BULLISH,
            conviction=1.0,
            entry_rationale="Maximum conviction",
            risk_factors=["Black swan"],
            recommended_action="Buy aggressively",
            bull_summary="All in",
            bear_summary="Ignored",
            model_used="llama3:8b",
            total_tokens=2000,
            duration_ms=10000,
            disclaimer="Not investment advice.",
        )
        assert thesis.conviction == pytest.approx(1.0, abs=1e-9)

    def test_conviction_above_one_rejected(self) -> None:
        with pytest.raises(ValidationError, match="conviction"):
            TradeThesis(
                direction=SignalDirection.BULLISH,
                conviction=1.5,
                entry_rationale="Over-confident",
                risk_factors=[],
                recommended_action="Buy",
                bull_summary="Bull",
                bear_summary="Bear",
                model_used="llama3:8b",
                total_tokens=0,
                duration_ms=0,
                disclaimer="Not investment advice.",
            )
