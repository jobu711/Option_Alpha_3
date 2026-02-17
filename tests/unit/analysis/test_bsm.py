"""Tests for Black-Scholes-Merton option pricing and Greeks.

Reference values sourced from:
    Hull, J.C. "Options, Futures, and Other Derivatives" (11th ed.)
    Chapter 15, Examples 15.6 and related tables.

    Standard BSM reference case: S=100, K=100, T=1.0, r=0.05, sigma=0.20
    - Call price ~ 10.4506
    - Put price  ~  5.5735
    - Call delta  ~  0.6368
    - Put delta   ~ -0.3632
"""

import math

import pytest
from pydantic import ValidationError

from Option_Alpha.analysis.bsm import (
    BSM_BISECTION_MAX_ITERATIONS,
    BSM_IV_LOWER_BOUND,
    BSM_IV_UPPER_BOUND,
    BSM_MAX_ITERATIONS,
    BSM_TOLERANCE,
    DAYS_PER_YEAR,
    bsm_greeks,
    bsm_price,
    implied_volatility,
)
from Option_Alpha.models.enums import OptionType
from Option_Alpha.models.options import OptionGreeks

# --- Standard BSM reference parameters (Hull Ch.15) ---
REF_SPOT: float = 100.0
REF_STRIKE: float = 100.0
REF_TIME: float = 1.0
REF_RATE: float = 0.05
REF_IV: float = 0.20

# Expected values from Hull (11th ed.) for ATM European options
REF_CALL_PRICE: float = 10.4506
REF_PUT_PRICE: float = 5.5735
REF_CALL_DELTA: float = 0.6368
REF_PUT_DELTA: float = -0.3632


class TestConstants:
    """Verify module-level constants are defined correctly."""

    def test_max_iterations(self) -> None:
        assert BSM_MAX_ITERATIONS == 50

    def test_tolerance(self) -> None:
        assert pytest.approx(1e-8) == BSM_TOLERANCE

    def test_iv_lower_bound(self) -> None:
        assert pytest.approx(0.001) == BSM_IV_LOWER_BOUND

    def test_iv_upper_bound(self) -> None:
        assert pytest.approx(5.0) == BSM_IV_UPPER_BOUND

    def test_bisection_max_iterations(self) -> None:
        assert BSM_BISECTION_MAX_ITERATIONS == 100

    def test_days_per_year(self) -> None:
        assert DAYS_PER_YEAR == 365


class TestBsmPrice:
    """Tests for bsm_price() — option pricing."""

    def test_call_price_hull_reference(self) -> None:
        """ATM call price matches Hull reference value.

        Reference: Hull, "Options, Futures, and Other Derivatives" (11th ed.)
        S=100, K=100, T=1.0, r=0.05, sigma=0.20 -> Call ~ 10.4506
        """
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert price == pytest.approx(REF_CALL_PRICE, rel=1e-4)

    def test_put_price_hull_reference(self) -> None:
        """ATM put price matches Hull reference value.

        Reference: Hull, "Options, Futures, and Other Derivatives" (11th ed.)
        S=100, K=100, T=1.0, r=0.05, sigma=0.20 -> Put ~ 5.5735
        """
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert price == pytest.approx(REF_PUT_PRICE, rel=1e-4)

    def test_put_call_parity(self) -> None:
        """Put-call parity: C - P = S - K * e^(-rT).

        This is a fundamental arbitrage relationship that any correct
        BSM implementation must satisfy.
        """
        call_price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        put_price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)

        parity_rhs = REF_SPOT - REF_STRIKE * math.exp(-REF_RATE * REF_TIME)
        assert call_price - put_price == pytest.approx(parity_rhs, rel=1e-8)

    @pytest.mark.parametrize(
        ("spot", "strike", "time_to_expiry", "rate", "iv", "option_type"),
        [
            (50.0, 100.0, 1.0, 0.05, 0.20, OptionType.CALL),  # Deep OTM call
            (150.0, 100.0, 1.0, 0.05, 0.20, OptionType.CALL),  # Deep ITM call
            (100.0, 100.0, 0.01, 0.05, 0.20, OptionType.CALL),  # Near expiry call
            (50.0, 100.0, 1.0, 0.05, 0.20, OptionType.PUT),  # Deep ITM put
            (150.0, 100.0, 1.0, 0.05, 0.20, OptionType.PUT),  # Deep OTM put
            (100.0, 100.0, 0.01, 0.05, 0.20, OptionType.PUT),  # Near expiry put
        ],
        ids=[
            "deep_otm_call",
            "deep_itm_call",
            "near_expiry_call",
            "deep_itm_put",
            "deep_otm_put",
            "near_expiry_put",
        ],
    )
    def test_put_call_parity_parametrized(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        iv: float,
        option_type: OptionType,
    ) -> None:
        """Put-call parity holds for various moneyness levels."""
        call_price = bsm_price(spot, strike, time_to_expiry, rate, iv, OptionType.CALL)
        put_price = bsm_price(spot, strike, time_to_expiry, rate, iv, OptionType.PUT)

        parity_rhs = spot - strike * math.exp(-rate * time_to_expiry)
        assert call_price - put_price == pytest.approx(parity_rhs, rel=1e-6)

    def test_call_price_non_negative(self) -> None:
        """Call price is always non-negative."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert price >= 0.0

    def test_put_price_non_negative(self) -> None:
        """Put price is always non-negative."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert price >= 0.0

    def test_deep_itm_call_near_intrinsic(self) -> None:
        """Deep ITM call price approaches intrinsic value (S - K)."""
        spot = 200.0
        strike = 100.0
        intrinsic = spot - strike
        price = bsm_price(spot, strike, 0.01, REF_RATE, REF_IV, OptionType.CALL)
        # With very little time, price should be close to intrinsic
        assert price == pytest.approx(intrinsic, rel=0.01)

    def test_deep_otm_call_near_zero(self) -> None:
        """Deep OTM call price approaches zero."""
        price = bsm_price(50.0, 200.0, 0.1, REF_RATE, REF_IV, OptionType.CALL)
        assert price == pytest.approx(0.0, abs=0.01)

    def test_higher_iv_increases_price(self) -> None:
        """Higher implied volatility increases option price (all else equal)."""
        price_low_iv = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 0.10, OptionType.CALL)
        price_high_iv = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 0.40, OptionType.CALL)
        assert price_high_iv > price_low_iv

    def test_longer_time_increases_call_price(self) -> None:
        """Longer time to expiry generally increases European call value."""
        price_short = bsm_price(REF_SPOT, REF_STRIKE, 0.1, REF_RATE, REF_IV, OptionType.CALL)
        price_long = bsm_price(REF_SPOT, REF_STRIKE, 2.0, REF_RATE, REF_IV, OptionType.CALL)
        assert price_long > price_short


class TestBsmPriceValidation:
    """Tests for input validation in bsm_price()."""

    def test_negative_spot_raises(self) -> None:
        with pytest.raises(ValueError, match="spot must be positive"):
            bsm_price(-100.0, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)

    def test_zero_spot_raises(self) -> None:
        with pytest.raises(ValueError, match="spot must be positive"):
            bsm_price(0.0, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)

    def test_negative_strike_raises(self) -> None:
        with pytest.raises(ValueError, match="strike must be positive"):
            bsm_price(REF_SPOT, -100.0, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)

    def test_zero_time_raises(self) -> None:
        with pytest.raises(ValueError, match="time_to_expiry must be positive"):
            bsm_price(REF_SPOT, REF_STRIKE, 0.0, REF_RATE, REF_IV, OptionType.CALL)

    def test_negative_time_raises(self) -> None:
        with pytest.raises(ValueError, match="time_to_expiry must be positive"):
            bsm_price(REF_SPOT, REF_STRIKE, -1.0, REF_RATE, REF_IV, OptionType.CALL)

    def test_zero_iv_raises(self) -> None:
        with pytest.raises(ValueError, match="iv must be positive"):
            bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 0.0, OptionType.CALL)

    def test_negative_iv_raises(self) -> None:
        with pytest.raises(ValueError, match="iv must be positive"):
            bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, -0.20, OptionType.CALL)


class TestBsmGreeks:
    """Tests for bsm_greeks() — full Greeks computation."""

    def test_call_delta_hull_reference(self) -> None:
        """ATM call delta matches Hull reference.

        Reference: Hull (11th ed.), S=100, K=100, T=1.0, r=0.05, sigma=0.20
        Call delta ~ 0.6368
        """
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.delta == pytest.approx(REF_CALL_DELTA, rel=1e-4)

    def test_put_delta_hull_reference(self) -> None:
        """ATM put delta matches Hull reference.

        Reference: Hull (11th ed.), S=100, K=100, T=1.0, r=0.05, sigma=0.20
        Put delta ~ -0.3632
        """
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert greeks.delta == pytest.approx(REF_PUT_DELTA, rel=1e-4)

    def test_returns_option_greeks_model(self) -> None:
        """bsm_greeks returns a proper OptionGreeks Pydantic model."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)

    def test_call_delta_put_delta_sum_to_one(self) -> None:
        """Call delta - put delta = 1.0 (BSM identity)."""
        call_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        put_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert call_greeks.delta - put_greeks.delta == pytest.approx(1.0, rel=1e-8)

    def test_gamma_same_for_call_and_put(self) -> None:
        """Gamma is identical for calls and puts on the same underlying."""
        call_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        put_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert call_greeks.gamma == pytest.approx(put_greeks.gamma, rel=1e-8)

    def test_vega_same_for_call_and_put(self) -> None:
        """Vega is identical for calls and puts on the same underlying."""
        call_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        put_greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert call_greeks.vega == pytest.approx(put_greeks.vega, rel=1e-8)

    def test_gamma_non_negative(self) -> None:
        """Gamma must be >= 0 for all options."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.gamma >= 0.0

    def test_vega_non_negative(self) -> None:
        """Vega must be >= 0 for all options."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.vega >= 0.0

    def test_call_delta_in_valid_range(self) -> None:
        """Call delta must be in [0, 1]."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert 0.0 <= greeks.delta <= 1.0

    def test_put_delta_in_valid_range(self) -> None:
        """Put delta must be in [-1, 0]."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert -1.0 <= greeks.delta <= 0.0

    def test_theta_is_daily(self) -> None:
        """Theta is expressed per day (annual / 365)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        # Theta should be small (per-day), not large (per-year)
        # For ATM option with T=1, daily theta is typically small
        assert abs(greeks.theta) < 1.0

    def test_call_theta_usually_negative(self) -> None:
        """ATM call theta is typically negative (time decay costs money)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.theta < 0.0

    def test_put_theta_usually_negative(self) -> None:
        """ATM put theta is typically negative (time decay costs money)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert greeks.theta < 0.0

    def test_deep_itm_call_delta_near_one(self) -> None:
        """Deep ITM call delta approaches 1.0."""
        greeks = bsm_greeks(150.0, 100.0, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.delta == pytest.approx(1.0, abs=0.05)

    def test_deep_otm_call_delta_near_zero(self) -> None:
        """Deep OTM call delta approaches 0.0."""
        greeks = bsm_greeks(50.0, 100.0, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.delta == pytest.approx(0.0, abs=0.05)

    def test_deep_itm_put_delta_near_negative_one(self) -> None:
        """Deep ITM put delta approaches -1.0."""
        greeks = bsm_greeks(50.0, 100.0, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert greeks.delta == pytest.approx(-1.0, abs=0.05)

    def test_deep_otm_put_delta_near_zero(self) -> None:
        """Deep OTM put delta approaches 0.0."""
        greeks = bsm_greeks(150.0, 100.0, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert greeks.delta == pytest.approx(0.0, abs=0.05)

    def test_near_expiry_atm_high_gamma(self) -> None:
        """Near-expiry ATM options have very high gamma."""
        near_expiry_greeks = bsm_greeks(
            REF_SPOT, REF_STRIKE, 0.01, REF_RATE, REF_IV, OptionType.CALL
        )
        far_expiry_greeks = bsm_greeks(
            REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL
        )
        assert near_expiry_greeks.gamma > far_expiry_greeks.gamma

    def test_near_expiry_rapid_theta_decay(self) -> None:
        """Near-expiry options have more rapid theta decay (more negative daily theta)."""
        near_expiry_greeks = bsm_greeks(
            REF_SPOT, REF_STRIKE, 0.01, REF_RATE, REF_IV, OptionType.CALL
        )
        far_expiry_greeks = bsm_greeks(
            REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL
        )
        # Near-expiry daily theta should be more negative
        assert near_expiry_greeks.theta < far_expiry_greeks.theta

    def test_call_rho_positive(self) -> None:
        """Call rho is positive (higher rates increase call value)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.rho > 0.0

    def test_put_rho_negative(self) -> None:
        """Put rho is negative (higher rates decrease put value)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.PUT)
        assert greeks.rho < 0.0

    @pytest.mark.parametrize("option_type", [OptionType.CALL, OptionType.PUT])
    def test_greeks_model_validates(self, option_type: OptionType) -> None:
        """Returned OptionGreeks passes Pydantic validation (delta in range, etc.)."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, option_type)
        # If validation fails, OptionGreeks constructor raises ValueError
        assert isinstance(greeks, OptionGreeks)

    @pytest.mark.parametrize(
        ("spot", "strike"),
        [
            (80.0, 100.0),
            (90.0, 100.0),
            (100.0, 100.0),
            (110.0, 100.0),
            (120.0, 100.0),
        ],
        ids=["otm", "slightly_otm", "atm", "slightly_itm", "itm"],
    )
    def test_gamma_positive_across_moneyness(self, spot: float, strike: float) -> None:
        """Gamma is always positive regardless of moneyness."""
        greeks = bsm_greeks(spot, strike, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.gamma > 0.0

    @pytest.mark.parametrize(
        ("spot", "strike"),
        [
            (80.0, 100.0),
            (90.0, 100.0),
            (100.0, 100.0),
            (110.0, 100.0),
            (120.0, 100.0),
        ],
        ids=["otm", "slightly_otm", "atm", "slightly_itm", "itm"],
    )
    def test_vega_positive_across_moneyness(self, spot: float, strike: float) -> None:
        """Vega is always positive regardless of moneyness."""
        greeks = bsm_greeks(spot, strike, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert greeks.vega > 0.0

    def test_greeks_frozen_immutable(self) -> None:
        """OptionGreeks model is frozen — attributes cannot be modified."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        with pytest.raises(ValidationError):
            greeks.delta = 0.5  # type: ignore[misc]


class TestBsmGreeksValidation:
    """Input validation tests for bsm_greeks()."""

    def test_negative_spot_raises(self) -> None:
        with pytest.raises(ValueError, match="spot must be positive"):
            bsm_greeks(-100.0, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)

    def test_zero_time_raises(self) -> None:
        with pytest.raises(ValueError, match="time_to_expiry must be positive"):
            bsm_greeks(REF_SPOT, REF_STRIKE, 0.0, REF_RATE, REF_IV, OptionType.CALL)

    def test_zero_iv_raises(self) -> None:
        with pytest.raises(ValueError, match="iv must be positive"):
            bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 0.0, OptionType.CALL)


class TestImpliedVolatility:
    """Tests for implied_volatility() — Newton-Raphson with bisection fallback."""

    def test_roundtrip_atm_call(self) -> None:
        """Compute price with known IV, then solve back to recover the same IV."""
        known_iv = 0.25
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, known_iv, OptionType.CALL)

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-4)

    def test_roundtrip_atm_put(self) -> None:
        """Round-trip IV for ATM put."""
        known_iv = 0.25
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, known_iv, OptionType.PUT)

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.PUT
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-4)

    @pytest.mark.parametrize(
        "known_iv",
        [0.05, 0.10, 0.20, 0.30, 0.50, 0.80, 1.0, 1.5, 2.0],
        ids=[
            "iv_5pct",
            "iv_10pct",
            "iv_20pct",
            "iv_30pct",
            "iv_50pct",
            "iv_80pct",
            "iv_100pct",
            "iv_150pct",
            "iv_200pct",
        ],
    )
    def test_roundtrip_various_ivs_call(self, known_iv: float) -> None:
        """Round-trip for various volatility levels (call)."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, known_iv, OptionType.CALL)

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    @pytest.mark.parametrize(
        "known_iv",
        [0.05, 0.10, 0.20, 0.30, 0.50, 0.80, 1.0, 1.5, 2.0],
        ids=[
            "iv_5pct",
            "iv_10pct",
            "iv_20pct",
            "iv_30pct",
            "iv_50pct",
            "iv_80pct",
            "iv_100pct",
            "iv_150pct",
            "iv_200pct",
        ],
    )
    def test_roundtrip_various_ivs_put(self, known_iv: float) -> None:
        """Round-trip for various volatility levels (put)."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, known_iv, OptionType.PUT)

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.PUT
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_roundtrip_deep_itm_call(self) -> None:
        """Round-trip IV for deep ITM call (may require bisection)."""
        known_iv = 0.20
        spot = 150.0
        strike = 100.0
        price = bsm_price(spot, strike, REF_TIME, REF_RATE, known_iv, OptionType.CALL)

        solved_iv = implied_volatility(price, spot, strike, REF_TIME, REF_RATE, OptionType.CALL)
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_roundtrip_deep_otm_call(self) -> None:
        """Round-trip IV for deep OTM call (may require bisection)."""
        known_iv = 0.30
        spot = 80.0
        strike = 120.0
        price = bsm_price(spot, strike, REF_TIME, REF_RATE, known_iv, OptionType.CALL)

        solved_iv = implied_volatility(price, spot, strike, REF_TIME, REF_RATE, OptionType.CALL)
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_roundtrip_deep_itm_put(self) -> None:
        """Round-trip IV for deep ITM put."""
        known_iv = 0.20
        spot = 70.0
        strike = 100.0
        price = bsm_price(spot, strike, REF_TIME, REF_RATE, known_iv, OptionType.PUT)

        solved_iv = implied_volatility(price, spot, strike, REF_TIME, REF_RATE, OptionType.PUT)
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_roundtrip_short_expiry(self) -> None:
        """Round-trip IV for short time to expiry."""
        known_iv = 0.25
        time_to_expiry = 0.05  # About 18 days
        price = bsm_price(
            REF_SPOT, REF_STRIKE, time_to_expiry, REF_RATE, known_iv, OptionType.CALL
        )

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, time_to_expiry, REF_RATE, OptionType.CALL
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_roundtrip_high_iv(self) -> None:
        """Round-trip IV for high volatility (e.g., meme stocks)."""
        known_iv = 3.0
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, known_iv, OptionType.CALL)

        solved_iv = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL
        )
        assert solved_iv == pytest.approx(known_iv, rel=1e-3)

    def test_market_price_below_lower_bound_raises(self) -> None:
        """Market price below European lower bound should raise ValueError."""
        # For a call with S=120, K=100, T=1, r=0.05:
        # European lower bound = max(120 - 100*e^(-0.05), 0) ~ 24.88
        # A market price of 15 is below the lower bound
        with pytest.raises(ValueError, match="below the European lower bound"):
            implied_volatility(15.0, 120.0, 100.0, REF_TIME, REF_RATE, OptionType.CALL)

    def test_zero_market_price_raises(self) -> None:
        """Zero market price should raise ValueError."""
        with pytest.raises(ValueError, match="market_price must be positive"):
            implied_volatility(0.0, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL)

    def test_negative_market_price_raises(self) -> None:
        """Negative market price should raise ValueError."""
        with pytest.raises(ValueError, match="market_price must be positive"):
            implied_volatility(-1.0, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL)

    def test_zero_time_raises(self) -> None:
        """Zero time to expiry should raise ValueError."""
        with pytest.raises(ValueError, match="time_to_expiry must be positive"):
            implied_volatility(5.0, REF_SPOT, REF_STRIKE, 0.0, REF_RATE, OptionType.CALL)

    def test_negative_time_raises(self) -> None:
        """Negative time to expiry should raise ValueError."""
        with pytest.raises(ValueError, match="time_to_expiry must be positive"):
            implied_volatility(5.0, REF_SPOT, REF_STRIKE, -1.0, REF_RATE, OptionType.CALL)

    def test_returns_float(self) -> None:
        """implied_volatility returns a float."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        result = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL
        )
        assert isinstance(result, float)

    def test_iv_result_positive(self) -> None:
        """Solved IV must be positive."""
        price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        result = implied_volatility(
            price, REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, OptionType.CALL
        )
        assert result > 0.0


class TestBsmNumericalProperties:
    """Tests for numerical stability and edge-case behavior."""

    def test_very_small_time_to_expiry(self) -> None:
        """Near-zero time to expiry produces valid results."""
        small_t = 0.001  # ~8.76 hours
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, small_t, REF_RATE, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)
        assert -1.0 <= greeks.delta <= 1.0
        assert greeks.gamma >= 0.0
        assert greeks.vega >= 0.0

    def test_very_high_iv(self) -> None:
        """Very high IV (e.g., 400%) produces valid Greeks."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 4.0, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)
        assert 0.0 <= greeks.delta <= 1.0

    def test_very_low_iv(self) -> None:
        """Very low IV produces valid Greeks."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, REF_RATE, 0.01, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)
        assert 0.0 <= greeks.delta <= 1.0

    def test_zero_interest_rate(self) -> None:
        """Zero risk-free rate produces valid results."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, 0.0, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)

    def test_negative_interest_rate(self) -> None:
        """Negative risk-free rate (like some EUR/JPY periods) produces valid results."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, REF_TIME, -0.01, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)

    def test_large_spot_strike_ratio(self) -> None:
        """Very large S/K ratio doesn't cause overflow."""
        greeks = bsm_greeks(1000.0, 10.0, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)

    def test_small_spot_strike_ratio(self) -> None:
        """Very small S/K ratio doesn't cause underflow."""
        greeks = bsm_greeks(10.0, 1000.0, REF_TIME, REF_RATE, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)

    def test_put_call_parity_with_zero_rate(self) -> None:
        """Put-call parity holds when r=0: C - P = S - K."""
        rate = 0.0
        call_price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, rate, REF_IV, OptionType.CALL)
        put_price = bsm_price(REF_SPOT, REF_STRIKE, REF_TIME, rate, REF_IV, OptionType.PUT)
        expected_diff = REF_SPOT - REF_STRIKE  # 0.0 when ATM
        assert call_price - put_price == pytest.approx(expected_diff, rel=1e-8)

    def test_long_dated_option(self) -> None:
        """Long-dated option (LEAPS, T=3 years) produces valid results."""
        greeks = bsm_greeks(REF_SPOT, REF_STRIKE, 3.0, REF_RATE, REF_IV, OptionType.CALL)
        assert isinstance(greeks, OptionGreeks)
        assert 0.0 <= greeks.delta <= 1.0
        assert greeks.gamma >= 0.0
        assert greeks.vega >= 0.0
