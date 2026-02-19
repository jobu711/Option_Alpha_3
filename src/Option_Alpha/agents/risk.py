"""Risk/moderator agent for the options analysis system.

Receives both bull and bear ``AgentResponse`` objects, synthesizes a final
``TradeThesis`` with direction, conviction, and risk factors. JSON output is
parsed and validated with retry logic via the shared ``_parsing`` helper.

The risk agent does NOT populate ``model_used``, ``total_tokens``, or
``duration_ms`` from the LLM output — those are set by code after parsing.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict

from Option_Alpha.agents._parsing import (
    THESIS_SCHEMA_HINT,
    parse_with_retry,
    prompt_to_chat,
)
from Option_Alpha.agents.context_builder import build_context_text
from Option_Alpha.agents.llm_client import LLMClient, LLMResponse
from Option_Alpha.agents.prompts import build_risk_messages
from Option_Alpha.models import AgentResponse, MarketContext, SignalDirection, TradeThesis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intermediate model for parsing (LLM output fields only)
# ---------------------------------------------------------------------------


class _ThesisParsed(BaseModel):
    """Intermediate model matching the JSON schema the LLM is asked to produce.

    Does NOT include ``model_used``, ``total_tokens``, or ``duration_ms``
    — those are added by the orchestrator / risk agent code.
    """

    model_config = ConfigDict(frozen=True)

    direction: SignalDirection
    conviction: float
    entry_rationale: str
    risk_factors: list[str]
    recommended_action: str
    bull_summary: str
    bear_summary: str


class RiskAgent:
    """Risk assessment / moderator agent.

    Synthesizes the bull and bear arguments into a final ``TradeThesis``.
    The LLM response only provides the content fields; metadata (model,
    tokens, timing) is added by code.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def run(
        self,
        context: MarketContext,
        bull_response: AgentResponse,
        bear_response: AgentResponse,
    ) -> tuple[TradeThesis, LLMResponse]:
        """Execute the risk assessment.

        Returns a tuple of ``(TradeThesis, LLMResponse)`` so the orchestrator
        can access the raw LLM metadata for token accumulation.

        Steps:
        1. Build context text from ``MarketContext``.
        2. Build risk prompt messages with both analyses.
        3. Convert ``PromptMessage`` -> ``ChatMessage``.
        4. Call the LLM with parse-and-retry.
        5. Build ``TradeThesis`` from parsed data + code-provided metadata.
        6. Return ``(TradeThesis, LLMResponse)``.
        """
        logger.info("RiskAgent: starting synthesis for %s", context.ticker)

        context_text = build_context_text(context)
        prompt_messages = build_risk_messages(
            context_text,
            bull_response.analysis,
            bear_response.analysis,
        )
        chat_messages = prompt_to_chat(prompt_messages)

        parsed, llm_response = await parse_with_retry(
            self._llm_client,
            chat_messages,
            _ThesisParsed,
            schema_hint=THESIS_SCHEMA_HINT,
        )

        # model_used, total_tokens, duration_ms filled by orchestrator;
        # we set initial values here that the orchestrator will override.
        thesis = TradeThesis(
            direction=parsed.direction,
            conviction=parsed.conviction,
            entry_rationale=parsed.entry_rationale,
            risk_factors=parsed.risk_factors,
            recommended_action=parsed.recommended_action,
            bull_summary=parsed.bull_summary,
            bear_summary=parsed.bear_summary,
            model_used=llm_response.model,
            total_tokens=0,
            duration_ms=0,
        )

        logger.info(
            "RiskAgent: completed for %s (direction=%s, conviction=%.2f)",
            context.ticker,
            thesis.direction.value,
            thesis.conviction,
        )

        return thesis, llm_response
