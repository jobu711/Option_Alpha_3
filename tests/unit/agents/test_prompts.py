"""Tests for the prompt builder functions (bull, bear, risk).

Verifies message counts, roles, version headers, input tags,
opponent argument delimiters, and PromptMessage immutability.
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

SAMPLE_CONTEXT: str = (
    "Ticker: AAPL\nCurrent Price: $186.75\nIV Rank: 45.2 (moderate)\nRSI(14): 55.3 (neutral)"
)

SAMPLE_BULL_ANALYSIS: str = "RSI at 55 suggests room for upward momentum."
SAMPLE_BEAR_ANALYSIS: str = "Elevated IV rank at 45 limits upside."


# ---------------------------------------------------------------------------
# Bull prompt
# ---------------------------------------------------------------------------


class TestBullPrompt:
    """Tests for build_bull_messages()."""

    def test_bull_messages_count(self) -> None:
        """Bull prompt produces exactly 2 messages."""
        msgs = build_bull_messages(SAMPLE_CONTEXT)
        assert len(msgs) == 2  # noqa: PLR2004

    def test_bull_system_role(self) -> None:
        """First message has role='system'."""
        msgs = build_bull_messages(SAMPLE_CONTEXT)
        assert msgs[0].role == "system"

    def test_bull_user_role(self) -> None:
        """Second message has role='user'."""
        msgs = build_bull_messages(SAMPLE_CONTEXT)
        assert msgs[1].role == "user"

    def test_bull_version_header(self) -> None:
        """System prompt contains 'VERSION: v1.0'."""
        msgs = build_bull_messages(SAMPLE_CONTEXT)
        assert "VERSION: v1.0" in msgs[0].content

    def test_bull_user_input_tags(self) -> None:
        """User message wraps context in <user_input> tags."""
        msgs = build_bull_messages(SAMPLE_CONTEXT)
        user_content = msgs[1].content
        assert "<user_input>" in user_content
        assert "</user_input>" in user_content
        assert SAMPLE_CONTEXT in user_content


# ---------------------------------------------------------------------------
# Bear prompt
# ---------------------------------------------------------------------------


class TestBearPrompt:
    """Tests for build_bear_messages()."""

    def test_bear_opponent_argument_tags(self) -> None:
        """Bear user message has <opponent_argument> tags."""
        msgs = build_bear_messages(SAMPLE_CONTEXT, SAMPLE_BULL_ANALYSIS)
        user_content = msgs[1].content
        assert "<opponent_argument>" in user_content
        assert "</opponent_argument>" in user_content

    def test_bear_includes_bull_analysis(self) -> None:
        """Bull analysis text appears in bear user message."""
        msgs = build_bear_messages(SAMPLE_CONTEXT, SAMPLE_BULL_ANALYSIS)
        user_content = msgs[1].content
        assert SAMPLE_BULL_ANALYSIS in user_content


# ---------------------------------------------------------------------------
# Risk prompt
# ---------------------------------------------------------------------------


class TestRiskPrompt:
    """Tests for build_risk_messages()."""

    def test_risk_both_arguments(self) -> None:
        """Risk user message has both bull and bear opponent arguments."""
        msgs = build_risk_messages(SAMPLE_CONTEXT, SAMPLE_BULL_ANALYSIS, SAMPLE_BEAR_ANALYSIS)
        user_content = msgs[1].content
        assert SAMPLE_BULL_ANALYSIS in user_content
        assert SAMPLE_BEAR_ANALYSIS in user_content

    def test_risk_role_attributes(self) -> None:
        """Risk opponent_argument tags have role='bull' and role='bear'."""
        msgs = build_risk_messages(SAMPLE_CONTEXT, SAMPLE_BULL_ANALYSIS, SAMPLE_BEAR_ANALYSIS)
        user_content = msgs[1].content
        assert 'role="bull"' in user_content
        assert 'role="bear"' in user_content


# ---------------------------------------------------------------------------
# PromptMessage immutability
# ---------------------------------------------------------------------------


class TestPromptMessageFrozen:
    """Tests for PromptMessage immutability."""

    def test_prompt_message_frozen(self) -> None:
        """PromptMessage is frozen -- attribute assignment raises."""
        pm = PromptMessage(role="system", content="test")
        with pytest.raises(ValidationError):
            pm.role = "user"  # type: ignore[misc]
