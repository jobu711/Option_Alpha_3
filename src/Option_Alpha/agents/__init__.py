"""AI debate agents for options analysis using PydanticAI."""

from Option_Alpha.agents._parsing import DISCLAIMER, AgentParsed
from Option_Alpha.agents.context_builder import build_context_text
from Option_Alpha.agents.fallback import build_fallback_thesis
from Option_Alpha.agents.model_config import (
    DEFAULT_HOST,
    DEFAULT_MODEL,
    build_ollama_model,
    validate_model_available,
)
from Option_Alpha.agents.orchestrator import DebateOrchestrator

__all__ = [
    "AgentParsed",
    "DISCLAIMER",
    "DEFAULT_HOST",
    "DEFAULT_MODEL",
    "DebateOrchestrator",
    "build_context_text",
    "build_fallback_thesis",
    "build_ollama_model",
    "validate_model_available",
]
