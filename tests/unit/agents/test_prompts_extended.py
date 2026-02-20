"""Extended prompt constant tests: content validation, keyword coverage, and schema completeness.

Verifies system prompt content descriptions, role keywords, constraint text,
and JSON output schema completeness for all three agent prompts.

Builder function tests (build_*_messages) and PromptMessage model tests have
been removed since those functions no longer exist in the PydanticAI version.
"""

from __future__ import annotations

from Option_Alpha.agents.prompts import (
    BEAR_SYSTEM_PROMPT,
    BULL_SYSTEM_PROMPT,
    PROMPT_VERSION,
    RISK_SYSTEM_PROMPT,
)

# ---------------------------------------------------------------------------
# Bull prompt content
# ---------------------------------------------------------------------------


class TestBullPromptContent:
    """Verify bull system prompt contains required role descriptions."""

    def test_system_prompt_contains_bullish_keyword(self) -> None:
        lower = BULL_SYSTEM_PROMPT.lower()
        assert "bull" in lower

    def test_system_prompt_contains_conviction(self) -> None:
        lower = BULL_SYSTEM_PROMPT.lower()
        assert "conviction" in lower

    def test_system_prompt_contains_json_instruction(self) -> None:
        lower = BULL_SYSTEM_PROMPT.lower()
        assert "json" in lower

    def test_system_prompt_contains_version(self) -> None:
        assert PROMPT_VERSION in BULL_SYSTEM_PROMPT

    def test_system_prompt_contains_key_points_field(self) -> None:
        assert "key_points" in BULL_SYSTEM_PROMPT

    def test_system_prompt_contains_contracts_referenced_field(self) -> None:
        assert "contracts_referenced" in BULL_SYSTEM_PROMPT

    def test_system_prompt_contains_greeks_cited_field(self) -> None:
        assert "greeks_cited" in BULL_SYSTEM_PROMPT

    def test_system_prompt_contains_word_limit(self) -> None:
        """System prompt specifies a word limit."""
        assert "500 words" in BULL_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Bear prompt content
# ---------------------------------------------------------------------------


class TestBearPromptContent:
    """Verify bear system prompt contains required role descriptions."""

    def test_system_prompt_contains_bear_keyword(self) -> None:
        lower = BEAR_SYSTEM_PROMPT.lower()
        assert "bear" in lower

    def test_system_prompt_contains_conviction(self) -> None:
        lower = BEAR_SYSTEM_PROMPT.lower()
        assert "conviction" in lower

    def test_system_prompt_contains_version(self) -> None:
        assert PROMPT_VERSION in BEAR_SYSTEM_PROMPT

    def test_system_prompt_contains_key_points_field(self) -> None:
        assert "key_points" in BEAR_SYSTEM_PROMPT

    def test_system_prompt_contains_downside_risk(self) -> None:
        lower = BEAR_SYSTEM_PROMPT.lower()
        assert "downside" in lower or "risk" in lower

    def test_system_prompt_contains_word_limit(self) -> None:
        assert "500 words" in BEAR_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Risk prompt content
# ---------------------------------------------------------------------------


class TestRiskPromptContent:
    """Verify risk system prompt contains required role descriptions."""

    def test_system_prompt_contains_risk_keyword(self) -> None:
        lower = RISK_SYSTEM_PROMPT.lower()
        assert "risk" in lower

    def test_system_prompt_contains_neutral_option(self) -> None:
        lower = RISK_SYSTEM_PROMPT.lower()
        assert "neutral" in lower

    def test_system_prompt_contains_version(self) -> None:
        assert PROMPT_VERSION in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_direction_field(self) -> None:
        assert "direction" in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_risk_factors_field(self) -> None:
        assert "risk_factors" in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_bull_summary_field(self) -> None:
        assert "bull_summary" in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_bear_summary_field(self) -> None:
        assert "bear_summary" in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_recommended_action_field(self) -> None:
        assert "recommended_action" in RISK_SYSTEM_PROMPT

    def test_system_prompt_contains_word_limit(self) -> None:
        assert "500 words" in RISK_SYSTEM_PROMPT

    def test_system_prompt_lists_valid_directions(self) -> None:
        """Risk prompt lists the three valid direction values."""
        assert "bullish" in RISK_SYSTEM_PROMPT
        assert "bearish" in RISK_SYSTEM_PROMPT
        assert "neutral" in RISK_SYSTEM_PROMPT
