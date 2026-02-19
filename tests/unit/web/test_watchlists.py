"""Tests for watchlist routes (GET /watchlists, POST, DELETE, ticker CRUD)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.scan import WatchlistSummary


class TestWatchlistsPage:
    """Tests for GET /watchlists."""

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_watchlists_returns_200(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /watchlists returns 200."""
        mock_repo = AsyncMock()
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/watchlists")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_watchlists_empty_state(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /watchlists shows page content with empty watchlist list."""
        mock_repo = AsyncMock()
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/watchlists")
        assert "Watchlists" in response.text

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_watchlists_shows_existing(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_watchlists: list[WatchlistSummary],
    ) -> None:
        """GET /watchlists shows existing watchlist names."""
        mock_repo = AsyncMock()
        mock_repo.list_watchlists = AsyncMock(return_value=sample_watchlists)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/watchlists")
        assert response.status_code == 200
        assert "Tech Growth" in response.text
        assert "Earnings Watch" in response.text


class TestCreateWatchlist:
    """Tests for POST /watchlists."""

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_create_watchlist(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """POST /watchlists creates a new watchlist and returns partial."""
        new_wl = WatchlistSummary(id=3, name="New List", created_at="2025-01-20T10:00:00Z")
        mock_repo = AsyncMock()
        mock_repo.create_watchlist = AsyncMock(return_value=3)
        mock_repo.list_watchlists = AsyncMock(return_value=[new_wl])
        mock_repo_cls.return_value = mock_repo

        response = client.post("/watchlists", data={"name": "New List"})
        assert response.status_code == 200
        mock_repo.create_watchlist.assert_called_once_with("New List")


class TestDeleteWatchlist:
    """Tests for DELETE /watchlists/{id}."""

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_delete_watchlist(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """DELETE /watchlists/1 deletes the watchlist."""
        mock_repo = AsyncMock()
        mock_repo.delete_watchlist = AsyncMock()
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.delete("/watchlists/1")
        assert response.status_code == 200
        mock_repo.delete_watchlist.assert_called_once_with(1)


class TestWatchlistTickers:
    """Tests for watchlist ticker CRUD routes."""

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_get_watchlist_tickers(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /watchlists/{id}/tickers returns ticker list partial."""
        mock_repo = AsyncMock()
        mock_repo.get_watchlist_tickers = AsyncMock(return_value=["AAPL", "MSFT"])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/watchlists/1/tickers")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_add_ticker(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """POST /watchlists/{id}/tickers adds a ticker."""
        mock_repo = AsyncMock()
        mock_repo.add_tickers_to_watchlist = AsyncMock()
        mock_repo.get_watchlist_tickers = AsyncMock(return_value=["AAPL", "GOOG"])
        mock_repo_cls.return_value = mock_repo

        response = client.post("/watchlists/1/tickers", data={"ticker": "goog"})
        assert response.status_code == 200
        # Ticker should be uppercased
        mock_repo.add_tickers_to_watchlist.assert_called_once_with(1, ["GOOG"])

    @patch("Option_Alpha.web.routes.watchlists.Repository")
    def test_remove_ticker(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """DELETE /watchlists/{id}/tickers/{ticker} removes the ticker."""
        mock_repo = AsyncMock()
        mock_repo.remove_tickers_from_watchlist = AsyncMock()
        mock_repo.get_watchlist_tickers = AsyncMock(return_value=["AAPL"])
        mock_repo_cls.return_value = mock_repo

        response = client.delete("/watchlists/1/tickers/GOOG")
        assert response.status_code == 200
        mock_repo.remove_tickers_from_watchlist.assert_called_once_with(1, ["GOOG"])
