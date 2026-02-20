"""Tests for contract filtering and recommendation engine.

Tests cover filter_contracts, select_expiration, select_by_delta,
and the end-to-end recommend_contract pipeline. All DTE-dependent tests
mock date.today() for deterministic results.
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from Option_Alpha.analysis.contracts import (
    DEFAULT_DELTA_TARGET,
    DEFAULT_DELTA_TARGET_HIGH,
    DEFAULT_DELTA_TARGET_LOW,
    MAX_DTE,
    MIN_DTE,
    MIN_OPEN_INTEREST,
    MIN_VOLUME,
    TARGET_DTE,
    filter_contracts,
    recommend_contract,
    select_by_delta,
    select_expiration,
)
from Option_Alpha.models.enums import OptionType, SignalDirection
from Option_Alpha.models.options import OptionContract, OptionGreeks

# Fixed "today" for all DTE calculations
MOCK_TODAY = datetime.date(2025, 1, 15)


def _mock_today() -> datetime.date:
    """Return the fixed mock date for deterministic DTE calculations."""
    return MOCK_TODAY


def make_contract(
    ticker: str = "AAPL",
    option_type: OptionType = OptionType.CALL,
    strike: str = "185.00",
    expiration: datetime.date | None = None,
    bid: str = "3.50",
    ask: str = "3.80",
    last: str = "3.65",
    volume: int = 500,
    open_interest: int = 2000,
    implied_volatility: float = 0.25,
    greeks: OptionGreeks | None = None,
) -> OptionContract:
    """Build a realistic OptionContract for testing.

    Defaults produce a liquid, mid-DTE call with tight spread.
    """
    if expiration is None:
        expiration = MOCK_TODAY + datetime.timedelta(days=TARGET_DTE)
    return OptionContract(
        ticker=ticker,
        option_type=option_type,
        strike=Decimal(strike),
        expiration=expiration,
        bid=Decimal(bid),
        ask=Decimal(ask),
        last=Decimal(last),
        volume=volume,
        open_interest=open_interest,
        implied_volatility=implied_volatility,
        greeks=greeks,
    )


def make_greeks(
    delta: float = 0.35,
    gamma: float = 0.04,
    theta: float = -0.08,
    vega: float = 0.15,
    rho: float = 0.02,
) -> OptionGreeks:
    """Build OptionGreeks with reasonable defaults."""
    return OptionGreeks(
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
    )


# ---------------------------------------------------------------------------
# filter_contracts tests
# ---------------------------------------------------------------------------


class TestFilterContracts:
    """Tests for filter_contracts()."""

    @patch("Option_Alpha.models.options.datetime")
    def test_bullish_returns_calls_only(self, mock_dt: object) -> None:
        """BULLISH direction filters to calls only."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        call = make_contract(option_type=OptionType.CALL)
        put = make_contract(option_type=OptionType.PUT)

        result = filter_contracts([call, put], SignalDirection.BULLISH)

        assert len(result) == 1
        assert result[0].option_type == OptionType.CALL

    @patch("Option_Alpha.models.options.datetime")
    def test_bearish_returns_puts_only(self, mock_dt: object) -> None:
        """BEARISH direction filters to puts only."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        call = make_contract(option_type=OptionType.CALL)
        put = make_contract(option_type=OptionType.PUT)

        result = filter_contracts([call, put], SignalDirection.BEARISH)

        assert len(result) == 1
        assert result[0].option_type == OptionType.PUT

    def test_neutral_returns_empty(self) -> None:
        """NEUTRAL direction always returns empty list."""
        call = make_contract(option_type=OptionType.CALL)
        result = filter_contracts([call], SignalDirection.NEUTRAL)
        assert result == []

    @patch("Option_Alpha.models.options.datetime")
    def test_removes_low_open_interest(self, mock_dt: object) -> None:
        """Contracts with OI below MIN_OPEN_INTEREST are excluded."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        low_oi = make_contract(open_interest=MIN_OPEN_INTEREST - 1)
        ok_oi = make_contract(open_interest=MIN_OPEN_INTEREST, strike="190.00")

        result = filter_contracts([low_oi, ok_oi], SignalDirection.BULLISH)

        assert len(result) == 1
        assert result[0].strike == Decimal("190.00")

    @patch("Option_Alpha.models.options.datetime")
    def test_removes_zero_volume(self, mock_dt: object) -> None:
        """Contracts with volume < MIN_VOLUME are excluded."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        zero_vol = make_contract(volume=0)
        ok_vol = make_contract(volume=MIN_VOLUME, strike="190.00")

        result = filter_contracts([zero_vol, ok_vol], SignalDirection.BULLISH)

        assert len(result) == 1
        assert result[0].strike == Decimal("190.00")

    @patch("Option_Alpha.models.options.datetime")
    def test_removes_wide_spread(self, mock_dt: object) -> None:
        """Contracts with spread/mid > MAX_SPREAD_PCT are excluded."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        # bid=1.00 ask=2.00 -> spread=1.00, mid=1.50 -> pct=0.667 > 0.30
        wide = make_contract(bid="1.00", ask="2.00", last="1.50")
        # bid=3.50 ask=3.80 -> spread=0.30, mid=3.65 -> pct=0.082 < 0.30
        tight = make_contract(bid="3.50", ask="3.80", last="3.65", strike="190.00")

        result = filter_contracts([wide, tight], SignalDirection.BULLISH)

        assert len(result) == 1
        assert result[0].strike == Decimal("190.00")

    @patch("Option_Alpha.models.options.datetime")
    def test_skips_zero_mid(self, mock_dt: object) -> None:
        """Contracts with mid = 0 (bid=0, ask=0) are skipped to avoid division by zero."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        zero_mid = make_contract(bid="0.00", ask="0.00", last="0.00")
        ok = make_contract(strike="190.00")

        result = filter_contracts([zero_mid, ok], SignalDirection.BULLISH)

        assert len(result) == 1
        assert result[0].strike == Decimal("190.00")

    @patch("Option_Alpha.models.options.datetime")
    def test_sorted_by_open_interest_descending(self, mock_dt: object) -> None:
        """Results are sorted by open_interest in descending order."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        low_oi = make_contract(open_interest=500, strike="180.00")
        mid_oi = make_contract(open_interest=1000, strike="185.00")
        high_oi = make_contract(open_interest=5000, strike="190.00")

        result = filter_contracts([low_oi, high_oi, mid_oi], SignalDirection.BULLISH)

        assert len(result) == 3
        assert result[0].open_interest == 5000
        assert result[1].open_interest == 1000
        assert result[2].open_interest == 500

    def test_empty_input_returns_empty(self) -> None:
        """Empty contract list returns empty list."""
        result = filter_contracts([], SignalDirection.BULLISH)
        assert result == []

    @patch("Option_Alpha.models.options.datetime")
    def test_spread_at_exactly_max_passes(self, mock_dt: object) -> None:
        """Spread percentage exactly equal to MAX_SPREAD_PCT (<=) passes."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        # Need spread/mid == 0.30 exactly
        # bid=3.50, ask=5.00 -> spread=1.50, mid=4.25 -> 1.50/4.25 = 0.3529 > 0.30
        # Let's compute: we need ask - bid = 0.30 * (bid + ask) / 2
        # Let bid=7.00, ask=10.00 -> spread=3.00, mid=8.50 -> 3.00/8.50 = 0.353 nope
        # bid=7.00, ask=7.00*(1+2*0.30)/(2-2*0.30+2) hmm, let me just pick values
        # We need spread/mid = 0.30. spread = ask-bid, mid = (ask+bid)/2
        # (ask-bid) / ((ask+bid)/2) = 0.30
        # 2*(ask-bid)/(ask+bid) = 0.30
        # Let bid=x, ask=x+d. 2d/(2x+d) = 0.30 -> d = 0.30*(2x+d)/2
        # d = 0.3x + 0.15d -> 0.85d = 0.3x -> d = 0.3x/0.85
        # For x=8.50: d = 2.55/0.85 = 3.00, ask=11.50
        # spread=3.00, mid=10.00, pct = 3.00/10.00 = 0.30
        contract = make_contract(bid="8.50", ask="11.50", last="10.00")

        result = filter_contracts([contract], SignalDirection.BULLISH)

        assert len(result) == 1


# ---------------------------------------------------------------------------
# select_expiration tests
# ---------------------------------------------------------------------------


class TestSelectExpiration:
    """Tests for select_expiration()."""

    @patch("Option_Alpha.models.options.datetime")
    def test_picks_closest_to_target_dte(self, mock_dt: object) -> None:
        """Selects the expiration nearest to TARGET_DTE (45)."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_30 = MOCK_TODAY + datetime.timedelta(days=30)
        exp_44 = MOCK_TODAY + datetime.timedelta(days=44)
        exp_60 = MOCK_TODAY + datetime.timedelta(days=60)

        contracts = [
            make_contract(expiration=exp_30, strike="180.00"),
            make_contract(expiration=exp_44, strike="185.00"),
            make_contract(expiration=exp_60, strike="190.00"),
        ]

        result = select_expiration(contracts)

        assert len(result) == 1
        assert result[0].expiration == exp_44

    @patch("Option_Alpha.models.options.datetime")
    def test_returns_all_contracts_at_best_expiration(self, mock_dt: object) -> None:
        """All contracts at the selected expiration are returned."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_45 = MOCK_TODAY + datetime.timedelta(days=45)

        contracts = [
            make_contract(expiration=exp_45, strike="180.00"),
            make_contract(expiration=exp_45, strike="185.00"),
            make_contract(expiration=exp_45, strike="190.00"),
        ]

        result = select_expiration(contracts)

        assert len(result) == 3

    @patch("Option_Alpha.models.options.datetime")
    def test_no_expirations_in_range_returns_empty(self, mock_dt: object) -> None:
        """Returns empty list when no expirations fall within [MIN_DTE, MAX_DTE]."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        too_short = MOCK_TODAY + datetime.timedelta(days=MIN_DTE - 1)
        too_long = MOCK_TODAY + datetime.timedelta(days=MAX_DTE + 1)

        contracts = [
            make_contract(expiration=too_short, strike="180.00"),
            make_contract(expiration=too_long, strike="185.00"),
        ]

        result = select_expiration(contracts)

        assert result == []

    @patch("Option_Alpha.models.options.datetime")
    def test_boundary_min_dte_included(self, mock_dt: object) -> None:
        """Expiration at exactly MIN_DTE is within range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_min = MOCK_TODAY + datetime.timedelta(days=MIN_DTE)

        contracts = [make_contract(expiration=exp_min)]

        result = select_expiration(contracts)

        assert len(result) == 1

    @patch("Option_Alpha.models.options.datetime")
    def test_boundary_max_dte_included(self, mock_dt: object) -> None:
        """Expiration at exactly MAX_DTE is within range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_max = MOCK_TODAY + datetime.timedelta(days=MAX_DTE)

        contracts = [make_contract(expiration=exp_max)]

        result = select_expiration(contracts)

        assert len(result) == 1

    def test_empty_input_returns_empty(self) -> None:
        """Empty contract list returns empty list."""
        result = select_expiration([])
        assert result == []

    @patch("Option_Alpha.models.options.datetime")
    def test_custom_target_dte(self, mock_dt: object) -> None:
        """Custom target_dte overrides the default."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_35 = MOCK_TODAY + datetime.timedelta(days=35)
        exp_55 = MOCK_TODAY + datetime.timedelta(days=55)

        contracts = [
            make_contract(expiration=exp_35, strike="180.00"),
            make_contract(expiration=exp_55, strike="185.00"),
        ]

        # target=55 -> exp_55 is closer
        result = select_expiration(contracts, target_dte=55)

        assert len(result) == 1
        assert result[0].expiration == exp_55


# ---------------------------------------------------------------------------
# select_by_delta tests
# ---------------------------------------------------------------------------


class TestSelectByDelta:
    """Tests for select_by_delta()."""

    @patch("Option_Alpha.models.options.datetime")
    def test_picks_delta_closest_to_target(self, mock_dt: object) -> None:
        """Selects the call contract with delta closest to DEFAULT_DELTA_TARGET."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(
                strike="180.00",
                greeks=make_greeks(delta=0.30),
            ),
            make_contract(
                strike="185.00",
                greeks=make_greeks(delta=0.35),
            ),
            make_contract(
                strike="190.00",
                greeks=make_greeks(delta=0.40),
            ),
        ]

        result = select_by_delta(contracts)

        assert result is not None
        assert result.strike == Decimal("185.00")
        assert result.greeks is not None
        assert result.greeks.delta == pytest.approx(DEFAULT_DELTA_TARGET, abs=1e-6)

    @patch("Option_Alpha.models.options.datetime")
    def test_puts_use_absolute_delta(self, mock_dt: object) -> None:
        """For puts, abs(delta) is compared to the target range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(
                option_type=OptionType.PUT,
                strike="180.00",
                greeks=make_greeks(delta=-0.35),
            ),
            make_contract(
                option_type=OptionType.PUT,
                strike="175.00",
                greeks=make_greeks(delta=-0.50),
            ),
        ]

        result = select_by_delta(contracts)

        assert result is not None
        assert result.strike == Decimal("180.00")

    @patch("Option_Alpha.models.options.datetime")
    def test_no_greeks_returns_none(self, mock_dt: object) -> None:
        """Contracts without greeks are skipped. All without -> None."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(strike="180.00", greeks=None),
            make_contract(strike="185.00", greeks=None),
        ]

        result = select_by_delta(contracts)

        assert result is None

    @patch("Option_Alpha.models.options.datetime")
    def test_no_delta_in_range_returns_none(self, mock_dt: object) -> None:
        """Returns None when no contract's delta falls in [0.30, 0.40]."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(
                strike="175.00",
                greeks=make_greeks(delta=0.60),
            ),
            make_contract(
                strike="195.00",
                greeks=make_greeks(delta=0.15),
            ),
        ]

        result = select_by_delta(contracts)

        assert result is None

    @patch("Option_Alpha.models.options.datetime")
    def test_boundary_delta_low_included(self, mock_dt: object) -> None:
        """Delta exactly at DEFAULT_DELTA_TARGET_LOW is in range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(
                strike="185.00",
                greeks=make_greeks(delta=DEFAULT_DELTA_TARGET_LOW),
            ),
        ]

        result = select_by_delta(contracts)

        assert result is not None
        assert result.greeks is not None
        assert result.greeks.delta == pytest.approx(DEFAULT_DELTA_TARGET_LOW, abs=1e-6)

    @patch("Option_Alpha.models.options.datetime")
    def test_boundary_delta_high_included(self, mock_dt: object) -> None:
        """Delta exactly at DEFAULT_DELTA_TARGET_HIGH is in range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        contracts = [
            make_contract(
                strike="185.00",
                greeks=make_greeks(delta=DEFAULT_DELTA_TARGET_HIGH),
            ),
        ]

        result = select_by_delta(contracts)

        assert result is not None
        assert result.greeks is not None
        assert result.greeks.delta == pytest.approx(DEFAULT_DELTA_TARGET_HIGH, abs=1e-6)

    def test_empty_list_returns_none(self) -> None:
        """Empty contract list returns None."""
        result = select_by_delta([])
        assert result is None


# ---------------------------------------------------------------------------
# recommend_contract tests (end-to-end pipeline)
# ---------------------------------------------------------------------------


class TestRecommendContract:
    """Tests for the recommend_contract() end-to-end pipeline."""

    @patch("Option_Alpha.models.options.datetime")
    def test_full_pipeline_returns_best_contract(self, mock_dt: object) -> None:
        """Happy path: pipeline selects the best contract through all stages."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_45 = MOCK_TODAY + datetime.timedelta(days=45)

        good_contract = make_contract(
            option_type=OptionType.CALL,
            strike="185.00",
            expiration=exp_45,
            bid="3.50",
            ask="3.80",
            volume=500,
            open_interest=2000,
            greeks=make_greeks(delta=0.35),
        )
        # Also add a put (should be filtered for BULLISH)
        put_contract = make_contract(
            option_type=OptionType.PUT,
            strike="175.00",
            expiration=exp_45,
            greeks=make_greeks(delta=-0.35),
        )

        result = recommend_contract([good_contract, put_contract], SignalDirection.BULLISH)

        assert result is not None
        assert result.strike == Decimal("185.00")
        assert result.option_type == OptionType.CALL

    @patch("Option_Alpha.models.options.datetime")
    def test_bearish_pipeline_selects_put(self, mock_dt: object) -> None:
        """BEARISH direction selects a put contract through the pipeline."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_45 = MOCK_TODAY + datetime.timedelta(days=45)

        put = make_contract(
            option_type=OptionType.PUT,
            strike="175.00",
            expiration=exp_45,
            greeks=make_greeks(delta=-0.35),
        )
        call = make_contract(
            option_type=OptionType.CALL,
            strike="185.00",
            expiration=exp_45,
            greeks=make_greeks(delta=0.35),
        )

        result = recommend_contract([put, call], SignalDirection.BEARISH)

        assert result is not None
        assert result.option_type == OptionType.PUT

    def test_neutral_returns_none(self) -> None:
        """NEUTRAL direction returns None (filter_contracts returns empty)."""
        contracts = [make_contract()]
        result = recommend_contract(contracts, SignalDirection.NEUTRAL)
        assert result is None

    @patch("Option_Alpha.models.options.datetime")
    def test_no_qualifying_contracts_returns_none(self, mock_dt: object) -> None:
        """Returns None when all contracts fail the filter stage."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        # All contracts have zero volume
        bad = make_contract(volume=0)

        result = recommend_contract([bad], SignalDirection.BULLISH)

        assert result is None

    @patch("Option_Alpha.models.options.datetime")
    def test_no_dte_in_range_filtered_by_select_expiration(self, mock_dt: object) -> None:
        """select_expiration returns empty when no DTE in [30, 60] range.

        recommend_contract no longer applies DTE filtering — the service
        layer handles expiration selection before contracts reach the
        recommendation pipeline.  This test verifies select_expiration
        still enforces the range independently.
        """
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        too_soon = MOCK_TODAY + datetime.timedelta(days=10)

        contracts = [
            make_contract(expiration=too_soon, greeks=make_greeks(delta=0.35)),
        ]

        result = select_expiration(contracts)

        assert result == []

    @patch("Option_Alpha.models.options.datetime")
    def test_no_delta_in_range_returns_none(self, mock_dt: object) -> None:
        """Returns None when no contract has delta within target range."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_45 = MOCK_TODAY + datetime.timedelta(days=45)

        contracts = [
            make_contract(
                expiration=exp_45,
                greeks=make_greeks(delta=0.80),
            ),
        ]

        result = recommend_contract(contracts, SignalDirection.BULLISH)

        assert result is None

    @patch("Option_Alpha.models.options.datetime")
    def test_no_greeks_returns_none(self, mock_dt: object) -> None:
        """Returns None when all qualifying contracts lack greeks."""
        mock_dt.date.today = _mock_today  # type: ignore[attr-defined]
        exp_45 = MOCK_TODAY + datetime.timedelta(days=45)

        contracts = [
            make_contract(expiration=exp_45, greeks=None),
        ]

        result = recommend_contract(contracts, SignalDirection.BULLISH)

        assert result is None

    def test_empty_input_returns_none(self) -> None:
        """Empty contract list returns None."""
        result = recommend_contract([], SignalDirection.BULLISH)
        assert result is None
