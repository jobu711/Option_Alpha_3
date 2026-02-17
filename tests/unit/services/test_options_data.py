"""Tests for OptionsDataService: chain fetching, expiration selection, filtering.

All yfinance calls are mocked. No real API calls.

Covers:
- fetch_option_chain() with BULLISH returns only calls
- fetch_option_chain() with BEARISH returns only puts
- fetch_option_chain() with NEUTRAL returns empty list
- select_expiration() selects closest to 45 DTE within 30-60 range
- select_expiration() falls back when no expirations in range
- Contract filtering: OI >= 100, spread <= 30%, volume >= 1, delta 0.30-0.40
- Zero bid/ask contracts filtered out
- Greeks flagged with correct GreeksSource
- IV NOT double-annualized
- fetch_expirations() returns sorted dates
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from Option_Alpha.models.enums import GreeksSource, OptionType, SignalDirection
from Option_Alpha.models.options import OptionContract, OptionGreeks
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.options_data import (
    DELTA_MAX_ABS,
    DELTA_MIN_ABS,
    DTE_MAX,
    DTE_MIN,
    DTE_TARGET,
    MAX_SPREAD_RATIO,
    MIN_OPEN_INTEREST,
    MIN_VOLUME,
    OptionsDataService,
)
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
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
def service(rate_limiter: RateLimiter, cache: ServiceCache) -> OptionsDataService:
    """OptionsDataService with mocked dependencies."""
    return OptionsDataService(rate_limiter=rate_limiter, cache=cache)


@pytest.fixture()
def mock_calls_df() -> pd.DataFrame:
    """Mock calls DataFrame with realistic option chain data."""
    return pd.DataFrame(
        {
            "strike": [180.0, 185.0, 190.0, 195.0],
            "bid": [8.50, 4.50, 2.10, 0.80],
            "ask": [8.70, 4.70, 2.30, 1.00],
            "lastPrice": [8.60, 4.60, 2.20, 0.90],
            "volume": [500, 1250, 800, 200],
            "openInterest": [3000, 8340, 5200, 1500],
            "impliedVolatility": [0.28, 0.30, 0.32, 0.35],
        }
    )


@pytest.fixture()
def mock_puts_df() -> pd.DataFrame:
    """Mock puts DataFrame with realistic option chain data."""
    return pd.DataFrame(
        {
            "strike": [175.0, 180.0, 185.0, 190.0],
            "bid": [0.60, 1.50, 3.80, 7.20],
            "ask": [0.80, 1.70, 4.00, 7.40],
            "lastPrice": [0.70, 1.60, 3.90, 7.30],
            "volume": [150, 600, 900, 400],
            "openInterest": [2000, 4500, 6100, 3200],
            "impliedVolatility": [0.34, 0.31, 0.29, 0.27],
        }
    )


@pytest.fixture()
def mock_calls_with_greeks_df() -> pd.DataFrame:
    """Mock calls DataFrame that includes Greek columns."""
    return pd.DataFrame(
        {
            "strike": [185.0, 190.0],
            "bid": [4.50, 2.10],
            "ask": [4.70, 2.30],
            "lastPrice": [4.60, 2.20],
            "volume": [1250, 800],
            "openInterest": [8340, 5200],
            "impliedVolatility": [0.30, 0.32],
            "delta": [0.35, 0.25],
            "gamma": [0.04, 0.03],
            "theta": [-0.08, -0.06],
            "vega": [0.12, 0.10],
            "rho": [0.01, 0.008],
        }
    )


def _mock_today() -> datetime.date:
    """Deterministic 'today' for tests."""
    return datetime.date(2025, 1, 15)


def _make_expirations(today: datetime.date) -> tuple[str, ...]:
    """Create realistic expiration date strings around target DTE."""
    return (
        (today + datetime.timedelta(days=7)).isoformat(),
        (today + datetime.timedelta(days=14)).isoformat(),
        (today + datetime.timedelta(days=35)).isoformat(),
        (today + datetime.timedelta(days=42)).isoformat(),
        (today + datetime.timedelta(days=56)).isoformat(),
        (today + datetime.timedelta(days=70)).isoformat(),
    )


# ---------------------------------------------------------------------------
# fetch_option_chain direction tests
# ---------------------------------------------------------------------------


class TestFetchOptionChainDirection:
    """Tests for directional filtering in fetch_option_chain()."""

    @pytest.mark.asyncio()
    async def test_bullish_returns_calls_only(
        self,
        service: OptionsDataService,
        mock_calls_df: pd.DataFrame,
        mock_puts_df: pd.DataFrame,
    ) -> None:
        """BULLISH direction returns call contracts only."""
        today = _mock_today()
        exps = _make_expirations(today)

        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=exps,
            ),
            patch.object(
                service,
                "_fetch_raw_option_chain",
                new_callable=AsyncMock,
                return_value=(mock_calls_df, mock_puts_df),
            ),
            patch("Option_Alpha.services.options_data.datetime") as mock_dt,
        ):
            mock_dt.date.today.return_value = today
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            mock_dt.timedelta = datetime.timedelta
            mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)

            contracts = await service.fetch_option_chain("AAPL", direction=SignalDirection.BULLISH)

        # All returned contracts should be calls
        for c in contracts:
            assert c.option_type is OptionType.CALL

    @pytest.mark.asyncio()
    async def test_bearish_returns_puts_only(
        self,
        service: OptionsDataService,
        mock_calls_df: pd.DataFrame,
        mock_puts_df: pd.DataFrame,
    ) -> None:
        """BEARISH direction returns put contracts only."""
        today = _mock_today()
        exps = _make_expirations(today)

        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=exps,
            ),
            patch.object(
                service,
                "_fetch_raw_option_chain",
                new_callable=AsyncMock,
                return_value=(mock_calls_df, mock_puts_df),
            ),
            patch("Option_Alpha.services.options_data.datetime") as mock_dt,
        ):
            mock_dt.date.today.return_value = today
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            mock_dt.timedelta = datetime.timedelta
            mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)

            contracts = await service.fetch_option_chain("AAPL", direction=SignalDirection.BEARISH)

        for c in contracts:
            assert c.option_type is OptionType.PUT

    @pytest.mark.asyncio()
    async def test_neutral_returns_empty_list(
        self,
        service: OptionsDataService,
    ) -> None:
        """NEUTRAL direction returns an empty list without fetching."""
        contracts = await service.fetch_option_chain("AAPL", direction=SignalDirection.NEUTRAL)
        assert contracts == []


# ---------------------------------------------------------------------------
# select_expiration tests
# ---------------------------------------------------------------------------


class TestSelectExpiration:
    """Tests for select_expiration()."""

    @pytest.mark.asyncio()
    async def test_selects_closest_to_45_dte_in_range(
        self,
        service: OptionsDataService,
    ) -> None:
        """Selects the expiration closest to 45 DTE within 30-60 range."""
        today = _mock_today()
        # Create expirations: 35, 42, 56, 70 DTE
        exps = (
            (today + datetime.timedelta(days=35)).isoformat(),
            (today + datetime.timedelta(days=42)).isoformat(),
            (today + datetime.timedelta(days=56)).isoformat(),
            (today + datetime.timedelta(days=70)).isoformat(),
        )

        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=exps,
            ),
            patch("Option_Alpha.services.options_data.datetime") as mock_dt,
        ):
            mock_dt.date.today.return_value = today
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            mock_dt.timedelta = datetime.timedelta
            mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)

            result = await service.select_expiration("AAPL")

        # 42 DTE is closest to 45 DTE target
        expected = today + datetime.timedelta(days=42)
        assert result == expected

    @pytest.mark.asyncio()
    async def test_fallback_when_no_expiration_in_range(
        self,
        service: OptionsDataService,
    ) -> None:
        """Falls back to closest to 45 DTE when none are in 30-60 range."""
        today = _mock_today()
        # All expirations outside 30-60 range
        exps = (
            (today + datetime.timedelta(days=7)).isoformat(),
            (today + datetime.timedelta(days=14)).isoformat(),
            (today + datetime.timedelta(days=90)).isoformat(),
        )

        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=exps,
            ),
            patch("Option_Alpha.services.options_data.datetime") as mock_dt,
        ):
            mock_dt.date.today.return_value = today
            mock_dt.date.fromisoformat = datetime.date.fromisoformat
            mock_dt.timedelta = datetime.timedelta
            mock_dt.date.side_effect = lambda *a, **kw: datetime.date(*a, **kw)

            result = await service.select_expiration("AAPL")

        # 14 DTE is furthest, 90 DTE is furthest; closest to 45 is 14 (|45-14|=31 vs |45-90|=45)
        # Actually |45-14|=31 and |45-90|=45, so 14 DTE is closer to 45
        # Wait: |45-7|=38, |45-14|=31, |45-90|=45, so 14 DTE is closest
        expected = today + datetime.timedelta(days=14)
        assert result == expected

    @pytest.mark.asyncio()
    async def test_no_expirations_raises_insufficient_data(
        self,
        service: OptionsDataService,
    ) -> None:
        """Empty expirations list raises InsufficientDataError."""
        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=(),
            ),
            pytest.raises(TickerNotFoundError, match="No options expirations"),
        ):
            await service.select_expiration("FAKE")


# ---------------------------------------------------------------------------
# Contract filtering tests
# ---------------------------------------------------------------------------


class TestContractFiltering:
    """Tests for _filter_contracts() static method."""

    def _make_contract(
        self,
        *,
        strike: str = "185.00",
        bid: str = "4.50",
        ask: str = "4.70",
        volume: int = 1250,
        open_interest: int = 8340,
        iv: float = 0.30,
        delta: float | None = 0.35,
    ) -> OptionContract:
        """Helper to create a test OptionContract."""
        greeks = None
        greeks_source = None
        if delta is not None:
            greeks = OptionGreeks(
                delta=delta,
                gamma=0.04,
                theta=-0.08,
                vega=0.12,
                rho=0.01,
            )
            greeks_source = GreeksSource.MARKET

        return OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal(strike),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal(bid),
            ask=Decimal(ask),
            last=Decimal("4.60"),
            volume=volume,
            open_interest=open_interest,
            implied_volatility=iv,
            greeks=greeks,
            greeks_source=greeks_source,
        )

    def test_valid_contract_passes_all_filters(self) -> None:
        """A contract meeting all criteria passes filtering."""
        contract = self._make_contract()
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 1

    def test_low_open_interest_filtered_out(self) -> None:
        """Contract with OI < 100 is filtered out."""
        contract = self._make_contract(open_interest=50)
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 0

    def test_zero_volume_filtered_out(self) -> None:
        """Contract with volume < 1 is filtered out."""
        contract = self._make_contract(volume=0)
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 0

    def test_wide_spread_filtered_out(self) -> None:
        """Contract with spread > 30% of mid is filtered out."""
        # bid=1.00, ask=2.00 => mid=1.50, spread=1.00, ratio=0.667 > 0.30
        contract = self._make_contract(bid="1.00", ask="2.00")
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 0

    def test_delta_outside_range_filtered_out(self) -> None:
        """Contract with delta outside 0.30-0.40 range is filtered out."""
        contract = self._make_contract(delta=0.55)
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 0

    def test_delta_below_range_filtered_out(self) -> None:
        """Contract with delta below 0.30 is filtered out."""
        contract = self._make_contract(delta=0.20)
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 0

    def test_contract_without_greeks_passes_delta_filter(self) -> None:
        """Contract without Greeks is NOT filtered by delta."""
        contract = self._make_contract(delta=None)
        filtered = OptionsDataService._filter_contracts([contract])
        assert len(filtered) == 1

    def test_delta_at_boundary_passes(self) -> None:
        """Contract with delta exactly at 0.30 or 0.40 passes."""
        contract_low = self._make_contract(delta=0.30)
        contract_high = self._make_contract(delta=0.40)
        filtered = OptionsDataService._filter_contracts([contract_low, contract_high])
        assert len(filtered) == 2


# ---------------------------------------------------------------------------
# Zero bid/ask filtering tests
# ---------------------------------------------------------------------------


class TestZeroBidAskFiltering:
    """Tests for zero bid/ask contract handling."""

    def test_zero_bid_and_ask_skipped_during_conversion(self) -> None:
        """Contracts with both bid=0 and ask=0 are skipped."""
        df = pd.DataFrame(
            {
                "strike": [185.0],
                "bid": [0.0],
                "ask": [0.0],
                "lastPrice": [0.0],
                "volume": [0],
                "openInterest": [100],
                "impliedVolatility": [0.30],
            }
        )
        contracts = OptionsDataService._dataframe_to_contracts(
            df,
            ticker="AAPL",
            option_type=OptionType.CALL,
            expiration=datetime.date(2025, 2, 21),
        )
        assert len(contracts) == 0

    def test_nonzero_bid_with_zero_ask_kept(self) -> None:
        """Contract with bid > 0 but ask = 0 is kept (unusual but possible)."""
        df = pd.DataFrame(
            {
                "strike": [185.0],
                "bid": [1.50],
                "ask": [0.0],
                "lastPrice": [1.00],
                "volume": [10],
                "openInterest": [100],
                "impliedVolatility": [0.30],
            }
        )
        contracts = OptionsDataService._dataframe_to_contracts(
            df,
            ticker="AAPL",
            option_type=OptionType.CALL,
            expiration=datetime.date(2025, 2, 21),
        )
        assert len(contracts) == 1


# ---------------------------------------------------------------------------
# Greeks source tests
# ---------------------------------------------------------------------------


class TestGreeksSource:
    """Tests for Greeks source tagging."""

    def test_greeks_flagged_as_market_source(
        self, mock_calls_with_greeks_df: pd.DataFrame
    ) -> None:
        """Greeks from yfinance are flagged with GreeksSource.MARKET."""
        contracts = OptionsDataService._dataframe_to_contracts(
            mock_calls_with_greeks_df,
            ticker="AAPL",
            option_type=OptionType.CALL,
            expiration=datetime.date(2025, 2, 21),
        )
        for c in contracts:
            if c.greeks is not None:
                assert c.greeks_source is GreeksSource.MARKET


# ---------------------------------------------------------------------------
# IV handling tests
# ---------------------------------------------------------------------------


class TestIVHandling:
    """Tests for implied volatility NOT being double-annualized."""

    def test_iv_not_double_annualized(self, mock_calls_df: pd.DataFrame) -> None:
        """IV from yfinance is stored as-is, not annualized again."""
        contracts = OptionsDataService._dataframe_to_contracts(
            mock_calls_df,
            ticker="AAPL",
            option_type=OptionType.CALL,
            expiration=datetime.date(2025, 2, 21),
        )
        # The raw IV in mock_calls_df is 0.28, 0.30, 0.32, 0.35
        # These should be stored directly without any sqrt(252) scaling
        for c in contracts:
            assert c.implied_volatility < 1.0, "IV should not be scaled (double-annualized)"


# ---------------------------------------------------------------------------
# fetch_expirations tests
# ---------------------------------------------------------------------------


class TestFetchExpirations:
    """Tests for fetch_expirations()."""

    @pytest.mark.asyncio()
    async def test_returns_sorted_dates(
        self,
        service: OptionsDataService,
    ) -> None:
        """fetch_expirations() returns dates sorted chronologically."""
        raw_exps = ("2025-05-16", "2025-03-21", "2025-04-18")

        with patch.object(
            service,
            "_fetch_raw_expirations",
            new_callable=AsyncMock,
            return_value=raw_exps,
        ):
            dates = await service.fetch_expirations("AAPL")

        assert dates == sorted(dates)
        assert len(dates) == 3
        assert dates[0] == datetime.date(2025, 3, 21)

    @pytest.mark.asyncio()
    async def test_empty_expirations_raises_ticker_not_found(
        self,
        service: OptionsDataService,
    ) -> None:
        """Empty expirations raises TickerNotFoundError."""
        with (
            patch.object(
                service,
                "_fetch_raw_expirations",
                new_callable=AsyncMock,
                return_value=(),
            ),
            pytest.raises(TickerNotFoundError, match="No options expirations"),
        ):
            await service.fetch_expirations("FAKE")

    @pytest.mark.asyncio()
    async def test_skips_unparseable_expirations(
        self,
        service: OptionsDataService,
    ) -> None:
        """Unparseable expiration strings are skipped."""
        raw_exps = ("2025-04-18", "not-a-date", "2025-05-16")

        with patch.object(
            service,
            "_fetch_raw_expirations",
            new_callable=AsyncMock,
            return_value=raw_exps,
        ):
            dates = await service.fetch_expirations("AAPL")

        assert len(dates) == 2


# ---------------------------------------------------------------------------
# Constants verification
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify service constants match documented values."""

    def test_dte_target(self) -> None:
        """DTE target is 45 days."""
        assert DTE_TARGET == 45

    def test_dte_range(self) -> None:
        """DTE range is 30-60 days."""
        assert DTE_MIN == 30
        assert DTE_MAX == 60

    def test_min_open_interest(self) -> None:
        """Minimum OI threshold is 100."""
        assert MIN_OPEN_INTEREST == 100

    def test_min_volume(self) -> None:
        """Minimum volume threshold is 1."""
        assert MIN_VOLUME == 1

    def test_max_spread_ratio(self) -> None:
        """Max spread ratio is 30%."""
        assert pytest.approx(0.30) == MAX_SPREAD_RATIO

    def test_delta_range(self) -> None:
        """Delta filter range is 0.30-0.40."""
        assert pytest.approx(0.30) == DELTA_MIN_ABS
        assert pytest.approx(0.40) == DELTA_MAX_ABS
