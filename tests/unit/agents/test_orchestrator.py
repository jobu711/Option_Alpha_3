"""Tests for the DebateOrchestrator.

Verifies the full Bull -> Bear -> Risk flow, fallback on various failure
modes, token accumulation, wall-clock timing, persistence calls, and
graceful persistence failure handling -- all with mocked agent runners.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import AgentParsed, _ThesisParsed
from Option_Alpha.agents.orchestrator import DebateOrchestrator
from Option_Alpha.data.repository import Repository
from Option_Alpha.models import GreeksCited, MarketContext, SignalDirection, TradeThesis

# ---------------------------------------------------------------------------
# Helpers: build mock return values
# ---------------------------------------------------------------------------

_PATCH_PREFIX = "Option_Alpha.agents.orchestrator"


def _make_bull_parsed() -> AgentParsed:
    """Build a realistic AgentParsed for the bull agent."""
    return AgentParsed(
        agent_role="bull",
        analysis="RSI at 55 suggests room for upward momentum.",
        key_points=["RSI neutral-to-bullish", "IV moderate", "Balanced sentiment"],
        conviction=0.65,
        contracts_referenced=["AAPL 185 call 2025-02-21"],
        greeks_cited=GreeksCited(delta=0.45, theta=-0.08),
    )


def _make_bear_parsed() -> AgentParsed:
    """Build a realistic AgentParsed for the bear agent."""
    return AgentParsed(
        agent_role="bear",
        analysis="Elevated IV rank at 45 limits upside.",
        key_points=["Near 52-week high", "Theta erodes value", "IV crush risk"],
        conviction=0.55,
        contracts_referenced=["AAPL 185 call 2025-02-21"],
        greeks_cited=GreeksCited(delta=0.45, theta=-0.08),
    )


def _make_risk_parsed() -> _ThesisParsed:
    """Build a realistic _ThesisParsed for the risk agent."""
    return _ThesisParsed(
        direction=SignalDirection.BULLISH,
        conviction=0.58,
        entry_rationale="Moderate bullish case.",
        risk_factors=["IV crush risk", "Theta decay"],
        recommended_action="Buy AAPL 185 call at mid price",
        bull_summary="Momentum favors mild upside.",
        bear_summary="Earnings risk caps gains.",
    )


def _make_usage(input_tokens: int = 400, output_tokens: int = 150) -> RunUsage:
    """Build a RunUsage with specified token counts."""
    return RunUsage(input_tokens=input_tokens, output_tokens=output_tokens, requests=1)


# ---------------------------------------------------------------------------
# Full debate success
# ---------------------------------------------------------------------------


class TestDebateOrchestratorSuccess:
    """Tests for the happy-path full debate flow."""

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_full_debate_success(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """All 3 agents succeed -> valid TradeThesis."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage(400, 150))
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage(500, 200))
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage(600, 250))

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert isinstance(thesis, TradeThesis)
        assert thesis.direction == SignalDirection.BULLISH
        assert thesis.conviction == pytest.approx(0.58, abs=0.01)

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_total_tokens_accumulated(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """total_tokens = sum of all 3 agents' input+output tokens."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage(400, 150))
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage(500, 200))
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage(600, 250))

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        # Bull: 400+150, Bear: 500+200, Risk: 600+250 = 2100
        expected_total = 400 + 150 + 500 + 200 + 600 + 250
        assert thesis.total_tokens == expected_total

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_duration_ms_non_negative(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """duration_ms >= 0 (wall clock time, may be 0 with fast mocks)."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage())

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.duration_ms >= 0

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_disclaimer_set(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """Thesis includes the educational disclaimer."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage())

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert "educational" in thesis.disclaimer.lower()
        assert "not investment advice" in thesis.disclaimer.lower()


# ---------------------------------------------------------------------------
# Fallback scenarios
# ---------------------------------------------------------------------------


class TestDebateOrchestratorFallback:
    """Tests for fallback when LLM is unavailable or agents fail."""

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_when_model_unavailable(
        self,
        mock_validate: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """validate_model_available() returns False -> fallback thesis."""
        mock_validate.return_value = False

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_bull_timeout(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """Bull agent times out -> fallback."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.side_effect = asyncio.TimeoutError

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_bear_timeout(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """Bear agent times out -> fallback."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.side_effect = TimeoutError()

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_risk_timeout(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """Risk agent times out -> fallback."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.side_effect = TimeoutError()

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_connect_error(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """httpx.ConnectError during agent -> fallback."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.side_effect = httpx.ConnectError("unreachable")

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_connection_refused(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """ConnectionRefusedError during agent -> fallback."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.side_effect = ConnectionRefusedError("refused")

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_fallback_on_validate_connect_error(
        self,
        mock_validate: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """httpx.ConnectError during validation -> fallback."""
        mock_validate.side_effect = httpx.ConnectError("unreachable")

        orchestrator = DebateOrchestrator()
        thesis = await orchestrator.run_debate(sample_market_context)

        assert thesis.model_used == "data-driven-fallback"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestDebateOrchestratorPersistence:
    """Tests for thesis persistence via Repository."""

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_persistence_called(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """repository.save_ai_thesis() called with correct args."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage())
        mock_repo = AsyncMock(spec=Repository)

        orchestrator = DebateOrchestrator(repository=mock_repo)
        thesis = await orchestrator.run_debate(sample_market_context)

        mock_repo.save_ai_thesis.assert_called_once_with("AAPL", thesis)

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_persistence_failure_does_not_crash(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """save_ai_thesis raises Exception -> debate still returns thesis."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage())
        mock_repo = AsyncMock(spec=Repository)
        mock_repo.save_ai_thesis = AsyncMock(side_effect=RuntimeError("db error"))

        orchestrator = DebateOrchestrator(repository=mock_repo)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert isinstance(thesis, TradeThesis)
        assert thesis.direction == SignalDirection.BULLISH

    @pytest.mark.asyncio()
    @patch(f"{_PATCH_PREFIX}.run_risk", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bear", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.run_bull", new_callable=AsyncMock)
    @patch(f"{_PATCH_PREFIX}.build_ollama_model")
    @patch(f"{_PATCH_PREFIX}.validate_model_available", new_callable=AsyncMock)
    async def test_no_persistence_without_repository(
        self,
        mock_validate: AsyncMock,
        mock_build_model: MagicMock,
        mock_run_bull: AsyncMock,
        mock_run_bear: AsyncMock,
        mock_run_risk: AsyncMock,
        sample_market_context: MarketContext,
    ) -> None:
        """repository=None -> no save called."""
        mock_validate.return_value = True
        mock_build_model.return_value = MagicMock()
        mock_run_bull.return_value = (_make_bull_parsed(), _make_usage())
        mock_run_bear.return_value = (_make_bear_parsed(), _make_usage())
        mock_run_risk.return_value = (_make_risk_parsed(), _make_usage())

        orchestrator = DebateOrchestrator(repository=None)
        thesis = await orchestrator.run_debate(sample_market_context)

        assert isinstance(thesis, TradeThesis)
