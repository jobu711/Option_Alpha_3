"""Extended prompt builder tests: content validation, empty inputs, PromptMessage model.

Verifies system prompt content descriptions, role keywords, constraint text,
and edge cases with empty or special-character inputs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from Option_Alpha.agents.prompts import (
    PromptMessage,
    build_bear_messages,
    build_bull_messages,
    build_risk_messages,
)

CONTEXT: str = "Ticker: AAPL\nCurrent Price: $186.75\nIV Rank: 45.2"
BULL_ANALYSIS: str = "RSI suggests upward momentum."
BEAR_ANALYSIS: str = "IV is elevated."


# ---------------------------------------------------------------------------
# Bull prompt content
# ---------------------------------------------------------------------------


class TestBullPromptContent:
    """Verify bull system prompt contains required role descriptions."""

    def test_system_prompt_contains_bullish_keyword(self) -> None:
        msgs = build_bull_messages(CONTEXT)
        system = msgs[0].content.lower()
        assert "bull" in system

    def test_system_prompt_contains_conviction(self) -> None:
        msgs = build_bull_messages(CONTEXT)
        system = msgs[0].content.lower()
        assert "conviction" in system

    def test_system_prompt_contains_json_instruction(self) -> None:
        msgs = build_bull_messages(CONTEXT)
        system = msgs[0].content.lower()
        assert "json" in system

    def test_empty_context(self) -> None:
        """Empty context still wraps in user_input tags."""
        msgs = build_bull_messages("")
        user = msgs[1].content
        assert "<user_input>" in user
        assert "</user_input>" in user

    def test_special_characters_not_escaped(self) -> None:
        """Context with XML-like characters is injected verbatim."""
        context = "Price: <$185 & IV > 30%"
        msgs = build_bull_messages(context)
        assert context in msgs[1].content


# ---------------------------------------------------------------------------
# Bear prompt content
# ---------------------------------------------------------------------------


class TestBearPromptContent:
    """Verify bear system prompt contains required role descriptions."""

    def test_system_prompt_contains_bear_keyword(self) -> None:
        msgs = build_bear_messages(CONTEXT, BULL_ANALYSIS)
        system = msgs[0].content.lower()
        assert "bear" in system

    def test_system_prompt_contains_conviction(self) -> None:
        msgs = build_bear_messages(CONTEXT, BULL_ANALYSIS)
        system = msgs[0].content.lower()
        assert "conviction" in system

    def test_empty_bull_analysis_accepted(self) -> None:
        msgs = build_bear_messages(CONTEXT, "")
        user = msgs[1].content
        assert "<opponent_argument>" in user

    def test_messages_count(self) -> None:
        msgs = build_bear_messages(CONTEXT, BULL_ANALYSIS)
        assert len(msgs) == 2

    def test_bear_version_header(self) -> None:
        msgs = build_bear_messages(CONTEXT, BULL_ANALYSIS)
        assert "VERSION: v1.0" in msgs[0].content


# ---------------------------------------------------------------------------
# Risk prompt content
# ---------------------------------------------------------------------------


class TestRiskPromptContent:
    """Verify risk system prompt contains required role descriptions."""

    def test_system_prompt_contains_risk_keyword(self) -> None:
        msgs = build_risk_messages(CONTEXT, BULL_ANALYSIS, BEAR_ANALYSIS)
        system = msgs[0].content.lower()
        assert "risk" in system

    def test_system_prompt_contains_neutral_option(self) -> None:
        msgs = build_risk_messages(CONTEXT, BULL_ANALYSIS, BEAR_ANALYSIS)
        system = msgs[0].content.lower()
        assert "neutral" in system

    def test_empty_analyses_accepted(self) -> None:
        msgs = build_risk_messages(CONTEXT, "", "")
        user = msgs[1].content
        assert 'role="bull"' in user
        assert 'role="bear"' in user

    def test_messages_count(self) -> None:
        msgs = build_risk_messages(CONTEXT, BULL_ANALYSIS, BEAR_ANALYSIS)
        assert len(msgs) == 2

    def test_risk_version_header(self) -> None:
        msgs = build_risk_messages(CONTEXT, BULL_ANALYSIS, BEAR_ANALYSIS)
        assert "VERSION: v1.0" in msgs[0].content


# ---------------------------------------------------------------------------
# PromptMessage model
# ---------------------------------------------------------------------------


class TestPromptMessageModel:
    """Extended tests for PromptMessage model."""

    def test_valid_construction(self) -> None:
        pm = PromptMessage(role="system", content="Test content")
        assert pm.role == "system"
        assert pm.content == "Test content"

    def test_json_roundtrip(self) -> None:
        original = PromptMessage(role="user", content="Some user input")
        restored = PromptMessage.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_any_role_accepted(self) -> None:
        """No validator limiting role to system/user/assistant."""
        pm = PromptMessage(role="custom_role", content="test")
        assert pm.role == "custom_role"

    def test_empty_content_accepted(self) -> None:
        pm = PromptMessage(role="system", content="")
        assert pm.content == ""

    def test_frozen_content_assignment_raises(self) -> None:
        pm = PromptMessage(role="system", content="original")
        with pytest.raises(ValidationError, match="frozen"):
            pm.content = "modified"  # type: ignore[misc]
