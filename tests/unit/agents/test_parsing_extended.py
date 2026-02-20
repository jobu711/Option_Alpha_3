"""Extended parsing tests: AgentParsed model tests and DISCLAIMER constant.

Tests for deleted functions (_extract_json, prompt_to_chat, MAX_RETRIES, schema
hints) have been removed since those functions no longer exist in the PydanticAI
version of _parsing.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from Option_Alpha.agents._parsing import DISCLAIMER, AgentParsed
from Option_Alpha.models import GreeksCited

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

    def test_disclaimer_not_empty(self) -> None:
        assert len(DISCLAIMER) > 0
        assert "educational" in DISCLAIMER.lower() or "not investment" in DISCLAIMER.lower()
