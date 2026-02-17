"""Reporting module: terminal output, markdown generation, and legal disclaimers.

Re-exports all public functions so consumers can import directly:
    from Option_Alpha.reporting import render_report, generate_markdown_report
"""

from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT, get_disclaimer
from Option_Alpha.reporting.formatters import (
    build_report_filename,
    detect_conflicting_signals,
    format_greek_impact,
    group_indicators_by_category,
)
from Option_Alpha.reporting.markdown import generate_markdown_report, save_report
from Option_Alpha.reporting.terminal import render_health, render_report, render_scan_results

__all__ = [
    # Disclaimer
    "DISCLAIMER_TEXT",
    "get_disclaimer",
    # Formatters
    "build_report_filename",
    "detect_conflicting_signals",
    "format_greek_impact",
    "group_indicators_by_category",
    # Markdown
    "generate_markdown_report",
    "save_report",
    # Terminal
    "render_health",
    "render_report",
    "render_scan_results",
]
