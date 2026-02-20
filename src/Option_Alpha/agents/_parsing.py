"""Shared intermediate parsing models and constants for debate agents.

Provides the Pydantic models used as ``output_type`` by PydanticAI agents
and the disclaimer constant attached to every trade thesis.

This is a private module — not exported from ``agents/__init__.py``.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

from Option_Alpha.models import GreeksCited, SignalDirection

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DISCLAIMER: str = "This is for educational purposes only. Not investment advice."

_THINK_TAG_RE: re.Pattern[str] = re.compile(r"<think>.*?</think>", re.DOTALL)
"""Matches ``<think>…</think>`` reasoning tags some models emit."""


def has_think_tags(text: str) -> bool:
    """Return ``True`` if *text* contains ``<think>`` tag content."""
    return bool(_THINK_TAG_RE.search(text))


# ---------------------------------------------------------------------------
# Intermediate model for bull/bear agent LLM output
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
# Intermediate model for risk agent LLM output
# ---------------------------------------------------------------------------


class _ThesisParsed(BaseModel):
    """Intermediate model matching the JSON schema the LLM is asked to produce.

    Does NOT include ``model_used``, ``total_tokens``, ``duration_ms``, or
    ``disclaimer`` -- those are added by the orchestrator / risk agent code.
    """

    model_config = ConfigDict(frozen=True)

    direction: SignalDirection
    conviction: float
    entry_rationale: str
    risk_factors: list[str]
    recommended_action: str
    bull_summary: str
    bear_summary: str
