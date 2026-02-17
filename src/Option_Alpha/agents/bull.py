"""Bullish debate agent for the options analysis system.

Takes a ``MarketContext`` and produces an ``AgentResponse`` by calling the
Ollama LLM with the bull prompt template. JSON output is parsed and
validated with retry logic via the shared ``_parsing`` helper.
"""

from __future__ import annotations

import logging

from Option_Alpha.agents._parsing import (
    AGENT_RESPONSE_SCHEMA_HINT,
    AgentParsed,
    parse_with_retry,
    prompt_to_chat,
)
from Option_Alpha.agents.context_builder import build_context_text
from Option_Alpha.agents.llm_client import LLMClient
from Option_Alpha.agents.prompts import build_bull_messages
from Option_Alpha.models import AgentResponse, MarketContext

logger = logging.getLogger(__name__)


class BullAgent:
    """Bullish debate agent.

    Takes a ``MarketContext``, calls the LLM with the bull prompt, and
    returns a validated ``AgentResponse`` with token metadata.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def run(self, context: MarketContext) -> AgentResponse:
        """Execute the bull analysis.

        Steps:
        1. Build context text from ``MarketContext``.
        2. Build prompt messages via ``build_bull_messages()``.
        3. Convert ``PromptMessage`` -> ``ChatMessage``.
        4. Call the LLM with parse-and-retry.
        5. Attach token/model metadata from ``LLMResponse``.
        6. Return ``AgentResponse``.
        """
        logger.info("BullAgent: starting analysis for %s", context.ticker)

        context_text = build_context_text(context)
        prompt_messages = build_bull_messages(context_text)
        chat_messages = prompt_to_chat(prompt_messages)

        parsed, llm_response = await parse_with_retry(
            self._llm_client,
            chat_messages,
            AgentParsed,
            schema_hint=AGENT_RESPONSE_SCHEMA_HINT,
        )

        response = AgentResponse(
            agent_role=parsed.agent_role,
            analysis=parsed.analysis,
            key_points=parsed.key_points,
            conviction=parsed.conviction,
            contracts_referenced=parsed.contracts_referenced,
            greeks_cited=parsed.greeks_cited,
            model_used=llm_response.model,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
        )

        logger.info(
            "BullAgent: completed for %s (conviction=%.2f, tokens=%d+%d)",
            context.ticker,
            response.conviction,
            response.input_tokens,
            response.output_tokens,
        )

        return response
