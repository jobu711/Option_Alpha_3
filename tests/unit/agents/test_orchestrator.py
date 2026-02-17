"""Tests for the DebateOrchestrator.

Verifies the full Bull -> Bear -> Risk flow, fallback on various failure
modes, token accumulation, wall-clock timing, persistence calls, and
graceful persistence failure handling -- all with mocked agents and LLM.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from Option_Alpha.agents.llm_client import LLMClient, LLMResponse
from Option_Alpha.agents.orchestrator import DebateOrchestrator
from Option_Alpha.data.repository import Repository
from Option_Alpha.models import MarketContext, SignalDirection, TradeThesis

# ---------------------------------------------------------------------------
# Mock LLM response data
# ---------------------------------------------------------------------------

MOCK_BULL_JSON: str = json.dumps(
    {
        "agent_role": "bull",
        "analysis": "RSI at 55 suggests room for upward momentum.",
        "key_points": ["RSI neutral-to-bullish", "IV moderate", "Balanced sentiment"],
        "conviction": 0.65,
        "contracts_referenced": ["AAPL 185 call 2025-02-21"],
        "greeks_cited": {"delta": 0.45, "theta": -0.08, "vega": None, "gamma": None, "rho": None},
    }
)

MOCK_BEAR_JSON: str = json.dumps(
    {
        "agent_role": "bear",
        "analysis": "Elevated IV rank at 45 limits upside.",
        "key_points": ["Near 52-week high", "Theta erodes value", "IV crush risk"],
        "conviction": 0.55,
        "contracts_referenced": ["AAPL 185 call 2025-02-21"],
        "greeks_cited": {"delta": 0.45, "theta": -0.08, "vega": None, "gamma": None, "rho": None},
    }
)

MOCK_THESIS_JSON: str = json.dumps(
    {
        "direction": "bullish",
        "conviction": 0.58,
        "entry_rationale": "Moderate bullish case.",
        "risk_factors": ["IV crush risk", "Theta decay"],
        "recommended_action": "Buy AAPL 185 call at mid price",
        "bull_summary": "Momentum favors mild upside.",
        "bear_summary": "Earnings risk caps gains.",
    }
)


def _make_llm_response(
    content: str,
    input_tokens: int = 500,
    output_tokens: int = 200,
) -> LLMResponse:
    return LLMResponse(
        content=content,
        model="llama3.1:8b",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=3000,
    )


def _build_mock_llm_client() -> AsyncMock:
    """Build a mock LLMClient that returns valid responses for all 3 agents."""
    mock_llm = AsyncMock(spec=LLMClient)
    mock_llm.validate_model = AsyncMock(return_value=True)

    bull_resp = _make_llm_response(MOCK_BULL_JSON, input_tokens=400, output_tokens=150)
    bear_resp = _make_llm_response(MOCK_BEAR_JSON, input_tokens=500, output_tokens=200)
    thesis_resp = _make_llm_response(MOCK_THESIS_JSON, input_tokens=600, output_tokens=250)

    mock_llm.chat = AsyncMock(side_effect=[bull_resp, bear_resp, thesis_resp])
    return mock_llm


# ---------------------------------------------------------------------------
# Full debate success
# ---------------------------------------------------------------------------


class TestDebateOrchestratorSuccess:
    """Tests for the happy-path full debate flow."""

    @pytest.mark.asyncio()
    async def test_full_debate_success(self, sample_market_context: MarketContext) -> None:
        """All 3 agents succeed -> valid TradeThesis."""
        mock_llm = _build_mock_llm_client()
        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert isinstance(thesis, TradeThesis)
        assert thesis.direction == SignalDirection.BULLISH
        assert thesis.conviction == pytest.approx(0.58, abs=0.01)

    @pytest.mark.asyncio()
    async def test_total_tokens_accumulated(self, sample_market_context: MarketContext) -> None:
        """total_tokens = sum of all 3 agents' input+output tokens."""
        mock_llm = _build_mock_llm_client()
        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        # Bull: 400+150, Bear: 500+200, Risk: 600+250 = 2100
        expected_total = 400 + 150 + 500 + 200 + 600 + 250
        assert thesis.total_tokens == expected_total

    @pytest.mark.asyncio()
    async def test_duration_ms_non_negative(self, sample_market_context: MarketContext) -> None:
        """duration_ms >= 0 (wall clock time, may be 0 with fast mocks)."""
        mock_llm = _build_mock_llm_client()
        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        # With mocked LLM calls that return instantly, duration_ms may be 0.
        # In production it will be positive. We verify it is at least non-negative.
        assert thesis.duration_ms >= 0


# ---------------------------------------------------------------------------
# Fallback scenarios
# ---------------------------------------------------------------------------


class TestDebateOrchestratorFallback:
    """Tests for fallback when LLM is unavailable or agents fail."""

    @pytest.mark.asyncio()
    async def test_fallback_when_model_unavailable(
        self, sample_market_context: MarketContext
    ) -> None:
        """validate_model() returns False -> fallback thesis."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=False)

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_fallback_on_bull_timeout(self, sample_market_context: MarketContext) -> None:
        """Bull agent times out -> fallback."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=True)
        mock_llm.chat = AsyncMock(side_effect=asyncio.TimeoutError)

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_fallback_on_bear_timeout(self, sample_market_context: MarketContext) -> None:
        """Bear agent times out -> fallback."""
        bull_resp = _make_llm_response(MOCK_BULL_JSON)

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=True)
        # Bull succeeds, bear times out
        mock_llm.chat = AsyncMock(side_effect=[bull_resp, TimeoutError()])

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_fallback_on_risk_timeout(self, sample_market_context: MarketContext) -> None:
        """Risk agent times out -> fallback."""
        bull_resp = _make_llm_response(MOCK_BULL_JSON)
        bear_resp = _make_llm_response(MOCK_BEAR_JSON)

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=True)
        mock_llm.chat = AsyncMock(side_effect=[bull_resp, bear_resp, TimeoutError()])

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_fallback_on_connect_error(self, sample_market_context: MarketContext) -> None:
        """httpx.ConnectError during agent -> fallback."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=True)
        mock_llm.chat = AsyncMock(side_effect=httpx.ConnectError("unreachable"))

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    async def test_fallback_on_parse_error(self, sample_market_context: MarketContext) -> None:
        """json.JSONDecodeError after retries -> fallback."""
        bad_resp = _make_llm_response("garbage not json")

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.validate_model = AsyncMock(return_value=True)
        mock_llm.chat = AsyncMock(return_value=bad_resp)

        orchestrator = DebateOrchestrator(mock_llm)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestDebateOrchestratorPersistence:
    """Tests for thesis persistence via Repository."""

    @pytest.mark.asyncio()
    async def test_persistence_called(self, sample_market_context: MarketContext) -> None:
        """repository.save_ai_thesis() called with correct args."""
        mock_llm = _build_mock_llm_client()
        mock_repo = AsyncMock(spec=Repository)

        orchestrator = DebateOrchestrator(mock_llm, repository=mock_repo)
        thesis = await orchestrator.run_debate(sample_market_context)

        mock_repo.save_ai_thesis.assert_called_once_with("AAPL", thesis)

    @pytest.mark.asyncio()
    async def test_persistence_failure_does_not_crash(
        self, sample_market_context: MarketContext
    ) -> None:
        """save_ai_thesis raises Exception -> debate still returns thesis."""
        mock_llm = _build_mock_llm_client()
        mock_repo = AsyncMock(spec=Repository)
        mock_repo.save_ai_thesis = AsyncMock(side_effect=RuntimeError("db error"))

        orchestrator = DebateOrchestrator(mock_llm, repository=mock_repo)
        thesis = await orchestrator.run_debate(sample_market_context)

        # Debate completed despite persistence failure
        assert isinstance(thesis, TradeThesis)
        assert thesis.direction == SignalDirection.BULLISH

    @pytest.mark.asyncio()
    async def test_no_persistence_without_repository(
        self, sample_market_context: MarketContext
    ) -> None:
        """repository=None -> no save called."""
        mock_llm = _build_mock_llm_client()

        orchestrator = DebateOrchestrator(mock_llm, repository=None)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert isinstance(thesis, TradeThesis)
        # No repository means no save_ai_thesis call -- we just verify no error
