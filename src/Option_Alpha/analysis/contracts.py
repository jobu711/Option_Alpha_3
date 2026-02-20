"""Contract filtering and recommendation engine.

Filters options contracts by liquidity, spread width, and directional fit,
then selects the best expiration and delta target for a single recommendation.
"""

import datetime
import logging
from decimal import Decimal

from Option_Alpha.analysis.bsm import bsm_greeks
from Option_Alpha.models.enums import OptionType, SignalDirection
from Option_Alpha.models.options import OptionContract, OptionGreeks

logger = logging.getLogger(__name__)

# --- Liquidity minimums ---
MIN_OPEN_INTEREST: int = 100
MIN_VOLUME: int = 1
MAX_SPREAD_PCT: float = 0.30

# --- DTE targeting ---
MIN_DTE: int = 30
MAX_DTE: int = 60
TARGET_DTE: int = 45

# --- Delta targeting ---
DEFAULT_DELTA_TARGET: float = 0.35
DEFAULT_DELTA_TARGET_LOW: float = 0.30
DEFAULT_DELTA_TARGET_HIGH: float = 0.40

_ZERO: Decimal = Decimal("0")

# --- BSM fallback for missing Greeks ---
RISK_FREE_RATE_FALLBACK: float = 0.05
DAYS_PER_YEAR: int = 365


def filter_contracts(
    contracts: list[OptionContract],
    direction: SignalDirection,
) -> list[OptionContract]:
    """Filter contracts by liquidity, spread, and directional type.

    Args:
        contracts: Raw list of option contracts to filter.
        direction: BULLISH selects calls, BEARISH selects puts,
            NEUTRAL returns an empty list.

    Returns:
        Filtered contracts sorted by open_interest descending.
    """
    if direction == SignalDirection.NEUTRAL:
        logger.debug("Direction is NEUTRAL — returning empty list")
        return []

    desired_type: OptionType = (
        OptionType.CALL if direction == SignalDirection.BULLISH else OptionType.PUT
    )

    filtered: list[OptionContract] = []
    for contract in contracts:
        if contract.option_type != desired_type:
            continue
        if contract.open_interest < MIN_OPEN_INTEREST:
            continue
        if contract.volume < MIN_VOLUME:
            continue
        if contract.mid == _ZERO:
            continue
        spread_pct: float = float(contract.spread / contract.mid)
        if spread_pct > MAX_SPREAD_PCT:
            continue
        filtered.append(contract)

    filtered.sort(key=lambda c: c.open_interest, reverse=True)

    logger.debug(
        "filter_contracts: %d -> %d contracts (direction=%s, type=%s)",
        len(contracts),
        len(filtered),
        direction.value,
        desired_type.value,
    )
    return filtered


def select_expiration(
    contracts: list[OptionContract],
    target_dte: int = TARGET_DTE,
) -> list[OptionContract]:
    """Select contracts at the expiration closest to target DTE.

    Args:
        contracts: Pre-filtered contracts (any expirations).
        target_dte: Ideal days to expiration. Defaults to TARGET_DTE (45).

    Returns:
        Contracts at the single best expiration, or empty if none in range.
    """
    if not contracts:
        return []

    # Collect unique expirations with their DTE values
    expiration_dte: dict[datetime.date, int] = {}
    for contract in contracts:
        if contract.expiration not in expiration_dte:
            expiration_dte[contract.expiration] = contract.dte

    # Filter to valid DTE range
    valid_expirations: list[tuple[datetime.date, int]] = [
        (exp_date, dte) for exp_date, dte in expiration_dte.items() if MIN_DTE <= dte <= MAX_DTE
    ]

    if not valid_expirations:
        logger.debug(
            "select_expiration: no expirations in [%d, %d] DTE range",
            MIN_DTE,
            MAX_DTE,
        )
        return []

    # Pick expiration closest to target
    best_date, best_dte = min(valid_expirations, key=lambda pair: abs(pair[1] - target_dte))

    result = [c for c in contracts if c.expiration == best_date]
    logger.debug(
        "select_expiration: picked %s (DTE=%d, target=%d), %d contracts",
        best_date.isoformat(),
        best_dte,
        target_dte,
        len(result),
    )
    return result


def _get_greeks(
    contract: OptionContract,
    spot: float,
    risk_free_rate: float = RISK_FREE_RATE_FALLBACK,
) -> OptionGreeks | None:
    """Return existing Greeks or compute via BSM as fallback.

    When yfinance does not provide Greeks (the common case), uses the
    contract's implied_volatility and the spot price to compute BSM Greeks.

    Args:
        contract: The option contract.
        spot: Current underlying price.
        risk_free_rate: Annualized risk-free rate (defaults to 5%).

    Returns:
        OptionGreeks if available or computable, None otherwise.
    """
    if contract.greeks is not None:
        return contract.greeks

    # Need valid IV and DTE for BSM
    if contract.implied_volatility <= 0.0:
        return None
    time_to_expiry = contract.dte / DAYS_PER_YEAR
    if time_to_expiry <= 0.0:
        return None
    strike_f = float(contract.strike)
    if strike_f <= 0.0 or spot <= 0.0:
        return None

    try:
        return bsm_greeks(
            spot=spot,
            strike=strike_f,
            time_to_expiry=time_to_expiry,
            risk_free_rate=risk_free_rate,
            iv=contract.implied_volatility,
            option_type=contract.option_type,
        )
    except (ValueError, OverflowError, ZeroDivisionError):
        logger.debug(
            "BSM Greeks failed for %s strike %s: IV=%.4f, DTE=%d",
            contract.ticker,
            contract.strike,
            contract.implied_volatility,
            contract.dte,
        )
        return None


def select_by_delta(
    contracts: list[OptionContract],
    spot: float | None = None,
    risk_free_rate: float = RISK_FREE_RATE_FALLBACK,
) -> OptionContract | None:
    """Select the contract with delta closest to the target range.

    When contracts lack market Greeks (common with yfinance), computes
    BSM Greeks as a fallback using each contract's implied volatility.

    Args:
        contracts: Pre-filtered contracts (single expiration preferred).
        spot: Current underlying price for BSM fallback. If None, estimated
            from the first contract's mid price and strike.
        risk_free_rate: Annualized risk-free rate for BSM fallback.

    Returns:
        Best contract by delta proximity, or None if no contract has or can
        compute a delta within the target range.
    """
    if not contracts:
        return None

    # Estimate spot from contracts if not provided
    if spot is None:
        # Use the median strike as a rough proxy for ATM / spot price
        sorted_strikes = sorted(float(c.strike) for c in contracts)
        spot = sorted_strikes[len(sorted_strikes) // 2]

    candidates: list[tuple[OptionContract, float]] = []
    for contract in contracts:
        greeks = _get_greeks(contract, spot, risk_free_rate)
        if greeks is None:
            continue
        # For puts, use abs(delta) to compare against target
        abs_delta = abs(greeks.delta) if contract.option_type == OptionType.PUT else greeks.delta

        if DEFAULT_DELTA_TARGET_LOW <= abs_delta <= DEFAULT_DELTA_TARGET_HIGH:
            distance = abs(abs_delta - DEFAULT_DELTA_TARGET)
            candidates.append((contract, distance))

    if not candidates:
        logger.debug("select_by_delta: no contracts with delta in target range")
        return None

    best_contract, best_distance = min(candidates, key=lambda pair: pair[1])
    best_greeks = _get_greeks(best_contract, spot, risk_free_rate)
    logger.debug(
        "select_by_delta: selected strike=%s, delta=%.4f (distance=%.4f, source=%s)",
        best_contract.strike,
        best_greeks.delta if best_greeks else 0.0,
        best_distance,
        "market" if best_contract.greeks is not None else "bsm",
    )
    return best_contract


def recommend_contract(
    contracts: list[OptionContract],
    direction: SignalDirection,
    spot: float | None = None,
) -> OptionContract | None:
    """Run the full recommendation pipeline: filter, select delta.

    The service layer already selects the best expiration, so this function
    only applies liquidity filtering and delta selection.  BSM Greeks are
    computed as a fallback when market Greeks are unavailable.

    Args:
        contracts: Pre-filtered contracts from the service (single expiration).
        direction: Market direction signal.
        spot: Current underlying price for BSM delta computation.

    Returns:
        Single best contract recommendation, or None if no contract qualifies.
    """
    filtered = filter_contracts(contracts, direction)
    if not filtered:
        logger.info("recommend_contract: no contracts passed filtering")
        return None

    # The service already selected the best expiration and may have fallen
    # back to one outside the strict [30, 60] DTE range.  Skip the
    # redundant DTE filter here to avoid discarding valid fallback picks.

    best = select_by_delta(filtered, spot=spot)
    if best is None:
        logger.info("recommend_contract: no contracts matched delta target")
    return best
