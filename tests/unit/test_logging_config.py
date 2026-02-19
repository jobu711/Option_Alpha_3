"""Tests for the centralized logging configuration module."""

from __future__ import annotations

import logging

import pytest

from Option_Alpha.logging_config import LOG_FORMAT, configure_logging


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """Reset root logger state between tests."""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]
    yield  # type: ignore[misc]
    root.setLevel(original_level)
    root.handlers = original_handlers


class TestConfigureLogging:
    """Tests for configure_logging() function."""

    def test_default_level_is_info(self) -> None:
        """Default call sets root logger to INFO."""
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_verbose_sets_debug(self) -> None:
        """verbose=True sets root logger to DEBUG."""
        configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_quiet_sets_warning(self) -> None:
        """quiet=True sets root logger to WARNING."""
        configure_logging(quiet=True)
        assert logging.getLogger().level == logging.WARNING

    def test_level_param_override(self) -> None:
        """Explicit level param sets the root logger level."""
        configure_logging(level="DEBUG")
        assert logging.getLogger().level == logging.DEBUG

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LOG_LEVEL env var sets root logger level."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        configure_logging()
        assert logging.getLogger().level == logging.DEBUG

    def test_module_level_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LOG_LEVEL_AGENTS env var sets the agents logger level."""
        monkeypatch.setenv("LOG_LEVEL_AGENTS", "DEBUG")
        configure_logging()
        agents_logger = logging.getLogger("Option_Alpha.agents")
        assert agents_logger.level == logging.DEBUG

    def test_force_overrides_existing(self) -> None:
        """configure_logging() overrides a prior basicConfig(CRITICAL)."""
        logging.basicConfig(level=logging.CRITICAL)
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_verbose_overrides_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """verbose=True takes priority over LOG_LEVEL env var."""
        monkeypatch.setenv("LOG_LEVEL", "WARNING")
        configure_logging(verbose=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_invalid_env_level_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid LOG_LEVEL env var falls back to INFO."""
        monkeypatch.setenv("LOG_LEVEL", "INVALID")
        configure_logging()
        assert logging.getLogger().level == logging.INFO

    def test_uvicorn_access_demoted(self) -> None:
        """configure_logging() demotes uvicorn.access to WARNING."""
        configure_logging()
        assert logging.getLogger("uvicorn.access").level == logging.WARNING


class TestLogFormat:
    """Tests for the LOG_FORMAT constant."""

    def test_format_includes_timestamp(self) -> None:
        """LOG_FORMAT includes %(asctime)s for timestamp."""
        assert "%(asctime)s" in LOG_FORMAT

    def test_format_includes_name(self) -> None:
        """LOG_FORMAT includes %(name)s for logger name."""
        assert "%(name)s" in LOG_FORMAT
