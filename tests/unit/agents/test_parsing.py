"""Tests for the shared parse_with_retry helper.

Verifies JSON extraction, markdown fence stripping, retry logic with
hint messages, and exhausted-retry error propagation.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pydantic
import pytest
from pydantic import BaseModel, ConfigDict

from Option_Alpha.agents._parsing import parse_with_retry
from Option_Alpha.agents.llm_client import ChatMessage, LLMClient, LLMResponse

# ---------------------------------------------------------------------------
# Test model matching the agent response schema
# ---------------------------------------------------------------------------


class _SimpleModel(BaseModel):
    """Minimal model for parse testing."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: float


_SCHEMA_HINT: str = '{"name": "...", "value": 0.0}'


def _make_llm_response(content: str) -> LLMResponse:
    """Build an LLMResponse with the given content."""
    return LLMResponse(
        content=content,
        model="llama3.1:8b",
        input_tokens=100,
        output_tokens=50,
        duration_ms=1000,
    )


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


class TestParseSuccess:
    """Tests for successful parsing on first attempt."""

    @pytest.mark.asyncio()
    async def test_parse_success_first_attempt(self) -> None:
        """Valid JSON -> returns model on first try."""
        valid_json = json.dumps({"name": "test", "value": 1.5})
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_llm_response(valid_json))

        messages = [ChatMessage(role="user", content="test")]
        result, llm_resp = await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT
        )

        assert result.name == "test"
        assert result.value == pytest.approx(1.5)
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio()
    async def test_parse_strips_markdown_fences(self) -> None:
        """Input wrapped in ```json ... ``` -> still parses."""
        fenced = '```json\n{"name": "fenced", "value": 2.0}\n```'
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=_make_llm_response(fenced))

        messages = [ChatMessage(role="user", content="test")]
        result, _ = await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT
        )

        assert result.name == "fenced"
        assert result.value == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Retry cases
# ---------------------------------------------------------------------------


class TestParseRetry:
    """Tests for retry behaviour on invalid responses."""

    @pytest.mark.asyncio()
    async def test_parse_retries_on_invalid_json(self) -> None:
        """First response invalid JSON, second valid -> succeeds."""
        bad = _make_llm_response("not json at all {{{")
        good = _make_llm_response(json.dumps({"name": "retry", "value": 3.0}))

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad, good])

        messages = [ChatMessage(role="user", content="test")]
        result, _ = await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=1
        )

        assert result.name == "retry"
        assert mock_llm.chat.call_count == 2  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_parse_retries_on_validation_error(self) -> None:
        """Valid JSON but wrong schema, then correct -> succeeds."""
        wrong_schema = _make_llm_response(json.dumps({"wrong_field": "oops"}))
        correct = _make_llm_response(json.dumps({"name": "fixed", "value": 4.0}))

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[wrong_schema, correct])

        messages = [ChatMessage(role="user", content="test")]
        result, _ = await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=1
        )

        assert result.name == "fixed"

    @pytest.mark.asyncio()
    async def test_parse_exhausts_retries(self) -> None:
        """All 3 attempts fail -> raises last error."""
        bad = _make_llm_response("garbage")
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=bad)

        messages = [ChatMessage(role="user", content="test")]
        with pytest.raises(json.JSONDecodeError):
            await parse_with_retry(
                mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=2
            )

        # 1 initial + 2 retries = 3 total
        assert mock_llm.chat.call_count == 3  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_parse_appends_hint_on_retry(self) -> None:
        """On retry, conversation grows with assistant + user hint messages."""
        bad = _make_llm_response("not valid json")
        good = _make_llm_response(json.dumps({"name": "ok", "value": 1.0}))

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad, good])

        messages = [ChatMessage(role="user", content="original")]
        await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=1
        )

        # Second call should have 4 messages: original + assistant + user hint
        second_call_args = mock_llm.chat.call_args_list[1]
        conversation = second_call_args[0][0]
        assert len(conversation) == 3  # noqa: PLR2004  # original + assistant + hint
        assert conversation[1].role == "assistant"
        assert conversation[2].role == "user"
        hint_text = conversation[2].content.lower()
        assert "schema" in hint_text or "format" in hint_text


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestParseEdgeCases:
    """Tests for boundary conditions."""

    @pytest.mark.asyncio()
    async def test_parse_max_retries_zero(self) -> None:
        """max_retries=0 with invalid JSON -> immediate failure (only 1 attempt)."""
        bad = _make_llm_response("not json")
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=bad)

        messages = [ChatMessage(role="user", content="test")]
        with pytest.raises(json.JSONDecodeError):
            await parse_with_retry(
                mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=0
            )

        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio()
    async def test_parse_returns_last_llm_response(self) -> None:
        """The LLMResponse from the successful attempt is returned."""
        bad = _make_llm_response("garbage")
        good_resp = LLMResponse(
            content=json.dumps({"name": "final", "value": 9.0}),
            model="llama3.1:8b",
            input_tokens=200,
            output_tokens=100,
            duration_ms=2000,
        )

        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(side_effect=[bad, good_resp])

        messages = [ChatMessage(role="user", content="test")]
        _, llm_resp = await parse_with_retry(
            mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=1
        )

        assert llm_resp.input_tokens == 200  # noqa: PLR2004
        assert llm_resp.output_tokens == 100  # noqa: PLR2004

    @pytest.mark.asyncio()
    async def test_parse_validation_error_type(self) -> None:
        """ValidationError raised when JSON is valid but schema wrong."""
        # Valid JSON but wrong schema every time
        wrong = _make_llm_response(json.dumps({"unrelated": 42}))
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.chat = AsyncMock(return_value=wrong)

        messages = [ChatMessage(role="user", content="test")]
        with pytest.raises(pydantic.ValidationError):
            await parse_with_retry(
                mock_llm, messages, _SimpleModel, schema_hint=_SCHEMA_HINT, max_retries=1
            )
