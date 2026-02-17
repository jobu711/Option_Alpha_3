"""Ollama LLM client wrapper with async interface, retry logic, and token tracking.

Wraps the synchronous ``ollama.Client`` in ``asyncio.to_thread()`` so that
all calls are non-blocking.  Structured JSON output is enforced via
``format="json"`` and ``stream=False``.  A ``<think>...</think>`` tag
stripping pass runs on every response before returning.

Retry strategy:
- ``httpx.ConnectError`` / ``ConnectionRefusedError``: exponential backoff
  [1 s, 2 s, 4 s] (max 3 retries).
- ``ollama.ResponseError`` with status 404 (model not found): raise
  immediately without retry.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx
import ollama
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_HOST: str = "http://localhost:11434"
DEFAULT_MODEL: str = "llama3.1:8b"
DEFAULT_TIMEOUT: float = 180.0
NUM_CTX: int = 8192

_THINK_TAG_RE: re.Pattern[str] = re.compile(r"<think>.*?</think>", re.DOTALL)

_RETRY_DELAYS: list[float] = [1.0, 2.0, 4.0]
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    httpx.ConnectError,
    ConnectionRefusedError,
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    """A single message in an Ollama chat conversation."""

    role: str
    content: str


class LLMResponse(BaseModel):
    """Parsed response from an Ollama chat completion."""

    model_config = ConfigDict(frozen=True)

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    duration_ms: int


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    """Async wrapper around ``ollama.Client`` for structured chat completions.

    Parameters
    ----------
    host:
        Ollama server URL.  Defaults to the ``OLLAMA_HOST`` environment
        variable or ``http://localhost:11434``.
    model:
        Model tag to use for all chat calls (e.g. ``"llama3.1:8b"``).
    """

    def __init__(
        self,
        host: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_host = host or os.environ.get("OLLAMA_HOST", DEFAULT_HOST)
        self._client: ollama.Client = ollama.Client(host=resolved_host)
        self._model: str = model
        self._host: str = resolved_host

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> LLMResponse:
        """Send a chat completion request to the Ollama server.

        The synchronous ``ollama.Client.chat`` call is executed in a
        background thread via ``asyncio.to_thread`` with an outer
        ``asyncio.wait_for`` timeout guard.

        Parameters
        ----------
        messages:
            Conversation history including an optional system message.
        timeout:
            Maximum wall-clock seconds to wait for the response.

        Returns
        -------
        LLMResponse
            Parsed response with content, token counts, and timing.

        Raises
        ------
        asyncio.TimeoutError
            If the call exceeds *timeout* seconds.
        ollama.ResponseError
            If the model is not found (status 404) or another server error.
        httpx.ConnectError
            If the Ollama server is unreachable after retries.
        """
        raw_messages: list[dict[str, str]] = [
            {"role": m.role, "content": m.content} for m in messages
        ]

        response = await self._call_with_retry(raw_messages, timeout=timeout)

        raw_content: str = response.message.content or ""
        content = _THINK_TAG_RE.sub("", raw_content).strip()

        input_tokens = response.prompt_eval_count or 0
        output_tokens = response.eval_count or 0
        total_duration_ns = response.total_duration or 0
        duration_ms = total_duration_ns // 1_000_000

        logger.info(
            "LLM response: model=%s input_tokens=%d output_tokens=%d duration_ms=%d",
            self._model,
            input_tokens,
            output_tokens,
            duration_ms,
        )

        return LLMResponse(
            content=content,
            model=response.model or self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )

    async def validate_model(self) -> bool:
        """Check whether the configured model exists on the Ollama server.

        Returns
        -------
        bool
            ``True`` if the model is available, ``False`` otherwise.
        """
        try:

            def _sync_show() -> object:
                return self._client.show(self._model)

            await asyncio.wait_for(
                asyncio.to_thread(_sync_show),
                timeout=30.0,
            )
        except ollama.ResponseError as exc:
            if exc.status_code == 404:  # noqa: PLR2004
                logger.warning("Model not found on Ollama server: %s", self._model)
                return False
            raise
        except _RETRYABLE_EXCEPTIONS:
            logger.warning("Ollama server unreachable at %s", self._host)
            return False
        else:
            return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        raw_messages: list[dict[str, str]],
        *,
        timeout: float,
    ) -> ollama.ChatResponse:
        """Execute the sync chat call with exponential-backoff retry.

        Retries on ``httpx.ConnectError`` and ``ConnectionRefusedError``.
        Raises immediately on ``ollama.ResponseError`` with status 404.
        """
        last_exception: BaseException | None = None

        for attempt, delay in enumerate(_RETRY_DELAYS):
            try:
                return await self._do_chat(raw_messages, timeout=timeout)
            except ollama.ResponseError as exc:
                if exc.status_code == 404:  # noqa: PLR2004
                    logger.error("Model not found: %s", self._model)
                    raise
                last_exception = exc
                logger.warning(
                    "Ollama ResponseError (attempt %d/%d): %s",
                    attempt + 1,
                    len(_RETRY_DELAYS),
                    exc,
                )
            except _RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                logger.warning(
                    "Connection error (attempt %d/%d, retry in %.0fs): %s",
                    attempt + 1,
                    len(_RETRY_DELAYS),
                    delay,
                    exc,
                )

            await asyncio.sleep(delay)

        # Final attempt (no sleep after)
        try:
            return await self._do_chat(raw_messages, timeout=timeout)
        except _RETRYABLE_EXCEPTIONS as exc:
            logger.error(
                "Ollama unreachable after %d retries: %s",
                len(_RETRY_DELAYS),
                exc,
            )
            raise
        except ollama.ResponseError as exc:
            if exc.status_code == 404:  # noqa: PLR2004
                raise
            if last_exception is not None:
                raise exc from last_exception
            raise

    async def _do_chat(
        self,
        raw_messages: list[dict[str, str]],
        *,
        timeout: float,
    ) -> ollama.ChatResponse:
        """Run the synchronous ``ollama.Client.chat`` in a thread with timeout."""
        model = self._model

        def _sync_call() -> ollama.ChatResponse:
            return self._client.chat(
                model=model,
                messages=raw_messages,
                format="json",
                stream=False,
                options={"num_ctx": NUM_CTX},
            )

        return await asyncio.wait_for(
            asyncio.to_thread(_sync_call),
            timeout=timeout,
        )
