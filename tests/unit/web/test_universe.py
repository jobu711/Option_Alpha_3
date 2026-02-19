"""Tests for universe routes (GET /universe, presets, filters)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.market_data import TickerInfo, UniverseStats
from Option_Alpha.models.scan import UniversePreset


class TestUniversePage:
    """Tests for GET /universe."""

    @patch("Option_Alpha.web.routes.universe.UniverseService")
    @patch("Option_Alpha.web.routes.universe.Repository")
    @patch("Option_Alpha.web.routes.universe.RateLimiter")
    @patch("Option_Alpha.web.routes.universe.ServiceCache")
    def test_universe_returns_200(
        self,
        mock_cache_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_repo_cls: AsyncMock,
        mock_universe_cls: MagicMock,
        client: TestClient,
        sample_ticker_infos: list[TickerInfo],
        sample_universe_stats: UniverseStats,
    ) -> None:
        """GET /universe returns 200."""
        mock_svc = AsyncMock()
        mock_svc.get_universe = AsyncMock(return_value=sample_ticker_infos)
        mock_svc.get_stats = AsyncMock(return_value=sample_universe_stats)
        mock_svc.aclose = AsyncMock()
        mock_universe_cls.return_value = mock_svc

        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/universe")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.universe.UniverseService")
    @patch("Option_Alpha.web.routes.universe.Repository")
    @patch("Option_Alpha.web.routes.universe.RateLimiter")
    @patch("Option_Alpha.web.routes.universe.ServiceCache")
    def test_universe_shows_stats(
        self,
        mock_cache_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_repo_cls: AsyncMock,
        mock_universe_cls: MagicMock,
        client: TestClient,
        sample_ticker_infos: list[TickerInfo],
        sample_universe_stats: UniverseStats,
    ) -> None:
        """GET /universe displays universe statistics."""
        mock_svc = AsyncMock()
        mock_svc.get_universe = AsyncMock(return_value=sample_ticker_infos)
        mock_svc.get_stats = AsyncMock(return_value=sample_universe_stats)
        mock_svc.aclose = AsyncMock()
        mock_universe_cls.return_value = mock_svc

        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/universe")
        assert "500" in response.text  # Total tickers
        assert "480" in response.text  # Active tickers

    @patch("Option_Alpha.web.routes.universe.UniverseService")
    @patch("Option_Alpha.web.routes.universe.Repository")
    @patch("Option_Alpha.web.routes.universe.RateLimiter")
    @patch("Option_Alpha.web.routes.universe.ServiceCache")
    def test_universe_includes_filter_controls(
        self,
        mock_cache_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_repo_cls: AsyncMock,
        mock_universe_cls: MagicMock,
        client: TestClient,
        sample_ticker_infos: list[TickerInfo],
        sample_universe_stats: UniverseStats,
    ) -> None:
        """GET /universe includes sector, tier, and source filter controls."""
        mock_svc = AsyncMock()
        mock_svc.get_universe = AsyncMock(return_value=sample_ticker_infos)
        mock_svc.get_stats = AsyncMock(return_value=sample_universe_stats)
        mock_svc.aclose = AsyncMock()
        mock_universe_cls.return_value = mock_svc

        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/universe")
        assert "filter-sector" in response.text
        assert "filter-tier" in response.text
        assert "filter-source" in response.text

    @patch("Option_Alpha.web.routes.universe.UniverseService")
    @patch("Option_Alpha.web.routes.universe.Repository")
    @patch("Option_Alpha.web.routes.universe.RateLimiter")
    @patch("Option_Alpha.web.routes.universe.ServiceCache")
    def test_universe_shows_ticker_symbols(
        self,
        mock_cache_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_repo_cls: AsyncMock,
        mock_universe_cls: MagicMock,
        client: TestClient,
        sample_ticker_infos: list[TickerInfo],
        sample_universe_stats: UniverseStats,
    ) -> None:
        """GET /universe shows ticker symbols from the universe."""
        mock_svc = AsyncMock()
        mock_svc.get_universe = AsyncMock(return_value=sample_ticker_infos)
        mock_svc.get_stats = AsyncMock(return_value=sample_universe_stats)
        mock_svc.aclose = AsyncMock()
        mock_universe_cls.return_value = mock_svc

        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/universe")
        assert "AAPL" in response.text
        assert "MSFT" in response.text

    @patch("Option_Alpha.web.routes.universe.UniverseService")
    @patch("Option_Alpha.web.routes.universe.Repository")
    @patch("Option_Alpha.web.routes.universe.RateLimiter")
    @patch("Option_Alpha.web.routes.universe.ServiceCache")
    def test_universe_cleans_up_service(
        self,
        mock_cache_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_repo_cls: AsyncMock,
        mock_universe_cls: MagicMock,
        client: TestClient,
        sample_ticker_infos: list[TickerInfo],
        sample_universe_stats: UniverseStats,
    ) -> None:
        """GET /universe calls aclose() on the UniverseService."""
        mock_svc = AsyncMock()
        mock_svc.get_universe = AsyncMock(return_value=sample_ticker_infos)
        mock_svc.get_stats = AsyncMock(return_value=sample_universe_stats)
        mock_svc.aclose = AsyncMock()
        mock_universe_cls.return_value = mock_svc

        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo.list_watchlists = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        client.get("/universe")
        mock_svc.aclose.assert_called_once()


class TestSavePreset:
    """Tests for POST /universe/presets."""

    @patch("Option_Alpha.web.routes.universe.Repository")
    def test_save_preset(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """POST /universe/presets saves a new preset."""
        mock_repo = AsyncMock()
        mock_repo.save_preset = AsyncMock(return_value=1)
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.post(
            "/universe/presets",
            data={"name": "Tech Large", "filters": '{"sectors": ["Technology"]}'},
        )
        assert response.status_code == 200
        mock_repo.save_preset.assert_called_once_with("Tech Large", '{"sectors": ["Technology"]}')


class TestListPresetsJson:
    """Tests for GET /api/presets."""

    @patch("Option_Alpha.web.routes.universe.Repository")
    def test_presets_json_returns_list(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_presets: list[UniversePreset],
    ) -> None:
        """GET /api/presets returns JSON list of presets."""
        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=sample_presets)
        mock_repo_cls.return_value = mock_repo

        response = client.get("/api/presets")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "Large Tech"

    @patch("Option_Alpha.web.routes.universe.Repository")
    def test_presets_json_empty(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /api/presets returns empty list when no presets."""
        mock_repo = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/api/presets")
        assert response.status_code == 200
        assert response.json() == []


class TestDeletePreset:
    """Tests for DELETE /universe/presets/{id}."""

    @patch("Option_Alpha.web.routes.universe.Repository")
    def test_delete_preset(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """DELETE /universe/presets/1 deletes the preset."""
        mock_repo = AsyncMock()
        mock_repo.delete_preset = AsyncMock()
        mock_repo.list_presets = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.delete("/universe/presets/1")
        assert response.status_code == 200
        mock_repo.delete_preset.assert_called_once_with(1)
