"""Tests for the dashboard route (GET /)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.scan import ScanRun, TickerScore


class TestDashboardRoute:
    """Tests for GET / (dashboard page)."""

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_returns_200(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET / returns 200 status code."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_empty_state(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET / shows empty state when no scans exist."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert response.status_code == 200
        # Empty state message from template
        assert "No scan results yet" in response.text

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_includes_dashboard_text(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET / includes 'Dashboard' in the page title."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert "Dashboard" in response.text

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_with_scan(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET / returns scan summary when a scan exists."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert response.status_code == 200
        assert "Latest Scan" in response.text
        assert "AAPL" in response.text

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_shows_top_5_only(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET / shows at most 5 tickers in the dashboard summary."""
        # Add a 6th ticker that should NOT appear
        scores_with_extra = [
            *sample_ticker_scores,
            TickerScore(ticker="GOOG", score=65.0, signals={}, rank=6),
        ]
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=scores_with_extra)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert response.status_code == 200
        # The route slices scores[:5], so GOOG (rank 6) should not appear
        assert "AAPL" in response.text
        assert "AMZN" in response.text
        assert "GOOG" not in response.text

    @patch("Option_Alpha.web.routes.dashboard.Repository")
    def test_dashboard_includes_disclaimer_text(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET / includes the disclaimer text from base.html."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/")
        assert "DISCLAIMER" in response.text
