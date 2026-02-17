"""Tests for the BearAgent.

Verifies that the bear agent receives the bull's analysis, produces a
valid bearish AgentResponse, handles token metadata, and retries on
parse failures -- all with a mocked LLMClient.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from Option_Alpha.agents.bear import BearAgent
from Option_Alpha.agents.llm_client import LLMClient, LLMResponse
from Option_Alpha.models import AgentResponse, GreeksCited, MarketContext

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_BEAR_JSON: str = json.dumps(
    {
        "agent_role": "bear",
        "analysis": "Elevated IV rank at 45 and proximity to 52-week high suggest limited upside.",
        "key_points": [
            "Price near 52-week high of $199.62 limits upside potential",
            "Theta decay at -$0.08/day erodes position value",
            "Earnings in 37 DTE introduces IV crush risk",
        ],
        "conviction": 0.55,
        "contracts_referenced": ["AAPL 185 call 2025-02-21"],
        "greeks_cited": {
            "delta": 0.45,
            "theta": -0.08,
            "vega": None,
            "gamma": None,
            "rho": None,
        },
    }
)


def _make_bear_llm_response(content: str = MOCK_BEAR_JSON) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="llama3.1:8b",
        input_tokens=600,
        output_tokens=250,
        duration_ms=3500,
    )


def _make_bull_agent_response() -> AgentResponse:
    """Create a sample bull AgentResponse to pass to the bear agent."""
    return AgentResponse(
        agent_role="bull",
        analysis="RSI at 55 suggests room for upward momentum.",
        key_points=["RSI neutral-to-bullish", "IV moderate"],
        conviction=0.65,
        contracts_referenced=["AAPL 185 call 2025-02-21"],
        greeks_cited=GreeksCited(delta=0.45, theta=-0.08),
        model_used="llama3.1:8b",
        input_tokens=500,
        output_tokens=200,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBearAgent:
    """Tests for BearAgent.run()."""

    @pytest.mark.asyncio()
    async def test_bear_run_success(self, sample_market_context: MarketContext) -> None:
        """Mock LLM returns valid bear JSON -> AgentResponse with role='bear'."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bear_llm_response())

        agent = BearAgent(mock_llm)
        result = await agent.run(sample_market_context, _make_bull_agent_response())

        assert isinstance(result, AgentResponse)
        assert result.agent_role == "bear"

    @pytest.mark.asyncio()
    async def test_bear_receives_bull_analysis(self, sample_market_context: MarketContext) -> None:
        """Verify bear prompt includes the bull's analysis text."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bear_llm_response())

        bull_resp = _make_bull_agent_response()
        agent = BearAgent(mock_llm)
        await agent.run(sample_market_context, bull_resp)

        # The first call's first arg is the messages list
        call_args = mock_llm.chat.call_args_list[0]
        messages = call_args[0][0]
        user_msg_content = messages[1].content
        assert bull_resp.analysis in user_msg_content

    @pytest.mark.asyncio()
    async def test_bear_conviction_range(self, sample_market_context: MarketContext) -> None:
        """Conviction preserved from LLM output."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bear_llm_response())

        agent = BearAgent(mock_llm)
        result = await agent.run(sample_market_context, _make_bull_agent_response())

        assert result.conviction == pytest.approx(0.55, abs=0.01)

    @pytest.mark.asyncio()
    async def test_bear_token_counts(self, sample_market_context: MarketContext) -> None:
        """Tokens passed through from LLMResponse."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bear_llm_response())

        agent = BearAgent(mock_llm)
        result = await agent.run(sample_market_context, _make_bull_agent_response())

        assert result.input_tokens == 600
        assert result.output_tokens == 250

    @pytest.mark.asyncio()
    async def test_bear_parse_failure_retries(self, sample_market_context: MarketContext) -> None:
        """First response bad JSON, second good -> succeeds."""
        bad_resp = _make_bear_llm_response("invalid json")
        good_resp = _make_bear_llm_response(MOCK_BEAR_JSON)

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad_resp, good_resp])

        agent = BearAgent(mock_llm)
        result = await agent.run(sample_market_context, _make_bull_agent_response())

        assert result.agent_role == "bear"
        assert mock_llm.chat.call_count == 2

    @pytest.mark.asyncio()
    async def test_bear_all_retries_fail(self, sample_market_context: MarketContext) -> None:
        """All attempts fail -> raises exception."""
        bad_resp = _make_bear_llm_response("garbage")
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=bad_resp)

        agent = BearAgent(mock_llm)

        with pytest.raises(Exception):  # noqa: B017, PT011
            await agent.run(sample_market_context, _make_bull_agent_response())
