"""Black-Scholes-Merton option pricing and Greeks computation.

Implements the standard BSM model for European-style options:
- Option pricing (calls and puts)
- Full Greeks computation (delta, gamma, theta, vega, rho)
- Implied volatility solver (Newton-Raphson with bisection fallback)

References:
    Hull, J.C. "Options, Futures, and Other Derivatives" (11th ed.)
    Chapter 15: The Black-Scholes-Merton Model
"""

import logging
import math

from scipy.stats import norm

from Option_Alpha.models.enums import OptionType
from Option_Alpha.models.options import OptionGreeks

logger = logging.getLogger(__name__)

# --- BSM solver constants ---
BSM_MAX_ITERATIONS: int = 50
BSM_TOLERANCE: float = 1e-8
BSM_IV_LOWER_BOUND: float = 0.001
BSM_IV_UPPER_BOUND: float = 5.0
BSM_BISECTION_MAX_ITERATIONS: int = 100

# --- Theta normalization ---
DAYS_PER_YEAR: int = 365

# --- Newton-Raphson initial guess (typical ATM IV) ---
BSM_IV_INITIAL_GUESS: float = 0.30


def _d1(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    iv: float,
) -> float:
    """Compute d1 in the BSM formula.

    d1 = (ln(S/K) + (r + sigma^2/2) * T) / (sigma * sqrt(T))
    """
    numerator = math.log(spot / strike) + (risk_free_rate + iv * iv / 2.0) * time_to_expiry
    denominator = iv * math.sqrt(time_to_expiry)
    return numerator / denominator


def _d2(d1_value: float, iv: float, time_to_expiry: float) -> float:
    """Compute d2 in the BSM formula.

    d2 = d1 - sigma * sqrt(T)
    """
    return d1_value - iv * math.sqrt(time_to_expiry)


def bsm_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    iv: float,
    option_type: OptionType,
) -> float:
    """Compute the Black-Scholes-Merton price of a European option.

    Args:
        spot: Current underlying price (S).
        strike: Option strike price (K).
        time_to_expiry: Time to expiration in years (T). Must be > 0.
        risk_free_rate: Annualized risk-free interest rate (r).
        iv: Implied volatility (sigma). Must be > 0.
        option_type: CALL or PUT.

    Returns:
        The theoretical option price.

    Raises:
        ValueError: If time_to_expiry <= 0 or iv <= 0.
    """
    _validate_inputs(spot, strike, time_to_expiry, iv)

    d1_val = _d1(spot, strike, time_to_expiry, risk_free_rate, iv)
    d2_val = _d2(d1_val, iv, time_to_expiry)
    discount_factor = math.exp(-risk_free_rate * time_to_expiry)

    if option_type == OptionType.CALL:
        price: float = spot * norm.cdf(d1_val) - strike * discount_factor * norm.cdf(d2_val)
    else:
        price = strike * discount_factor * norm.cdf(-d2_val) - spot * norm.cdf(-d1_val)

    return price


def bsm_greeks(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    iv: float,
    option_type: OptionType,
) -> OptionGreeks:
    """Compute full BSM Greeks for a European option.

    Args:
        spot: Current underlying price (S).
        strike: Option strike price (K).
        time_to_expiry: Time to expiration in years (T). Must be > 0.
        risk_free_rate: Annualized risk-free interest rate (r).
        iv: Implied volatility (sigma). Must be > 0.
        option_type: CALL or PUT.

    Returns:
        OptionGreeks model with delta, gamma, theta (per day), vega, and rho.

    Raises:
        ValueError: If time_to_expiry <= 0 or iv <= 0.
    """
    _validate_inputs(spot, strike, time_to_expiry, iv)

    d1_val = _d1(spot, strike, time_to_expiry, risk_free_rate, iv)
    d2_val = _d2(d1_val, iv, time_to_expiry)
    sqrt_t = math.sqrt(time_to_expiry)
    discount_factor = math.exp(-risk_free_rate * time_to_expiry)
    n_d1_pdf = norm.pdf(d1_val)

    # --- Gamma (same for calls and puts) ---
    gamma = n_d1_pdf / (spot * iv * sqrt_t)

    # --- Vega (same for calls and puts) ---
    # Standard vega is per 1.0 change in volatility
    vega = spot * n_d1_pdf * sqrt_t

    if option_type == OptionType.CALL:
        delta = float(norm.cdf(d1_val))
        # Annual theta for call
        theta_annual = -(spot * n_d1_pdf * iv) / (
            2.0 * sqrt_t
        ) - risk_free_rate * strike * discount_factor * float(norm.cdf(d2_val))
        rho = strike * time_to_expiry * discount_factor * float(norm.cdf(d2_val))
    else:
        delta = float(norm.cdf(d1_val)) - 1.0
        # Annual theta for put
        theta_annual = -(spot * n_d1_pdf * iv) / (
            2.0 * sqrt_t
        ) + risk_free_rate * strike * discount_factor * float(norm.cdf(-d2_val))
        rho = -strike * time_to_expiry * discount_factor * float(norm.cdf(-d2_val))

    # Convert theta from annual to per-day
    theta_daily = theta_annual / DAYS_PER_YEAR

    return OptionGreeks(
        delta=delta,
        gamma=float(gamma),
        theta=theta_daily,
        vega=float(vega),
        rho=rho,
    )


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float:
    """Solve for implied volatility using Newton-Raphson with bisection fallback.

    Uses Newton-Raphson iteration: vol -= (bsm_price - market_price) / vega.
    Falls back to bisection method if Newton-Raphson fails to converge.

    Args:
        market_price: Observed market price of the option.
        spot: Current underlying price (S).
        strike: Option strike price (K).
        time_to_expiry: Time to expiration in years (T). Must be > 0.
        risk_free_rate: Annualized risk-free interest rate (r).
        option_type: CALL or PUT.

    Returns:
        The implied volatility (annualized).

    Raises:
        ValueError: If the market price is below intrinsic value or IV cannot
            be determined within the allowed iteration limits.
    """
    if time_to_expiry <= 0:
        msg = f"time_to_expiry must be positive, got {time_to_expiry}"
        raise ValueError(msg)

    if market_price <= 0:
        msg = f"market_price must be positive, got {market_price}"
        raise ValueError(msg)

    # Check if market price is below the European lower bound.
    # For European options, the lower bound accounts for discounting:
    #   Call: max(S - K*e^(-rT), 0)
    #   Put:  max(K*e^(-rT) - S, 0)
    lower_bound = _european_lower_bound(spot, strike, time_to_expiry, risk_free_rate, option_type)
    if market_price < lower_bound - BSM_TOLERANCE:
        msg = (
            f"market_price ({market_price}) is below the European lower bound "
            f"({lower_bound}), IV cannot be determined"
        )
        raise ValueError(msg)

    # --- Newton-Raphson ---
    iv_estimate = _newton_raphson_iv(
        market_price, spot, strike, time_to_expiry, risk_free_rate, option_type
    )
    if iv_estimate is not None:
        return iv_estimate

    # --- Bisection fallback ---
    logger.info("Newton-Raphson did not converge, falling back to bisection method")
    iv_estimate = _bisection_iv(
        market_price, spot, strike, time_to_expiry, risk_free_rate, option_type
    )
    if iv_estimate is not None:
        return iv_estimate

    msg = (
        f"Implied volatility solver did not converge after "
        f"{BSM_MAX_ITERATIONS} Newton-Raphson and "
        f"{BSM_BISECTION_MAX_ITERATIONS} bisection iterations"
    )
    raise ValueError(msg)


def _validate_inputs(
    spot: float,
    strike: float,
    time_to_expiry: float,
    iv: float,
) -> None:
    """Validate common BSM inputs.

    Raises:
        ValueError: If any input is out of valid range.
    """
    if spot <= 0:
        msg = f"spot must be positive, got {spot}"
        raise ValueError(msg)
    if strike <= 0:
        msg = f"strike must be positive, got {strike}"
        raise ValueError(msg)
    if time_to_expiry <= 0:
        msg = f"time_to_expiry must be positive, got {time_to_expiry}"
        raise ValueError(msg)
    if iv <= 0:
        msg = f"iv must be positive, got {iv}"
        raise ValueError(msg)


def _european_lower_bound(
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float:
    """Compute the European option lower bound (no-arbitrage).

    For European options the lower bound accounts for discounting:
      Call: max(S - K * e^(-rT), 0)
      Put:  max(K * e^(-rT) - S, 0)
    """
    discount_factor = math.exp(-risk_free_rate * time_to_expiry)
    if option_type == OptionType.CALL:
        return max(spot - strike * discount_factor, 0.0)
    return max(strike * discount_factor - spot, 0.0)


def _newton_raphson_iv(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float | None:
    """Attempt to solve IV using Newton-Raphson iteration.

    Returns the IV estimate if converged, or None if it failed.
    """
    vol = BSM_IV_INITIAL_GUESS

    for _ in range(BSM_MAX_ITERATIONS):
        try:
            price = bsm_price(spot, strike, time_to_expiry, risk_free_rate, vol, option_type)
            diff = price - market_price

            if abs(diff) < BSM_TOLERANCE:
                return vol

            # Vega for Newton-Raphson step
            d1_val = _d1(spot, strike, time_to_expiry, risk_free_rate, vol)
            sqrt_t = math.sqrt(time_to_expiry)
            vega = spot * norm.pdf(d1_val) * sqrt_t

            if vega < BSM_TOLERANCE:
                # Vega too small for reliable Newton-Raphson — fall back
                return None

            vol = vol - diff / vega

            # Clamp to valid range
            if vol <= BSM_IV_LOWER_BOUND or vol >= BSM_IV_UPPER_BOUND:
                return None

        except (ValueError, ZeroDivisionError, OverflowError):
            return None

    return None


def _bisection_iv(
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float,
    option_type: OptionType,
) -> float | None:
    """Attempt to solve IV using bisection method.

    Returns the IV estimate if converged, or None if it failed.
    """
    low = BSM_IV_LOWER_BOUND
    high = BSM_IV_UPPER_BOUND

    # Verify that the root is bracketed
    try:
        price_low = bsm_price(spot, strike, time_to_expiry, risk_free_rate, low, option_type)
        price_high = bsm_price(spot, strike, time_to_expiry, risk_free_rate, high, option_type)
    except (ValueError, OverflowError):
        return None

    if (price_low - market_price) * (price_high - market_price) > 0:
        # Root is not bracketed — cannot solve
        return None

    for _ in range(BSM_BISECTION_MAX_ITERATIONS):
        mid = (low + high) / 2.0

        try:
            price_mid = bsm_price(spot, strike, time_to_expiry, risk_free_rate, mid, option_type)
        except (ValueError, OverflowError):
            return None

        diff = price_mid - market_price

        if abs(diff) < BSM_TOLERANCE:
            return mid

        if diff > 0:
            high = mid
        else:
            low = mid

    # Return best estimate after max iterations
    return (low + high) / 2.0
