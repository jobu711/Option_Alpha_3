"""Tests for the HTTP request logging middleware in web/app.py."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


class TestRequestLoggingMiddleware:
    """Tests for the log_requests middleware."""

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_request_logged_at_info(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GET / produces an INFO-level log from the access logger."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        with caplog.at_level(logging.DEBUG, logger="Option_Alpha.web.access"):
            client.get("/")

        info_messages = [
            r
            for r in caplog.records
            if r.name == "Option_Alpha.web.access" and r.levelno == logging.INFO
        ]
        assert len(info_messages) >= 1
        assert "GET" in info_messages[0].message
        assert "/" in info_messages[0].message

    def test_static_not_logged_at_info(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GET /static/* does NOT produce an INFO-level access log."""
        with caplog.at_level(logging.DEBUG, logger="Option_Alpha.web.access"):
            # Static file may 404 but middleware still runs
            client.get("/static/js/htmx.min.js")

        info_messages = [
            r
            for r in caplog.records
            if r.name == "Option_Alpha.web.access" and r.levelno == logging.INFO
        ]
        assert len(info_messages) == 0

    def test_health_not_logged_at_info(
        self,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """GET /api/health does NOT produce an INFO-level access log."""
        with caplog.at_level(logging.DEBUG, logger="Option_Alpha.web.access"):
            client.get("/api/health")

        info_messages = [
            r
            for r in caplog.records
            if r.name == "Option_Alpha.web.access" and r.levelno == logging.INFO
        ]
        assert len(info_messages) == 0

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_log_includes_duration(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Access log message includes duration in milliseconds."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        with caplog.at_level(logging.DEBUG, logger="Option_Alpha.web.access"):
            client.get("/")

        access_messages = [r for r in caplog.records if r.name == "Option_Alpha.web.access"]
        assert len(access_messages) >= 1
        assert "ms" in access_messages[0].message

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_log_includes_status_code(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Access log message includes the HTTP status code."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        with caplog.at_level(logging.DEBUG, logger="Option_Alpha.web.access"):
            client.get("/")

        access_messages = [r for r in caplog.records if r.name == "Option_Alpha.web.access"]
        assert len(access_messages) >= 1
        assert "200" in access_messages[0].message
