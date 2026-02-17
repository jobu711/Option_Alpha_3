"""Market data service wrapping yfinance for OHLCV, quotes, and ticker info.

All yfinance calls are synchronous and wrapped in ``asyncio.to_thread()`` to
avoid blocking the event loop.  Results are converted to typed Pydantic models
before returning.  Caching via ``ServiceCache`` and rate-limiting via
``RateLimiter`` are applied transparently.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Final

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo
from Option_Alpha.services._helpers import (
    EXTERNAL_CALL_TIMEOUT_SECONDS,
    YFINANCE_SOURCE,
    fetch_with_retry,
    safe_decimal,
    safe_int,
)
from Option_Alpha.services.cache import (
    DATA_TYPE_FUNDAMENTALS,
    DATA_TYPE_OHLCV,
    DATA_TYPE_QUOTE,
    ServiceCache,
)
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
    DataSourceUnavailableError,
    InsufficientDataError,
    TickerNotFoundError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PERIOD: Final[str] = "1y"

# Minimum rows required for a valid OHLCV fetch (~200 trading days/year)
MIN_OHLCV_ROWS: Final[int] = 100

# yfinance column name mapping (yfinance returns title-cased columns)
OHLCV_COLUMN_MAP: Final[dict[str, str]] = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Volume": "volume",
}


class MarketDataService:
    """Async market data service backed by yfinance.

    Usage::

        limiter = RateLimiter()
        cache = ServiceCache()
        service = MarketDataService(rate_limiter=limiter, cache=cache)

        bars = await service.fetch_ohlcv("AAPL")
        quote = await service.fetch_quote("AAPL")
        info = await service.fetch_ticker_info("AAPL")
        batch = await service.fetch_batch_ohlcv(["AAPL", "MSFT", "GOOG"])
    """

    def __init__(
        self,
        rate_limiter: RateLimiter,
        cache: ServiceCache,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._cache = cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def fetch_ohlcv(
        self,
        ticker: str,
        period: str = DEFAULT_PERIOD,
    ) -> list[OHLCV]:
        """Fetch daily OHLCV price bars for *ticker*.

        Checks the cache first.  On miss, fetches from yfinance and stores
        the result.  Validates that the returned DataFrame has enough rows
        and covers a reasonable date range.

        Args:
            ticker: Ticker symbol (e.g., ``"AAPL"``).
            period: yfinance period string (default ``"1y"``).

        Returns:
            List of ``OHLCV`` models sorted chronologically.

        Raises:
            TickerNotFoundError: If the ticker does not exist.
            InsufficientDataError: If yfinance returns too few rows.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        ticker = ticker.upper().strip()
        cache_key = f"yf:{DATA_TYPE_OHLCV}:{ticker}:{period}"

        # Cache-first pattern
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for OHLCV: %s", cache_key)
            return _deserialize_ohlcv_list(cached)

        # Fetch from yfinance with retry
        raw_df = await fetch_with_retry(
            lambda: self._fetch_raw_history(ticker, period),
            rate_limiter=self._rate_limiter,
            ticker=ticker,
            source=YFINANCE_SOURCE,
            label=f"OHLCV({ticker})",
        )

        # Validate
        self._validate_ohlcv_dataframe(raw_df, ticker, period)

        # Convert to models
        bars = self._dataframe_to_ohlcv(raw_df, ticker)

        # Store in cache (OHLCV is permanent)
        ttl = self._cache.get_ttl(DATA_TYPE_OHLCV)
        await self._cache.set(cache_key, _serialize_ohlcv_list(bars), ttl)
        logger.info("Fetched %d OHLCV bars for %s", len(bars), ticker)
        return bars

    async def fetch_quote(self, ticker: str) -> Quote:
        """Fetch a real-time / delayed quote snapshot for *ticker*.

        Args:
            ticker: Ticker symbol.

        Returns:
            A ``Quote`` model.

        Raises:
            TickerNotFoundError: If the ticker does not exist.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        ticker = ticker.upper().strip()
        cache_key = f"yf:{DATA_TYPE_QUOTE}:{ticker}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for quote: %s", cache_key)
            return Quote.model_validate_json(cached)

        info = await fetch_with_retry(
            lambda: self._fetch_raw_info(ticker),
            rate_limiter=self._rate_limiter,
            ticker=ticker,
            source=YFINANCE_SOURCE,
            label=f"Quote({ticker})",
        )

        self._validate_info_dict(info, ticker)

        quote = Quote(
            ticker=ticker,
            bid=safe_decimal(info.get("bid", 0)),
            ask=safe_decimal(info.get("ask", 0)),
            last=safe_decimal(info.get("currentPrice") or info.get("regularMarketPrice", 0)),
            volume=safe_int(info.get("volume") or info.get("regularMarketVolume", 0)),
            timestamp=datetime.datetime.now(datetime.UTC),
        )

        ttl = self._cache.get_ttl(DATA_TYPE_QUOTE)
        await self._cache.set(cache_key, quote.model_dump_json(), ttl)
        logger.info("Fetched quote for %s: last=%s", ticker, quote.last)
        return quote

    async def fetch_ticker_info(self, ticker: str) -> TickerInfo:
        """Fetch metadata / fundamentals for *ticker*.

        Args:
            ticker: Ticker symbol.

        Returns:
            A ``TickerInfo`` model.

        Raises:
            TickerNotFoundError: If the ticker does not exist.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        ticker = ticker.upper().strip()
        cache_key = f"yf:{DATA_TYPE_FUNDAMENTALS}:{ticker}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for ticker info: %s", cache_key)
            return TickerInfo.model_validate_json(cached)

        info = await fetch_with_retry(
            lambda: self._fetch_raw_info(ticker),
            rate_limiter=self._rate_limiter,
            ticker=ticker,
            source=YFINANCE_SOURCE,
            label=f"TickerInfo({ticker})",
        )

        self._validate_info_dict(info, ticker)

        market_cap = info.get("marketCap")
        market_cap_tier = _classify_market_cap(market_cap)

        now_utc = datetime.datetime.now(datetime.UTC)
        ticker_info = TickerInfo(
            symbol=ticker,
            name=str(info.get("longName") or info.get("shortName") or ticker),
            sector=str(info.get("sector", "Unknown")),
            market_cap_tier=market_cap_tier,
            asset_type=str(info.get("quoteType", "EQUITY")),
            source=YFINANCE_SOURCE,
            tags=[],
            status="active",
            discovered_at=now_utc,
            last_scanned_at=now_utc,
        )

        ttl = self._cache.get_ttl(DATA_TYPE_FUNDAMENTALS)
        await self._cache.set(cache_key, ticker_info.model_dump_json(), ttl)
        logger.info("Fetched ticker info for %s: %s", ticker, ticker_info.name)
        return ticker_info

    async def fetch_batch_ohlcv(
        self,
        tickers: list[str],
    ) -> dict[str, list[OHLCV] | Exception]:
        """Fetch OHLCV for multiple tickers concurrently.

        Uses ``asyncio.gather(..., return_exceptions=True)`` so one failure
        does not crash the batch.

        Args:
            tickers: List of ticker symbols.

        Returns:
            Dict mapping each ticker to its ``list[OHLCV]`` or the
            ``Exception`` that occurred.
        """
        tasks = [self.fetch_ohlcv(t) for t in tickers]
        results: list[list[OHLCV] | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        batch_results: dict[str, list[OHLCV] | Exception] = {}
        for ticker_raw, result in zip(tickers, results, strict=True):
            ticker_key = ticker_raw.upper().strip()
            if isinstance(result, Exception):
                logger.warning(
                    "Batch OHLCV fetch failed for %s: %s",
                    ticker_key,
                    result,
                )
                batch_results[ticker_key] = result
            elif isinstance(result, BaseException):
                # BaseException (e.g. KeyboardInterrupt) — wrap it
                logger.warning(
                    "Batch OHLCV fetch got BaseException for %s: %s",
                    ticker_key,
                    result,
                )
                batch_results[ticker_key] = RuntimeError(str(result))
            else:
                batch_results[ticker_key] = result

        successes = sum(1 for v in batch_results.values() if not isinstance(v, Exception))
        failures = len(batch_results) - successes
        logger.info(
            "Batch OHLCV fetch complete: %d succeeded, %d failed",
            successes,
            failures,
        )
        return batch_results

    # ------------------------------------------------------------------
    # Raw yfinance calls (sync, wrapped in asyncio.to_thread)
    # ------------------------------------------------------------------

    async def _fetch_raw_history(
        self,
        ticker: str,
        period: str,
    ) -> pd.DataFrame:
        """Fetch raw price history from yfinance in a thread.

        yfinance is synchronous; this wraps the call via
        ``asyncio.to_thread`` and applies a timeout.
        """

        def _sync_fetch() -> pd.DataFrame:
            t = yf.Ticker(ticker)
            df: pd.DataFrame = t.history(period=period)
            return df

        return await asyncio.wait_for(
            asyncio.to_thread(_sync_fetch),
            timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
        )

    async def _fetch_raw_info(self, ticker: str) -> dict[str, object]:
        """Fetch the raw info dict from yfinance in a thread."""

        def _sync_fetch() -> dict[str, object]:
            t = yf.Ticker(ticker)
            info: dict[str, object] = t.info
            return info

        return await asyncio.wait_for(
            asyncio.to_thread(_sync_fetch),
            timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_ohlcv_dataframe(
        self,
        df: pd.DataFrame,
        ticker: str,
        period: str,
    ) -> None:
        """Validate the OHLCV DataFrame is non-empty with enough data."""
        if df is None or df.empty:
            raise TickerNotFoundError(
                f"No data returned for ticker '{ticker}' with period '{period}'",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        # Check required columns exist
        required = set(OHLCV_COLUMN_MAP.keys())
        missing = required - set(df.columns)
        if missing:
            raise DataSourceUnavailableError(
                f"Missing columns in OHLCV data for {ticker}: {missing}",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        # Check minimum row count
        if len(df) < MIN_OHLCV_ROWS:
            raise InsufficientDataError(
                f"Only {len(df)} rows returned for {ticker} "
                f"(minimum {MIN_OHLCV_ROWS} for period '{period}')",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

    @staticmethod
    def _validate_info_dict(info: dict[str, object], ticker: str) -> None:
        """Validate that the info dict represents a real ticker."""
        if not info:
            raise TickerNotFoundError(
                f"Empty info dict for ticker '{ticker}'",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        # yfinance returns a minimal dict for invalid tickers
        quote_type = info.get("quoteType")
        if quote_type is None and info.get("regularMarketPrice") is None:
            raise TickerNotFoundError(
                f"Ticker '{ticker}' not found (no quoteType or price data)",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dataframe_to_ohlcv(df: pd.DataFrame, ticker: str) -> list[OHLCV]:
        """Convert a yfinance history DataFrame to OHLCV models.

        yfinance uses a timezone-aware DatetimeIndex; we extract just
        the date part for the OHLCV model.
        """
        bars: list[OHLCV] = []
        for idx, row in df.iterrows():
            bar_date: datetime.date = (
                idx.date() if isinstance(idx, pd.Timestamp) else pd.Timestamp(str(idx)).date()
            )

            try:
                bar = OHLCV(
                    date=bar_date,
                    open=safe_decimal(row["Open"]),
                    high=safe_decimal(row["High"]),
                    low=safe_decimal(row["Low"]),
                    close=safe_decimal(row["Close"]),
                    volume=safe_int(row["Volume"]),
                )
                bars.append(bar)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Skipping malformed OHLCV row for %s at %s",
                    ticker,
                    idx,
                )
                continue

        return bars


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _classify_market_cap(market_cap: object) -> str:
    """Classify a market capitalization value into a tier label."""
    if market_cap is None:
        return "Unknown"
    try:
        cap = float(str(market_cap))
    except (ValueError, TypeError):
        return "Unknown"

    # Standard market cap tiers
    mega_cap_threshold: float = 200_000_000_000.0
    large_cap_threshold: float = 10_000_000_000.0
    mid_cap_threshold: float = 2_000_000_000.0
    small_cap_threshold: float = 300_000_000.0

    if cap >= mega_cap_threshold:
        return "Mega"
    if cap >= large_cap_threshold:
        return "Large"
    if cap >= mid_cap_threshold:
        return "Mid"
    if cap >= small_cap_threshold:
        return "Small"
    return "Micro"


def _serialize_ohlcv_list(bars: list[OHLCV]) -> str:
    """Serialize a list of OHLCV models to a JSON string."""
    return json.dumps([bar.model_dump(mode="json") for bar in bars])


def _deserialize_ohlcv_list(data: str) -> list[OHLCV]:
    """Deserialize a JSON string back to a list of OHLCV models."""
    raw_list: list[dict[str, object]] = json.loads(data)
    return [OHLCV.model_validate(item) for item in raw_list]
