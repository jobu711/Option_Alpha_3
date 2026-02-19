"""Tests for the scanner routes (GET /scanner, GET /scanner/results)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.scan import ScanRun, TickerScore


class TestScannerPage:
    """Tests for GET /scanner."""

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_returns_200(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /scanner returns 200."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[])
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_empty_state(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /scanner shows empty state when no scans exist."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[])
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert response.status_code == 200
        assert "No scan results yet" in response.text

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_shows_run_scan_button(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /scanner includes a Run Scan button."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[])
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert "Run Scan" in response.text

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_shows_scan_history(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
    ) -> None:
        """GET /scanner shows scan history when scans exist."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[sample_scan_run])
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert response.status_code == 200
        assert "Scan History" in response.text
        assert "high_iv" in response.text

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_includes_htmx_attributes(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /scanner includes HTMX attributes for Run Scan button."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[])
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert "hx-post" in response.text or "hx-get" in response.text

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_scanner_with_results_shows_tickers(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET /scanner displays ticker scores when a scan with results exists."""
        mock_repo = AsyncMock()
        mock_repo.list_scan_runs = AsyncMock(return_value=[sample_scan_run])
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner")
        assert response.status_code == 200
        assert "AAPL" in response.text
        assert "MSFT" in response.text


class TestScannerResults:
    """Tests for GET /scanner/results (HTMX partial)."""

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_results_returns_200(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /scanner/results returns 200 with empty results."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner/results")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_results_sort_by_ticker(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET /scanner/results?sort=ticker sorts alphabetically."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner/results?sort=ticker&direction=asc")
        assert response.status_code == 200
        # AAPL should come before TSLA in ascending order
        text = response.text
        aapl_pos = text.find("AAPL")
        tsla_pos = text.find("TSLA")
        assert aapl_pos < tsla_pos

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_results_sort_by_score_desc(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET /scanner/results?sort=score&direction=desc shows highest first."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner/results?sort=score&direction=desc")
        assert response.status_code == 200
        # AAPL (82.5) should come before AMZN (68.1)
        text = response.text
        aapl_pos = text.find("AAPL")
        amzn_pos = text.find("AMZN")
        assert aapl_pos < amzn_pos

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_results_sort_direction_asc(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_scan_run: ScanRun,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET /scanner/results?sort=score&direction=asc shows lowest first."""
        mock_repo = AsyncMock()
        mock_repo.get_latest_scan = AsyncMock(return_value=sample_scan_run)
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner/results?sort=score&direction=asc")
        assert response.status_code == 200
        # AMZN (68.1) should come before AAPL (82.5) in ascending
        text = response.text
        amzn_pos = text.find("AMZN")
        aapl_pos = text.find("AAPL")
        assert amzn_pos < aapl_pos

    @patch("Option_Alpha.web.routes.scanner.Repository")
    def test_results_with_scan_id(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_ticker_scores: list[TickerScore],
    ) -> None:
        """GET /scanner/results?scan_id=X fetches scores for that specific scan."""
        mock_repo = AsyncMock()
        mock_repo.get_scores_for_scan = AsyncMock(return_value=sample_ticker_scores)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/scanner/results?scan_id=scan-123")
        assert response.status_code == 200
        mock_repo.get_scores_for_scan.assert_called_once_with("scan-123")
