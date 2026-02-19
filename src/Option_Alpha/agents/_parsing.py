"""Shared JSON-parse-and-validate-with-retry helper for debate agents.

All three agents (bull, bear, risk) need to parse LLM text output as JSON
and validate it against a Pydantic model. On failure they retry up to
``MAX_RETRIES`` times by appending a schema hint to the conversation and
re-calling the LLM.

This is a private module — not exported from ``agents/__init__.py``.
"""

from __future__ import annotations

import json
import logging
import re

import pydantic
from pydantic import BaseModel, ConfigDict

from Option_Alpha.agents.llm_client import (
    DEFAULT_TIMEOUT,
    ChatMessage,
    LLMClient,
    LLMResponse,
)
from Option_Alpha.agents.prompts.bull_prompt import PromptMessage
from Option_Alpha.models import GreeksCited

logger = logging.getLogger(__name__)

MAX_RETRIES: int = 2

# Regex to strip markdown JSON fences the LLM sometimes wraps around output.
_JSON_FENCE_RE: re.Pattern[str] = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.DOTALL)

# ---------------------------------------------------------------------------
# Shared constants used by bull, bear, and risk agents
# ---------------------------------------------------------------------------

AGENT_RESPONSE_SCHEMA_HINT: str = (
    '{"agent_role": "bull|bear", "analysis": "...", "key_points": ["..."], '
    '"conviction": 0.0, "contracts_referenced": ["..."], '
    '"greeks_cited": {"delta": null, "gamma": null, "theta": null, '
    '"vega": null, "rho": null}}'
)

THESIS_SCHEMA_HINT: str = (
    '{"direction": "bullish|bearish|neutral", "conviction": 0.0, '
    '"entry_rationale": "...", "risk_factors": ["..."], '
    '"recommended_action": "...", "bull_summary": "...", '
    '"bear_summary": "..."}'
)


# ---------------------------------------------------------------------------
# Shared intermediate model for bull/bear agent LLM output
# ---------------------------------------------------------------------------


class AgentParsed(BaseModel):
    """Intermediate model for raw bull/bear LLM output before metadata is attached."""

    model_config = ConfigDict(frozen=True)

    agent_role: str
    analysis: str
    key_points: list[str]
    conviction: float
    contracts_referenced: list[str]
    greeks_cited: GreeksCited


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def prompt_to_chat(messages: list[PromptMessage]) -> list[ChatMessage]:
    """Convert prompt builder output to LLM client input."""
    return [ChatMessage(role=pm.role, content=pm.content) for pm in messages]


def _extract_json(raw: str) -> str:
    """Strip markdown fences and leading/trailing noise from *raw*.

    If the LLM wraps its JSON in ```json ... ```, extract the inner text.
    Otherwise return the original string stripped.
    """
    match = _JSON_FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


async def parse_with_retry[T: pydantic.BaseModel](
    llm_client: LLMClient,
    messages: list[ChatMessage],
    model_type: type[T],
    *,
    schema_hint: str,
    max_retries: int = MAX_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[T, LLMResponse]:
    """Call the LLM, parse the response as JSON, and validate into *model_type*.

    On ``json.JSONDecodeError`` or ``pydantic.ValidationError`` the function
    appends a corrective hint message and retries up to *max_retries* times.

    Parameters
    ----------
    llm_client:
        The Ollama LLM client to call.
    messages:
        Initial chat messages (system + user).
    model_type:
        Pydantic model class to validate the parsed JSON against.
    schema_hint:
        A string representation of the expected JSON schema, included in
        the retry hint so the LLM can self-correct.
    max_retries:
        Maximum number of retry attempts after the initial call.
    timeout:
        Timeout in seconds passed to ``llm_client.chat()``.

    Returns
    -------
    tuple[T, LLMResponse]
        The validated model instance and the *last* ``LLMResponse`` (for
        token/timing metadata).

    Raises
    ------
    json.JSONDecodeError
        If parsing fails after all retries.
    pydantic.ValidationError
        If validation fails after all retries.
    """
    conversation = list(messages)  # mutable copy
    last_error: Exception | None = None

    total_attempts = 1 + max_retries
    for attempt in range(total_attempts):
        llm_response = await llm_client.chat(conversation, timeout=timeout)

        raw_content = _extract_json(llm_response.content)

        try:
            parsed = json.loads(raw_content)
            result = model_type.model_validate(parsed)
            logger.info(
                "Parsed %s on attempt %d/%d",
                model_type.__name__,
                attempt + 1,
                total_attempts,
            )
            return result, llm_response
        except (json.JSONDecodeError, pydantic.ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Parse/validation error for %s (attempt %d/%d): %s",
                model_type.__name__,
                attempt + 1,
                total_attempts,
                exc,
            )

            if attempt < max_retries:
                hint_content = (
                    "Your response was not valid JSON matching the schema. "
                    f"Please try again with exactly this format: {schema_hint}"
                )
                conversation.append(
                    ChatMessage(role="assistant", content=llm_response.content),
                )
                conversation.append(
                    ChatMessage(role="user", content=hint_content),
                )

    # All retries exhausted — re-raise the last error
    assert last_error is not None
    raise last_error
