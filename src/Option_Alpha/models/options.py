"""Options contract models with Greek validation and spread definitions.

OptionGreeks validates ranges at the boundary to reject bad API data.
OptionContract is frozen with computed mid, spread, and DTE fields.
All Decimal fields have custom serializers for safe JSON roundtrips.
"""

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field, field_serializer, field_validator

from Option_Alpha.models.enums import GreeksSource, OptionType, PositionSide, SpreadType

# --- Validation boundaries for Greeks ---
DELTA_MIN: float = -1.0
DELTA_MAX: float = 1.0
GAMMA_MIN: float = 0.0
VEGA_MIN: float = 0.0


class OptionGreeks(BaseModel):
    """Sensitivity measures for an option contract.

    Validates ranges on construction to reject garbage data from APIs:
    - delta must be in [-1.0, 1.0]
    - gamma must be >= 0
    - vega must be >= 0
    """

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    @field_validator("delta")
    @classmethod
    def validate_delta(cls, value: float) -> float:
        """Delta must be between -1.0 and 1.0."""
        if not DELTA_MIN <= value <= DELTA_MAX:
            msg = f"delta must be between {DELTA_MIN} and {DELTA_MAX}, got {value}"
            raise ValueError(msg)
        return value

    @field_validator("gamma")
    @classmethod
    def validate_gamma(cls, value: float) -> float:
        """Gamma must be non-negative."""
        if value < GAMMA_MIN:
            msg = f"gamma must be >= {GAMMA_MIN}, got {value}"
            raise ValueError(msg)
        return value

    @field_validator("vega")
    @classmethod
    def validate_vega(cls, value: float) -> float:
        """Vega must be non-negative."""
        if value < VEGA_MIN:
            msg = f"vega must be >= {VEGA_MIN}, got {value}"
            raise ValueError(msg)
        return value


class OptionContract(BaseModel):
    """A single options contract with pricing and Greeks.

    Frozen because contract data is a point-in-time snapshot.
    Computed fields provide mid price, bid-ask spread, and DTE.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    option_type: OptionType
    strike: Decimal
    expiration: datetime.date
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: int
    open_interest: int
    implied_volatility: float
    greeks: OptionGreeks | None = None
    greeks_source: GreeksSource | None = None

    @field_serializer("strike", "bid", "ask", "last")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mid(self) -> Decimal:
        """Mid price: (bid + ask) / 2, better fair value estimate than last."""
        return (self.bid + self.ask) / 2

    @computed_field  # type: ignore[prop-decorator]
    @property
    def spread(self) -> Decimal:
        """Bid-ask spread. Wide spread indicates illiquidity."""
        return self.ask - self.bid

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dte(self) -> int:
        """Days to expiration from today."""
        return (self.expiration - datetime.date.today()).days


class SpreadLeg(BaseModel):
    """A single leg of a multi-leg options spread."""

    contract: OptionContract
    position: PositionSide
    quantity: int


class OptionSpread(BaseModel):
    """A multi-leg options spread strategy with risk parameters.

    max_profit and max_loss are None when the risk is unlimited
    (e.g., naked calls have unlimited max_loss).
    """

    spread_type: SpreadType
    legs: list[SpreadLeg]
    max_profit: Decimal | None = None
    max_loss: Decimal | None = None
    breakeven: list[Decimal]
    net_debit_credit: Decimal
    pop: float | None = None

    @field_serializer("max_profit", "max_loss", "net_debit_credit")
    def serialize_decimal(self, value: Decimal | None) -> str | None:
        """Serialize Decimal fields as strings to preserve precision."""
        if value is None:
            return None
        return str(value)

    @field_serializer("breakeven")
    def serialize_breakeven(self, value: list[Decimal]) -> list[str]:
        """Serialize breakeven Decimal list as strings."""
        return [str(v) for v in value]
