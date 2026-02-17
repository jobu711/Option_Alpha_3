"""Tests for HealthService: Ollama, Anthropic, yfinance, and SQLite checks.

All external calls are mocked. No real API calls.

Covers:
- check_all() when everything is healthy -- all True in HealthStatus
- check_all() when one service is down -- others still checked
- check_ollama() succeeds when model exists
- check_ollama() fails when model missing
- check_ollama() fails when Ollama is unreachable
- check_anthropic() succeeds when API reachable
- check_anthropic() fails when key missing or API unreachable
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


def _patch_client(
    service: HealthService,
    response: MagicMock | None = None,
    *,
    side_effect: Exception | None = None,
) -> None:
    """Replace the service's shared httpx client with a mock."""
    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_client.get = AsyncMock(return_value=response)
    service._client = mock_client


# ---------------------------------------------------------------------------
# check_all tests
# ---------------------------------------------------------------------------


class TestCheckAll:
    """Tests for check_all() consolidated health check."""

    @pytest.mark.asyncio()
    async def test_all_healthy(self) -> None:
        """check_all() returns all True when everything is healthy."""
        service = HealthService(database=None)
        _patch_client(service, _mock_ollama_response())

        with (
            patch.object(service, "_yfinance_canary", return_value=True),
            patch.object(service, "check_anthropic", return_value=True),
        ):
            status = await service.check_all()

        assert isinstance(status, HealthStatus)
        assert status.ollama_available is True
        assert status.anthropic_available is True
        assert status.yfinance_available is True
        # sqlite_available is False because no database was configured
        assert status.sqlite_available is False

    @pytest.mark.asyncio()
    async def test_one_service_down_others_still_checked(self) -> None:
        """When Ollama is down, yfinance and SQLite are still checked."""
        service = HealthService(database=None)
        _patch_client(service, side_effect=httpx.ConnectError("refused"))

        with (
            patch.object(service, "_yfinance_canary", return_value=True),
            patch.object(service, "check_anthropic", return_value=True),
        ):
            status = await service.check_all()

        assert status.ollama_available is False
        assert status.anthropic_available is True
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
        _patch_client(service, response)
        result = await service.check_ollama()
        assert result is True

    @pytest.mark.asyncio()
    async def test_fails_when_model_missing(self) -> None:
        """check_ollama() returns False when required model is not found."""
        service = HealthService()
        _patch_client(service, _mock_ollama_response(models=["other:model", "phi:latest"]))
        result = await service.check_ollama()
        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_when_ollama_unreachable(self) -> None:
        """check_ollama() returns False when Ollama is not running."""
        service = HealthService()
        _patch_client(service, side_effect=httpx.ConnectError("Connection refused"))
        result = await service.check_ollama()
        assert result is False

    @pytest.mark.asyncio()
    async def test_returns_model_list(self) -> None:
        """_check_ollama_with_models() returns list of available models."""
        service = HealthService()
        model_names = [REQUIRED_OLLAMA_MODEL, "codellama:7b"]
        _patch_client(service, _mock_ollama_response(models=model_names))

        available, models = await service._check_ollama_with_models()

        assert available is True
        assert REQUIRED_OLLAMA_MODEL in models
        assert "codellama:7b" in models

    @pytest.mark.asyncio()
    async def test_non_200_returns_false(self) -> None:
        """Non-200 HTTP response means Ollama is not healthy."""
        service = HealthService()
        _patch_client(service, _mock_ollama_response(status_code=500))
        result = await service.check_ollama()
        assert result is False


# ---------------------------------------------------------------------------
# check_anthropic tests
# ---------------------------------------------------------------------------


class TestCheckAnthropic:
    """Tests for check_anthropic()."""

    @pytest.mark.asyncio()
    async def test_succeeds_when_api_reachable(self) -> None:
        """check_anthropic() returns True when API responds (any status)."""
        service = HealthService()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"}):
            result = await service.check_anthropic()

        assert result is True

    @pytest.mark.asyncio()
    async def test_succeeds_even_with_401(self) -> None:
        """check_anthropic() returns True on 401 — API is reachable."""
        service = HealthService()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        service._client = mock_client

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-bad-key"}):
            result = await service.check_anthropic()

        assert result is True

    @pytest.mark.asyncio()
    async def test_fails_when_no_api_key(self) -> None:
        """check_anthropic() returns False when ANTHROPIC_API_KEY not set."""
        service = HealthService()

        with patch.dict("os.environ", {}, clear=True):
            result = await service.check_anthropic()

        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_when_api_unreachable(self) -> None:
        """check_anthropic() returns False on connection error."""
        service = HealthService()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused"),
        )
        service._client = mock_client

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"}):
            result = await service.check_anthropic()

        assert result is False

    @pytest.mark.asyncio()
    async def test_fails_on_timeout(self) -> None:
        """check_anthropic() returns False on timeout."""
        service = HealthService()
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=TimeoutError("timed out"))
        service._client = mock_client

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test-key"}):
            result = await service.check_anthropic()

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
        _patch_client(service, side_effect=httpx.ConnectError("refused"))

        with (
            patch.object(service, "_yfinance_canary", return_value=False),
            patch.object(service, "check_anthropic", return_value=False),
        ):
            status = await service.check_all()

        assert hasattr(status, "ollama_available")
        assert hasattr(status, "anthropic_available")
        assert hasattr(status, "yfinance_available")
        assert hasattr(status, "sqlite_available")
        assert hasattr(status, "ollama_models")
        assert hasattr(status, "last_check")
        assert status.last_check is not None
