"""Tests for settings routes (GET /settings, POST /settings)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# Default settings values (mirrored from settings route to avoid import chain issues)
_DEFAULT_SETTINGS: dict[str, str | int] = {
    "ollama_endpoint": "http://localhost:11434",
    "ollama_model": "llama3.1:8b",
    "scan_top_n": 10,
    "scan_min_volume": 100000,
    "scan_dte_min": 20,
    "scan_dte_max": 60,
}


class TestSettingsPage:
    """Tests for GET /settings."""

    @patch("Option_Alpha.web.routes.settings._load_settings")
    def test_settings_returns_200(
        self,
        mock_load: MagicMock,
        client: TestClient,
    ) -> None:
        """GET /settings returns 200."""
        mock_load.return_value = dict(_DEFAULT_SETTINGS)
        response = client.get("/settings")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.settings._load_settings")
    def test_settings_shows_form(
        self,
        mock_load: MagicMock,
        client: TestClient,
    ) -> None:
        """GET /settings shows the settings form."""
        mock_load.return_value = dict(_DEFAULT_SETTINGS)
        response = client.get("/settings")
        assert "Settings" in response.text
        assert "ollama_endpoint" in response.text
        assert "ollama_model" in response.text

    @patch("Option_Alpha.web.routes.settings._load_settings")
    def test_settings_includes_defaults(
        self,
        mock_load: MagicMock,
        client: TestClient,
    ) -> None:
        """GET /settings shows default values in form fields."""
        mock_load.return_value = dict(_DEFAULT_SETTINGS)
        response = client.get("/settings")
        assert "http://localhost:11434" in response.text
        assert "llama3.1:8b" in response.text

    @patch("Option_Alpha.web.routes.settings._load_settings")
    def test_settings_loads_custom_values(
        self,
        mock_load: MagicMock,
        client: TestClient,
    ) -> None:
        """GET /settings loads and displays existing custom settings."""
        custom: dict[str, str | int] = {
            "ollama_endpoint": "http://custom:11434",
            "ollama_model": "mistral:7b",
            "scan_top_n": 20,
            "scan_min_volume": 200000,
            "scan_dte_min": 30,
            "scan_dte_max": 90,
        }
        mock_load.return_value = custom
        response = client.get("/settings")
        assert "http://custom:11434" in response.text
        assert "mistral:7b" in response.text

    @patch("Option_Alpha.web.routes.settings._load_settings")
    def test_settings_includes_save_button(
        self,
        mock_load: MagicMock,
        client: TestClient,
    ) -> None:
        """GET /settings shows a Save Settings button."""
        mock_load.return_value = dict(_DEFAULT_SETTINGS)
        response = client.get("/settings")
        assert "Save Settings" in response.text


class TestSaveSettings:
    """Tests for POST /settings."""

    @patch("Option_Alpha.web.routes.settings._save_settings")
    def test_save_settings_returns_200(
        self,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /settings saves settings and returns 200."""
        response = client.post(
            "/settings",
            data={
                "ollama_endpoint": "http://localhost:11434",
                "ollama_model": "llama3.1:8b",
                "scan_top_n": "10",
                "scan_min_volume": "100000",
                "scan_dte_min": "20",
                "scan_dte_max": "60",
            },
        )
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.settings._save_settings")
    def test_save_settings_calls_save(
        self,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /settings calls _save_settings with correct data."""
        client.post(
            "/settings",
            data={
                "ollama_endpoint": "http://custom:11434",
                "ollama_model": "mistral:7b",
                "scan_top_n": "25",
                "scan_min_volume": "50000",
                "scan_dte_min": "15",
                "scan_dte_max": "90",
            },
        )
        mock_save.assert_called_once_with(
            {
                "ollama_endpoint": "http://custom:11434",
                "ollama_model": "mistral:7b",
                "scan_top_n": 25,
                "scan_min_volume": 50000,
                "scan_dte_min": 15,
                "scan_dte_max": 90,
            }
        )

    @patch("Option_Alpha.web.routes.settings._save_settings")
    def test_save_settings_shows_confirmation(
        self,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /settings shows 'saved successfully' confirmation."""
        response = client.post(
            "/settings",
            data={
                "ollama_endpoint": "http://localhost:11434",
                "ollama_model": "llama3.1:8b",
                "scan_top_n": "10",
                "scan_min_volume": "100000",
                "scan_dte_min": "20",
                "scan_dte_max": "60",
            },
        )
        assert "saved successfully" in response.text
