"""Versioned system prompt constants for AI debate agents.

Each module exports a plain string constant containing the system prompt
for the corresponding agent role.  PydanticAI agents consume these
directly via the ``system_prompt`` parameter.
"""

from Option_Alpha.agents.prompts.bear_prompt import BEAR_SYSTEM_PROMPT
from Option_Alpha.agents.prompts.bull_prompt import BULL_SYSTEM_PROMPT, PROMPT_VERSION
from Option_Alpha.agents.prompts.risk_prompt import RISK_SYSTEM_PROMPT

__all__ = [
    "PROMPT_VERSION",
    "BULL_SYSTEM_PROMPT",
    "BEAR_SYSTEM_PROMPT",
    "RISK_SYSTEM_PROMPT",
]
