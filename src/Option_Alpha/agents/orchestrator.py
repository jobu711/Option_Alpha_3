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
import pydantic
from pydantic_ai.exceptions import UnexpectedModelBehavior

from Option_Alpha.agents._parsing import DISCLAIMER
from Option_Alpha.agents.bear import BearDeps, run_bear
from Option_Alpha.agents.bull import BullDeps, run_bull
from Option_Alpha.agents.context_builder import build_context_text
from Option_Alpha.agents.fallback import build_fallback_thesis
from Option_Alpha.agents.model_config import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    build_ollama_model,
    validate_model_available,
)
from Option_Alpha.agents.risk import RiskDeps, run_risk
from Option_Alpha.data.repository import Repository
from Option_Alpha.models import MarketContext, SignalDirection, TradeThesis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_TIMEOUT: float = 180.0
_BULLISH_SCORE_THRESHOLD: float = 50.0

# Exceptions that trigger data-driven fallback
_FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    asyncio.TimeoutError,
    json.JSONDecodeError,
    pydantic.ValidationError,
    UnexpectedModelBehavior,
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
    host:
        Base URL of the Ollama server (e.g. ``http://localhost:11434``).
    model_name:
        Name of the Ollama model to use (e.g. ``llama3.1:8b``).
    repository:
        Optional persistence layer. If provided, the final thesis is
        saved via ``repository.save_ai_thesis()``.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        model_name: str = DEFAULT_MODEL,
        repository: Repository | None = None,
    ) -> None:
        self._host = host
        self._model_name = model_name
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
            model_available = await validate_model_available(self._host, self._model_name)
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
        model = build_ollama_model(self._host, self._model_name)
        context_text = build_context_text(context)

        # Bull
        logger.info("DebateOrchestrator: running bull agent for %s", context.ticker)
        bull_deps = BullDeps(context_text=context_text)
        bull_parsed, bull_usage = await asyncio.wait_for(
            run_bull(bull_deps, model),
            timeout=_AGENT_TIMEOUT,
        )

        # Bear
        logger.info("DebateOrchestrator: running bear agent for %s", context.ticker)
        bear_deps = BearDeps(context_text=context_text, bull_argument=bull_parsed.analysis)
        bear_parsed, bear_usage = await asyncio.wait_for(
            run_bear(bear_deps, model),
            timeout=_AGENT_TIMEOUT,
        )

        # Risk
        logger.info("DebateOrchestrator: running risk agent for %s", context.ticker)
        risk_deps = RiskDeps(
            context_text=context_text,
            bull_argument=bull_parsed.analysis,
            bear_argument=bear_parsed.analysis,
        )
        risk_parsed, risk_usage = await asyncio.wait_for(
            run_risk(risk_deps, model),
            timeout=_AGENT_TIMEOUT,
        )

        # Accumulate total tokens from all three agents
        combined_usage = bull_usage + bear_usage + risk_usage
        total_tokens = combined_usage.total_tokens

        # Compute wall-clock duration
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Reconstruct thesis with accumulated totals (frozen model)
        final_thesis = TradeThesis(
            direction=risk_parsed.direction,
            conviction=risk_parsed.conviction,
            entry_rationale=risk_parsed.entry_rationale,
            risk_factors=risk_parsed.risk_factors,
            recommended_action=risk_parsed.recommended_action,
            bull_summary=risk_parsed.bull_summary,
            bear_summary=risk_parsed.bear_summary,
            model_used=self._model_name,
            total_tokens=total_tokens,
            duration_ms=elapsed_ms,
            disclaimer=DISCLAIMER,
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
