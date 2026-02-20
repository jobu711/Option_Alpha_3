"""Model configuration for PydanticAI agents using Ollama's OpenAI-compatible endpoint.

Provides factory functions to build a PydanticAI OpenAIModel pointed at a local Ollama
instance and to validate that the target model is available before starting a debate.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai.settings import ModelSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HOST: str = "http://localhost:11434"
"""Base URL of the Ollama server (without ``/v1``)."""

DEFAULT_MODEL: str = "llama3.1:8b"
"""Default Ollama model to use for AI debate agents."""

DEFAULT_NUM_CTX: int = 8192
"""Default context-window size passed to Ollama via ``extra_body``."""

DEFAULT_MODEL_SETTINGS: ModelSettings = ModelSettings(
    extra_body={"num_ctx": DEFAULT_NUM_CTX},
)
"""Model settings passed to every PydanticAI agent run.

Sends ``num_ctx`` via ``extra_body`` so Ollama uses an 8 192-token context
window instead of its default (2 048).  Without this, debate prompts are
silently truncated.
"""

_VALIDATE_TIMEOUT_SECONDS: float = 5.0
"""Timeout for the model-availability health check."""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _resolve_host(host: str | None = None) -> str:
    """Return the Ollama host, preferring *host* > ``OLLAMA_HOST`` env var > default."""
    return host or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)


def build_ollama_model(
    host: str | None = None,
    model_name: str = DEFAULT_MODEL,
) -> OpenAIModel:
    """Create a PydanticAI ``OpenAIModel`` backed by Ollama's OpenAI-compatible API.

    Args:
        host: Root URL of the Ollama server (e.g. ``http://localhost:11434``).
              Falls back to the ``OLLAMA_HOST`` environment variable, then
              :data:`DEFAULT_HOST`.  ``/v1`` is appended automatically.
        model_name: Name of the Ollama model to target (e.g. ``llama3.1:8b``).

    Returns:
        A fully configured ``OpenAIModel`` ready for use with PydanticAI agents.
    """
    resolved = _resolve_host(host)
    base_url = f"{resolved}/v1"
    provider = OllamaProvider(base_url=base_url)
    model = OpenAIModel(model_name, provider=provider)
    logger.info("Built OpenAIModel for Ollama: model=%s, base_url=%s", model_name, base_url)  # noqa: E501
    return model


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def validate_model_available(
    host: str | None = None,
    model_name: str = DEFAULT_MODEL,
) -> bool:
    """Check whether *model_name* is served by the Ollama instance at *host*.

    Makes an HTTP GET to ``{host}/api/tags`` and inspects the response for the
    requested model.  Returns ``True`` if found, ``False`` otherwise.  Never
    raises — network errors and timeouts are caught and logged.

    Args:
        host: Root URL of the Ollama server.
        model_name: Model name to look for in the tag list.

    Returns:
        ``True`` when the model is available, ``False`` on any failure.
    """
    host = _resolve_host(host)
    url = f"{host}/api/tags"
    try:
        async with httpx.AsyncClient() as client:
            response = await asyncio.wait_for(
                client.get(url),
                timeout=_VALIDATE_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        models: list[dict[str, Any]] = data.get("models", [])
        available_names: list[str] = [m.get("name", "") for m in models]
        found = model_name in available_names
        if found:
            logger.info("Model '%s' is available on %s", model_name, host)
        else:
            logger.warning(
                "Model '%s' not found on %s. Available: %s",
                model_name,
                host,
                available_names,
            )
        return found
    except TimeoutError:
        logger.warning("Timeout reaching Ollama at %s", host)
        return False
    except httpx.HTTPStatusError as exc:
        logger.warning("Ollama returned HTTP %s at %s", exc.response.status_code, url)
        return False
    except httpx.HTTPError as exc:
        logger.warning("HTTP error contacting Ollama at %s: %s", host, exc)
        return False
    except Exception:
        logger.exception("Unexpected error validating model availability at %s", host)
        return False
