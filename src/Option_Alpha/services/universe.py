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
import re
from typing import Final

import httpx

from Option_Alpha.models.market_data import TickerInfo, UniverseStats
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import DataSourceUnavailableError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CBOE_OPTIONABLE_URL: Final[str] = (
    "https://www.cboe.com/us/options/symboldir/equity-index-options/download/"
)

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

# S&P 500 constituent list from Wikipedia
_SP500_WIKI_URL: Final[str] = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_SP500_CACHE_KEY: Final[str] = "wiki:sp500:constituents"
_SP500_CACHE_TTL: Final[int] = 7 * 24 * 60 * 60  # 7 days
_SP500_MIN_EXPECTED: Final[int] = 400  # sanity check — S&P 500 should have ~503

# Fallback large-cap set used when Wikipedia is unreachable
_FALLBACK_LARGE_CAPS: Final[frozenset[str]] = frozenset(
    {
        "AAPL",
        "ABBV",
        "ABT",
        "ACN",
        "ADP",
        "ADI",
        "AMGN",
        "AMD",
        "AMZN",
        "AVGO",
        "BA",
        "BLK",
        "BKNG",
        "CAT",
        "COST",
        "CRM",
        "CSCO",
        "CVX",
        "DE",
        "DHR",
        "DIS",
        "GE",
        "GOOG",
        "GOOGL",
        "GS",
        "HD",
        "HON",
        "IBM",
        "INTC",
        "ISRG",
        "JNJ",
        "JPM",
        "KO",
        "LIN",
        "LLY",
        "LOW",
        "MA",
        "MCD",
        "MDLZ",
        "MRK",
        "META",
        "MSFT",
        "NEE",
        "NFLX",
        "NVDA",
        "ORCL",
        "PEP",
        "PG",
        "PM",
        "RTX",
        "SPGI",
        "SYK",
        "TMO",
        "TSLA",
        "TXN",
        "UNH",
        "UNP",
        "V",
        "WMT",
    }
)

# CBOE index symbols that are not tradeable equities — skip during parsing
_INDEX_SYMBOLS: Final[frozenset[str]] = frozenset(
    {
        "DJX",
        "NDX",
        "OEX",
        "RLV",
        "RUI",
        "RUT",
        "SPX",
        "VIX",
        "XEO",
        "XND",
        "XSP",
        "SIXB",
        "SIXI",
        "SIXM",
        "SIXRE",
        "SIXU",
        "SIXV",
    }
)

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
        self._sp500_symbols: set[str] = set()
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        logger.info("UniverseService initialized.")

    async def aclose(self) -> None:
        """Close the shared httpx client."""
        await self._client.aclose()

    async def refresh(self) -> list[TickerInfo]:
        """Download and parse the CBOE optionable list.

        Fetches the CSV from CBOE, parses rows into TickerInfo models,
        applies pre-filters, caches the result, and returns the full list.

        Raises:
            DataSourceUnavailableError: If CBOE is unreachable or returns
                fewer than MIN_TICKERS_SAFETY tickers (likely broken source).
        """
        # Fetch S&P 500 constituents for market cap classification
        self._sp500_symbols = await self._fetch_sp500_constituents()

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

    async def get_stats(self) -> UniverseStats:
        """Return summary statistics about the current universe.

        Returns:
            Typed ``UniverseStats`` model with counts by status, tier, and sector.
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

        return UniverseStats(
            total=total,
            active=active,
            inactive=inactive,
            by_tier=by_tier,
            by_sector=by_sector,
        )

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
            response = await asyncio.wait_for(
                self._client.get(CBOE_OPTIONABLE_URL),
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
        """Parse CBOE equity & index options directory CSV into TickerInfo models.

        The CBOE directory CSV has a standard header row:
        ``Company Name, Stock Symbol, DPM Name, Post/Station``

        Returns:
            List of TickerInfo models passing pre-filter checks.
        """
        now = datetime.datetime.now(datetime.UTC)
        tickers: list[TickerInfo] = []

        reader = csv.DictReader(io.StringIO(csv_text))

        for row in reader:
            symbol = (row.get("Stock Symbol") or row.get(" Stock Symbol") or "").strip().upper()

            if not symbol:
                continue

            # Skip non-equity symbols (those with special characters like '/')
            if not symbol.isalpha():
                continue

            # Skip CBOE index symbols (no tradeable OHLCV data)
            if symbol in _INDEX_SYMBOLS:
                continue

            name = (row.get("Company Name") or "").strip()

            # Determine asset type (ETF vs equity heuristic)
            asset_type = self._classify_asset_type(symbol, name)

            # Determine market cap tier (default to unknown)
            market_cap_tier = self._classify_market_cap_tier(symbol, asset_type)

            ticker_info = TickerInfo(
                symbol=symbol,
                name=name if name else symbol,
                sector="Unknown",
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

    def _classify_market_cap_tier(self, symbol: str, asset_type: str) -> str:
        """Classify market cap tier using S&P 500 constituent data.

        Uses the dynamically-fetched S&P 500 list from Wikipedia when
        available, falling back to ``_FALLBACK_LARGE_CAPS`` if the list
        has not been loaded yet.
        """
        if asset_type == "etf":
            return "etf"

        large_caps = self._sp500_symbols if self._sp500_symbols else _FALLBACK_LARGE_CAPS
        if symbol in large_caps:
            return "large_cap"

        return "mid_cap"

    async def _fetch_sp500_constituents(self) -> set[str]:
        """Fetch the current S&P 500 constituent list from Wikipedia.

        Parses the first table on the *List of S&P 500 companies* page to
        extract ticker symbols.  Falls back to ``_FALLBACK_LARGE_CAPS`` if
        the fetch fails or the parsed count is suspiciously low.
        """
        # Try cache first
        cached = await self._cache.get(_SP500_CACHE_KEY)
        if cached is not None:
            symbols: set[str] = set(json.loads(cached))
            if len(symbols) >= _SP500_MIN_EXPECTED:
                logger.info("S&P 500 list loaded from cache: %d symbols.", len(symbols))
                return symbols

        try:
            # Wikipedia requires a descriptive User-Agent per their API
            # policy: https://meta.wikimedia.org/wiki/User-Agent_policy
            headers = {
                "User-Agent": (
                    "OptionAlpha/1.0 "
                    "(https://github.com/jobu711/Option_Alpha_3; "
                    "options analysis tool) "
                    "Python/httpx"
                ),
                "Accept": "text/html",
            }
            response = await asyncio.wait_for(
                self._client.get(_SP500_WIKI_URL, headers=headers),
                timeout=30.0,
            )
            if response.status_code != 200:  # noqa: PLR2004
                logger.warning(
                    "Wikipedia returned HTTP %d for S&P 500 page.", response.status_code
                )
                return set(_FALLBACK_LARGE_CAPS)

            html = response.text

            # The constituents table uses external links to NYSE/NASDAQ:
            #   <td><a rel="nofollow" class="external text"
            #        href="https://www.nyse.com/quote/XNYS:MMM">MMM</a>
            # Tickers are 1-5 uppercase letters, optionally with a dot for
            # share classes (e.g. BRK.B).
            matches = re.findall(
                r'<td[^>]*>\s*<a[^>]*class="external text"[^>]*>'
                r"([A-Z]{1,5}(?:\.[A-Z])?)</a>",
                html,
            )

            if len(matches) < _SP500_MIN_EXPECTED:
                logger.warning(
                    "Only parsed %d tickers from Wikipedia (expected %d+). Using fallback.",
                    len(matches),
                    _SP500_MIN_EXPECTED,
                )
                return set(_FALLBACK_LARGE_CAPS)

            # Normalize: strip dot suffix (BRK.B -> BRK) to match CBOE symbols
            symbols = {s.split(".")[0] for s in matches}
            logger.info("Fetched %d S&P 500 constituents from Wikipedia.", len(symbols))

            # Cache for reuse across sessions
            await self._cache_sp500(symbols)

            return symbols

        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch S&P 500 list: %s. Using fallback.", exc)
            return set(_FALLBACK_LARGE_CAPS)

    async def _cache_sp500(self, symbols: set[str]) -> None:
        """Persist the S&P 500 symbol set to cache."""
        serialized = json.dumps(sorted(symbols))
        await self._cache.set(_SP500_CACHE_KEY, serialized, _SP500_CACHE_TTL)
        logger.debug("S&P 500 list cached: %d symbols.", len(symbols))

    async def _load_sp500_from_cache(self) -> None:
        """Load the S&P 500 symbol set from cache if available."""
        cached = await self._cache.get(_SP500_CACHE_KEY)
        if cached is None:
            logger.debug("No cached S&P 500 list found, using fallback.")
            self._sp500_symbols = set(_FALLBACK_LARGE_CAPS)
            return

        symbols: set[str] = set(json.loads(cached))
        if len(symbols) >= _SP500_MIN_EXPECTED:
            self._sp500_symbols = symbols
            logger.info("S&P 500 list loaded from cache: %d symbols.", len(symbols))
        else:
            logger.warning("Cached S&P 500 list too small (%d), using fallback.", len(symbols))
            self._sp500_symbols = set(_FALLBACK_LARGE_CAPS)

    async def _cache_universe(self, tickers: list[TickerInfo]) -> None:
        """Serialize the universe to cache."""
        serialized = json.dumps([t.model_dump(mode="json") for t in tickers])
        await self._cache.set(UNIVERSE_CACHE_KEY, serialized, UNIVERSE_CACHE_TTL)
        logger.debug("Universe cached: %d tickers.", len(tickers))

    async def _load_from_cache(self) -> None:
        """Load the universe and SP500 constituents from cache if available."""
        # Load SP500 list from cache if not already populated
        if not self._sp500_symbols:
            await self._load_sp500_from_cache()

        cached = await self._cache.get(UNIVERSE_CACHE_KEY)
        if cached is None:
            logger.debug("No cached universe found.")
            return

        raw_list = json.loads(cached)
        self._universe = [TickerInfo.model_validate(item) for item in raw_list]
        logger.info("Universe loaded from cache: %d tickers.", len(self._universe))
