"""Tests for Rich-based terminal output rendering.

Validates that render_report, render_scan_results, and render_health
produce correct output and do not raise. Uses a captured Rich Console
to inspect output content.
"""

from __future__ import annotations

import datetime
import re
from io import StringIO
from unittest.mock import patch

from rich.console import Console

from Option_Alpha.models.analysis import MarketContext, TradeThesis
from Option_Alpha.models.health import HealthStatus
from Option_Alpha.models.options import OptionContract
from Option_Alpha.models.scan import TickerScore

# Regex to strip ANSI escape codes from Rich output
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from Rich console output."""
    return _ANSI_ESCAPE.sub("", text)


def _make_captured_console() -> Console:
    """Create a Console that captures output to a StringIO buffer."""
    return Console(file=StringIO(), force_terminal=True, width=120)


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


class TestRenderReport:
    """Tests for render_report()."""

    def test_render_report_does_not_raise(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
        sample_option_contract: OptionContract,
    ) -> None:
        """render_report should complete without raising."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(
                sample_trade_thesis,
                sample_market_context,
                contract=sample_option_contract,
                signals={"rsi": 55.0, "adx": 30.0},
            )
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert len(output) > 0

    def test_render_report_contains_disclaimer(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Disclaimer must appear in the terminal output."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        # DISCLAIMER_TEXT contains key phrases; check for substrings
        # Rich may add markup, so check lowercase content
        assert "disclaimer" in output.lower()

    def test_render_report_contains_ticker(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must include the ticker symbol from MarketContext."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "AAPL" in output

    def test_render_report_contains_strategy_summary(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Strategy Summary section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Strategy Summary" in output

    def test_render_report_contains_debate_summary(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Debate Summary section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Debate Summary" in output

    def test_render_report_contains_market_snapshot(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Market Snapshot section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Market Snapshot" in output

    def test_render_report_contains_key_factors(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Key Factors section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Key Factors" in output

    def test_render_report_contains_risk_assessment(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Risk Assessment section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Risk Assessment" in output

    def test_render_report_contains_metadata(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Output must contain the Metadata section."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Metadata" in output

    def test_render_report_bullish_direction(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Bullish direction should appear in the output."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "BULLISH" in output

    def test_render_report_handles_none_contract(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """render_report should work when contract is None."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(sample_trade_thesis, sample_market_context, contract=None)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "AAPL" in output

    def test_render_report_with_signals(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
    ) -> None:
        """Indicator signals should appear when provided."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(
                sample_trade_thesis,
                sample_market_context,
                signals={"rsi": 55.0, "adx": 30.0, "iv_rank": 60.0},
            )
        output = captured.file.getvalue()  # type: ignore[union-attr]
        # Indicators should be rendered with interpretations
        assert "rsi" in output.lower() or "Momentum" in output

    def test_render_report_with_greeks_table(
        self,
        sample_trade_thesis: TradeThesis,
        sample_market_context: MarketContext,
        sample_option_contract: OptionContract,
    ) -> None:
        """Greeks table should appear when contract has greeks."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_report

            render_report(
                sample_trade_thesis,
                sample_market_context,
                contract=sample_option_contract,
            )
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Greeks" in output
        assert "Delta" in output


# ---------------------------------------------------------------------------
# render_scan_results
# ---------------------------------------------------------------------------


class TestRenderScanResults:
    """Tests for render_scan_results()."""

    def _make_scores(self) -> list[TickerScore]:
        """Create sample scores for testing."""
        return [
            TickerScore(
                ticker="AAPL",
                score=87.3,
                signals={"rsi": 72.0, "adx": 34.0, "bb_width": 25.0, "iv_rank": 62.0},
                rank=1,
            ),
            TickerScore(
                ticker="MSFT",
                score=82.1,
                signals={"rsi": 60.0, "adx": 28.0, "bb_width": 45.0, "iv_rank": 55.0},
                rank=2,
            ),
        ]

    def test_compact_format_output(self) -> None:
        """Compact format (verbose=False) should show ticker and score."""
        captured = _make_captured_console()
        scores = self._make_scores()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_scan_results

            render_scan_results(scores, verbose=False)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "AAPL" in output
        assert "MSFT" in output

    def test_verbose_mode_shows_detail(self) -> None:
        """Verbose mode should display a table with signal details."""
        captured = _make_captured_console()
        scores = self._make_scores()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_scan_results

            render_scan_results(scores, verbose=True)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Scan Results" in output
        assert "AAPL" in output
        # Verbose has "Signals" column
        assert "Signals" in output

    def test_empty_scores_message(self) -> None:
        """Empty scores should show threshold message."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_scan_results

            render_scan_results([], verbose=False)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "threshold" in output.lower() or "no tickers" in output.lower()

    def test_disclaimer_in_scan_results(self) -> None:
        """Disclaimer should appear in scan results output."""
        captured = _make_captured_console()
        scores = self._make_scores()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_scan_results

            render_scan_results(scores, verbose=False)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        # Disclaimer text is printed at the end
        assert "educational" in output.lower() or "DISCLAIMER" in output

    def test_compact_shows_rank(self) -> None:
        """Compact format should show the rank number."""
        captured = _make_captured_console()
        scores = self._make_scores()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_scan_results

            render_scan_results(scores, verbose=False)
        output = _strip_ansi(captured.file.getvalue())  # type: ignore[union-attr]
        assert "#1" in output or "# 1" in output


# ---------------------------------------------------------------------------
# render_health
# ---------------------------------------------------------------------------


class TestRenderHealth:
    """Tests for render_health()."""

    def test_all_services_available(self, sample_health_status: HealthStatus) -> None:
        """When all services are up, output should show OK for each."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(sample_health_status)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "OK" in output
        assert "Ollama" in output
        assert "Anthropic" in output
        assert "Yahoo Finance" in output
        assert "SQLite" in output

    def test_unavailable_services_show_fail(self) -> None:
        """When a service is down, FAIL should appear for it."""
        status = HealthStatus(
            ollama_available=False,
            anthropic_available=False,
            yfinance_available=True,
            sqlite_available=True,
            ollama_models=[],
            last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
        )
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(status)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "FAIL" in output

    def test_ollama_models_displayed(self, sample_health_status: HealthStatus) -> None:
        """Ollama models should be listed when available."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(sample_health_status)
        # Strip ANSI codes since Rich may insert formatting mid-token
        output = _strip_ansi(captured.file.getvalue())  # type: ignore[union-attr]
        assert "llama3:70b" in output
        assert "mistral:7b" in output

    def test_no_ollama_models_message(self) -> None:
        """When no ollama models, should show appropriate message."""
        status = HealthStatus(
            ollama_available=False,
            anthropic_available=True,
            yfinance_available=True,
            sqlite_available=True,
            ollama_models=[],
            last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
        )
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(status)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "No Ollama models" in output

    def test_last_check_timestamp(self, sample_health_status: HealthStatus) -> None:
        """Last check timestamp should appear in output."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(sample_health_status)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "Last check" in output

    def test_health_title(self, sample_health_status: HealthStatus) -> None:
        """Output should contain the health check title."""
        captured = _make_captured_console()
        with patch("Option_Alpha.reporting.terminal.console", captured):
            from Option_Alpha.reporting.terminal import render_health

            render_health(sample_health_status)
        output = captured.file.getvalue()  # type: ignore[union-attr]
        assert "System Health Check" in output
