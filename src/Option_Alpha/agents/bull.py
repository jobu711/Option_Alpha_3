"""Bullish debate agent using PydanticAI.

Exposes a module-level ``bull_agent`` and a convenience ``run_bull()`` wrapper
that calls the agent with the supplied dependencies and model override.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import AgentParsed, has_think_tags
from Option_Alpha.agents.model_config import DEFAULT_MODEL_SETTINGS
from Option_Alpha.agents.prompts import BULL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@dataclass
class BullDeps:
    """Dependencies injected into the bull agent at runtime."""

    context_text: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

bull_agent: Agent[BullDeps, AgentParsed] = Agent(
    "openai:llama3.1:8b",  # placeholder — overridden at runtime via model param
    output_type=AgentParsed,
    retries=2,
    defer_model_check=True,
    model_settings=DEFAULT_MODEL_SETTINGS,
)


@bull_agent.system_prompt
async def _bull_system_prompt(ctx: RunContext[BullDeps]) -> str:  # noqa: ARG001
    """Return the bull system prompt."""
    return BULL_SYSTEM_PROMPT


@bull_agent.output_validator
def _reject_think_tags(data: AgentParsed) -> AgentParsed:
    """Reject output that still contains ``<think>`` tag remnants."""
    if has_think_tags(data.analysis):
        raise ModelRetry("Strip <think> tags — return only the requested JSON.")
    return data


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


async def run_bull(deps: BullDeps, model: OpenAIModel) -> tuple[AgentParsed, RunUsage]:
    """Run the bull agent and return ``(parsed_output, usage)``.

    Parameters
    ----------
    deps:
        Runtime dependencies containing the market context text.
    model:
        A PydanticAI ``OpenAIModel`` pointing at the Ollama instance.

    Returns
    -------
    tuple[AgentParsed, RunUsage]
        The validated parsed output and token-usage metadata.
    """
    user_prompt = (
        "<user_input>\n"
        f"{deps.context_text}\n"
        "</user_input>\n"
        "\n"
        "Analyze the above market data and provide your bullish case as JSON."
    )
    result = await bull_agent.run(user_prompt, deps=deps, model=model)
    logger.info(
        "Bull agent completed (input_tokens=%d, output_tokens=%d)",
        result.usage().input_tokens,
        result.usage().output_tokens,
    )
    return result.output, result.usage()
