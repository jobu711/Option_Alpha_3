"""Tests for HealthService: Ollama, yfinance, and SQLite health checks.

All external calls are mocked. No real API calls.

Covers:
- check_all() when everything is healthy -- all True in HealthStatus
- check_all() when one service is down -- others still checked
- check_ollama() succeeds when model exists
- check_ollama() fails when model missing
- check_ollama() fails when Ollama is unreachable
- check_yfinance() succeeds with valid SPY data
- check_yfinance() fails when yfinance errors
- check_database() succeeds with valid connection
- check_database() fails when DB is inaccessible
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from Option_Alpha.data.database import Database
from Option_Alpha.models.health import HealthStatus
from Option_Alpha.services.health import (
    REQUIRED_OLLAMA_MODEL,
    HealthService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_ollama_response(
    models: list[str] | None = None,
    status_code: int = 200,
) -> MagicMock:
    """Create a mock httpx response for the Ollama tags endpoint."""
    response = MagicMock()
    response.status_code = status_code
    if models is None:
        models = [REQUIRED_OLLAMA_MODEL, "mistral:7b"]
    response.json.return_value = {
        "models": [{"name": m} for m in models],
    }
    return response


# ---------------------------------------------------------------------------
# check_all tests
# ---------------------------------------------------------------------------


class TestCheckAll:
    """Tests for check_all() consolidated health check."""

    @pytest.mark.asyncio()
    async def test_all_healthy(self) -> None:
        """check_all() returns all True when everything is healthy."""
        service = HealthService(database=None)

        # Mock Ollama
        ollama_response = _mock_ollama_response()

        # Mock yfinance canary
        mock_yf_result = True

        with (
            patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_httpx_cls,
            patch.object(
                service,
                "_yfinance_canary",
                return_value=mock_yf_result,
            ),
        ):
            mock_httpx_client = AsyncMock()
            mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
            mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
            mock_httpx_client.get = AsyncMock(return_value=ollama_response)
            mock_httpx_cls.return_value = mock_httpx_client

            status = await service.check_all()

        assert isinstance(status, HealthStatus)
        assert status.ollama_available is True
        assert status.yfinance_available is True
        # sqlite_available is False because no database was configured
        assert status.sqlite_available is False

    @pytest.mark.asyncio()
    async def test_one_service_down_others_still_checked(self) -> None:
        """When Ollama is down, yfinance and SQLite are still checked."""
        service = HealthService(database=None)

        with (
            patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_httpx_cls,
            patch.object(
                service,
                "_yfinance_canary",
                return_value=True,
            ),
        ):
            mock_httpx_client = AsyncMock()
            mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
            mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
            # Ollama is unreachable
            mock_httpx_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_httpx_cls.return_value = mock_httpx_client

            status = await service.check_all()

        assert status.ollama_available is False
        assert status.yfinance_available is True


# ---------------------------------------------------------------------------
# check_ollama tests
# ---------------------------------------------------------------------------


class TestCheckOllama:
    """Tests for check_ollama() and _check_ollama_with_models()."""

    @pytest.mark.asyncio()
    async def test_succeeds_when_required_model_exists(self) -> None:
        """check_ollama() returns True when llama3.1:8b is available."""
        service = HealthService()
        response = _mock_ollama_response(models=[REQUIRED_OLLAMA_MODEL, "other:model"])

        with patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_cls.return_value = mock_client

            result = await service.check_ollama()

        assert result is True

    @pytest.mark.asyncio()
    async def test_fails_when_model_missing(self) -> None:
        """check_ollama() returns False when required model is not found."""
        service = HealthService()
        response = _mock_ollama_response(models=["other:model", "phi:latest"])

        with patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_cls.return_value = mock_client

            result = await service.check_ollama()

        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_when_ollama_unreachable(self) -> None:
        """check_ollama() returns False when Ollama is not running."""
        service = HealthService()

        with patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_cls.return_value = mock_client

            result = await service.check_ollama()

        assert result is False

    @pytest.mark.asyncio()
    async def test_returns_model_list(self) -> None:
        """_check_ollama_with_models() returns list of available models."""
        service = HealthService()
        model_names = [REQUIRED_OLLAMA_MODEL, "codellama:7b"]
        response = _mock_ollama_response(models=model_names)

        with patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_cls.return_value = mock_client

            available, models = await service._check_ollama_with_models()

        assert available is True
        assert REQUIRED_OLLAMA_MODEL in models
        assert "codellama:7b" in models

    @pytest.mark.asyncio()
    async def test_non_200_returns_false(self) -> None:
        """Non-200 HTTP response means Ollama is not healthy."""
        service = HealthService()
        response = _mock_ollama_response(status_code=500)

        with patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_cls.return_value = mock_client

            result = await service.check_ollama()

        assert result is False


# ---------------------------------------------------------------------------
# check_yfinance tests
# ---------------------------------------------------------------------------


class TestCheckYfinance:
    """Tests for check_yfinance()."""

    @pytest.mark.asyncio()
    async def test_succeeds_with_valid_spy_data(self) -> None:
        """check_yfinance() returns True when SPY canary fetch succeeds."""
        service = HealthService()

        with patch.object(
            service,
            "_yfinance_canary",
            return_value=True,
        ):
            result = await service.check_yfinance()

        assert result is True

    @pytest.mark.asyncio()
    async def test_fails_when_yfinance_errors(self) -> None:
        """check_yfinance() returns False when yfinance raises."""
        service = HealthService()

        with patch.object(
            service,
            "_yfinance_canary",
            side_effect=RuntimeError("yfinance broken"),
        ):
            result = await service.check_yfinance()

        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_when_canary_returns_empty(self) -> None:
        """check_yfinance() returns False when SPY returns no data."""
        service = HealthService()

        with patch.object(
            service,
            "_yfinance_canary",
            return_value=False,
        ):
            result = await service.check_yfinance()

        assert result is False

    @pytest.mark.asyncio()
    async def test_timeout_returns_false(self) -> None:
        """check_yfinance() returns False when the canary check times out."""
        service = HealthService()

        with patch.object(
            service,
            "_yfinance_canary",
            side_effect=TimeoutError("timed out"),
        ):
            result = await service.check_yfinance()

        assert result is False


# ---------------------------------------------------------------------------
# check_database tests
# ---------------------------------------------------------------------------


class TestCheckDatabase:
    """Tests for check_database()."""

    @pytest.mark.asyncio()
    async def test_succeeds_with_valid_connection(self) -> None:
        """check_database() returns True when DB is accessible."""
        async with Database(db_path=":memory:") as db:
            service = HealthService(database=db)
            result = await service.check_database()

        assert result is True

    @pytest.mark.asyncio()
    async def test_fails_when_no_database_configured(self) -> None:
        """check_database() returns False when no database is set."""
        service = HealthService(database=None)
        result = await service.check_database()
        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_when_db_query_errors(self) -> None:
        """check_database() returns False when the DB query fails."""
        mock_db = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=RuntimeError("DB corrupted"))
        mock_db.connection = mock_conn

        service = HealthService(database=mock_db)
        result = await service.check_database()
        assert result is False


# ---------------------------------------------------------------------------
# HealthStatus model integration
# ---------------------------------------------------------------------------


class TestHealthStatusModel:
    """Tests that check_all() returns a properly structured HealthStatus."""

    @pytest.mark.asyncio()
    async def test_health_status_has_correct_fields(self) -> None:
        """HealthStatus from check_all() has all required fields."""
        service = HealthService(database=None)

        with (
            patch("Option_Alpha.services.health.httpx.AsyncClient") as mock_cls,
            patch.object(
                service,
                "_yfinance_canary",
                return_value=False,
            ),
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_cls.return_value = mock_client

            status = await service.check_all()

        assert hasattr(status, "ollama_available")
        assert hasattr(status, "yfinance_available")
        assert hasattr(status, "sqlite_available")
        assert hasattr(status, "ollama_models")
        assert hasattr(status, "last_check")
        assert status.last_check is not None
