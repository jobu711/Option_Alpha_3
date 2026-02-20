"""Tests for the bull PydanticAI agent.

Verifies that ``run_bull()`` returns a properly typed ``(AgentParsed, RunUsage)``
tuple using PydanticAI's ``TestModel``.
"""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from Option_Alpha.agents._parsing import AgentParsed
from Option_Alpha.agents.bull import BullDeps, run_bull

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunBull:
    """Tests for run_bull() with PydanticAI TestModel."""

    @pytest.mark.asyncio()
    async def test_returns_agent_parsed(self) -> None:
        """run_bull() returns an AgentParsed instance as the first element."""
        model = TestModel()
        deps = BullDeps(context_text="Ticker: AAPL\nPrice: $186.75\nIV Rank: 45.2")
        parsed, _usage = await run_bull(deps, model)

        assert isinstance(parsed, AgentParsed)

    @pytest.mark.asyncio()
    async def test_returns_run_usage(self) -> None:
        """run_bull() returns a RunUsage instance as the second element."""
        model = TestModel()
        deps = BullDeps(context_text="Ticker: AAPL\nPrice: $186.75")
        _parsed, usage = await run_bull(deps, model)

        assert isinstance(usage, RunUsage)

    @pytest.mark.asyncio()
    async def test_usage_has_non_negative_tokens(self) -> None:
        """Token counts in RunUsage are non-negative integers."""
        model = TestModel()
        deps = BullDeps(context_text="test context")
        _parsed, usage = await run_bull(deps, model)

        assert isinstance(usage.total_tokens, int)
        assert usage.total_tokens >= 0
        assert usage.input_tokens >= 0
        assert usage.output_tokens >= 0

    @pytest.mark.asyncio()
    async def test_parsed_has_required_fields(self) -> None:
        """AgentParsed output has all required fields populated."""
        model = TestModel()
        deps = BullDeps(context_text="Ticker: AAPL\nRSI(14): 55.3")
        parsed, _usage = await run_bull(deps, model)

        assert isinstance(parsed.agent_role, str)
        assert isinstance(parsed.analysis, str)
        assert isinstance(parsed.key_points, list)
        assert isinstance(parsed.conviction, float)
        assert isinstance(parsed.contracts_referenced, list)

    @pytest.mark.asyncio()
    async def test_usage_requests_at_least_one(self) -> None:
        """At least one request is made to the model."""
        model = TestModel()
        deps = BullDeps(context_text="Ticker: AAPL")
        _parsed, usage = await run_bull(deps, model)

        assert usage.requests >= 1
