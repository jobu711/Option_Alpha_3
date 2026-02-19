"""Shared test fixtures for the Option Alpha test suite.

Provides realistic sample instances of all core models so tests don't
need to inline large construction blocks.
"""

import datetime
from decimal import Decimal

import pytest

from Option_Alpha.models import (
    AgentResponse,
    GreeksCited,
    HealthStatus,
    MarketContext,
    OptionContract,
    OptionGreeks,
    OptionSpread,
    OptionType,
    PositionSide,
    Quote,
    ScanRun,
    SignalDirection,
    SpreadLeg,
    SpreadType,
    TickerScore,
    TradeThesis,
)
from Option_Alpha.models.market_data import OHLCV, TickerInfo


@pytest.fixture()
def sample_ohlcv() -> OHLCV:
    """A valid OHLCV bar with realistic AAPL daily data."""
    return OHLCV(
        date=datetime.date(2025, 1, 15),
        open=Decimal("185.50"),
        high=Decimal("187.25"),
        low=Decimal("184.10"),
        close=Decimal("186.75"),
        volume=52_340_000,
    )


@pytest.fixture()
def sample_quote() -> Quote:
    """A valid real-time quote snapshot for AAPL."""
    return Quote(
        ticker="AAPL",
        bid=Decimal("186.50"),
        ask=Decimal("186.55"),
        last=Decimal("186.52"),
        volume=35_120_000,
        timestamp=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_option_greeks() -> OptionGreeks:
    """Valid OptionGreeks with typical ATM call values."""
    return OptionGreeks(
        delta=0.45,
        gamma=0.05,
        theta=-0.08,
        vega=0.12,
        rho=0.01,
    )


@pytest.fixture()
def sample_option_contract(sample_option_greeks: OptionGreeks) -> OptionContract:
    """A valid AAPL call option contract with all fields populated."""
    return OptionContract(
        ticker="AAPL",
        option_type=OptionType.CALL,
        strike=Decimal("185.00"),
        expiration=datetime.date(2025, 2, 21),
        bid=Decimal("4.50"),
        ask=Decimal("4.70"),
        last=Decimal("4.60"),
        volume=1250,
        open_interest=8340,
        implied_volatility=0.28,
        greeks=sample_option_greeks,
    )


@pytest.fixture()
def sample_market_context() -> MarketContext:
    """Fully populated MarketContext with realistic AAPL options data."""
    return MarketContext(
        ticker="AAPL",
        current_price=Decimal("186.75"),
        price_52w_high=Decimal("199.62"),
        price_52w_low=Decimal("164.08"),
        iv_rank=45.2,
        iv_percentile=52.8,
        atm_iv_30d=0.28,
        rsi_14=55.3,
        macd_signal="neutral",
        put_call_ratio=0.85,
        next_earnings=datetime.date(2025, 4, 24),
        dte_target=37,
        target_strike=Decimal("185.00"),
        target_delta=0.45,
        sector="Technology",
        data_timestamp=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_trade_thesis() -> TradeThesis:
    """A valid TradeThesis with all required fields."""
    return TradeThesis(
        direction=SignalDirection.BULLISH,
        conviction=0.72,
        entry_rationale="RSI at 55 with bullish MACD crossover suggests upward momentum.",
        risk_factors=["Earnings in 30 days", "IV rank elevated at 45%"],
        recommended_action="Buy 185 call expiring Feb 21",
        bull_summary="Technical momentum favors upside with support at 184.",
        bear_summary="Elevated IV may compress post-earnings, capping gains.",
        model_used="claude-sonnet-4-5-20250929",
        total_tokens=1500,
        duration_ms=3200,
    )


@pytest.fixture()
def sample_agent_response() -> AgentResponse:
    """A valid AgentResponse from a bullish debate agent."""
    return AgentResponse(
        agent_role="bull",
        analysis="RSI at 55 suggests momentum. MACD crossover is bullish.",
        key_points=["RSI oversold bounce", "MACD bullish crossover"],
        conviction=0.72,
        contracts_referenced=["AAPL 185C 2025-02-21"],
        greeks_cited=GreeksCited(delta=0.45, theta=-0.08),
        model_used="claude-sonnet-4-5-20250929",
        input_tokens=500,
        output_tokens=200,
    )


@pytest.fixture()
def sample_ticker_info() -> TickerInfo:
    """A valid TickerInfo for AAPL."""
    return TickerInfo(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        market_cap_tier="mega",
        asset_type="equity",
        source="yfinance",
        tags=["faang", "tech", "mega-cap"],
        status="active",
        discovered_at=datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
        last_scanned_at=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_scan_run() -> ScanRun:
    """A valid ScanRun tracking a completed scan."""
    return ScanRun(
        id="scan-20250115-001",
        started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
        completed_at=datetime.datetime(2025, 1, 15, 9, 35, 0, tzinfo=datetime.UTC),
        status="completed",
        preset="high_iv",
        sectors=["Technology", "Healthcare"],
        ticker_count=50,
        top_n=10,
    )


@pytest.fixture()
def sample_ticker_score() -> TickerScore:
    """A valid TickerScore from a scan run."""
    return TickerScore(
        ticker="AAPL",
        score=82.5,
        signals={"iv_rank": 45.2, "rsi_momentum": 22.3, "volume_surge": 15.0},
        rank=1,
    )


@pytest.fixture()
def sample_health_status() -> HealthStatus:
    """A valid HealthStatus snapshot."""
    return HealthStatus(
        ollama_available=True,
        anthropic_available=True,
        yfinance_available=True,
        sqlite_available=True,
        ollama_models=["llama3:70b", "mistral:7b"],
        last_check=datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC),
    )


@pytest.fixture()
def sample_spread_leg(sample_option_contract: OptionContract) -> SpreadLeg:
    """A valid SpreadLeg for a long call position."""
    return SpreadLeg(
        contract=sample_option_contract,
        position=PositionSide.LONG,
        quantity=1,
    )


@pytest.fixture()
def sample_option_spread(sample_option_contract: OptionContract) -> OptionSpread:
    """A valid vertical call spread with two legs."""
    long_leg = SpreadLeg(
        contract=sample_option_contract,
        position=PositionSide.LONG,
        quantity=1,
    )
    short_contract = OptionContract(
        ticker="AAPL",
        option_type=OptionType.CALL,
        strike=Decimal("190.00"),
        expiration=datetime.date(2025, 2, 21),
        bid=Decimal("2.80"),
        ask=Decimal("3.00"),
        last=Decimal("2.90"),
        volume=980,
        open_interest=6200,
        implied_volatility=0.26,
    )
    short_leg = SpreadLeg(
        contract=short_contract,
        position=PositionSide.SHORT,
        quantity=1,
    )
    return OptionSpread(
        spread_type=SpreadType.VERTICAL,
        legs=[long_leg, short_leg],
        max_profit=Decimal("3.10"),
        max_loss=Decimal("1.90"),
        breakeven=[Decimal("186.90")],
        net_debit_credit=Decimal("1.90"),
        pop=0.55,
    )
