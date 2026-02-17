"""Tests for options models: OptionGreeks, OptionContract, SpreadLeg, OptionSpread.

Covers:
- JSON roundtrip for all models
- Greek range validation (delta, gamma, vega)
- Valid Greeks at boundary values
- OptionContract computed fields (mid, spread, dte)
- Mock date.today() for DTE tests
- Decimal precision survives roundtrip
- Frozen immutability
- OptionSpread with multiple legs
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from Option_Alpha.models.enums import OptionType, PositionSide, SpreadType
from Option_Alpha.models.options import (
    OptionContract,
    OptionGreeks,
    OptionSpread,
    SpreadLeg,
)


class TestOptionGreeks:
    """Tests for OptionGreeks validation and serialization."""

    def test_valid_construction(self, sample_option_greeks: OptionGreeks) -> None:
        """OptionGreeks can be constructed with valid data."""
        assert sample_option_greeks.delta == pytest.approx(0.45, rel=1e-4)
        assert sample_option_greeks.gamma == pytest.approx(0.05, rel=1e-4)
        assert sample_option_greeks.theta == pytest.approx(-0.08, rel=1e-4)
        assert sample_option_greeks.vega == pytest.approx(0.12, rel=1e-4)
        assert sample_option_greeks.rho == pytest.approx(0.01, rel=1e-4)

    def test_json_roundtrip(self, sample_option_greeks: OptionGreeks) -> None:
        """OptionGreeks survives a full JSON serialize/deserialize cycle."""
        json_str = sample_option_greeks.model_dump_json()
        restored = OptionGreeks.model_validate_json(json_str)
        assert restored.delta == pytest.approx(sample_option_greeks.delta, rel=1e-4)
        assert restored.gamma == pytest.approx(sample_option_greeks.gamma, rel=1e-4)
        assert restored.theta == pytest.approx(sample_option_greeks.theta, rel=1e-4)
        assert restored.vega == pytest.approx(sample_option_greeks.vega, rel=1e-4)
        assert restored.rho == pytest.approx(sample_option_greeks.rho, rel=1e-4)

    # --- Delta validation ---

    def test_delta_above_max_rejected(self) -> None:
        """Delta > 1.0 is rejected."""
        with pytest.raises(ValidationError, match="delta"):
            OptionGreeks(delta=1.01, gamma=0.05, theta=-0.08, vega=0.12, rho=0.01)

    def test_delta_below_min_rejected(self) -> None:
        """Delta < -1.0 is rejected."""
        with pytest.raises(ValidationError, match="delta"):
            OptionGreeks(delta=-1.01, gamma=0.05, theta=-0.08, vega=0.12, rho=0.01)

    def test_delta_at_max_boundary(self) -> None:
        """Delta = 1.0 is valid (deep ITM call)."""
        greeks = OptionGreeks(delta=1.0, gamma=0.0, theta=-0.01, vega=0.0, rho=0.01)
        assert greeks.delta == pytest.approx(1.0, rel=1e-4)

    def test_delta_at_min_boundary(self) -> None:
        """Delta = -1.0 is valid (deep ITM put)."""
        greeks = OptionGreeks(delta=-1.0, gamma=0.0, theta=-0.01, vega=0.0, rho=0.01)
        assert greeks.delta == pytest.approx(-1.0, rel=1e-4)

    def test_delta_zero(self) -> None:
        """Delta = 0.0 is valid (far OTM option)."""
        greeks = OptionGreeks(delta=0.0, gamma=0.0, theta=-0.001, vega=0.0, rho=0.0)
        assert greeks.delta == pytest.approx(0.0, rel=1e-4)

    # --- Gamma validation ---

    def test_gamma_negative_rejected(self) -> None:
        """Gamma < 0 is rejected."""
        with pytest.raises(ValidationError, match="gamma"):
            OptionGreeks(delta=0.5, gamma=-0.01, theta=-0.08, vega=0.12, rho=0.01)

    def test_gamma_zero_valid(self) -> None:
        """Gamma = 0.0 is valid (deep ITM or far OTM)."""
        greeks = OptionGreeks(delta=0.99, gamma=0.0, theta=-0.01, vega=0.01, rho=0.01)
        assert greeks.gamma == pytest.approx(0.0, rel=1e-4)

    # --- Vega validation ---

    def test_vega_negative_rejected(self) -> None:
        """Vega < 0 is rejected."""
        with pytest.raises(ValidationError, match="vega"):
            OptionGreeks(delta=0.5, gamma=0.05, theta=-0.08, vega=-0.01, rho=0.01)

    def test_vega_zero_valid(self) -> None:
        """Vega = 0.0 is valid (deep ITM near expiry)."""
        greeks = OptionGreeks(delta=0.99, gamma=0.0, theta=-0.5, vega=0.0, rho=0.01)
        assert greeks.vega == pytest.approx(0.0, rel=1e-4)

    # --- Theta and Rho (no validation boundaries) ---

    def test_theta_negative_valid(self) -> None:
        """Theta is usually negative (time decay costs money)."""
        greeks = OptionGreeks(delta=0.45, gamma=0.05, theta=-0.08, vega=0.12, rho=0.01)
        assert greeks.theta == pytest.approx(-0.08, rel=1e-4)

    def test_rho_negative_valid(self) -> None:
        """Rho can be negative (puts have negative rho)."""
        greeks = OptionGreeks(delta=-0.45, gamma=0.05, theta=-0.08, vega=0.12, rho=-0.02)
        assert greeks.rho == pytest.approx(-0.02, rel=1e-4)


class TestOptionContract:
    """Tests for OptionContract with computed fields and immutability."""

    def test_valid_construction(self, sample_option_contract: OptionContract) -> None:
        """OptionContract can be constructed with valid data."""
        assert sample_option_contract.ticker == "AAPL"
        assert sample_option_contract.option_type is OptionType.CALL
        assert sample_option_contract.strike == Decimal("185.00")
        assert sample_option_contract.volume == 1250
        assert sample_option_contract.open_interest == 8340
        assert sample_option_contract.implied_volatility == pytest.approx(0.28, rel=1e-4)
        assert sample_option_contract.greeks is not None

    def test_json_roundtrip(self, sample_option_contract: OptionContract) -> None:
        """OptionContract survives a full JSON serialize/deserialize cycle.

        Note: computed fields (mid, spread, dte) are included in serialization
        output but dte depends on date.today(), so we compare non-computed fields
        and check computed ones individually.
        """
        json_str = sample_option_contract.model_dump_json()
        restored = OptionContract.model_validate_json(json_str)
        # Compare non-computed fields
        assert restored.ticker == sample_option_contract.ticker
        assert restored.option_type is sample_option_contract.option_type
        assert restored.strike == sample_option_contract.strike
        assert restored.expiration == sample_option_contract.expiration
        assert restored.bid == sample_option_contract.bid
        assert restored.ask == sample_option_contract.ask
        assert restored.last == sample_option_contract.last
        assert restored.volume == sample_option_contract.volume
        assert restored.open_interest == sample_option_contract.open_interest
        assert restored.implied_volatility == pytest.approx(
            sample_option_contract.implied_volatility, rel=1e-4
        )

    def test_decimal_precision_survives_serialization(self) -> None:
        """Strike, bid, ask, last Decimal values maintain precision through JSON."""
        contract = OptionContract(
            ticker="TEST",
            option_type=OptionType.CALL,
            strike=Decimal("1.05"),
            expiration=datetime.date(2025, 3, 21),
            bid=Decimal("0.15"),
            ask=Decimal("0.17"),
            last=Decimal("0.16"),
            volume=100,
            open_interest=500,
            implied_volatility=0.30,
        )
        json_str = contract.model_dump_json()
        restored = OptionContract.model_validate_json(json_str)
        assert restored.strike == Decimal("1.05")
        assert restored.bid == Decimal("0.15")
        assert restored.ask == Decimal("0.17")
        assert restored.last == Decimal("0.16")
        assert "1.050000000000000" not in json_str

    def test_computed_mid_price(self, sample_option_contract: OptionContract) -> None:
        """Mid price is (bid + ask) / 2."""
        expected_mid = (Decimal("4.50") + Decimal("4.70")) / 2
        assert sample_option_contract.mid == expected_mid

    def test_computed_spread(self, sample_option_contract: OptionContract) -> None:
        """Spread is ask - bid."""
        expected_spread = Decimal("4.70") - Decimal("4.50")
        assert sample_option_contract.spread == expected_spread

    def test_computed_dte_with_mocked_today(self) -> None:
        """DTE is correctly calculated by mocking date.today().

        Never depend on actual current date -- mock it.
        """
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.50"),
            ask=Decimal("4.70"),
            last=Decimal("4.60"),
            volume=1000,
            open_interest=5000,
            implied_volatility=0.28,
        )
        # Mock date.today() in the options module to get deterministic DTE
        mock_today = datetime.date(2025, 1, 15)
        with patch("Option_Alpha.models.options.datetime") as mock_dt:
            mock_dt.date.today.return_value = mock_today
            # Also need real date class for the subtraction to work
            mock_dt.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
            expected_dte = (datetime.date(2025, 2, 21) - mock_today).days
            assert contract.dte == expected_dte
            assert contract.dte == 37

    def test_computed_dte_zero_at_expiration(self) -> None:
        """DTE is 0 when today equals expiration date."""
        expiration = datetime.date(2025, 2, 21)
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.PUT,
            strike=Decimal("180.00"),
            expiration=expiration,
            bid=Decimal("1.00"),
            ask=Decimal("1.20"),
            last=Decimal("1.10"),
            volume=500,
            open_interest=3000,
            implied_volatility=0.25,
        )
        with patch("Option_Alpha.models.options.datetime") as mock_dt:
            mock_dt.date.today.return_value = expiration
            mock_dt.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
            assert contract.dte == 0

    def test_computed_dte_negative_past_expiration(self) -> None:
        """DTE is negative when expiration is in the past."""
        expiration = datetime.date(2025, 1, 10)
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=expiration,
            bid=Decimal("0.01"),
            ask=Decimal("0.02"),
            last=Decimal("0.01"),
            volume=10,
            open_interest=100,
            implied_volatility=0.50,
        )
        with patch("Option_Alpha.models.options.datetime") as mock_dt:
            mock_dt.date.today.return_value = datetime.date(2025, 1, 15)
            mock_dt.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
            assert contract.dte == -5

    def test_frozen_immutability(self, sample_option_contract: OptionContract) -> None:
        """Assigning to a frozen model field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_option_contract.strike = Decimal("999.99")  # type: ignore[misc]

    def test_contract_without_greeks(self) -> None:
        """OptionContract is valid without Greeks (not all sources provide them)."""
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.50"),
            ask=Decimal("4.70"),
            last=Decimal("4.60"),
            volume=1000,
            open_interest=5000,
            implied_volatility=0.28,
        )
        assert contract.greeks is None
        assert contract.greeks_source is None

    def test_contract_with_greeks_source(self) -> None:
        """OptionContract can include greeks_source metadata."""
        from Option_Alpha.models.enums import GreeksSource

        greeks = OptionGreeks(delta=0.5, gamma=0.04, theta=-0.07, vega=0.11, rho=0.01)
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.50"),
            ask=Decimal("4.70"),
            last=Decimal("4.60"),
            volume=1000,
            open_interest=5000,
            implied_volatility=0.28,
            greeks=greeks,
            greeks_source=GreeksSource.MARKET,
        )
        assert contract.greeks_source is GreeksSource.MARKET


class TestSpreadLeg:
    """Tests for SpreadLeg model."""

    def test_valid_construction(self, sample_spread_leg: SpreadLeg) -> None:
        """SpreadLeg can be constructed with valid data."""
        assert sample_spread_leg.position is PositionSide.LONG
        assert sample_spread_leg.quantity == 1
        assert sample_spread_leg.contract.ticker == "AAPL"

    def test_json_roundtrip(self, sample_spread_leg: SpreadLeg) -> None:
        """SpreadLeg survives a full JSON serialize/deserialize cycle."""
        json_str = sample_spread_leg.model_dump_json()
        restored = SpreadLeg.model_validate_json(json_str)
        assert restored.position is sample_spread_leg.position
        assert restored.quantity == sample_spread_leg.quantity
        assert restored.contract.ticker == sample_spread_leg.contract.ticker
        assert restored.contract.strike == sample_spread_leg.contract.strike


class TestOptionSpread:
    """Tests for OptionSpread model."""

    def test_valid_construction(self, sample_option_spread: OptionSpread) -> None:
        """OptionSpread can be constructed with valid data."""
        assert sample_option_spread.spread_type is SpreadType.VERTICAL
        assert len(sample_option_spread.legs) == 2
        assert sample_option_spread.max_profit == Decimal("3.10")
        assert sample_option_spread.max_loss == Decimal("1.90")
        assert sample_option_spread.net_debit_credit == Decimal("1.90")
        assert sample_option_spread.pop == pytest.approx(0.55, abs=0.01)

    def test_json_roundtrip(self, sample_option_spread: OptionSpread) -> None:
        """OptionSpread survives a full JSON serialize/deserialize cycle."""
        json_str = sample_option_spread.model_dump_json()
        restored = OptionSpread.model_validate_json(json_str)
        assert restored.spread_type is sample_option_spread.spread_type
        assert len(restored.legs) == len(sample_option_spread.legs)
        assert restored.max_profit == sample_option_spread.max_profit
        assert restored.max_loss == sample_option_spread.max_loss
        assert restored.net_debit_credit == sample_option_spread.net_debit_credit
        assert len(restored.breakeven) == len(sample_option_spread.breakeven)
        assert restored.breakeven[0] == sample_option_spread.breakeven[0]

    def test_decimal_precision_on_spread_fields(self, sample_option_spread: OptionSpread) -> None:
        """Decimal fields on OptionSpread survive JSON roundtrip."""
        json_str = sample_option_spread.model_dump_json()
        restored = OptionSpread.model_validate_json(json_str)
        assert restored.max_profit == Decimal("3.10")
        assert restored.max_loss == Decimal("1.90")
        assert restored.net_debit_credit == Decimal("1.90")
        assert restored.breakeven == [Decimal("186.90")]

    def test_none_max_profit_and_loss(self) -> None:
        """max_profit and max_loss can be None (unlimited risk strategies)."""
        contract = OptionContract(
            ticker="AAPL",
            option_type=OptionType.CALL,
            strike=Decimal("185.00"),
            expiration=datetime.date(2025, 2, 21),
            bid=Decimal("4.50"),
            ask=Decimal("4.70"),
            last=Decimal("4.60"),
            volume=1000,
            open_interest=5000,
            implied_volatility=0.28,
        )
        leg = SpreadLeg(
            contract=contract,
            position=PositionSide.SHORT,
            quantity=1,
        )
        spread = OptionSpread(
            spread_type=SpreadType.STRADDLE,
            legs=[leg],
            max_profit=None,
            max_loss=None,
            breakeven=[Decimal("180.30"), Decimal("189.70")],
            net_debit_credit=Decimal("-4.70"),
            pop=None,
        )
        assert spread.max_profit is None
        assert spread.max_loss is None
        assert spread.pop is None

    def test_multiple_breakeven_points(self) -> None:
        """Spreads can have multiple breakeven points (e.g., straddles)."""
        contract = OptionContract(
            ticker="SPY",
            option_type=OptionType.CALL,
            strike=Decimal("450.00"),
            expiration=datetime.date(2025, 3, 21),
            bid=Decimal("8.00"),
            ask=Decimal("8.20"),
            last=Decimal("8.10"),
            volume=5000,
            open_interest=20000,
            implied_volatility=0.22,
        )
        leg = SpreadLeg(contract=contract, position=PositionSide.LONG, quantity=1)
        spread = OptionSpread(
            spread_type=SpreadType.STRADDLE,
            legs=[leg],
            max_profit=None,
            max_loss=Decimal("16.20"),
            breakeven=[Decimal("433.80"), Decimal("466.20")],
            net_debit_credit=Decimal("16.20"),
        )
        assert len(spread.breakeven) == 2
        assert spread.breakeven[0] == Decimal("433.80")
        assert spread.breakeven[1] == Decimal("466.20")
