"""Debate orchestrator: runs the full Bull -> Bear -> Risk single-pass flow.

If the Ollama LLM is unavailable or any agent fails (timeout, parse error,
connection refused), the orchestrator falls back to a data-driven thesis
built from composite score and indicator values alone.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

import httpx
import ollama
import pydantic

from Option_Alpha.agents.bear import BearAgent
from Option_Alpha.agents.bull import BullAgent
from Option_Alpha.agents.fallback import build_fallback_thesis
from Option_Alpha.agents.llm_client import DEFAULT_TIMEOUT, LLMClient
from Option_Alpha.agents.risk import RiskAgent
from Option_Alpha.data.repository import Repository
from Option_Alpha.models import MarketContext, SignalDirection, TradeThesis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_TIMEOUT: float = DEFAULT_TIMEOUT
_BULLISH_SCORE_THRESHOLD: float = 50.0

# Exceptions that trigger data-driven fallback
_FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.TimeoutError,
    json.JSONDecodeError,
    pydantic.ValidationError,
    ollama.ResponseError,
    httpx.ConnectError,
    ConnectionRefusedError,
)


def _direction_from_score(composite_score: float) -> SignalDirection:
    """Derive signal direction from composite score for fallback."""
    if composite_score >= _BULLISH_SCORE_THRESHOLD:
        return SignalDirection.BULLISH
    return SignalDirection.BEARISH


class DebateOrchestrator:
    """Runs the full Bull -> Bear -> Risk single-pass debate flow.

    Parameters
    ----------
    llm_client:
        Shared Ollama LLM client used by all three agents.
    repository:
        Optional persistence layer. If provided, the final thesis is
        saved via ``repository.save_ai_thesis()``.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        repository: Repository | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._repository = repository

    async def run_debate(
        self,
        context: MarketContext,
        *,
        composite_score: float = 50.0,
        iv_rank: float = 50.0,
        rsi_14: float = 50.0,
        adx: float | None = None,
    ) -> TradeThesis:
        """Run a full debate on the given market context.

        Flow:
        1. Validate model availability.
        2. Run Bull -> Bear -> Risk sequentially.
        3. Accumulate token counts and wall-clock timing.
        4. Persist thesis if repository is provided.
        5. On any failure, fall back to data-driven thesis.

        Parameters
        ----------
        context:
            Market context snapshot for the debate.
        composite_score:
            Overall score from the scoring engine (0-100).
        iv_rank:
            Current IV rank (0-100).
        rsi_14:
            14-period RSI value.
        adx:
            Average Directional Index value, or ``None`` if unavailable.

        Returns
        -------
        TradeThesis
            The final trade thesis (AI-debated or data-driven fallback).
        """
        logger.info("DebateOrchestrator: starting debate for %s", context.ticker)
        start_time = time.monotonic()

        # Check LLM availability
        try:
            model_available = await self._llm_client.validate_model()
        except _FALLBACK_EXCEPTIONS as exc:
            logger.warning(
                "DebateOrchestrator: LLM validation failed for %s: %s",
                context.ticker,
                exc,
            )
            model_available = False

        if not model_available:
            logger.warning(
                "DebateOrchestrator: LLM unavailable, using fallback for %s",
                context.ticker,
            )
            return await self._fallback(
                context.ticker,
                composite_score=composite_score,
                iv_rank=iv_rank,
                rsi_14=rsi_14,
                adx=adx,
            )

        try:
            thesis = await self._run_agents(
                context,
                start_time=start_time,
            )
        except _FALLBACK_EXCEPTIONS as exc:
            logger.warning(
                "DebateOrchestrator: agent failure for %s, using fallback: %s",
                context.ticker,
                exc,
            )
            return await self._fallback(
                context.ticker,
                composite_score=composite_score,
                iv_rank=iv_rank,
                rsi_14=rsi_14,
                adx=adx,
            )

        # Persist if repository available
        if self._repository is not None:
            try:
                await self._repository.save_ai_thesis(context.ticker, thesis)
                logger.info(
                    "DebateOrchestrator: persisted thesis for %s",
                    context.ticker,
                )
            except Exception:
                logger.exception(
                    "DebateOrchestrator: failed to persist thesis for %s",
                    context.ticker,
                )

        return thesis

    async def _run_agents(
        self,
        context: MarketContext,
        *,
        start_time: float,
    ) -> TradeThesis:
        """Execute the three agents sequentially and build the final thesis."""
        bull_agent = BullAgent(self._llm_client)
        bear_agent = BearAgent(self._llm_client)
        risk_agent = RiskAgent(self._llm_client)

        # Bull
        logger.info("DebateOrchestrator: running bull agent for %s", context.ticker)
        bull_response = await asyncio.wait_for(
            bull_agent.run(context),
            timeout=_AGENT_TIMEOUT,
        )

        # Bear
        logger.info("DebateOrchestrator: running bear agent for %s", context.ticker)
        bear_response = await asyncio.wait_for(
            bear_agent.run(context, bull_response),
            timeout=_AGENT_TIMEOUT,
        )

        # Risk
        logger.info("DebateOrchestrator: running risk agent for %s", context.ticker)
        risk_thesis, risk_llm_response = await asyncio.wait_for(
            risk_agent.run(context, bull_response, bear_response),
            timeout=_AGENT_TIMEOUT,
        )

        # Accumulate total tokens from all three agents
        total_tokens = (
            bull_response.input_tokens
            + bull_response.output_tokens
            + bear_response.input_tokens
            + bear_response.output_tokens
            + risk_llm_response.input_tokens
            + risk_llm_response.output_tokens
        )

        # Compute wall-clock duration
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Reconstruct thesis with accumulated totals (frozen model)
        final_thesis = TradeThesis(
            direction=risk_thesis.direction,
            conviction=risk_thesis.conviction,
            entry_rationale=risk_thesis.entry_rationale,
            risk_factors=risk_thesis.risk_factors,
            recommended_action=risk_thesis.recommended_action,
            bull_summary=risk_thesis.bull_summary,
            bear_summary=risk_thesis.bear_summary,
            model_used=risk_thesis.model_used,
            total_tokens=total_tokens,
            duration_ms=elapsed_ms,
        )

        logger.info(
            "DebateOrchestrator: debate complete for %s "
            "(direction=%s, conviction=%.2f, tokens=%d, duration=%dms)",
            context.ticker,
            final_thesis.direction.value,
            final_thesis.conviction,
            total_tokens,
            elapsed_ms,
        )

        return final_thesis

    async def _fallback(
        self,
        ticker: str,
        *,
        composite_score: float,
        iv_rank: float,
        rsi_14: float,
        adx: float | None,
    ) -> TradeThesis:
        """Build a data-driven fallback thesis."""
        direction = _direction_from_score(composite_score)
        return await build_fallback_thesis(
            ticker,
            composite_score,
            direction,
            iv_rank=iv_rank,
            rsi_14=rsi_14,
            adx=adx,
        )
