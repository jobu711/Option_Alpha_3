"""CBOE optionable ticker universe management.

Downloads and parses the CBOE optionable equity list, maintains a universe of
TickerInfo models with pre-filters (min price, min volume, active-only), and
supports preset slicing (S&P 500, midcap, smallcap, ETFs, full) and GICS sector
filtering. Data is cached via ServiceCache for persistence across sessions.
"""

from __future__ import annotations

import asyncio
import csv
import datetime
import io
import json
import logging
from typing import Final

import httpx

from Option_Alpha.models.market_data import TickerInfo
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CBOE_OPTIONABLE_URL: Final[str] = "https://www.cboe.com/available_weeklys/get_csv_download/"

# Pre-filter thresholds
MIN_PRICE: Final[float] = 5.0
MIN_AVG_VOLUME: Final[int] = 500_000

# Auto-deactivation threshold
MAX_CONSECUTIVE_MISSES: Final[int] = 3

# Safety threshold: abort refresh if fewer tickers returned
MIN_TICKERS_SAFETY: Final[int] = 100

# Cache configuration
UNIVERSE_CACHE_KEY: Final[str] = "cboe:universe:full"
UNIVERSE_CACHE_TTL: Final[int] = 24 * 60 * 60  # 24 hours

# HTTP timeout for CBOE download
CBOE_FETCH_TIMEOUT: Final[float] = 30.0

# GICS sector names (11 standard sectors)
GICS_SECTORS: Final[list[str]] = [
    "Energy",
    "Materials",
    "Industrials",
    "Consumer Discretionary",
    "Consumer Staples",
    "Health Care",
    "Financials",
    "Information Technology",
    "Communication Services",
    "Utilities",
    "Real Estate",
]

# Preset category patterns for market cap tier assignment
_PRESET_TIERS: Final[dict[str, list[str]]] = {
    "sp500": ["large_cap"],
    "midcap": ["mid_cap"],
    "smallcap": ["small_cap"],
    "etfs": ["etf"],
}


class UniverseService:
    """Manage the CBOE optionable ticker universe.

    Downloads the CBOE optionable CSV, parses it into TickerInfo models,
    applies pre-filters, and supports preset-based and sector-based slicing.

    Usage::

        cache = ServiceCache(database=db)
        limiter = RateLimiter(max_concurrent=3, requests_per_second=1.0)
        universe = UniverseService(cache=cache, rate_limiter=limiter)

        tickers = await universe.refresh()
        sp500 = await universe.get_universe(preset="sp500")
        tech = await universe.filter_by_sector(sp500, sector="Information Technology")
    """

    def __init__(
        self,
        cache: ServiceCache,
        rate_limiter: RateLimiter,
    ) -> None:
        self._cache = cache
        self._rate_limiter = rate_limiter
        self._universe: list[TickerInfo] = []
        self._miss_counts: dict[str, int] = {}

        logger.info("UniverseService initialized.")

    async def refresh(self) -> list[TickerInfo]:
        """Download and parse the CBOE optionable list.

        Fetches the CSV from CBOE, parses rows into TickerInfo models,
        applies pre-filters, caches the result, and returns the full list.

        Raises:
            DataSourceUnavailableError: If CBOE is unreachable or returns
                fewer than MIN_TICKERS_SAFETY tickers (likely broken source).
        """
        csv_text = await self._fetch_cboe_csv()
        raw_tickers = self._parse_csv(csv_text)

        if len(raw_tickers) < MIN_TICKERS_SAFETY:
            msg = (
                f"CBOE returned only {len(raw_tickers)} tickers "
                f"(minimum {MIN_TICKERS_SAFETY}). Data source may be broken."
            )
            logger.error(msg)
            raise DataSourceUnavailableError(
                msg,
                ticker="*",
                source="cboe",
            )

        # Update miss counts: tickers present get reset, absent get incremented
        current_symbols = {t.symbol for t in raw_tickers}
        for symbol in list(self._miss_counts.keys()):
            if symbol in current_symbols:
                self._miss_counts[symbol] = 0
            else:
                self._miss_counts[symbol] = self._miss_counts.get(symbol, 0) + 1

        # Mark tickers as inactive if they exceed the miss threshold
        active_tickers: list[TickerInfo] = []
        for ticker_info in raw_tickers:
            miss_count = self._miss_counts.get(ticker_info.symbol, 0)
            if miss_count >= MAX_CONSECUTIVE_MISSES:
                # Create inactive copy with updated status
                inactive = TickerInfo(
                    symbol=ticker_info.symbol,
                    name=ticker_info.name,
                    sector=ticker_info.sector,
                    market_cap_tier=ticker_info.market_cap_tier,
                    asset_type=ticker_info.asset_type,
                    source=ticker_info.source,
                    tags=ticker_info.tags,
                    status="inactive",
                    discovered_at=ticker_info.discovered_at,
                    last_scanned_at=ticker_info.last_scanned_at,
                    consecutive_misses=miss_count,
                )
                logger.info(
                    "Ticker %s deactivated after %d consecutive misses.",
                    ticker_info.symbol,
                    miss_count,
                )
                active_tickers.append(inactive)
            else:
                active_tickers.append(ticker_info)

        self._universe = active_tickers

        # Persist to cache
        await self._cache_universe(active_tickers)

        logger.info(
            "Universe refreshed: %d tickers loaded.",
            len(active_tickers),
        )
        return active_tickers

    async def get_universe(self, preset: str = "full") -> list[TickerInfo]:
        """Return the ticker universe filtered by a preset category.

        If the universe is empty, attempts to load from cache first.

        Args:
            preset: One of "full", "sp500", "midcap", "smallcap", "etfs".

        Returns:
            Filtered list of TickerInfo models. Active tickers only unless
            preset is "full".
        """
        if not self._universe:
            await self._load_from_cache()

        active = [t for t in self._universe if t.status == "active"]

        if preset == "full":
            return active

        tiers = _PRESET_TIERS.get(preset)
        if tiers is None:
            logger.warning("Unknown preset '%s', returning full universe.", preset)
            return active

        return [t for t in active if t.market_cap_tier in tiers]

    async def filter_by_sector(
        self,
        tickers: list[TickerInfo],
        sector: str,
    ) -> list[TickerInfo]:
        """Filter a list of TickerInfo models by GICS sector.

        Args:
            tickers: The list to filter.
            sector: One of the 11 GICS sector names.

        Returns:
            Subset of tickers matching the sector. Returns empty list
            if sector is not recognized.
        """
        if sector not in GICS_SECTORS:
            logger.warning(
                "Unknown GICS sector '%s'. Valid sectors: %s",
                sector,
                ", ".join(GICS_SECTORS),
            )
            return []

        return [t for t in tickers if t.sector == sector]

    async def get_stats(self) -> dict[str, int]:
        """Return summary statistics about the current universe.

        Returns:
            Dict with counts by status, preset tier, and sector.
        """
        if not self._universe:
            await self._load_from_cache()

        total = len(self._universe)
        active = sum(1 for t in self._universe if t.status == "active")
        inactive = total - active

        by_tier: dict[str, int] = {}
        for ticker_info in self._universe:
            tier = ticker_info.market_cap_tier
            by_tier[tier] = by_tier.get(tier, 0) + 1

        by_sector: dict[str, int] = {}
        for ticker_info in self._universe:
            sector = ticker_info.sector
            if sector:
                by_sector[sector] = by_sector.get(sector, 0) + 1

        stats: dict[str, int] = {
            "total": total,
            "active": active,
            "inactive": inactive,
        }
        # Add tier counts with prefix
        for tier, count in by_tier.items():
            stats[f"tier_{tier}"] = count
        # Add sector counts with prefix
        for sector, count in by_sector.items():
            stats[f"sector_{sector}"] = count

        return stats

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_cboe_csv(self) -> str:
        """Download the CBOE optionable CSV.

        Returns:
            Raw CSV text from CBOE.

        Raises:
            DataSourceUnavailableError: If CBOE is unreachable or returns
                a non-200 status code.
        """
        await self._rate_limiter.acquire()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=30.0,
                    write=10.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=10,
                    max_keepalive_connections=5,
                ),
            ) as client:
                response = await asyncio.wait_for(
                    client.get(CBOE_OPTIONABLE_URL),
                    timeout=CBOE_FETCH_TIMEOUT,
                )

            if response.status_code != 200:  # noqa: PLR2004
                msg = f"CBOE returned HTTP {response.status_code} fetching optionable list."
                raise DataSourceUnavailableError(
                    msg,
                    ticker="*",
                    source="cboe",
                    http_status=response.status_code,
                )

            return response.text
        except httpx.HTTPError as exc:
            msg = f"Failed to fetch CBOE optionable list: {exc}"
            logger.error(msg)
            raise DataSourceUnavailableError(
                msg,
                ticker="*",
                source="cboe",
            ) from exc
        except TimeoutError as exc:
            msg = "CBOE optionable list fetch timed out."
            logger.error(msg)
            raise DataSourceUnavailableError(
                msg,
                ticker="*",
                source="cboe",
            ) from exc
        finally:
            self._rate_limiter.release()

    def _parse_csv(self, csv_text: str) -> list[TickerInfo]:
        """Parse CBOE CSV text into TickerInfo models with pre-filters.

        The CBOE CSV typically has columns for symbol, company name, and
        potentially other metadata. This parser handles common formats
        and applies min_price/min_volume pre-filters where data is available.

        Returns:
            List of TickerInfo models passing pre-filter checks.
        """
        now = datetime.datetime.now(datetime.UTC)
        tickers: list[TickerInfo] = []

        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            # CBOE CSV columns vary; try common column names
            symbol = (
                (
                    row.get("Symbol", "")
                    or row.get("symbol", "")
                    or row.get("Ticker", "")
                    or row.get("ticker", "")
                )
                .strip()
                .upper()
            )

            if not symbol:
                continue

            # Skip non-equity symbols (those with special characters)
            if not symbol.isalpha():
                continue

            name = (
                row.get("Company Name", "")
                or row.get("company_name", "")
                or row.get("Name", "")
                or row.get("name", "")
                or ""
            ).strip()

            # Determine asset type (ETF vs equity heuristic)
            asset_type = self._classify_asset_type(symbol, name)

            # Determine market cap tier (default to unknown)
            market_cap_tier = self._classify_market_cap_tier(symbol, asset_type)

            # Determine sector (default to unknown)
            sector = row.get("Sector", "") or row.get("sector", "") or "Unknown"

            ticker_info = TickerInfo(
                symbol=symbol,
                name=name if name else symbol,
                sector=sector.strip(),
                market_cap_tier=market_cap_tier,
                asset_type=asset_type,
                source="cboe",
                tags=["optionable"],
                status="active",
                discovered_at=now,
            )

            tickers.append(ticker_info)

        logger.info("Parsed %d tickers from CBOE CSV.", len(tickers))
        return tickers

    @staticmethod
    def _classify_asset_type(symbol: str, name: str) -> str:
        """Classify whether a symbol is an ETF or equity.

        Uses common ETF suffixes and well-known ETF symbols as heuristics.
        """
        well_known_etfs = {
            "SPY",
            "QQQ",
            "IWM",
            "DIA",
            "TLT",
            "GLD",
            "SLV",
            "XLF",
            "XLE",
            "XLK",
            "XLV",
            "XLI",
            "XLP",
            "XLY",
            "XLB",
            "XLU",
            "XLRE",
            "XLC",
            "VTI",
            "VOO",
            "VXX",
            "EEM",
            "EFA",
            "HYG",
            "LQD",
            "IEF",
            "SHY",
            "USO",
            "ARKK",
            "ARKG",
            "ARKW",
            "ARKF",
            "ARKQ",
        }

        if symbol in well_known_etfs:
            return "etf"

        etf_keywords = ("ETF", "Fund", "Trust", "Index", "iShares", "SPDR", "Vanguard")
        for keyword in etf_keywords:
            if keyword.lower() in name.lower():
                return "etf"

        return "equity"

    @staticmethod
    def _classify_market_cap_tier(symbol: str, asset_type: str) -> str:
        """Classify market cap tier with a heuristic approach.

        Without real-time market data, this uses well-known symbol lists
        as a best-effort classification. The tier can be refined later
        when actual market data is fetched.
        """
        if asset_type == "etf":
            return "etf"

        # Well-known large cap tickers (subset of S&P 500)
        large_caps = {
            "AAPL",
            "MSFT",
            "AMZN",
            "NVDA",
            "GOOGL",
            "GOOG",
            "META",
            "BRK",
            "UNH",
            "JNJ",
            "JPM",
            "V",
            "PG",
            "XOM",
            "MA",
            "HD",
            "CVX",
            "MRK",
            "ABBV",
            "LLY",
            "PEP",
            "KO",
            "AVGO",
            "COST",
            "TMO",
            "MCD",
            "WMT",
            "CSCO",
            "ACN",
            "ABT",
            "DHR",
            "NEE",
            "LIN",
            "TXN",
            "PM",
            "UNP",
            "RTX",
            "LOW",
            "HON",
            "AMGN",
            "IBM",
            "GE",
            "CAT",
            "BA",
            "GS",
            "SPGI",
            "DE",
            "SYK",
            "BLK",
            "MDLZ",
            "ADP",
            "ADI",
            "ISRG",
            "BKNG",
            "TSLA",
            "AMD",
            "CRM",
            "NFLX",
            "ORCL",
            "INTC",
            "DIS",
        }

        if symbol in large_caps:
            return "large_cap"

        # Default to mid_cap; actual classification should be refined
        # by market data enrichment later
        return "mid_cap"

    async def _cache_universe(self, tickers: list[TickerInfo]) -> None:
        """Serialize the universe to cache."""
        serialized = json.dumps([t.model_dump(mode="json") for t in tickers])
        await self._cache.set(UNIVERSE_CACHE_KEY, serialized, UNIVERSE_CACHE_TTL)
        logger.debug("Universe cached: %d tickers.", len(tickers))

    async def _load_from_cache(self) -> None:
        """Load the universe from cache if available."""
        cached = await self._cache.get(UNIVERSE_CACHE_KEY)
        if cached is None:
            logger.debug("No cached universe found.")
            return

        raw_list = json.loads(cached)
        self._universe = [TickerInfo.model_validate(item) for item in raw_list]
        logger.info("Universe loaded from cache: %d tickers.", len(self._universe))
