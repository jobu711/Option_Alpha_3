"""Contract filtering and recommendation engine.

Filters options contracts by liquidity, spread width, and directional fit,
then selects the best expiration and delta target for a single recommendation.
"""

import datetime
import logging
from decimal import Decimal

from Option_Alpha.models.enums import OptionType, SignalDirection
from Option_Alpha.models.options import OptionContract

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


def select_by_delta(
    contracts: list[OptionContract],
) -> OptionContract | None:
    """Select the contract with delta closest to the target range.

    Args:
        contracts: Pre-filtered contracts (single expiration preferred).

    Returns:
        Best contract by delta proximity, or None if no contract has greeks
        or no delta falls within [DEFAULT_DELTA_TARGET_LOW, DEFAULT_DELTA_TARGET_HIGH].
    """
    candidates: list[tuple[OptionContract, float]] = []
    for contract in contracts:
        if contract.greeks is None:
            continue
        # For puts, use abs(delta) to compare against target
        if contract.option_type == OptionType.PUT:
            abs_delta = abs(contract.greeks.delta)
        else:
            abs_delta = contract.greeks.delta

        if DEFAULT_DELTA_TARGET_LOW <= abs_delta <= DEFAULT_DELTA_TARGET_HIGH:
            distance = abs(abs_delta - DEFAULT_DELTA_TARGET)
            candidates.append((contract, distance))

    if not candidates:
        logger.debug("select_by_delta: no contracts with delta in target range")
        return None

    best_contract, best_distance = min(candidates, key=lambda pair: pair[1])
    logger.debug(
        "select_by_delta: selected strike=%s, delta=%.4f (distance=%.4f)",
        best_contract.strike,
        best_contract.greeks.delta if best_contract.greeks else 0.0,
        best_distance,
    )
    return best_contract


def recommend_contract(
    contracts: list[OptionContract],
    direction: SignalDirection,
) -> OptionContract | None:
    """Run the full recommendation pipeline: filter, select expiration, select delta.

    Args:
        contracts: Raw list of option contracts.
        direction: Market direction signal.

    Returns:
        Single best contract recommendation, or None if no contract qualifies.
    """
    filtered = filter_contracts(contracts, direction)
    if not filtered:
        logger.info("recommend_contract: no contracts passed filtering")
        return None

    at_expiration = select_expiration(filtered)
    if not at_expiration:
        logger.info("recommend_contract: no contracts in target DTE range")
        return None

    best = select_by_delta(at_expiration)
    if best is None:
        logger.info("recommend_contract: no contracts matched delta target")
    return best
