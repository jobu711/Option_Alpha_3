"""Tests for health routes (GET /health, POST /health/recheck)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.health import HealthStatus


class TestHealthPage:
    """Tests for GET /health."""

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_health_returns_200(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """GET /health returns 200."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.get("/health")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_health_shows_status_indicators(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """GET /health shows online/offline status indicators."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.get("/health")
        assert "Online" in response.text
        assert "Ollama" in response.text
        assert "yfinance" in response.text
        assert "SQLite" in response.text

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_health_shows_ollama_models(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """GET /health shows available Ollama models when Ollama is online."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.get("/health")
        assert "llama3.1:8b" in response.text
        assert "mistral:7b" in response.text

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_health_shows_offline_services(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status_degraded: HealthStatus,
    ) -> None:
        """GET /health shows offline status when services are down."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status_degraded)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.get("/health")
        assert "Offline" in response.text

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_health_cleans_up_service(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """GET /health calls aclose() on the HealthService."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        client.get("/health")
        mock_svc.aclose.assert_called_once()


class TestHealthRecheck:
    """Tests for POST /health/recheck."""

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_recheck_returns_200(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """POST /health/recheck returns 200 with updated status partial."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.post("/health/recheck")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.health.HealthService")
    def test_recheck_shows_updated_status(
        self,
        mock_health_cls: MagicMock,
        client: TestClient,
        sample_health_status: HealthStatus,
    ) -> None:
        """POST /health/recheck returns partial with status info."""
        mock_svc = AsyncMock()
        mock_svc.check_all = AsyncMock(return_value=sample_health_status)
        mock_svc.aclose = AsyncMock()
        mock_health_cls.return_value = mock_svc

        response = client.post("/health/recheck")
        assert "Ollama" in response.text
        assert "Online" in response.text
