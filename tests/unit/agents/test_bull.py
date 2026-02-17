"""Tests for the BullAgent.

Verifies prompt construction, LLM response parsing, conviction passthrough,
token metadata, and retry behaviour -- all with a mocked LLMClient.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from Option_Alpha.agents.bull import BullAgent
from Option_Alpha.agents.llm_client import LLMClient, LLMResponse
from Option_Alpha.models import AgentResponse, MarketContext

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_BULL_JSON: str = json.dumps(
    {
        "agent_role": "bull",
        "analysis": "RSI at 55 suggests room for upward momentum. MACD neutral crossover pending.",
        "key_points": [
            "RSI at 55.3 indicates neutral-to-bullish momentum",
            "IV rank at 45.2 suggests moderate options pricing",
            "Put/call ratio at 0.85 shows balanced sentiment",
        ],
        "conviction": 0.65,
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


def _make_bull_llm_response(content: str = MOCK_BULL_JSON) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="llama3.1:8b",
        input_tokens=500,
        output_tokens=200,
        duration_ms=3000,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBullAgent:
    """Tests for BullAgent.run()."""

    @pytest.mark.asyncio()
    async def test_bull_run_success(self, sample_market_context: MarketContext) -> None:
        """Mock LLM returns valid bull JSON -> AgentResponse with role='bull'."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bull_llm_response())

        agent = BullAgent(mock_llm)
        result = await agent.run(sample_market_context)

        assert isinstance(result, AgentResponse)
        assert result.agent_role == "bull"
        assert len(result.key_points) == 3  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_bull_conviction_range(self, sample_market_context: MarketContext) -> None:
        """Conviction from LLM is preserved in AgentResponse."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bull_llm_response())

        agent = BullAgent(mock_llm)
        result = await agent.run(sample_market_context)

        assert result.conviction == pytest.approx(0.65, abs=0.01)

    @pytest.mark.asyncio()
    async def test_bull_model_used_from_llm(self, sample_market_context: MarketContext) -> None:
        """model_used comes from LLMResponse.model."""
        resp = LLMResponse(
            content=MOCK_BULL_JSON,
            model="custom-model:latest",
            input_tokens=500,
            output_tokens=200,
            duration_ms=3000,
        )
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=resp)

        agent = BullAgent(mock_llm)
        result = await agent.run(sample_market_context)

        assert result.model_used == "custom-model:latest"

    @pytest.mark.asyncio()
    async def test_bull_token_counts(self, sample_market_context: MarketContext) -> None:
        """input/output tokens correctly passed through."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_bull_llm_response())

        agent = BullAgent(mock_llm)
        result = await agent.run(sample_market_context)

        assert result.input_tokens == 500  # noqa: PLR2004
        assert result.output_tokens == 200  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_bull_parse_failure_retries(self, sample_market_context: MarketContext) -> None:
        """First response bad JSON, second good -> succeeds."""
        bad_resp = _make_bull_llm_response("not valid json {{")
        good_resp = _make_bull_llm_response(MOCK_BULL_JSON)

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad_resp, good_resp])

        agent = BullAgent(mock_llm)
        result = await agent.run(sample_market_context)

        assert result.agent_role == "bull"
        assert mock_llm.chat.call_count == 2  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_bull_all_retries_fail(self, sample_market_context: MarketContext) -> None:
        """All attempts fail -> raises exception."""
        bad_resp = _make_bull_llm_response("garbage")
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=bad_resp)

        agent = BullAgent(mock_llm)

        with pytest.raises(Exception):  # noqa: B017, PT011
            await agent.run(sample_market_context)
