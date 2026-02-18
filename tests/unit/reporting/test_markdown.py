"""Tests for GitHub-Flavored Markdown report generation.

Covers generate_markdown_report content and structure, and save_report
file creation with proper naming conventions.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.models.enums import OptionType
from Option_Alpha.models.options import OptionContract
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT
from Option_Alpha.reporting.markdown import generate_markdown_report, save_report

# ---------------------------------------------------------------------------
# generate_markdown_report
# ---------------------------------------------------------------------------


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report()."""

    def test_returns_nonempty_string(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Must return a non-empty string."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_header_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 1: Header with # Options Analysis."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "# Options Analysis" in result

    def test_contains_market_snapshot_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 2: Market Snapshot header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Market Snapshot" in result

    def test_contains_strategy_summary_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 3: Strategy Summary header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Strategy Summary" in result

    def test_contains_debate_summary_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 4: Debate Summary header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Debate Summary" in result

    def test_contains_key_factors_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 5: Key Factors header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Key Factors" in result

    def test_contains_risk_assessment_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 6: Risk Assessment header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Risk Assessment" in result

    def test_contains_metadata_section(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 7: Metadata header."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "## Metadata" in result

    def test_contains_disclaimer(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Section 8: Full disclaimer text must appear in the report."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert DISCLAIMER_TEXT in result

    def test_contains_ticker(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Report must mention the ticker from context."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "AAPL" in result

    def test_contains_metadata_block_fields(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Metadata block must contain data source, model used, and duration."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "Data Source: yfinance" in result
        assert sample_trade_thesis.model_used in result
        assert "Analysis Duration" in result

    def test_tables_have_pipe_separators(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """GFM tables must use pipe separators."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        # Market snapshot table has pipes
        assert "| Metric | Value |" in result
        assert "|--------|-------|" in result

    def test_contains_direction(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Report should contain the direction (BULLISH/BEARISH/NEUTRAL)."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "BULLISH" in result

    def test_contains_conviction(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Report should contain conviction percentage."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "72%" in result

    def test_contains_bull_case(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Report should contain the bull summary."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "### Bull Case" in result
        assert sample_trade_thesis.bull_summary in result

    def test_contains_bear_case(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Report should contain the bear summary."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "### Bear Case" in result
        assert sample_trade_thesis.bear_summary in result

    def test_risk_factors_listed(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Risk factors should be numbered in the output."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert "1. Earnings in 30 days" in result
        assert "2. IV rank elevated at 45%" in result

    def test_with_contract(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
        sample_option_contract: OptionContract,
    ) -> None:
        """When a contract is provided, Greeks table should appear."""
        result = generate_markdown_report(
            sample_trade_thesis,
            sample_market_context,
            contract=sample_option_contract,
        )
        assert "### Greeks" in result
        assert "| Greek | Value | What It Means |" in result
        assert "Delta" in result
        assert "Theta" in result

    def test_with_signals(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """When signals are provided, indicator section should appear."""
        signals = {"rsi": 55.0, "adx": 30.0, "iv_rank": 60.0}
        result = generate_markdown_report(
            sample_trade_thesis,
            sample_market_context,
            signals=signals,
        )
        assert "### Indicators" in result
        assert "Momentum" in result or "Trend" in result

    def test_without_contract_no_greeks(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Without a contract, Greeks section should not appear."""
        result = generate_markdown_report(
            sample_trade_thesis,
            sample_market_context,
            contract=None,
        )
        assert "### Greeks" not in result

    def test_without_signals_no_indicators(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Without signals, Indicators section should not appear."""
        result = generate_markdown_report(
            sample_trade_thesis,
            sample_market_context,
            signals=None,
        )
        assert "### Indicators" not in result

    def test_timestamp_in_header(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Header should contain the data timestamp."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        expected_ts = sample_market_context.data_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert expected_ts in result

    def test_metadata_code_block(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Metadata should be wrapped in a code block."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        # The metadata section uses ``` code fences
        assert "```" in result

    def test_disclaimer_is_blockquote(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Disclaimer should be in a blockquote (> prefix)."""
        result = generate_markdown_report(sample_trade_thesis, sample_market_context)
        assert f"> {DISCLAIMER_TEXT}" in result

    def test_conflict_warnings_shown_with_conflicting_signals(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Conflicting signals should produce warning blockquotes."""
        signals = {"rsi": 75.0, "adx": 30.0}  # overbought + strong trend = conflict
        result = generate_markdown_report(
            sample_trade_thesis,
            sample_market_context,
            signals=signals,
        )
        assert "Warning" in result


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------


class _FakeDate(datetime.date):
    """A date subclass that overrides today() for deterministic tests."""

    _frozen: datetime.date | None = None

    @classmethod
    def today(cls) -> datetime.date:  # type: ignore[override]
        if cls._frozen is not None:
            return cls._frozen
        return super().today()


class TestSaveReport:
    """Tests for save_report()."""

    @staticmethod
    def _patch_today(year: int, month: int, day: int) -> patch:
        """Return a context-manager that freezes datetime.date.today()."""
        frozen = datetime.date(year, month, day)

        class Frozen(_FakeDate):
            _frozen = frozen

        return patch("Option_Alpha.reporting.formatters.datetime.date", Frozen)

    def test_creates_file(self, tmp_path: Path) -> None:
        """save_report must create a file in the reports directory."""
        with patch(
            "Option_Alpha.reporting.markdown.DEFAULT_REPORTS_DIR",
            str(tmp_path / "reports"),
        ):
            filepath = save_report(
                content="# Test Report\n\nTest content.",
                ticker="AAPL",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
            )
        assert filepath.exists()
        assert filepath.read_text(encoding="utf-8") == "# Test Report\n\nTest content."

    def test_filename_convention(self, tmp_path: Path) -> None:
        """Filename must follow {TICKER}_{DATE}_{STRIKE}{C/P}_analysis.md pattern."""
        with (
            patch(
                "Option_Alpha.reporting.markdown.DEFAULT_REPORTS_DIR",
                str(tmp_path / "reports"),
            ),
            self._patch_today(2025, 3, 15),
        ):
            filepath = save_report(
                content="# Test",
                ticker="AAPL",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
            )
        assert filepath.name == "AAPL_2025-03-15_185C_analysis.md"

    def test_creates_reports_dir(self, tmp_path: Path) -> None:
        """Reports directory should be created if it does not exist."""
        target_dir = str(tmp_path / "new_reports_dir")
        with patch(
            "Option_Alpha.reporting.markdown.DEFAULT_REPORTS_DIR",
            target_dir,
        ):
            filepath = save_report(
                content="# Test",
                ticker="TSLA",
                strike=Decimal("250"),
                option_type=OptionType.PUT,
            )
        assert filepath.exists()
        assert filepath.parent.exists()

    def test_put_option_filename(self, tmp_path: Path) -> None:
        """Put option filename should use P suffix."""
        with (
            patch(
                "Option_Alpha.reporting.markdown.DEFAULT_REPORTS_DIR",
                str(tmp_path / "reports"),
            ),
            self._patch_today(2025, 3, 15),
        ):
            filepath = save_report(
                content="# Test",
                ticker="SPY",
                strike=Decimal("455"),
                option_type=OptionType.PUT,
            )
        assert "455P" in filepath.name

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """save_report must return a Path object."""
        with patch(
            "Option_Alpha.reporting.markdown.DEFAULT_REPORTS_DIR",
            str(tmp_path / "reports"),
        ):
            result = save_report(
                content="# Test",
                ticker="AAPL",
                strike=Decimal("185"),
                option_type=OptionType.CALL,
            )
        assert isinstance(result, Path)
