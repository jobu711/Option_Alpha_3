"""Shared helpers for yfinance-based service modules.

Consolidates safe type conversions and the retry-with-backoff pattern used
by both ``market_data`` and ``options_data`` services.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable, Coroutine
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import (
    DataSourceUnavailableError,
    InsufficientDataError,
    TickerNotFoundError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

YFINANCE_SOURCE: Final[str] = "yfinance"
EXTERNAL_CALL_TIMEOUT_SECONDS: Final[float] = 30.0

# Retry configuration for yfinance calls
MAX_RETRIES: Final[int] = 3
BACKOFF_DELAYS: Final[list[float]] = [1.0, 2.0, 4.0]


# ---------------------------------------------------------------------------
# Safe type conversions
# ---------------------------------------------------------------------------


def safe_decimal(value: object) -> Decimal:
    """Convert a numeric value to Decimal via string to preserve precision.

    Falls back to ``Decimal("0")`` for NaN / None / unparseable values.
    """
    if value is None:
        return Decimal("0")
    try:
        str_val = str(value)
        if str_val in ("nan", "inf", "-inf", "None"):
            return Decimal("0")
        return Decimal(str_val)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def safe_int(value: object) -> int:
    """Convert a numeric value to int, treating NaN/None as 0."""
    if value is None:
        return 0
    try:
        float_val = float(str(value))
        if float_val != float_val:  # NaN check without numpy
            return 0
        return int(float_val)
    except (ValueError, TypeError):
        return 0


def safe_float(value: object) -> float:
    """Convert a numeric value to float, treating NaN/None as 0.0."""
    if value is None:
        return 0.0
    try:
        float_val = float(str(value))
        if math.isnan(float_val) or math.isinf(float_val):
            return 0.0
        return float_val
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


async def fetch_with_retry[T](
    fetch_fn: Callable[[], Coroutine[Any, Any, T]],
    *,
    rate_limiter: RateLimiter,
    ticker: str,
    source: str,
    label: str,
    max_retries: int = MAX_RETRIES,
    backoff_delays: list[float] | None = None,
) -> T:
    """Retry a fetch coroutine with exponential backoff and rate limiting.

    Catches broad ``Exception`` because yfinance raises inconsistent
    types, then re-raises as ``DataSourceUnavailableError`` after
    exhausting retries.  Domain exceptions (``TickerNotFoundError``,
    ``InsufficientDataError``) are re-raised immediately without retry.

    Args:
        fetch_fn: Zero-argument callable returning a coroutine.
        rate_limiter: RateLimiter instance for acquire/release.
        ticker: Ticker symbol for error context.
        source: Data source name for error context.
        label: Human-readable label for log messages.
        max_retries: Maximum number of attempts (default 3).
        backoff_delays: Delay schedule in seconds (default [1.0, 2.0, 4.0]).

    Returns:
        Whatever *fetch_fn* returns.

    Raises:
        DataSourceUnavailableError: After exhausting all retries.
        TickerNotFoundError: Re-raised immediately.
        InsufficientDataError: Re-raised immediately.
    """
    delays = backoff_delays if backoff_delays is not None else BACKOFF_DELAYS
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        await rate_limiter.acquire()
        try:
            result = await fetch_fn()
            return result
        except (TickerNotFoundError, InsufficientDataError):
            raise
        except TimeoutError as exc:
            last_exc = exc
            logger.warning(
                "%s timed out (attempt %d/%d)",
                label,
                attempt + 1,
                max_retries,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "%s failed (attempt %d/%d): %s",
                label,
                attempt + 1,
                max_retries,
                exc,
            )
        finally:
            rate_limiter.release()

        # Backoff before next retry (not after the last attempt)
        if attempt < max_retries - 1:
            delay = delays[attempt] if attempt < len(delays) else delays[-1]
            await asyncio.sleep(delay)

    # All retries exhausted
    assert last_exc is not None  # noqa: S101
    raise DataSourceUnavailableError(
        f"Failed to fetch {label} after {max_retries} retries: {last_exc}",
        ticker=ticker,
        source=source,
    )
