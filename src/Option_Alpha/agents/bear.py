"""Bearish debate agent using PydanticAI.

Exposes a module-level ``bear_agent`` and a convenience ``run_bear()`` wrapper
that calls the agent with the supplied dependencies and model override.
The bear agent receives the bull's analysis and must rebut it with
data-driven counter-arguments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import AgentParsed, has_think_tags
from Option_Alpha.agents.model_config import DEFAULT_MODEL_SETTINGS
from Option_Alpha.agents.prompts import BEAR_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@dataclass
class BearDeps:
    """Dependencies injected into the bear agent at runtime."""

    context_text: str
    bull_argument: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

bear_agent: Agent[BearDeps, AgentParsed] = Agent(
    "openai:llama3.1:8b",  # placeholder — overridden at runtime via model param
    output_type=AgentParsed,
    retries=2,
    defer_model_check=True,
    model_settings=DEFAULT_MODEL_SETTINGS,
)


@bear_agent.system_prompt
async def _bear_system_prompt(ctx: RunContext[BearDeps]) -> str:  # noqa: ARG001
    """Return the bear system prompt."""
    return BEAR_SYSTEM_PROMPT


@bear_agent.output_validator
def _reject_think_tags(data: AgentParsed) -> AgentParsed:
    """Reject output that still contains ``<think>`` tag remnants."""
    if has_think_tags(data.analysis):
        raise ModelRetry("Strip <think> tags — return only the requested JSON.")
    return data


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


async def run_bear(deps: BearDeps, model: OpenAIModel) -> tuple[AgentParsed, RunUsage]:
    """Run the bear agent and return ``(parsed_output, usage)``.

    Parameters
    ----------
    deps:
        Runtime dependencies containing market context text and the bull's argument.
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
        "<opponent_argument>\n"
        f"{deps.bull_argument}\n"
        "</opponent_argument>\n"
        "\n"
        "Analyze the above market data, rebut the bull's argument, "
        "and provide your bearish case as JSON."
    )
    result = await bear_agent.run(user_prompt, deps=deps, model=model)
    logger.info(
        "Bear agent completed (input_tokens=%d, output_tokens=%d)",
        result.usage().input_tokens,
        result.usage().output_tokens,
    )
    return result.output, result.usage()
