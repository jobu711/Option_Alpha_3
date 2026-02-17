"""Tests for FredService: risk-free rate fetching with caching and fallback.

All httpx calls are mocked. No real API calls.

Covers:
- get_risk_free_rate() returns correct decimal from FRED response
- Fallback to 5% when FRED is unavailable
- Fallback when no API key configured
- Cache integration: second call returns cached rate
- Handles FRED's "." missing data convention
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.fred import (
    FRED_CACHE_KEY,
    RISK_FREE_RATE_FALLBACK,
    FredService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def cache() -> ServiceCache:
    """Memory-only cache for tests."""
    return ServiceCache(database=None)


@pytest.fixture()
def fred_service(cache: ServiceCache) -> FredService:
    """FredService with a configured API key."""
    return FredService(cache=cache, api_key="test_api_key_12345")


@pytest.fixture()
def fred_service_no_key(cache: ServiceCache) -> FredService:
    """FredService without an API key."""
    return FredService(cache=cache, api_key=None)


def _mock_fred_response(
    value: str = "4.25",
    status_code: int = 200,
) -> MagicMock:
    """Create a mock httpx response with FRED JSON format."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {
        "observations": [
            {"date": "2025-01-15", "value": value},
        ],
    }
    return response


# ---------------------------------------------------------------------------
# get_risk_free_rate tests
# ---------------------------------------------------------------------------


class TestGetRiskFreeRate:
    """Tests for get_risk_free_rate()."""

    @pytest.mark.asyncio()
    async def test_returns_correct_decimal_from_fred(self, fred_service: FredService) -> None:
        """Converts FRED's percentage value (4.25) to decimal (0.0425)."""
        mock_response = _mock_fred_response(value="4.25")

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(0.0425, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_fallback_when_fred_unavailable(self, fred_service: FredService) -> None:
        """Returns fallback rate (5%) when FRED returns an error."""
        mock_response = _mock_fred_response(status_code=500)

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(RISK_FREE_RATE_FALLBACK, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_fallback_when_no_api_key(self, fred_service_no_key: FredService) -> None:
        """Returns fallback rate when no API key is configured."""
        rate = await fred_service_no_key.get_risk_free_rate()
        assert rate == pytest.approx(RISK_FREE_RATE_FALLBACK, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_cache_hit_returns_cached_rate(
        self,
        fred_service: FredService,
        cache: ServiceCache,
    ) -> None:
        """Second call returns the cached rate without re-fetching."""
        # Pre-populate cache
        await cache.set(FRED_CACHE_KEY, "0.0425", 86400)

        rate = await fred_service.get_risk_free_rate()
        assert rate == pytest.approx(0.0425, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_caches_result_after_fetch(
        self,
        fred_service: FredService,
        cache: ServiceCache,
    ) -> None:
        """Fetched rate is cached for subsequent calls."""
        mock_response = _mock_fred_response(value="3.80")

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            await fred_service.get_risk_free_rate()

        # Verify it was cached
        cached = await cache.get(FRED_CACHE_KEY)
        assert cached is not None
        assert float(cached) == pytest.approx(0.038, rel=1e-4)


class TestFREDMissingData:
    """Tests for FRED's '.' missing data convention."""

    @pytest.mark.asyncio()
    async def test_handles_dot_missing_data(self, fred_service: FredService) -> None:
        """FRED uses '.' for missing data; service skips to next observation."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "observations": [
                {"date": "2025-01-15", "value": "."},
                {"date": "2025-01-14", "value": "."},
                {"date": "2025-01-13", "value": "4.10"},
            ],
        }

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(0.041, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_all_missing_data_raises_and_falls_back(self, fred_service: FredService) -> None:
        """When all observations are '.', falls back to default rate."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "observations": [
                {"date": "2025-01-15", "value": "."},
                {"date": "2025-01-14", "value": "."},
            ],
        }

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        # Should fall back because _fetch_from_fred raises DataSourceUnavailableError
        assert rate == pytest.approx(RISK_FREE_RATE_FALLBACK, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_handles_empty_value_string(self, fred_service: FredService) -> None:
        """Empty value strings are treated as missing."""
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "observations": [
                {"date": "2025-01-15", "value": ""},
                {"date": "2025-01-14", "value": "3.90"},
            ],
        }

        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(0.039, rel=1e-4)


class TestFREDNetworkErrors:
    """Tests for network error handling."""

    @pytest.mark.asyncio()
    async def test_httpx_error_falls_back(self, fred_service: FredService) -> None:
        """httpx.HTTPError falls back to default rate."""
        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(RISK_FREE_RATE_FALLBACK, rel=1e-4)

    @pytest.mark.asyncio()
    async def test_timeout_falls_back(self, fred_service: FredService) -> None:
        """Timeout falls back to default rate."""
        with patch("Option_Alpha.services.fred.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=TimeoutError("timed out"))
            mock_client_cls.return_value = mock_client

            rate = await fred_service.get_risk_free_rate()

        assert rate == pytest.approx(RISK_FREE_RATE_FALLBACK, rel=1e-4)


class TestConstants:
    """Verify FRED service constants."""

    def test_fallback_rate_is_five_percent(self) -> None:
        """Fallback risk-free rate is 5%."""
        assert pytest.approx(0.05, rel=1e-4) == RISK_FREE_RATE_FALLBACK
