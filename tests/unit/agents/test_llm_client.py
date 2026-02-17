"""Tests for the Ollama LLM client wrapper.

Verifies async wrapper, retry logic, think-tag stripping, token extraction,
and model validation — all without hitting a real Ollama server.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, Mock, patch

import httpx
import ollama
import pytest

from Option_Alpha.agents.llm_client import (
    DEFAULT_HOST,
    ChatMessage,
    LLMClient,
    LLMResponse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_chat_response(
    content: str,
    model: str = "llama3.1:8b",
    prompt_eval_count: int = 500,
    eval_count: int = 200,
    total_duration: int = 3_000_000_000,
) -> Mock:
    """Build a mock matching ``ollama.ChatResponse`` shape."""
    response = Mock(spec=ollama.ChatResponse)
    response.message = Mock()
    response.message.content = content
    response.model = model
    response.prompt_eval_count = prompt_eval_count
    response.eval_count = eval_count
    response.total_duration = total_duration
    return response


# ---------------------------------------------------------------------------
# Chat success
# ---------------------------------------------------------------------------


class TestLLMClientChat:
    """Tests for LLMClient.chat() happy path and content processing."""

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_success(self, mock_client_class: MagicMock) -> None:
        """Valid chat returns correct LLMResponse fields."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.return_value = _make_mock_chat_response('{"key": "value"}')

        client = LLMClient(host="http://localhost:11434", model="llama3.1:8b")
        response = await client.chat([ChatMessage(role="user", content="test")])

        assert isinstance(response, LLMResponse)
        assert response.content == '{"key": "value"}'
        assert response.model == "llama3.1:8b"

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_strips_think_tags(self, mock_client_class: MagicMock) -> None:
        """Think tags are stripped from LLM output."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        raw = '<think>reasoning here</think>{"json": true}'
        mock_instance.chat.return_value = _make_mock_chat_response(raw)

        client = LLMClient(host="http://localhost:11434")
        response = await client.chat([ChatMessage(role="user", content="test")])

        assert response.content == '{"json": true}'
        assert "<think>" not in response.content

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_strips_nested_think_tags(self, mock_client_class: MagicMock) -> None:
        """Multiple think tag blocks are all stripped."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        raw = "<think>first</think>start<think>second block</think>end"
        mock_instance.chat.return_value = _make_mock_chat_response(raw)

        client = LLMClient(host="http://localhost:11434")
        response = await client.chat([ChatMessage(role="user", content="test")])

        assert "<think>" not in response.content
        assert "startend" in response.content

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_json_mode_and_stream_false(self, mock_client_class: MagicMock) -> None:
        """Verify chat passes format='json' and stream=False to ollama."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.return_value = _make_mock_chat_response("{}")

        client = LLMClient(host="http://localhost:11434", model="llama3.1:8b")
        await client.chat([ChatMessage(role="user", content="test")])

        mock_instance.chat.assert_called_once()
        call_kwargs = mock_instance.chat.call_args
        assert call_kwargs.kwargs.get("format") == "json" or call_kwargs[1].get("format") == "json"
        # Check stream=False
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get("stream") is False
        else:
            assert call_kwargs[1].get("stream") is False

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_num_ctx_option(self, mock_client_class: MagicMock) -> None:
        """Verify options={'num_ctx': 8192} is passed."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.return_value = _make_mock_chat_response("{}")

        client = LLMClient(host="http://localhost:11434")
        await client.chat([ChatMessage(role="user", content="test")])

        call_kwargs = mock_instance.chat.call_args
        options = call_kwargs.kwargs.get("options") or call_kwargs[1].get("options")
        assert options is not None
        assert options["num_ctx"] == 8192  # noqa: PLR2004

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_token_counts_from_response(self, mock_client_class: MagicMock) -> None:
        """Token counts and duration_ms are correctly extracted from response."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.return_value = _make_mock_chat_response(
            "{}",
            prompt_eval_count=750,
            eval_count=300,
            total_duration=5_500_000_000,
        )

        client = LLMClient(host="http://localhost:11434")
        response = await client.chat([ChatMessage(role="user", content="test")])

        assert response.input_tokens == 750  # noqa: PLR2004
        assert response.output_tokens == 300  # noqa: PLR2004
        assert response.duration_ms == 5500  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


class TestLLMClientTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_timeout(self, mock_client_class: MagicMock) -> None:
        """Slow LLM response triggers asyncio.TimeoutError."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        # Simulate timeout by patching _do_chat to raise
        client = LLMClient(host="http://localhost:11434")

        with (
            patch.object(client, "_do_chat", side_effect=asyncio.TimeoutError),
            pytest.raises(asyncio.TimeoutError),
        ):
            await client.chat(
                [ChatMessage(role="user", content="test")],
                timeout=0.01,
            )


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestLLMClientRetry:
    """Tests for retry/backoff behaviour."""

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.asyncio.sleep", return_value=None)
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_retry_on_connect_error(
        self,
        mock_client_class: MagicMock,
        _mock_sleep: MagicMock,
    ) -> None:
        """ConnectError on first 2 calls, success on 3rd -> retry works."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        error = httpx.ConnectError("connection refused")
        success = _make_mock_chat_response('{"ok": true}')
        mock_instance.chat.side_effect = [error, error, success]

        client = LLMClient(host="http://localhost:11434")
        response = await client.chat([ChatMessage(role="user", content="test")])

        assert response.content == '{"ok": true}'
        assert mock_instance.chat.call_count == 3  # noqa: PLR2004

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.asyncio.sleep", return_value=None)
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_retry_exhausted(
        self,
        mock_client_class: MagicMock,
        _mock_sleep: MagicMock,
    ) -> None:
        """All retries fail with ConnectError -> exception raised."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.side_effect = httpx.ConnectError("connection refused")

        client = LLMClient(host="http://localhost:11434")

        with pytest.raises(httpx.ConnectError):
            await client.chat([ChatMessage(role="user", content="test")])

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_chat_no_retry_on_404(self, mock_client_class: MagicMock) -> None:
        """ResponseError(404) raises immediately without retry."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.chat.side_effect = ollama.ResponseError("model not found", status_code=404)

        client = LLMClient(host="http://localhost:11434")

        with pytest.raises(ollama.ResponseError):
            await client.chat([ChatMessage(role="user", content="test")])

        # Should NOT have retried
        assert mock_instance.chat.call_count == 1


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------


class TestLLMClientValidateModel:
    """Tests for validate_model()."""

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_validate_model_exists(self, mock_client_class: MagicMock) -> None:
        """show() succeeds -> returns True."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.show.return_value = {"modelfile": "..."}

        client = LLMClient(host="http://localhost:11434")
        result = await client.validate_model()

        assert result is True

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_validate_model_not_found(self, mock_client_class: MagicMock) -> None:
        """show() raises 404 -> returns False."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.show.side_effect = ollama.ResponseError("model not found", status_code=404)

        client = LLMClient(host="http://localhost:11434")
        result = await client.validate_model()

        assert result is False

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_validate_model_server_unreachable(self, mock_client_class: MagicMock) -> None:
        """ConnectError -> returns False."""
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance
        mock_instance.show.side_effect = httpx.ConnectError("unreachable")

        client = LLMClient(host="http://localhost:11434")
        result = await client.validate_model()

        assert result is False


# ---------------------------------------------------------------------------
# Host resolution
# ---------------------------------------------------------------------------


class TestLLMClientHost:
    """Tests for host resolution from env vars."""

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_default_host_from_env(self, mock_client_class: MagicMock) -> None:
        """OLLAMA_HOST env var is used when no host kwarg provided."""
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://remote:11434"}):
            LLMClient()
        mock_client_class.assert_called_with(host="http://remote:11434")

    @pytest.mark.asyncio()
    @patch("Option_Alpha.agents.llm_client.ollama.Client")
    async def test_default_host_fallback(self, mock_client_class: MagicMock) -> None:
        """No env var -> uses DEFAULT_HOST."""
        with patch.dict("os.environ", {}, clear=True):
            LLMClient()
        mock_client_class.assert_called_with(host=DEFAULT_HOST)
