"""Tests for the RiskAgent.

Verifies that the risk agent synthesizes bull + bear into a TradeThesis,
preserves direction and disclaimer, sets initial token values, and
handles parse failures -- all with a mocked LLMClient.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from Option_Alpha.agents.llm_client import LLMClient, LLMResponse
from Option_Alpha.agents.risk import RiskAgent
from Option_Alpha.models import (
    AgentResponse,
    GreeksCited,
    MarketContext,
    SignalDirection,
    TradeThesis,
)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_THESIS_JSON: str = json.dumps(
    {
        "direction": "bullish",
        "conviction": 0.58,
        "entry_rationale": "Moderate bullish case with RSI at 55 and balanced sentiment.",
        "risk_factors": ["IV crush risk near earnings", "Theta decay of $0.08/day"],
        "recommended_action": "Buy AAPL 185 call at mid price with tight stop",
        "bull_summary": "Momentum indicators favor mild upside with moderate conviction.",
        "bear_summary": "Proximity to 52-week high and earnings risk cap potential gains.",
    }
)


def _make_risk_llm_response(content: str = MOCK_THESIS_JSON) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="llama3.1:8b",
        input_tokens=700,
        output_tokens=300,
        duration_ms=4000,
    )


def _make_agent_response(role: str) -> AgentResponse:
    """Create a sample AgentResponse for the given role."""
    return AgentResponse(
        agent_role=role,
        analysis=f"Sample {role} analysis.",
        key_points=[f"{role} point 1", f"{role} point 2"],
        conviction=0.60,
        contracts_referenced=["AAPL 185 call 2025-02-21"],
        greeks_cited=GreeksCited(delta=0.45, theta=-0.08),
        model_used="llama3.1:8b",
        input_tokens=500,
        output_tokens=200,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRiskAgent:
    """Tests for RiskAgent.run()."""

    @pytest.mark.asyncio()
    async def test_risk_run_success(self, sample_market_context: MarketContext) -> None:
        """Returns (TradeThesis, LLMResponse) tuple."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_risk_llm_response())

        agent = RiskAgent(mock_llm)
        thesis, llm_resp = await agent.run(
            sample_market_context,
            _make_agent_response("bull"),
            _make_agent_response("bear"),
        )

        assert isinstance(thesis, TradeThesis)
        assert isinstance(llm_resp, LLMResponse)

    @pytest.mark.asyncio()
    async def test_risk_direction_from_llm(self, sample_market_context: MarketContext) -> None:
        """direction field from LLM JSON is preserved."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_risk_llm_response())

        agent = RiskAgent(mock_llm)
        thesis, _ = await agent.run(
            sample_market_context,
            _make_agent_response("bull"),
            _make_agent_response("bear"),
        )

        assert thesis.direction == SignalDirection.BULLISH

    @pytest.mark.asyncio()
    async def test_risk_disclaimer_set(self, sample_market_context: MarketContext) -> None:
        """disclaimer is the standard educational disclaimer string."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_risk_llm_response())

        agent = RiskAgent(mock_llm)
        thesis, _ = await agent.run(
            sample_market_context,
            _make_agent_response("bull"),
            _make_agent_response("bear"),
        )

        assert "educational" in thesis.disclaimer.lower()
        assert "not investment advice" in thesis.disclaimer.lower()

    @pytest.mark.asyncio()
    async def test_risk_initial_tokens_zero(self, sample_market_context: MarketContext) -> None:
        """total_tokens=0 and duration_ms=0 (orchestrator fills these)."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_risk_llm_response())

        agent = RiskAgent(mock_llm)
        thesis, _ = await agent.run(
            sample_market_context,
            _make_agent_response("bull"),
            _make_agent_response("bear"),
        )

        assert thesis.total_tokens == 0
        assert thesis.duration_ms == 0

    @pytest.mark.asyncio()
    async def test_risk_parse_failure_retries(self, sample_market_context: MarketContext) -> None:
        """First response bad JSON, second good -> succeeds."""
        bad_resp = _make_risk_llm_response("not json")
        good_resp = _make_risk_llm_response(MOCK_THESIS_JSON)

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad_resp, good_resp])

        agent = RiskAgent(mock_llm)
        thesis, _ = await agent.run(
            sample_market_context,
            _make_agent_response("bull"),
            _make_agent_response("bear"),
        )

        assert thesis.direction == SignalDirection.BULLISH

    @pytest.mark.asyncio()
    async def test_risk_all_retries_fail(self, sample_market_context: MarketContext) -> None:
        """All attempts fail -> raises exception."""
        bad_resp = _make_risk_llm_response("garbage")
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=bad_resp)

        agent = RiskAgent(mock_llm)

        with pytest.raises(Exception):  # noqa: B017, PT011
            await agent.run(
                sample_market_context,
                _make_agent_response("bull"),
                _make_agent_response("bear"),
            )
