"""Tests for the risk PydanticAI agent.

Verifies that ``run_risk()`` returns a properly typed ``(_ThesisParsed, RunUsage)``
tuple using PydanticAI's ``TestModel``.  The risk agent receives both the bull's
and bear's analyses as dependencies.
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import _ThesisParsed
from Option_Alpha.agents.risk import RiskDeps, run_risk
from Option_Alpha.models import SignalDirection

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunRisk:
    """Tests for run_risk() with PydanticAI TestModel."""

    @pytest.mark.asyncio()
    async def test_returns_thesis_parsed(self) -> None:
        """run_risk() returns a _ThesisParsed instance as the first element."""
        model = TestModel()
        deps = RiskDeps(
            context_text="Ticker: AAPL\nPrice: $186.75\nIV Rank: 45.2",
            bull_argument="RSI at 55 suggests room for upward momentum.",
            bear_argument="Elevated IV rank at 45 limits upside.",
        )
        parsed, _usage = await run_risk(deps, model)

        assert isinstance(parsed, _ThesisParsed)

    @pytest.mark.asyncio()
    async def test_returns_run_usage(self) -> None:
        """run_risk() returns a RunUsage instance as the second element."""
        model = TestModel()
        deps = RiskDeps(
            context_text="Ticker: AAPL",
            bull_argument="Bull case.",
            bear_argument="Bear case.",
        )
        _parsed, usage = await run_risk(deps, model)

        assert isinstance(usage, RunUsage)

    @pytest.mark.asyncio()
    async def test_direction_is_signal_direction(self) -> None:
        """The parsed direction field is a SignalDirection enum member."""
        model = TestModel()
        deps = RiskDeps(
            context_text="Ticker: AAPL",
            bull_argument="Bull case text.",
            bear_argument="Bear case text.",
        )
        parsed, _usage = await run_risk(deps, model)

        assert isinstance(parsed.direction, SignalDirection)

    @pytest.mark.asyncio()
    async def test_usage_has_non_negative_tokens(self) -> None:
        """Token counts in RunUsage are non-negative integers."""
        model = TestModel()
        deps = RiskDeps(
            context_text="test context",
            bull_argument="bull text",
            bear_argument="bear text",
        )
        _parsed, usage = await run_risk(deps, model)

        assert isinstance(usage.total_tokens, int)
        assert usage.total_tokens >= 0
        assert usage.input_tokens >= 0
        assert usage.output_tokens >= 0

    @pytest.mark.asyncio()
    async def test_parsed_has_required_fields(self) -> None:
        """_ThesisParsed output has all required fields populated."""
        model = TestModel()
        deps = RiskDeps(
            context_text="Ticker: AAPL\nRSI(14): 55.3",
            bull_argument="Bull argument here.",
            bear_argument="Bear argument here.",
        )
        parsed, _usage = await run_risk(deps, model)

        assert isinstance(parsed.conviction, float)
        assert isinstance(parsed.entry_rationale, str)
        assert isinstance(parsed.risk_factors, list)
        assert isinstance(parsed.recommended_action, str)
        assert isinstance(parsed.bull_summary, str)
        assert isinstance(parsed.bear_summary, str)

    @pytest.mark.asyncio()
    async def test_risk_deps_requires_both_arguments(self) -> None:
        """RiskDeps requires context_text, bull_argument, and bear_argument."""
        deps = RiskDeps(
            context_text="Ticker: AAPL",
            bull_argument="Bull argued this.",
            bear_argument="Bear argued that.",
        )
        assert deps.context_text == "Ticker: AAPL"
        assert deps.bull_argument == "Bull argued this."
        assert deps.bear_argument == "Bear argued that."

    @pytest.mark.asyncio()
    async def test_usage_requests_at_least_one(self) -> None:
        """At least one request is made to the model."""
        model = TestModel()
        deps = RiskDeps(
            context_text="Ticker: AAPL",
            bull_argument="bull text",
            bear_argument="bear text",
        )
        _parsed, usage = await run_risk(deps, model)

        assert usage.requests >= 1
