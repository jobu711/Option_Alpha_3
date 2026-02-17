"""Tests for services/_helpers.py: safe_float, fetch_with_retry.

safe_float and fetch_with_retry are used across all service modules but had
zero dedicated test coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from Option_Alpha.services._helpers import (
    BACKOFF_DELAYS,
    MAX_RETRIES,
    fetch_with_retry,
    safe_float,
)
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
    DataSourceUnavailableError,
    InsufficientDataError,
    TickerNotFoundError,
)

# ---------------------------------------------------------------------------
# safe_float
# ---------------------------------------------------------------------------


class TestSafeFloat:
    """Test safe_float conversion with all edge cases."""

    def test_normal_float(self) -> None:
        assert safe_float(1.5) == pytest.approx(1.5, abs=1e-9)

    def test_normal_int(self) -> None:
        assert safe_float(42) == pytest.approx(42.0, abs=1e-9)

    def test_string_numeric(self) -> None:
        assert safe_float("2.5") == pytest.approx(2.5, abs=1e-9)

    def test_none_returns_zero(self) -> None:
        assert safe_float(None) == pytest.approx(0.0, abs=1e-9)

    def test_nan_float_returns_zero(self) -> None:
        assert safe_float(float("nan")) == pytest.approx(0.0, abs=1e-9)

    def test_inf_returns_zero(self) -> None:
        assert safe_float(float("inf")) == pytest.approx(0.0, abs=1e-9)

    def test_negative_inf_returns_zero(self) -> None:
        assert safe_float(float("-inf")) == pytest.approx(0.0, abs=1e-9)

    def test_string_nan_returns_zero(self) -> None:
        result = safe_float("nan")
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_string_inf_returns_zero(self) -> None:
        result = safe_float("inf")
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_unparseable_string_returns_zero(self) -> None:
        assert safe_float("not_a_number") == pytest.approx(0.0, abs=1e-9)

    def test_zero_int(self) -> None:
        assert safe_float(0) == pytest.approx(0.0, abs=1e-9)

    def test_zero_float(self) -> None:
        assert safe_float(0.0) == pytest.approx(0.0, abs=1e-9)

    def test_negative_float(self) -> None:
        assert safe_float(-3.14) == pytest.approx(-3.14, rel=1e-6)

    def test_very_large_float(self) -> None:
        result = safe_float(1e308)
        assert result == pytest.approx(1e308, rel=1e-6)

    def test_bool_true_returns_zero(self) -> None:
        # float(str(True)) = float("True") → ValueError → 0.0
        assert safe_float(True) == pytest.approx(0.0, abs=1e-9)

    def test_bool_false_returns_zero(self) -> None:
        assert safe_float(False) == pytest.approx(0.0, abs=1e-9)

    def test_empty_string_returns_zero(self) -> None:
        assert safe_float("") == pytest.approx(0.0, abs=1e-9)

    def test_whitespace_string_returns_zero(self) -> None:
        assert safe_float("   ") == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# fetch_with_retry
# ---------------------------------------------------------------------------


def _build_rate_limiter() -> MagicMock:
    """Build a mock RateLimiter with async acquire/release."""
    mock = MagicMock(spec=RateLimiter)
    mock.acquire = AsyncMock()
    mock.release = MagicMock()
    return mock


class TestFetchWithRetrySuccess:
    """Happy-path tests for fetch_with_retry."""

    @pytest.mark.asyncio()
    async def test_success_on_first_attempt(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(return_value="data")
        result = await fetch_with_retry(
            fetch_fn,
            rate_limiter=limiter,
            ticker="AAPL",
            source="test",
            label="test_fetch",
            backoff_delays=[0.0],
        )
        assert result == "data"
        limiter.acquire.assert_awaited_once()
        limiter.release.assert_called_once()

    @pytest.mark.asyncio()
    async def test_success_on_second_attempt(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(side_effect=[RuntimeError("boom"), "data"])
        result = await fetch_with_retry(
            fetch_fn,
            rate_limiter=limiter,
            ticker="AAPL",
            source="test",
            label="test_fetch",
            backoff_delays=[0.0],
        )
        assert result == "data"
        assert limiter.acquire.await_count == 2
        assert limiter.release.call_count == 2

    @pytest.mark.asyncio()
    async def test_success_on_third_attempt(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(
            side_effect=[RuntimeError("1"), RuntimeError("2"), "data"],
        )
        result = await fetch_with_retry(
            fetch_fn,
            rate_limiter=limiter,
            ticker="AAPL",
            source="test",
            label="test_fetch",
            backoff_delays=[0.0, 0.0, 0.0],
        )
        assert result == "data"
        assert fetch_fn.await_count == 3


class TestFetchWithRetryDomainExceptions:
    """Domain exceptions bypass retry and re-raise immediately."""

    @pytest.mark.asyncio()
    async def test_ticker_not_found_reraise_no_retry(self) -> None:
        limiter = _build_rate_limiter()
        exc = TickerNotFoundError("FAKE", ticker="FAKE", source="test")
        fetch_fn = AsyncMock(side_effect=exc)
        with pytest.raises(TickerNotFoundError):
            await fetch_with_retry(
                fetch_fn,
                rate_limiter=limiter,
                ticker="FAKE",
                source="test",
                label="test_fetch",
                backoff_delays=[0.0],
            )
        # Only one attempt — no retry
        fetch_fn.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_insufficient_data_reraise_no_retry(self) -> None:
        limiter = _build_rate_limiter()
        exc = InsufficientDataError("too few", ticker="AAPL", source="test")
        fetch_fn = AsyncMock(side_effect=exc)
        with pytest.raises(InsufficientDataError):
            await fetch_with_retry(
                fetch_fn,
                rate_limiter=limiter,
                ticker="AAPL",
                source="test",
                label="test_fetch",
                backoff_delays=[0.0],
            )
        fetch_fn.assert_awaited_once()


class TestFetchWithRetryExhausted:
    """All retries exhausted raises DataSourceUnavailableError."""

    @pytest.mark.asyncio()
    async def test_all_retries_exhausted(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(side_effect=RuntimeError("persistent failure"))
        with pytest.raises(DataSourceUnavailableError, match="persistent failure"):
            await fetch_with_retry(
                fetch_fn,
                rate_limiter=limiter,
                ticker="AAPL",
                source="yfinance",
                label="OHLCV(AAPL)",
                max_retries=3,
                backoff_delays=[0.0, 0.0, 0.0],
            )
        assert fetch_fn.await_count == 3

    @pytest.mark.asyncio()
    async def test_timeout_triggers_retry(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(
            side_effect=[TimeoutError("slow"), TimeoutError("slow"), "ok"],
        )
        result = await fetch_with_retry(
            fetch_fn,
            rate_limiter=limiter,
            ticker="AAPL",
            source="test",
            label="test_fetch",
            max_retries=3,
            backoff_delays=[0.0, 0.0, 0.0],
        )
        assert result == "ok"

    @pytest.mark.asyncio()
    async def test_max_retries_one_single_attempt(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(DataSourceUnavailableError):
            await fetch_with_retry(
                fetch_fn,
                rate_limiter=limiter,
                ticker="AAPL",
                source="test",
                label="test_fetch",
                max_retries=1,
                backoff_delays=[0.0],
            )
        fetch_fn.assert_awaited_once()


class TestFetchWithRetryBackoff:
    """Verify backoff delay behavior."""

    @pytest.mark.asyncio()
    async def test_custom_backoff_delays(self) -> None:
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(
            side_effect=[RuntimeError("1"), RuntimeError("2"), "ok"],
        )
        result = await fetch_with_retry(
            fetch_fn,
            rate_limiter=limiter,
            ticker="AAPL",
            source="test",
            label="test_fetch",
            max_retries=3,
            backoff_delays=[0.0, 0.0],
        )
        assert result == "ok"

    @pytest.mark.asyncio()
    async def test_release_called_on_exception(self) -> None:
        """Rate limiter release is called even when fetch_fn raises."""
        limiter = _build_rate_limiter()
        fetch_fn = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(DataSourceUnavailableError):
            await fetch_with_retry(
                fetch_fn,
                rate_limiter=limiter,
                ticker="AAPL",
                source="test",
                label="test_fetch",
                max_retries=2,
                backoff_delays=[0.0],
            )
        assert limiter.release.call_count == 2


class TestFetchWithRetryConstants:
    """Verify module-level constants."""

    def test_max_retries_default(self) -> None:
        assert MAX_RETRIES == 3

    def test_backoff_delays_default(self) -> None:
        assert len(BACKOFF_DELAYS) == 3
        assert BACKOFF_DELAYS[0] == pytest.approx(1.0, abs=1e-9)
        assert BACKOFF_DELAYS[1] == pytest.approx(2.0, abs=1e-9)
        assert BACKOFF_DELAYS[2] == pytest.approx(4.0, abs=1e-9)
