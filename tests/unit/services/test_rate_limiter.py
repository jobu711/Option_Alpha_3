"""Tests for the RateLimiter: concurrency, token bucket, retry, and backoff.

Covers:
- acquire() blocks when semaphore is full
- Token bucket correctly limits rate
- execute() with a successful coroutine factory
- execute() retries on RateLimitExceededError
- execute() respects retry_after attribute on exception
- execute() raises after exhausting max retries
- Backoff delay selection from schedule
- Custom configuration (different rates, retry counts)
"""

from __future__ import annotations

import asyncio
import contextlib
import time

import pytest

from Option_Alpha.services.rate_limiter import (
    DEFAULT_BACKOFF_DELAYS,
    RateLimiter,
)
from Option_Alpha.utils.exceptions import RateLimitExceededError


@pytest.fixture()
def fast_limiter() -> RateLimiter:
    """A rate limiter with fast settings for testing."""
    return RateLimiter(
        max_concurrent=5,
        requests_per_second=100.0,
        max_retries=3,
        backoff_delays=[0.01, 0.02, 0.04],
    )


@pytest.fixture()
def slow_limiter() -> RateLimiter:
    """A rate limiter with a tight concurrency of 1 for blocking tests."""
    return RateLimiter(
        max_concurrent=1,
        requests_per_second=100.0,
        max_retries=2,
        backoff_delays=[0.01, 0.02],
    )


class TestAcquireRelease:
    """Tests for acquire/release concurrency control."""

    @pytest.mark.asyncio()
    async def test_acquire_succeeds_when_slots_available(self, fast_limiter: RateLimiter) -> None:
        """acquire() returns immediately when concurrency slots are available."""
        await fast_limiter.acquire()
        fast_limiter.release()

    @pytest.mark.asyncio()
    async def test_acquire_blocks_when_semaphore_full(self, slow_limiter: RateLimiter) -> None:
        """acquire() blocks when all concurrency slots are taken."""
        # Acquire the single available slot
        await slow_limiter.acquire()

        acquired = False

        async def try_acquire() -> None:
            nonlocal acquired
            await slow_limiter.acquire()
            acquired = True

        task = asyncio.create_task(try_acquire())
        # Give the task a moment to try acquiring
        await asyncio.sleep(0.05)
        assert not acquired, "Should be blocked waiting for the semaphore"

        # Release the slot so the blocked task can proceed
        slow_limiter.release()
        await asyncio.sleep(0.05)
        assert acquired, "Should have acquired after release"

        slow_limiter.release()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


class TestTokenBucket:
    """Tests for the token bucket rate-limiting mechanism."""

    @pytest.mark.asyncio()
    async def test_token_bucket_allows_burst_up_to_max_tokens(self) -> None:
        """Token bucket allows a burst of requests up to max_concurrent."""
        limiter = RateLimiter(
            max_concurrent=3,
            requests_per_second=100.0,
        )
        # Should be able to acquire 3 tokens immediately (burst)
        start = time.monotonic()
        for _ in range(3):
            await limiter.acquire()
            limiter.release()
        elapsed = time.monotonic() - start
        # Burst should complete quickly (< 0.5s)
        assert elapsed < 0.5

    @pytest.mark.asyncio()
    async def test_token_bucket_rate_limits_sustained_requests(self) -> None:
        """Token bucket throttles sustained requests to the configured rate."""
        # 10 requests/sec, max_concurrent=2
        limiter = RateLimiter(
            max_concurrent=2,
            requests_per_second=10.0,
        )
        # Exhaust the burst capacity
        for _ in range(2):
            await limiter.acquire()
            limiter.release()

        # The next acquire should wait for a token refill (~0.1s at 10 req/s)
        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start
        limiter.release()
        # Should take at least some time (token refill interval)
        # Using a generous lower bound to avoid flaky tests
        assert elapsed >= 0.05


class TestExecute:
    """Tests for execute() with retry logic."""

    @pytest.mark.asyncio()
    async def test_execute_returns_result_on_success(self, fast_limiter: RateLimiter) -> None:
        """execute() returns the coroutine result on success."""
        result = await fast_limiter.execute(
            lambda: _async_value("hello"),
            ticker="AAPL",
            source="test",
        )
        assert result == "hello"

    @pytest.mark.asyncio()
    async def test_execute_retries_on_rate_limit_error(self, fast_limiter: RateLimiter) -> None:
        """execute() retries when RateLimitExceededError is raised.

        The execute() method accepts a callable factory that produces a
        fresh awaitable on each retry attempt.
        """
        call_count = 0

        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitExceededError(
                    "rate limited",
                    ticker="AAPL",
                    source="test",
                )
            return "success"

        result = await fast_limiter.execute(
            flaky,
            ticker="AAPL",
            source="test",
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio()
    async def test_execute_respects_retry_after_on_exception(
        self, fast_limiter: RateLimiter
    ) -> None:
        """execute() uses retry_after from the exception when available."""
        exc = RateLimitExceededError(
            "rate limited",
            ticker="AAPL",
            source="test",
        )
        exc.retry_after = 0.01
        delay = fast_limiter._get_retry_delay(exc, attempt=0)
        assert delay == pytest.approx(0.01, abs=0.001)

    @pytest.mark.asyncio()
    async def test_execute_raises_after_max_retries(self) -> None:
        """execute() raises RateLimitExceededError after exhausting retries."""
        limiter = RateLimiter(
            max_concurrent=5,
            requests_per_second=100.0,
            max_retries=2,
            backoff_delays=[0.01, 0.02],
        )

        async def always_fail() -> str:
            raise RateLimitExceededError(
                "always limited",
                ticker="AAPL",
                source="test",
            )

        with pytest.raises(RateLimitExceededError, match="always limited"):
            await limiter.execute(
                always_fail,
                ticker="AAPL",
                source="test",
            )


class TestBackoffDelays:
    """Tests for _get_retry_delay backoff schedule."""

    def test_backoff_uses_schedule_for_valid_attempt(self) -> None:
        """_get_retry_delay returns the scheduled delay for the attempt index."""
        limiter = RateLimiter(
            max_concurrent=5,
            requests_per_second=10.0,
            backoff_delays=[1.0, 2.0, 4.0],
        )
        exc = RateLimitExceededError("limited", ticker="X", source="test")
        assert limiter._get_retry_delay(exc, attempt=0) == pytest.approx(1.0)
        assert limiter._get_retry_delay(exc, attempt=1) == pytest.approx(2.0)
        assert limiter._get_retry_delay(exc, attempt=2) == pytest.approx(4.0)

    def test_backoff_uses_last_delay_beyond_schedule(self) -> None:
        """_get_retry_delay uses the last delay when attempt exceeds schedule."""
        limiter = RateLimiter(
            max_concurrent=5,
            requests_per_second=10.0,
            backoff_delays=[1.0, 2.0],
        )
        exc = RateLimitExceededError("limited", ticker="X", source="test")
        # Attempt 5 is beyond the 2-element schedule
        assert limiter._get_retry_delay(exc, attempt=5) == pytest.approx(2.0)

    def test_retry_after_attribute_overrides_backoff(self) -> None:
        """retry_after attribute on exception overrides the backoff schedule."""
        limiter = RateLimiter(
            max_concurrent=5,
            requests_per_second=10.0,
            backoff_delays=[1.0, 2.0, 4.0],
        )
        exc = RateLimitExceededError("limited", ticker="X", source="test")
        exc.retry_after = 7.5
        assert limiter._get_retry_delay(exc, attempt=0) == pytest.approx(7.5)

    def test_retry_after_zero_or_negative_falls_back_to_schedule(self) -> None:
        """retry_after <= 0 falls back to the backoff schedule."""
        limiter = RateLimiter(
            max_concurrent=5,
            requests_per_second=10.0,
            backoff_delays=[1.0, 2.0],
        )
        exc = RateLimitExceededError("limited", ticker="X", source="test")
        exc.retry_after = 0.0
        assert limiter._get_retry_delay(exc, attempt=0) == pytest.approx(1.0)

        exc.retry_after = -1.0
        assert limiter._get_retry_delay(exc, attempt=1) == pytest.approx(2.0)


class TestCustomConfiguration:
    """Tests for RateLimiter with non-default settings."""

    def test_default_backoff_delays_constant(self) -> None:
        """DEFAULT_BACKOFF_DELAYS matches documented schedule."""
        assert DEFAULT_BACKOFF_DELAYS == [1.0, 2.0, 4.0, 8.0, 16.0]

    @pytest.mark.asyncio()
    async def test_custom_max_retries(self) -> None:
        """RateLimiter respects custom max_retries setting."""
        limiter = RateLimiter(
            max_concurrent=2,
            requests_per_second=100.0,
            max_retries=1,
            backoff_delays=[0.01],
        )

        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise RateLimitExceededError("always", ticker="X", source="test")

        with pytest.raises(RateLimitExceededError):
            await limiter.execute(
                always_fail,
                ticker="X",
                source="test",
            )

        # max_retries=1 means 2 total attempts (0 + 1 retry)
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_custom_requests_per_second(self) -> None:
        """RateLimiter token interval adjusts with requests_per_second."""
        limiter = RateLimiter(
            max_concurrent=1,
            requests_per_second=50.0,
        )
        # Token interval should be 1/50 = 0.02 seconds
        assert limiter._token_interval == pytest.approx(0.02, rel=1e-4)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _async_value(value: str) -> str:
    """Return a value asynchronously (simple awaitable for testing)."""
    return value
