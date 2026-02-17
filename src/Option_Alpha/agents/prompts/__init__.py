"""Versioned prompt templates for AI debate agents.

Each module exports builder functions that construct message lists
for Ollama's chat API. Messages use the Ollama convention where
system messages are included inside the messages list with
``{"role": "system", "content": "..."}``.
"""

from Option_Alpha.agents.prompts.bear_prompt import build_bear_messages
from Option_Alpha.agents.prompts.bull_prompt import PromptMessage, build_bull_messages
from Option_Alpha.agents.prompts.risk_prompt import build_risk_messages

__all__ = [
    "PromptMessage",
    "build_bull_messages",
    "build_bear_messages",
    "build_risk_messages",
]
