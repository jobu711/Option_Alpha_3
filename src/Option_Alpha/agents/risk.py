"""Risk/moderator debate agent using PydanticAI.

Exposes a module-level ``risk_agent`` and a convenience ``run_risk()`` wrapper
that calls the agent with the supplied dependencies and model override.
The risk agent synthesizes both bull and bear arguments into a final trade
thesis with direction, conviction, and risk factors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import _ThesisParsed, has_think_tags
from Option_Alpha.agents.model_config import DEFAULT_MODEL_SETTINGS
from Option_Alpha.agents.prompts import RISK_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


@dataclass
class RiskDeps:
    """Dependencies injected into the risk agent at runtime."""

    context_text: str
    bull_argument: str
    bear_argument: str


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

risk_agent: Agent[RiskDeps, _ThesisParsed] = Agent(
    "openai:llama3.1:8b",  # placeholder — overridden at runtime via model param
    output_type=_ThesisParsed,
    retries=2,
    defer_model_check=True,
    model_settings=DEFAULT_MODEL_SETTINGS,
)


@risk_agent.system_prompt
async def _risk_system_prompt(ctx: RunContext[RiskDeps]) -> str:  # noqa: ARG001
    """Return the risk system prompt."""
    return RISK_SYSTEM_PROMPT


@risk_agent.output_validator
def _reject_think_tags(data: _ThesisParsed) -> _ThesisParsed:
    """Reject output that still contains ``<think>`` tag remnants."""
    if has_think_tags(data.entry_rationale):
        raise ModelRetry("Strip <think> tags — return only the requested JSON.")
    return data


# ---------------------------------------------------------------------------
# Convenience runner
# ---------------------------------------------------------------------------


async def run_risk(deps: RiskDeps, model: OpenAIModel) -> tuple[_ThesisParsed, RunUsage]:
    """Run the risk agent and return ``(parsed_output, usage)``.

    Parameters
    ----------
    deps:
        Runtime dependencies containing market context text, the bull's argument,
        and the bear's argument.
    model:
        A PydanticAI ``OpenAIModel`` pointing at the Ollama instance.

    Returns
    -------
    tuple[_ThesisParsed, RunUsage]
        The validated parsed output and token-usage metadata.
    """
    user_prompt = (
        "<user_input>\n"
        f"{deps.context_text}\n"
        "</user_input>\n"
        "\n"
        '<opponent_argument role="bull">\n'
        f"{deps.bull_argument}\n"
        "</opponent_argument>\n"
        "\n"
        '<opponent_argument role="bear">\n'
        f"{deps.bear_argument}\n"
        "</opponent_argument>\n"
        "\n"
        "Synthesize both arguments and provide your risk assessment as JSON."
    )
    result = await risk_agent.run(user_prompt, deps=deps, model=model)
    logger.info(
        "Risk agent completed (direction=%s, conviction=%.2f, input_tokens=%d, output_tokens=%d)",
        result.output.direction.value,
        result.output.conviction,
        result.usage().input_tokens,
        result.usage().output_tokens,
    )
    return result.output, result.usage()
