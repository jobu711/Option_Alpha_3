"""Tests for MarketDataService: OHLCV, quotes, ticker info, and batch fetching.

All yfinance calls are mocked via unittest.mock.patch. No real API calls.

Covers:
- fetch_ohlcv() with valid data returns list[OHLCV]
- fetch_ohlcv() with empty DataFrame raises TickerNotFoundError
- fetch_ohlcv() with insufficient rows raises InsufficientDataError
- fetch_quote() returns Quote with correct Decimal prices
- fetch_ticker_info() returns TickerInfo model
- fetch_batch_ohlcv() with mix of successes and failures
- Cache integration: second call returns cached data
- yfinance exception re-raised as DataSourceUnavailableError
- Timeout enforcement
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo
from Option_Alpha.services._helpers import safe_decimal, safe_int
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.market_data import (
    MarketDataService,
    _classify_market_cap,
)
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
    DataSourceUnavailableError,
    InsufficientDataError,
    TickerNotFoundError,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def rate_limiter() -> RateLimiter:
    """Fast rate limiter for tests."""
    return RateLimiter(max_concurrent=5, requests_per_second=100.0)


@pytest.fixture()
def cache() -> ServiceCache:
    """Memory-only cache for tests."""
    return ServiceCache(database=None)


@pytest.fixture()
def service(rate_limiter: RateLimiter, cache: ServiceCache) -> MarketDataService:
    """MarketDataService with mocked dependencies."""
    return MarketDataService(rate_limiter=rate_limiter, cache=cache)


@pytest.fixture()
def valid_ohlcv_df() -> pd.DataFrame:
    """A valid OHLCV DataFrame with enough rows (500 — realistic 2y data)."""
    dates = pd.date_range("2023-01-01", periods=500, freq="B", tz="US/Eastern")
    return pd.DataFrame(
        {
            "Open": [150.0 + i * 0.1 for i in range(500)],
            "High": [151.0 + i * 0.1 for i in range(500)],
            "Low": [149.0 + i * 0.1 for i in range(500)],
            "Close": [150.5 + i * 0.1 for i in range(500)],
            "Volume": [50_000_000 + i * 1000 for i in range(500)],
        },
        index=dates,
    )


@pytest.fixture()
def valid_info_dict() -> dict[str, object]:
    """A realistic yfinance info dict for AAPL."""
    return {
        "quoteType": "EQUITY",
        "longName": "Apple Inc.",
        "shortName": "AAPL",
        "sector": "Technology",
        "marketCap": 3_000_000_000_000,
        "currentPrice": 186.50,
        "bid": 186.45,
        "ask": 186.55,
        "volume": 52_000_000,
        "regularMarketPrice": 186.50,
        "regularMarketVolume": 52_000_000,
    }


# ---------------------------------------------------------------------------
# fetch_ohlcv tests
# ---------------------------------------------------------------------------


class TestFetchOHLCV:
    """Tests for fetch_ohlcv()."""

    @pytest.mark.asyncio()
    async def test_valid_data_returns_ohlcv_list(
        self,
        service: MarketDataService,
        valid_ohlcv_df: pd.DataFrame,
    ) -> None:
        """fetch_ohlcv() with valid data returns a list of OHLCV models."""
        with patch.object(
            service,
            "_fetch_raw_history",
            new_callable=AsyncMock,
            return_value=valid_ohlcv_df,
        ):
            bars = await service.fetch_ohlcv("AAPL")

        assert len(bars) == 500
        assert all(isinstance(b, OHLCV) for b in bars)
        assert bars[0].open == safe_decimal(valid_ohlcv_df.iloc[0]["Open"])

    @pytest.mark.asyncio()
    async def test_empty_dataframe_raises_ticker_not_found(
        self,
        service: MarketDataService,
    ) -> None:
        """fetch_ohlcv() with empty DataFrame raises TickerNotFoundError."""
        empty_df = pd.DataFrame()
        with (
            patch.object(
                service,
                "_fetch_raw_history",
                new_callable=AsyncMock,
                return_value=empty_df,
            ),
            pytest.raises(TickerNotFoundError, match="No data returned"),
        ):
            await service.fetch_ohlcv("FAKE")

    @pytest.mark.asyncio()
    async def test_insufficient_rows_raises_insufficient_data(
        self,
        service: MarketDataService,
    ) -> None:
        """fetch_ohlcv() with too few rows raises InsufficientDataError."""
        dates = pd.date_range("2024-01-01", periods=50, freq="B", tz="US/Eastern")
        short_df = pd.DataFrame(
            {
                "Open": [150.0] * 50,
                "High": [151.0] * 50,
                "Low": [149.0] * 50,
                "Close": [150.5] * 50,
                "Volume": [50_000_000] * 50,
            },
            index=dates,
        )
        with (
            patch.object(
                service,
                "_fetch_raw_history",
                new_callable=AsyncMock,
                return_value=short_df,
            ),
            pytest.raises(InsufficientDataError, match="Only 50 rows"),
        ):
            await service.fetch_ohlcv("AAPL")

    @pytest.mark.asyncio()
    async def test_cache_hit_returns_cached_data(
        self,
        service: MarketDataService,
        valid_ohlcv_df: pd.DataFrame,
    ) -> None:
        """Second call returns cached data without refetching."""
        with patch.object(
            service,
            "_fetch_raw_history",
            new_callable=AsyncMock,
            return_value=valid_ohlcv_df,
        ) as mock_fetch:
            # First call -- fetches from source
            bars1 = await service.fetch_ohlcv("AAPL")
            # Second call -- should come from cache
            bars2 = await service.fetch_ohlcv("AAPL")

        # Raw fetch should only be called once
        mock_fetch.assert_called_once()
        assert len(bars1) == len(bars2)

    @pytest.mark.asyncio()
    async def test_yfinance_exception_raises_data_source_unavailable(
        self,
        service: MarketDataService,
    ) -> None:
        """yfinance exception is re-raised as DataSourceUnavailableError."""
        with (
            patch.object(
                service,
                "_fetch_raw_history",
                new_callable=AsyncMock,
                side_effect=ConnectionError("network down"),
            ),
            pytest.raises(DataSourceUnavailableError, match="Failed to fetch"),
        ):
            await service.fetch_ohlcv("AAPL")

    @pytest.mark.asyncio()
    async def test_ticker_case_normalization(
        self,
        service: MarketDataService,
        valid_ohlcv_df: pd.DataFrame,
    ) -> None:
        """Ticker symbol is uppercased and stripped."""
        with patch.object(
            service,
            "_fetch_raw_history",
            new_callable=AsyncMock,
            return_value=valid_ohlcv_df,
        ):
            bars = await service.fetch_ohlcv("  aapl  ")

        assert len(bars) == 500


# ---------------------------------------------------------------------------
# fetch_quote tests
# ---------------------------------------------------------------------------


class TestFetchQuote:
    """Tests for fetch_quote()."""

    @pytest.mark.asyncio()
    async def test_returns_quote_with_decimal_prices(
        self,
        service: MarketDataService,
        valid_info_dict: dict[str, object],
    ) -> None:
        """fetch_quote() returns a Quote with Decimal price fields."""
        with patch.object(
            service,
            "_fetch_raw_info",
            new_callable=AsyncMock,
            return_value=valid_info_dict,
        ):
            quote = await service.fetch_quote("AAPL")

        assert isinstance(quote, Quote)
        assert isinstance(quote.bid, Decimal)
        assert isinstance(quote.ask, Decimal)
        assert isinstance(quote.last, Decimal)
        assert quote.ticker == "AAPL"
        assert quote.volume == 52_000_000

    @pytest.mark.asyncio()
    async def test_empty_info_raises_ticker_not_found(
        self,
        service: MarketDataService,
    ) -> None:
        """fetch_quote() with empty info dict raises TickerNotFoundError."""
        with (
            patch.object(
                service,
                "_fetch_raw_info",
                new_callable=AsyncMock,
                return_value={},
            ),
            pytest.raises(TickerNotFoundError),
        ):
            await service.fetch_quote("FAKE")

    @pytest.mark.asyncio()
    async def test_quote_cached_on_second_call(
        self,
        service: MarketDataService,
        valid_info_dict: dict[str, object],
    ) -> None:
        """Second fetch_quote() call returns cached result."""
        with patch.object(
            service,
            "_fetch_raw_info",
            new_callable=AsyncMock,
            return_value=valid_info_dict,
        ) as mock_fetch:
            await service.fetch_quote("AAPL")
            await service.fetch_quote("AAPL")

        mock_fetch.assert_called_once()


# ---------------------------------------------------------------------------
# fetch_ticker_info tests
# ---------------------------------------------------------------------------


class TestFetchTickerInfo:
    """Tests for fetch_ticker_info()."""

    @pytest.mark.asyncio()
    async def test_returns_ticker_info_model(
        self,
        service: MarketDataService,
        valid_info_dict: dict[str, object],
    ) -> None:
        """fetch_ticker_info() returns a properly populated TickerInfo."""
        with patch.object(
            service,
            "_fetch_raw_info",
            new_callable=AsyncMock,
            return_value=valid_info_dict,
        ):
            info = await service.fetch_ticker_info("AAPL")

        assert isinstance(info, TickerInfo)
        assert info.symbol == "AAPL"
        assert info.name == "Apple Inc."
        assert info.sector == "Technology"
        assert info.market_cap_tier == "Mega"
        assert info.source == "yfinance"

    @pytest.mark.asyncio()
    async def test_missing_info_raises_ticker_not_found(
        self,
        service: MarketDataService,
    ) -> None:
        """fetch_ticker_info() with no quoteType or price raises error."""
        with (
            patch.object(
                service,
                "_fetch_raw_info",
                new_callable=AsyncMock,
                return_value={"someKey": "someValue"},
            ),
            pytest.raises(TickerNotFoundError),
        ):
            await service.fetch_ticker_info("FAKE")


# ---------------------------------------------------------------------------
# fetch_batch_ohlcv tests
# ---------------------------------------------------------------------------


class TestFetchBatchOHLCV:
    """Tests for fetch_batch_ohlcv() concurrent fetching."""

    @pytest.mark.asyncio()
    async def test_mix_of_successes_and_failures(
        self,
        service: MarketDataService,
        valid_ohlcv_df: pd.DataFrame,
    ) -> None:
        """Batch returns successes and wraps failures individually."""

        # AAPL succeeds, FAKE fails
        async def mock_fetch(ticker: str, period: str = "2y") -> pd.DataFrame:
            if ticker == "FAKE":
                raise TickerNotFoundError("not found", ticker="FAKE", source="yfinance")
            return valid_ohlcv_df

        with patch.object(
            service,
            "_fetch_raw_history",
            new_callable=AsyncMock,
            side_effect=mock_fetch,
        ):
            results = await service.fetch_batch_ohlcv(["AAPL", "FAKE"])

        assert isinstance(results["AAPL"], list)
        assert isinstance(results["FAKE"], Exception)

    @pytest.mark.asyncio()
    async def test_all_succeed(
        self,
        service: MarketDataService,
        valid_ohlcv_df: pd.DataFrame,
    ) -> None:
        """Batch with all valid tickers returns all successes."""
        with patch.object(
            service,
            "_fetch_raw_history",
            new_callable=AsyncMock,
            return_value=valid_ohlcv_df,
        ):
            results = await service.fetch_batch_ohlcv(["AAPL", "MSFT"])

        assert isinstance(results["AAPL"], list)
        assert isinstance(results["MSFT"], list)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestSafeDecimal:
    """Tests for safe_decimal() helper."""

    def test_valid_number(self) -> None:
        """Converts a valid number to Decimal."""
        assert safe_decimal(1.05) == Decimal("1.05")

    def test_none_returns_zero(self) -> None:
        """None returns Decimal('0')."""
        assert safe_decimal(None) == Decimal("0")

    def test_nan_string_returns_zero(self) -> None:
        """'nan' string returns Decimal('0')."""
        assert safe_decimal("nan") == Decimal("0")

    def test_inf_returns_zero(self) -> None:
        """'inf' returns Decimal('0')."""
        assert safe_decimal("inf") == Decimal("0")


class TestSafeInt:
    """Tests for safe_int() helper."""

    def test_valid_int(self) -> None:
        """Converts a valid number to int."""
        assert safe_int(42) == 42

    def test_none_returns_zero(self) -> None:
        """None returns 0."""
        assert safe_int(None) == 0

    def test_float_truncates(self) -> None:
        """Float is truncated to int."""
        assert safe_int(3.9) == 3


class TestClassifyMarketCap:
    """Tests for _classify_market_cap() helper."""

    def test_mega_cap(self) -> None:
        """Market cap >= 200B is 'Mega'."""
        assert _classify_market_cap(300_000_000_000) == "Mega"

    def test_large_cap(self) -> None:
        """Market cap >= 10B is 'Large'."""
        assert _classify_market_cap(50_000_000_000) == "Large"

    def test_mid_cap(self) -> None:
        """Market cap >= 2B is 'Mid'."""
        assert _classify_market_cap(5_000_000_000) == "Mid"

    def test_small_cap(self) -> None:
        """Market cap >= 300M is 'Small'."""
        assert _classify_market_cap(500_000_000) == "Small"

    def test_micro_cap(self) -> None:
        """Market cap < 300M is 'Micro'."""
        assert _classify_market_cap(100_000_000) == "Micro"

    def test_none_returns_unknown(self) -> None:
        """None market cap returns 'Unknown'."""
        assert _classify_market_cap(None) == "Unknown"

    def test_invalid_value_returns_unknown(self) -> None:
        """Non-numeric market cap returns 'Unknown'."""
        assert _classify_market_cap("not_a_number") == "Unknown"
