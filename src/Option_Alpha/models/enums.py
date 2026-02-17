"""StrEnum types for the options domain.

All enums use Python 3.13+ StrEnum. Values are lowercase strings.
Use enum members in business logic, never raw strings.
"""

from enum import StrEnum


class OptionType(StrEnum):
    """Type of option contract."""

    CALL = "call"
    PUT = "put"


class PositionSide(StrEnum):
    """Whether the position is long or short."""

    LONG = "long"
    SHORT = "short"


class SignalDirection(StrEnum):
    """Directional signal from analysis or debate agents."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class GreeksSource(StrEnum):
    """Where the Greeks values originated."""

    MARKET = "market"
    CALCULATED = "calculated"
    MODEL = "model"


class SpreadType(StrEnum):
    """Multi-leg options spread strategy type."""

    VERTICAL = "vertical"
    CALENDAR = "calendar"
    IRON_CONDOR = "iron_condor"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
