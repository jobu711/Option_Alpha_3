"""Reporting module: terminal output and markdown generation.

Re-exports all public functions so consumers can import directly:
    from Option_Alpha.reporting import render_report, generate_markdown_report
"""

from Option_Alpha.reporting.formatters import (
    build_report_filename,
    detect_conflicting_signals,
    format_greek_impact,
    group_indicators_by_category,
)
from Option_Alpha.reporting.markdown import generate_markdown_report, save_report
from Option_Alpha.reporting.terminal import render_health, render_report, render_scan_results

__all__ = [
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
