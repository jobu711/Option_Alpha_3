"""Options data service wrapping yfinance for chain fetching and filtering.

All yfinance calls are synchronous and wrapped in ``asyncio.to_thread()`` to
avoid blocking the event loop.  Results are converted to typed ``OptionContract``
models with proper filtering for liquidity, delta, and open interest.

Key rules:
- Implied volatility from yfinance is already annualized -- DO NOT annualize.
- Bid/ask of 0.00 is flagged as illiquid and filtered out.
- Greeks from yfinance are flagged with ``GreeksSource.MARKET``.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from decimal import Decimal
from typing import Any, Final

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from Option_Alpha.models.enums import (
    GreeksSource,
    OptionType,
    SignalDirection,
)
from Option_Alpha.models.options import OptionContract, OptionGreeks
from Option_Alpha.services._helpers import (
    EXTERNAL_CALL_TIMEOUT_SECONDS,
    YFINANCE_SOURCE,
    fetch_with_retry,
    safe_decimal,
    safe_float,
    safe_int,
)
from Option_Alpha.services.cache import DATA_TYPE_CHAIN, ServiceCache
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.utils.exceptions import InsufficientDataError, TickerNotFoundError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Expiration selection: target 45 DTE, acceptable range 30-60 DTE
DTE_TARGET: Final[int] = 45
DTE_MIN: Final[int] = 30
DTE_MAX: Final[int] = 60

# Contract filtering thresholds
MIN_OPEN_INTEREST: Final[int] = 100
MIN_VOLUME: Final[int] = 1
MAX_SPREAD_RATIO: Final[float] = 0.30  # spread <= 30% of mid price
DELTA_MIN_ABS: Final[float] = 0.30
DELTA_MAX_ABS: Final[float] = 0.40

# Greek validation boundaries (same as model, used for pre-filter)
DELTA_FLOOR: Final[float] = -1.0
DELTA_CEILING: Final[float] = 1.0
GAMMA_FLOOR: Final[float] = 0.0
VEGA_FLOOR: Final[float] = 0.0


class OptionsDataService:
    """Async options data service backed by yfinance.

    Usage::

        limiter = RateLimiter()
        cache = ServiceCache()
        service = OptionsDataService(rate_limiter=limiter, cache=cache)

        contracts = await service.fetch_option_chain("AAPL")
        expiration = await service.select_expiration("AAPL")
        expirations = await service.fetch_expirations("AAPL")
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

    async def fetch_option_chain(
        self,
        ticker: str,
        direction: SignalDirection = SignalDirection.NEUTRAL,
    ) -> list[OptionContract]:
        """Fetch and filter option contracts for *ticker*.

        Selects the best expiration date (closest to 45 DTE within 30-60
        range), then fetches and filters contracts based on liquidity,
        open interest, and delta.

        For ``BULLISH`` direction, returns calls only.
        For ``BEARISH`` direction, returns puts only.
        For ``NEUTRAL``, returns an empty list (no directional signal).

        Args:
            ticker: Ticker symbol.
            direction: Signal direction for filtering call/put side.

        Returns:
            Filtered list of ``OptionContract`` models.

        Raises:
            TickerNotFoundError: If the ticker does not exist.
            InsufficientDataError: If no suitable expiration found.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        ticker = ticker.upper().strip()

        if direction == SignalDirection.NEUTRAL:
            logger.info(
                "Neutral direction for %s -- skipping chain fetch",
                ticker,
            )
            return []

        # Select the best expiration
        expiration = await self.select_expiration(ticker)
        expiration_str = expiration.isoformat()

        cache_key = f"yf:{DATA_TYPE_CHAIN}:{ticker}:{expiration_str}:{direction.value}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for option chain: %s", cache_key)
            return _deserialize_contract_list(cached)

        # Fetch raw chain from yfinance
        raw_calls, raw_puts = await fetch_with_retry(
            lambda: self._fetch_raw_option_chain(ticker, expiration_str),
            rate_limiter=self._rate_limiter,
            ticker=ticker,
            source=YFINANCE_SOURCE,
            label=f"OptionChain({ticker}, {expiration_str})",
        )

        # Select appropriate side based on direction
        if direction == SignalDirection.BULLISH:
            raw_df = raw_calls
            option_type = OptionType.CALL
        else:  # BEARISH
            raw_df = raw_puts
            option_type = OptionType.PUT

        if raw_df is None or raw_df.empty:
            raise InsufficientDataError(
                f"No {option_type.value} contracts for {ticker} at {expiration_str}",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        # Convert to models and filter
        contracts = self._dataframe_to_contracts(
            raw_df,
            ticker=ticker,
            option_type=option_type,
            expiration=expiration,
        )
        filtered = self._filter_contracts(contracts)

        # Store in cache
        ttl = self._cache.get_ttl(DATA_TYPE_CHAIN)
        await self._cache.set(cache_key, _serialize_contract_list(filtered), ttl)
        logger.info(
            "Fetched %d %s contracts for %s (exp=%s, %d after filter)",
            len(contracts),
            option_type.value,
            ticker,
            expiration_str,
            len(filtered),
        )
        return filtered

    async def select_expiration(self, ticker: str) -> datetime.date:
        """Select the best expiration date for *ticker*.

        Targets 45 DTE within the 30-60 DTE range.  If no expiration
        falls in that range, picks the closest available to 45 DTE.

        Args:
            ticker: Ticker symbol.

        Returns:
            The selected expiration date.

        Raises:
            TickerNotFoundError: If the ticker does not exist.
            InsufficientDataError: If no expirations are available.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        expirations = await self.fetch_expirations(ticker)

        if not expirations:
            raise InsufficientDataError(
                f"No option expirations available for {ticker}",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        today = datetime.date.today()

        # Filter to 30-60 DTE range
        in_range: list[datetime.date] = []
        for exp in expirations:
            dte = (exp - today).days
            if DTE_MIN <= dte <= DTE_MAX:
                in_range.append(exp)

        target_date = today + datetime.timedelta(days=DTE_TARGET)

        if in_range:
            best = min(
                in_range,
                key=lambda d: abs((d - target_date).days),
            )
            logger.debug(
                "Selected expiration %s for %s (DTE=%d)",
                best.isoformat(),
                ticker,
                (best - today).days,
            )
            return best

        # No expiration in range -- pick closest to 45 DTE
        best = min(
            expirations,
            key=lambda d: abs((d - target_date).days),
        )
        logger.warning(
            "No expiration in %d-%d DTE range for %s; using %s (DTE=%d)",
            DTE_MIN,
            DTE_MAX,
            ticker,
            best.isoformat(),
            (best - today).days,
        )
        return best

    async def fetch_expirations(self, ticker: str) -> list[datetime.date]:
        """Fetch all available option expiration dates for *ticker*.

        Args:
            ticker: Ticker symbol.

        Returns:
            Sorted list of expiration dates.

        Raises:
            TickerNotFoundError: If ticker has no options.
            DataSourceUnavailableError: If yfinance is unreachable.
        """
        ticker = ticker.upper().strip()

        raw_expirations = await fetch_with_retry(
            lambda: self._fetch_raw_expirations(ticker),
            rate_limiter=self._rate_limiter,
            ticker=ticker,
            source=YFINANCE_SOURCE,
            label=f"Expirations({ticker})",
        )

        if not raw_expirations:
            raise TickerNotFoundError(
                f"No options expirations found for {ticker}",
                ticker=ticker,
                source=YFINANCE_SOURCE,
            )

        dates: list[datetime.date] = []
        for exp_str in raw_expirations:
            try:
                dates.append(datetime.date.fromisoformat(str(exp_str)))
            except ValueError:
                logger.warning("Skipping unparseable expiration: %s", exp_str)
                continue

        dates.sort()
        logger.debug("Found %d expirations for %s", len(dates), ticker)
        return dates

    # ------------------------------------------------------------------
    # Raw yfinance calls (sync, wrapped in asyncio.to_thread)
    # ------------------------------------------------------------------

    async def _fetch_raw_option_chain(
        self,
        ticker: str,
        expiration: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch raw calls and puts DataFrames from yfinance."""

        def _sync_fetch() -> tuple[pd.DataFrame, pd.DataFrame]:
            t = yf.Ticker(ticker)
            chain: Any = t.option_chain(expiration)
            calls: pd.DataFrame = chain.calls
            puts: pd.DataFrame = chain.puts
            return calls, puts

        return await asyncio.wait_for(
            asyncio.to_thread(_sync_fetch),
            timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
        )

    async def _fetch_raw_expirations(
        self,
        ticker: str,
    ) -> tuple[str, ...]:
        """Fetch raw expiration strings from yfinance."""

        def _sync_fetch() -> tuple[str, ...]:
            t = yf.Ticker(ticker)
            exps: tuple[str, ...] = t.options
            return exps

        return await asyncio.wait_for(
            asyncio.to_thread(_sync_fetch),
            timeout=EXTERNAL_CALL_TIMEOUT_SECONDS,
        )

    # ------------------------------------------------------------------
    # Conversion and filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _dataframe_to_contracts(
        df: pd.DataFrame,
        *,
        ticker: str,
        option_type: OptionType,
        expiration: datetime.date,
    ) -> list[OptionContract]:
        """Convert a yfinance options DataFrame to ``OptionContract``.

        yfinance does not provide per-contract Greeks in the chain
        DataFrame, so ``greeks`` is set to ``None`` unless the DataFrame
        happens to include delta/gamma/theta/vega/rho columns.
        """
        contracts: list[OptionContract] = []

        greeks_cols = ("delta", "gamma", "theta", "vega", "rho")
        has_greeks = all(col in df.columns for col in greeks_cols)

        for _, row in df.iterrows():
            bid = safe_decimal(row.get("bid"))
            ask = safe_decimal(row.get("ask"))

            # Flag zero bid/ask as illiquid -- skip
            if bid == Decimal("0") and ask == Decimal("0"):
                continue

            greeks: OptionGreeks | None = None
            greeks_source: GreeksSource | None = None

            if has_greeks:
                delta = safe_float(row.get("delta"))
                gamma = safe_float(row.get("gamma"))
                theta = safe_float(row.get("theta"))
                vega = safe_float(row.get("vega"))
                rho = safe_float(row.get("rho"))

                # Only attach Greeks if delta is in valid range
                if DELTA_FLOOR <= delta <= DELTA_CEILING and gamma >= GAMMA_FLOOR:
                    try:
                        greeks = OptionGreeks(
                            delta=delta,
                            gamma=gamma,
                            theta=theta,
                            vega=max(vega, VEGA_FLOOR),
                            rho=rho,
                        )
                        greeks_source = GreeksSource.MARKET
                    except ValueError:
                        logger.debug(
                            "Invalid Greeks for %s strike %s",
                            ticker,
                            row.get("strike"),
                        )

            # IV from yfinance is already annualized -- DO NOT scale
            implied_vol = safe_float(row.get("impliedVolatility"))

            try:
                contract = OptionContract(
                    ticker=ticker,
                    option_type=option_type,
                    strike=safe_decimal(row.get("strike")),
                    expiration=expiration,
                    bid=bid,
                    ask=ask,
                    last=safe_decimal(row.get("lastPrice")),
                    volume=safe_int(row.get("volume")),
                    open_interest=safe_int(row.get("openInterest")),
                    implied_volatility=implied_vol,
                    greeks=greeks,
                    greeks_source=greeks_source,
                )
                contracts.append(contract)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Skipping malformed contract for %s strike %s",
                    ticker,
                    row.get("strike"),
                )
                continue

        return contracts

    @staticmethod
    def _filter_contracts(
        contracts: list[OptionContract],
    ) -> list[OptionContract]:
        """Apply liquidity and delta filters to contracts.

        Filters:
        - Open interest >= MIN_OPEN_INTEREST (100)
        - Volume >= MIN_VOLUME (1)
        - Spread <= MAX_SPREAD_RATIO (30%) of mid price
        - Delta abs between DELTA_MIN_ABS and DELTA_MAX_ABS
          (only if Greeks available; contracts without Greeks kept)
        """
        filtered: list[OptionContract] = []

        for contract in contracts:
            # Open interest filter
            if contract.open_interest < MIN_OPEN_INTEREST:
                continue

            # Volume filter
            if contract.volume < MIN_VOLUME:
                continue

            # Spread ratio filter -- avoid div by zero
            mid = contract.mid
            if mid > Decimal("0"):
                spread_ratio = float(contract.spread / mid)
                if spread_ratio > MAX_SPREAD_RATIO:
                    continue
            elif contract.spread > Decimal("0"):
                # Mid is zero but there's a spread -- illiquid
                continue

            # Delta filter (only when Greeks are available)
            if contract.greeks is not None:
                abs_delta = abs(contract.greeks.delta)
                if not (DELTA_MIN_ABS <= abs_delta <= DELTA_MAX_ABS):
                    continue

            filtered.append(contract)

        return filtered


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_contract_list(
    contracts: list[OptionContract],
) -> str:
    """Serialize a list of OptionContract models to JSON."""
    return json.dumps([c.model_dump(mode="json") for c in contracts])


def _deserialize_contract_list(
    data: str,
) -> list[OptionContract]:
    """Deserialize a JSON string to OptionContract models."""
    raw_list: list[dict[str, object]] = json.loads(data)
    return [OptionContract.model_validate(item) for item in raw_list]
