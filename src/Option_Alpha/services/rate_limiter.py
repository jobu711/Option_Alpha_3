"""Async rate limiter with token bucket algorithm and retry logic.

Provides concurrency control via asyncio.Semaphore and rate limiting via a
token bucket. Designed for gating requests to external data sources (yfinance,
CBOE, etc.) with configurable backoff and automatic retry on HTTP 429 responses.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable
from typing import TypeVar

from Option_Alpha.utils.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YFINANCE_REQUESTS_PER_SECOND: float = 2.0
YFINANCE_MAX_CONCURRENT: int = 5
DEFAULT_MAX_RETRIES: int = 5
DEFAULT_BACKOFF_DELAYS: list[float] = [1.0, 2.0, 4.0, 8.0, 16.0]


class RateLimiter:
    """Async rate limiter combining concurrency control and token bucket.

    Usage::

        limiter = RateLimiter(max_concurrent=5, requests_per_second=2.0)

        # Simple acquire/release
        await limiter.acquire()
        try:
            result = await some_http_call()
        finally:
            limiter.release()

        # Or use execute() for automatic retry with backoff
        result = await limiter.execute(
            fetch_data(ticker),
            ticker="AAPL",
            source="yfinance",
        )
    """

    def __init__(
        self,
        max_concurrent: int = YFINANCE_MAX_CONCURRENT,
        requests_per_second: float = YFINANCE_REQUESTS_PER_SECOND,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_delays: list[float] | None = None,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._requests_per_second = requests_per_second
        self._max_retries = max_retries
        self._backoff_delays = (
            backoff_delays if backoff_delays is not None else list(DEFAULT_BACKOFF_DELAYS)
        )

        # Token bucket state
        self._token_interval = 1.0 / requests_per_second
        self._tokens = float(max_concurrent)
        self._max_tokens = float(max_concurrent)
        self._last_refill_time = time.monotonic()
        self._bucket_lock = asyncio.Lock()

        logger.info(
            "RateLimiter initialized: max_concurrent=%d, rate=%.1f req/s, max_retries=%d",
            max_concurrent,
            requests_per_second,
            max_retries,
        )

    async def acquire(self) -> None:
        """Block until both concurrency and rate limits allow a request.

        Acquires a semaphore slot for concurrency control, then waits for
        a token from the token bucket for rate limiting.
        """
        await self._semaphore.acquire()
        await self._wait_for_token()

    def release(self) -> None:
        """Release a concurrency slot back to the semaphore."""
        self._semaphore.release()

    async def execute(
        self,
        coro: Awaitable[T],
        *,
        ticker: str,
        source: str,
    ) -> T:
        """Execute an awaitable with rate limiting and automatic retry.

        Retries on RateLimitExceededError using the configured backoff
        schedule. If a ``retry_after`` attribute is present on the exception,
        that value is used instead of the backoff delay.

        Args:
            coro: The awaitable to execute (typically an HTTP fetch coroutine).
            ticker: Ticker symbol for error context.
            source: Data source name for error context.

        Returns:
            The result of the awaitable.

        Raises:
            RateLimitExceededError: After exhausting all retries.
        """
        last_exception: RateLimitExceededError | None = None

        for attempt in range(self._max_retries + 1):
            await self.acquire()
            try:
                result: T = await coro
                return result
            except RateLimitExceededError as exc:
                last_exception = exc
                delay = self._get_retry_delay(exc, attempt)

                if attempt >= self._max_retries:
                    logger.error(
                        "Rate limit exceeded for %s from %s after %d retries",
                        ticker,
                        source,
                        self._max_retries,
                    )
                    raise

                logger.warning(
                    "Rate limited on %s from %s (attempt %d/%d), retrying in %.1fs",
                    ticker,
                    source,
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
            finally:
                self.release()

        # This branch should be unreachable, but satisfies the type checker.
        assert last_exception is not None  # noqa: S101
        raise last_exception

    # ------------------------------------------------------------------
    # Token bucket internals
    # ------------------------------------------------------------------

    async def _wait_for_token(self) -> None:
        """Wait until a token is available in the bucket."""
        while True:
            async with self._bucket_lock:
                self._refill_tokens()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

            # No token available — sleep for one interval and retry
            await asyncio.sleep(self._token_interval)

    def _refill_tokens(self) -> None:
        """Add tokens based on elapsed time since the last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill_time
        new_tokens = elapsed * self._requests_per_second
        self._tokens = min(self._max_tokens, self._tokens + new_tokens)
        self._last_refill_time = now

    def _get_retry_delay(
        self,
        exc: RateLimitExceededError,
        attempt: int,
    ) -> float:
        """Determine how long to wait before the next retry.

        Uses the ``Retry-After`` header value from the exception if available
        (stored as ``retry_after`` attribute). Otherwise falls back to the
        configured backoff schedule.
        """
        # Check for Retry-After on the exception
        retry_after: float | None = getattr(exc, "retry_after", None)
        if retry_after is not None and retry_after > 0:
            return retry_after

        # Fall back to backoff schedule
        if attempt < len(self._backoff_delays):
            return self._backoff_delays[attempt]

        # Beyond the schedule — use the last delay
        return self._backoff_delays[-1]
