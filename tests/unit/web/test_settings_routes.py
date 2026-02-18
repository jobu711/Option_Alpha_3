"""Tests for the /api/settings endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
Settings file I/O is patched to avoid writing to disk.
"""

from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.web.app import create_app
from Option_Alpha.web.routes.settings import WebSettings


def _create_test_app() -> FastAPI:
    """Create a FastAPI app for settings testing."""
    return create_app()


class TestGetSettings:
    """Tests for GET /api/settings."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """GET /api/settings should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        with patch(
            "Option_Alpha.web.routes.settings._load_settings",
            return_value=WebSettings(),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/settings")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_default_values(self) -> None:
        """GET /api/settings should return defaults when no settings file exists."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        with patch(
            "Option_Alpha.web.routes.settings._load_settings",
            return_value=WebSettings(),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/settings")

        body = response.json()
        assert body["ollama_endpoint"] == "http://localhost:11434"
        assert body["ollama_model"] == "llama3.1:8b"
        assert body["scan_top_n"] == 10
        assert body["scan_min_volume"] == 100
        assert body["default_dte_min"] == 20
        assert body["default_dte_max"] == 60

    @pytest.mark.asyncio
    async def test_returns_all_expected_fields(self) -> None:
        """Response should contain all WebSettings fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        with patch(
            "Option_Alpha.web.routes.settings._load_settings",
            return_value=WebSettings(),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/settings")

        body = response.json()
        expected_fields = {
            "ollama_endpoint",
            "ollama_model",
            "scan_top_n",
            "scan_min_volume",
            "default_dte_min",
            "default_dte_max",
        }
        assert expected_fields.issubset(body.keys())


class TestUpdateSettings:
    """Tests for PUT /api/settings."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """PUT /api/settings should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        with patch("Option_Alpha.web.routes.settings._save_settings"):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/settings",
                    json={
                        "ollama_endpoint": "http://localhost:11434",
                        "ollama_model": "llama3.1:8b",
                        "scan_top_n": 10,
                        "scan_min_volume": 100,
                        "default_dte_min": 20,
                        "default_dte_max": 60,
                    },
                )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_updated_values(self) -> None:
        """PUT /api/settings should return the updated settings."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        new_settings = {
            "ollama_endpoint": "http://custom:11434",
            "ollama_model": "llama3.2:3b",
            "scan_top_n": 25,
            "scan_min_volume": 500,
            "default_dte_min": 30,
            "default_dte_max": 90,
        }
        with patch("Option_Alpha.web.routes.settings._save_settings"):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put("/api/settings", json=new_settings)

        body = response.json()
        assert body["ollama_endpoint"] == "http://custom:11434"
        assert body["ollama_model"] == "llama3.2:3b"
        assert body["scan_top_n"] == 25
        assert body["scan_min_volume"] == 500
        assert body["default_dte_min"] == 30
        assert body["default_dte_max"] == 90

    @pytest.mark.asyncio
    async def test_round_trip(self) -> None:
        """PUT followed by GET should return the same settings."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        custom_settings = {
            "ollama_endpoint": "http://remote:11434",
            "ollama_model": "mistral:7b",
            "scan_top_n": 15,
            "scan_min_volume": 200,
            "default_dte_min": 25,
            "default_dte_max": 45,
        }
        custom_model = WebSettings(**custom_settings)

        with (
            patch("Option_Alpha.web.routes.settings._save_settings"),
            patch(
                "Option_Alpha.web.routes.settings._load_settings",
                return_value=custom_model,
            ),
        ):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # PUT
                put_response = await client.put("/api/settings", json=custom_settings)
                # GET
                get_response = await client.get("/api/settings")

        assert put_response.json() == get_response.json()

    @pytest.mark.asyncio
    async def test_calls_save(self) -> None:
        """PUT /api/settings should call _save_settings."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        with patch("Option_Alpha.web.routes.settings._save_settings") as mock_save:
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                await client.put(
                    "/api/settings",
                    json={
                        "ollama_endpoint": "http://localhost:11434",
                        "ollama_model": "llama3.1:8b",
                        "scan_top_n": 10,
                        "scan_min_volume": 100,
                        "default_dte_min": 20,
                        "default_dte_max": 60,
                    },
                )
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_fields_use_defaults(self) -> None:
        """PUT with partial body should fill in defaults for missing fields."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        # Send only some fields — Pydantic uses defaults for the rest
        with patch("Option_Alpha.web.routes.settings._save_settings"):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/settings",
                    json={"scan_top_n": 42},
                )

        body = response.json()
        assert body["scan_top_n"] == 42
        # Other fields should have defaults
        assert body["ollama_endpoint"] == "http://localhost:11434"
        assert body["ollama_model"] == "llama3.1:8b"


class TestWebSettingsModel:
    """Tests for the WebSettings Pydantic model itself."""

    def test_default_values(self) -> None:
        """WebSettings should have sensible defaults."""
        settings = WebSettings()
        assert settings.ollama_endpoint == "http://localhost:11434"
        assert settings.ollama_model == "llama3.1:8b"
        assert settings.scan_top_n == 10
        assert settings.scan_min_volume == 100
        assert settings.default_dte_min == 20
        assert settings.default_dte_max == 60

    def test_json_round_trip(self) -> None:
        """WebSettings should survive JSON serialization round-trip."""
        original = WebSettings(
            ollama_endpoint="http://custom:11434",
            ollama_model="llama3.2:3b",
            scan_top_n=25,
            scan_min_volume=500,
            default_dte_min=30,
            default_dte_max=90,
        )
        restored = WebSettings.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_frozen(self) -> None:
        """WebSettings should be immutable (frozen=True)."""
        settings = WebSettings()
        with pytest.raises(Exception):  # noqa: B017, PT011
            settings.scan_top_n = 99  # type: ignore[misc]
