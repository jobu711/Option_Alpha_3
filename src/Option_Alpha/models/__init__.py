"""Pydantic v2 models, enums, and type definitions.

Re-exports all public models so consumers can import directly:
    from Option_Alpha.models import OptionContract, OptionType, MarketContext
"""

from Option_Alpha.models.analysis import (
    AgentResponse,
    GreeksCited,
    MarketContext,
    TradeThesis,
)
from Option_Alpha.models.enums import (
    GreeksSource,
    OptionType,
    PositionSide,
    SignalDirection,
    SpreadType,
)
from Option_Alpha.models.health import HealthStatus
from Option_Alpha.models.market_data import OHLCV, Quote, TickerInfo
from Option_Alpha.models.options import OptionContract, OptionGreeks, OptionSpread, SpreadLeg
from Option_Alpha.models.scan import ScanRun, TickerScore, WatchlistSummary

__all__ = [
    # Enums
    "GreeksSource",
    "OptionType",
    "PositionSide",
    "SignalDirection",
    "SpreadType",
    # Market data
    "OHLCV",
    "Quote",
    "TickerInfo",
    # Options
    "OptionContract",
    "OptionGreeks",
    "OptionSpread",
    "SpreadLeg",
    # Analysis
    "AgentResponse",
    "GreeksCited",
    "MarketContext",
    "TradeThesis",
    # Scan
    "ScanRun",
    "TickerScore",
    "WatchlistSummary",
    # Health
    "HealthStatus",
]
