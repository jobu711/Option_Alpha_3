"""Extended parsing tests: _extract_json direct tests, prompt_to_chat, AgentParsed model.

These functions were only tested indirectly through parse_with_retry.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from Option_Alpha.agents._parsing import (
    AGENT_RESPONSE_SCHEMA_HINT,
    MAX_RETRIES,
    THESIS_SCHEMA_HINT,
    AgentParsed,
    _extract_json,
    prompt_to_chat,
)
from Option_Alpha.agents.llm_client import ChatMessage
from Option_Alpha.agents.prompts.bull_prompt import PromptMessage
from Option_Alpha.models import GreeksCited

# ---------------------------------------------------------------------------
# _extract_json — direct tests
# ---------------------------------------------------------------------------


class TestExtractJson:
    """Direct tests for the _extract_json private function."""

    def test_plain_json_passthrough(self) -> None:
        raw = '{"key": "val"}'
        assert _extract_json(raw) == '{"key": "val"}'

    def test_strips_whitespace(self) -> None:
        raw = '   {"key": "val"}   '
        assert _extract_json(raw) == '{"key": "val"}'

    def test_json_fence_with_language_tag(self) -> None:
        raw = '```json\n{"key": "val"}\n```'
        assert _extract_json(raw) == '{"key": "val"}'

    def test_json_fence_without_language_tag(self) -> None:
        raw = '```\n{"key": "val"}\n```'
        assert _extract_json(raw) == '{"key": "val"}'

    def test_inner_whitespace_stripped(self) -> None:
        raw = '```json\n  {"spaced": true}  \n```'
        assert _extract_json(raw) == '{"spaced": true}'

    def test_preamble_and_suffix_ignored(self) -> None:
        raw = 'Here is my response:\n```json\n{"key": "val"}\n```\nHope that helps!'
        assert _extract_json(raw) == '{"key": "val"}'

    def test_empty_fence_returns_empty_string(self) -> None:
        raw = "```json\n\n```"
        assert _extract_json(raw) == ""

    def test_unclosed_fence_returns_stripped_raw(self) -> None:
        raw = '```json\n{"unclosed"}'
        assert _extract_json(raw) == '```json\n{"unclosed"}'

    def test_first_fence_extracted_when_multiple(self) -> None:
        raw = '```json\n{"first": 1}\n```\nMore text\n```json\n{"second": 2}\n```'
        result = _extract_json(raw)
        assert '"first"' in result


# ---------------------------------------------------------------------------
# prompt_to_chat — direct tests
# ---------------------------------------------------------------------------


class TestPromptToChat:
    """Direct tests for prompt_to_chat conversion."""

    def test_empty_list(self) -> None:
        result = prompt_to_chat([])
        assert result == []

    def test_single_system_message(self) -> None:
        pm = PromptMessage(role="system", content="You are a bull agent.")
        result = prompt_to_chat([pm])
        assert len(result) == 1
        assert isinstance(result[0], ChatMessage)
        assert result[0].role == "system"
        assert result[0].content == "You are a bull agent."

    def test_system_and_user_messages(self) -> None:
        messages = [
            PromptMessage(role="system", content="System prompt"),
            PromptMessage(role="user", content="User input"),
        ]
        result = prompt_to_chat(messages)
        assert len(result) == 2
        assert result[0].role == "system"
        assert result[1].role == "user"

    def test_preserves_content_exactly(self) -> None:
        content = "Special chars: <tag> & 'quotes' \"double\""
        pm = PromptMessage(role="user", content=content)
        result = prompt_to_chat([pm])
        assert result[0].content == content


# ---------------------------------------------------------------------------
# AgentParsed model tests
# ---------------------------------------------------------------------------


class TestAgentParsed:
    """Unit tests for the AgentParsed intermediate model."""

    def test_valid_construction(self) -> None:
        parsed = AgentParsed(
            agent_role="bull",
            analysis="RSI oversold bounce likely",
            key_points=["RSI at 30", "MACD crossover"],
            conviction=0.72,
            contracts_referenced=["AAPL 185C 2025-02-21"],
            greeks_cited=GreeksCited(delta=0.45),
        )
        assert parsed.agent_role == "bull"
        assert parsed.conviction == pytest.approx(0.72, rel=1e-4)

    def test_json_roundtrip(self) -> None:
        original = AgentParsed(
            agent_role="bear",
            analysis="IV crush risk post-earnings",
            key_points=["IV at 72nd percentile"],
            conviction=0.65,
            contracts_referenced=["AAPL 185P 2025-02-21"],
            greeks_cited=GreeksCited(delta=-0.55, vega=0.12),
        )
        restored = AgentParsed.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_frozen_immutability(self) -> None:
        parsed = AgentParsed(
            agent_role="bull",
            analysis="Test",
            key_points=[],
            conviction=0.5,
            contracts_referenced=[],
            greeks_cited=GreeksCited(),
        )
        with pytest.raises(ValidationError, match="frozen"):
            parsed.conviction = 0.9  # type: ignore[misc]

    def test_empty_key_points_and_contracts(self) -> None:
        parsed = AgentParsed(
            agent_role="bull",
            analysis="Minimal response",
            key_points=[],
            conviction=0.3,
            contracts_referenced=[],
            greeks_cited=GreeksCited(),
        )
        assert parsed.key_points == []
        assert parsed.contracts_referenced == []

    def test_all_greeks_cited_none(self) -> None:
        parsed = AgentParsed(
            agent_role="bull",
            analysis="No Greeks cited",
            key_points=[],
            conviction=0.5,
            contracts_referenced=[],
            greeks_cited=GreeksCited(),
        )
        assert parsed.greeks_cited.delta is None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestParsingConstants:
    """Verify module-level constants are defined correctly."""

    def test_max_retries(self) -> None:
        assert MAX_RETRIES == 2

    def test_agent_response_schema_hint_valid_json_structure(self) -> None:
        assert "agent_role" in AGENT_RESPONSE_SCHEMA_HINT
        assert "conviction" in AGENT_RESPONSE_SCHEMA_HINT

    def test_thesis_schema_hint_valid_json_structure(self) -> None:
        assert "direction" in THESIS_SCHEMA_HINT
        assert "risk_factors" in THESIS_SCHEMA_HINT
