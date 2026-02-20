"""Tests for the prompt string constants (bull, bear, risk).

Verifies version headers, role keywords, JSON schema references, and
key constraint text in each system prompt constant.
"""

from __future__ import annotations

from Option_Alpha.agents.prompts import (
    BEAR_SYSTEM_PROMPT,
    BULL_SYSTEM_PROMPT,
    PROMPT_VERSION,
    RISK_SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# PROMPT_VERSION
# ---------------------------------------------------------------------------


class TestPromptVersion:
    """Tests for the PROMPT_VERSION constant."""

    def test_version_is_string(self) -> None:
        assert isinstance(PROMPT_VERSION, str)

    def test_version_not_empty(self) -> None:
        assert len(PROMPT_VERSION) > 0

    def test_version_value(self) -> None:
        assert PROMPT_VERSION == "v1.0"


# ---------------------------------------------------------------------------
# Bull prompt
# ---------------------------------------------------------------------------


class TestBullPrompt:
    """Tests for BULL_SYSTEM_PROMPT constant."""

    def test_bull_version_header(self) -> None:
        """System prompt contains 'VERSION: v1.0'."""
        assert "VERSION: v1.0" in BULL_SYSTEM_PROMPT

    def test_bull_contains_bullish_role(self) -> None:
        """System prompt references the bullish role."""
        assert "bull" in BULL_SYSTEM_PROMPT.lower()

    def test_bull_contains_json_schema(self) -> None:
        """System prompt references the output JSON schema fields."""
        assert "agent_role" in BULL_SYSTEM_PROMPT
        assert "conviction" in BULL_SYSTEM_PROMPT

    def test_bull_contains_key_constraints(self) -> None:
        """System prompt mentions key constraints like Greeks and IV."""
        lower = BULL_SYSTEM_PROMPT.lower()
        assert "greeks" in lower
        assert "iv rank" in lower or "iv" in lower

    def test_bull_is_string(self) -> None:
        assert isinstance(BULL_SYSTEM_PROMPT, str)

    def test_bull_not_empty(self) -> None:
        assert len(BULL_SYSTEM_PROMPT) > 0


# ---------------------------------------------------------------------------
# Bear prompt
# ---------------------------------------------------------------------------


class TestBearPrompt:
    """Tests for BEAR_SYSTEM_PROMPT constant."""

    def test_bear_version_header(self) -> None:
        assert "VERSION: v1.0" in BEAR_SYSTEM_PROMPT

    def test_bear_contains_bearish_role(self) -> None:
        assert "bear" in BEAR_SYSTEM_PROMPT.lower()

    def test_bear_contains_json_schema(self) -> None:
        assert "agent_role" in BEAR_SYSTEM_PROMPT
        assert "conviction" in BEAR_SYSTEM_PROMPT

    def test_bear_contains_rebuttal_instruction(self) -> None:
        """Bear prompt instructs addressing the bull's claims."""
        lower = BEAR_SYSTEM_PROMPT.lower()
        assert "bull" in lower

    def test_bear_is_string(self) -> None:
        assert isinstance(BEAR_SYSTEM_PROMPT, str)


# ---------------------------------------------------------------------------
# Risk prompt
# ---------------------------------------------------------------------------


class TestRiskPrompt:
    """Tests for RISK_SYSTEM_PROMPT constant."""

    def test_risk_version_header(self) -> None:
        assert "VERSION: v1.0" in RISK_SYSTEM_PROMPT

    def test_risk_contains_risk_role(self) -> None:
        assert "risk" in RISK_SYSTEM_PROMPT.lower()

    def test_risk_contains_neutral_option(self) -> None:
        """Risk prompt mentions the neutral direction option."""
        assert "neutral" in RISK_SYSTEM_PROMPT.lower()

    def test_risk_contains_direction_field(self) -> None:
        """Risk prompt JSON schema includes direction field."""
        assert "direction" in RISK_SYSTEM_PROMPT

    def test_risk_contains_risk_factors_field(self) -> None:
        """Risk prompt JSON schema includes risk_factors field."""
        assert "risk_factors" in RISK_SYSTEM_PROMPT

    def test_risk_is_string(self) -> None:
        assert isinstance(RISK_SYSTEM_PROMPT, str)
