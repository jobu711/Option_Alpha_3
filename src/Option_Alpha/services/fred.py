"""FRED risk-free rate fetching service.

Fetches the DGS10 (10-year Treasury constant maturity yield) from the
Federal Reserve Economic Data (FRED) API. Falls back to a configurable
default rate when FRED is unavailable. Results are cached for 24 hours
via ServiceCache.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Final

import httpx

from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.utils.exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRED_API_BASE_URL: Final[str] = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES_ID: Final[str] = "DGS10"
RISK_FREE_RATE_FALLBACK: Final[float] = 0.05

# Cache configuration
FRED_CACHE_KEY: Final[str] = "fred:rate:DGS10"
FRED_CACHE_TTL: Final[int] = 24 * 60 * 60  # 24 hours

# HTTP timeout for FRED API
FRED_FETCH_TIMEOUT: Final[float] = 10.0

# Number of recent observations to request (to handle missing data days)
FRED_OBSERVATION_LIMIT: Final[int] = 5


class FredService:
    """Fetch the risk-free rate from the FRED API.

    The 10-year Treasury yield (DGS10) is used as a proxy for the risk-free
    rate in options pricing models. This service fetches the latest value,
    caches it for 24 hours, and falls back to a default rate if FRED is
    unavailable.

    Usage::

        cache = ServiceCache(database=db)
        fred = FredService(cache=cache, api_key="your_fred_api_key")
        rate = await fred.get_risk_free_rate()
        # Returns e.g. 0.045 for 4.5%
    """

    def __init__(
        self,
        cache: ServiceCache,
        api_key: str | None = None,
    ) -> None:
        self._cache = cache
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        logger.info(
            "FredService initialized: api_key=%s",
            "configured" if api_key else "not configured",
        )

    async def aclose(self) -> None:
        """Close the shared httpx client."""
        await self._client.aclose()

    async def get_risk_free_rate(self) -> float:
        """Return the current risk-free rate as a decimal (e.g. 0.045 for 4.5%).

        Checks cache first, then fetches from FRED. Falls back to
        RISK_FREE_RATE_FALLBACK if FRED is unavailable or the API key
        is not configured.

        Returns:
            The 10-year Treasury yield as a decimal fraction.
        """
        # Check cache first
        cached = await self._cache.get(FRED_CACHE_KEY)
        if cached is not None:
            rate = float(cached)
            logger.debug("Risk-free rate from cache: %.4f", rate)
            return rate

        # Attempt to fetch from FRED
        if self._api_key is None:
            logger.warning(
                "FRED API key not configured. Using fallback rate: %.4f",
                RISK_FREE_RATE_FALLBACK,
            )
            return RISK_FREE_RATE_FALLBACK

        try:
            rate = await self._fetch_from_fred()
            # Cache the result
            await self._cache.set(FRED_CACHE_KEY, str(rate), FRED_CACHE_TTL)
            logger.info("Risk-free rate fetched from FRED: %.4f", rate)
            return rate
        except (DataSourceUnavailableError, TimeoutError, httpx.HTTPError) as exc:
            logger.warning(
                "FRED unavailable (%s). Using fallback rate: %.4f",
                exc,
                RISK_FREE_RATE_FALLBACK,
            )
            return RISK_FREE_RATE_FALLBACK

    async def _fetch_from_fred(self) -> float:
        """Fetch the latest DGS10 observation from FRED.

        Returns:
            The yield as a decimal (e.g. 0.045 for 4.5%).

        Raises:
            DataSourceUnavailableError: If FRED returns an error or no
                valid observations are found.
        """
        params: dict[str, str] = {
            "series_id": FRED_SERIES_ID,
            "api_key": self._api_key or "",
            "file_type": "json",
            "sort_order": "desc",
            "limit": str(FRED_OBSERVATION_LIMIT),
        }

        try:
            response = await asyncio.wait_for(
                self._client.get(FRED_API_BASE_URL, params=params),
                timeout=FRED_FETCH_TIMEOUT,
            )
        except TimeoutError as exc:
            msg = "FRED API request timed out."
            logger.error(msg)
            raise DataSourceUnavailableError(
                msg,
                ticker="DGS10",
                source="fred",
            ) from exc

        if response.status_code != 200:  # noqa: PLR2004
            msg = f"FRED returned HTTP {response.status_code}."
            raise DataSourceUnavailableError(
                msg,
                ticker="DGS10",
                source="fred",
                http_status=response.status_code,
            )

        data = response.json()
        observations = data.get("observations", [])

        # Find the most recent non-missing observation
        for obs in observations:
            value_str = obs.get("value", ".")
            if value_str == "." or not value_str:
                # FRED uses "." for missing data
                continue
            try:
                yield_percent = float(value_str)
            except (ValueError, TypeError):
                continue

            # FRED returns the yield as a percentage (e.g. 4.5 for 4.5%)
            # Convert to decimal form (0.045)
            rate = yield_percent / 100.0
            return rate

        msg = "No valid DGS10 observations found in FRED response."
        raise DataSourceUnavailableError(
            msg,
            ticker="DGS10",
            source="fred",
        )
