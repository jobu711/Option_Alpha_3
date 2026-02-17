"""Analysis models: market context, agent responses, and trade thesis.

MarketContext is intentionally flat (no nested objects) because agents
parse flat key-value pairs better in prompt text. AgentResponse and
TradeThesis capture the debate output with conviction scores and metadata.
"""

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from Option_Alpha.models.enums import SignalDirection

# --- Validation boundaries ---
CONVICTION_MIN: float = 0.0
CONVICTION_MAX: float = 1.0


class MarketContext(BaseModel):
    """Snapshot of market data passed to both debate agents.

    Kept intentionally flat -- agents handle flat structures better than
    deeply nested objects when parsing prompt text.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    current_price: Decimal
    price_52w_high: Decimal
    price_52w_low: Decimal
    iv_rank: float
    iv_percentile: float
    atm_iv_30d: float
    rsi_14: float
    macd_signal: str
    put_call_ratio: float
    next_earnings: datetime.date | None = None
    dte_target: int
    target_strike: Decimal
    target_delta: float
    sector: str
    data_timestamp: datetime.datetime

    @field_serializer("current_price", "price_52w_high", "price_52w_low", "target_strike")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)


class AgentResponse(BaseModel):
    """Response from a single debate agent (bullish or bearish).

    Contains the analysis text, conviction score, and metadata about
    token usage and model identity for tracking costs and quality.
    """

    agent_role: str
    analysis: str
    key_points: list[str]
    conviction: float
    contracts_referenced: list[str]
    greeks_cited: dict[str, float]
    model_used: str
    input_tokens: int
    output_tokens: int

    @field_validator("conviction")
    @classmethod
    def validate_conviction(cls, value: float) -> float:
        """Conviction must be between 0.0 and 1.0."""
        if not CONVICTION_MIN <= value <= CONVICTION_MAX:
            msg = f"conviction must be between {CONVICTION_MIN} and {CONVICTION_MAX}, got {value}"
            raise ValueError(msg)
        return value


class TradeThesis(BaseModel):
    """Final output of the debate: a directional trade thesis with risk context.

    Every thesis includes a disclaimer field that must be populated from
    reporting/disclaimer.py before user-facing output.
    """

    model_config = ConfigDict(frozen=True)

    direction: SignalDirection
    conviction: float
    entry_rationale: str
    risk_factors: list[str]
    recommended_action: str
    bull_summary: str
    bear_summary: str
    model_used: str
    total_tokens: int
    duration_ms: int
    disclaimer: str

    @field_validator("conviction")
    @classmethod
    def validate_conviction(cls, value: float) -> float:
        """Conviction must be between 0.0 and 1.0."""
        if not CONVICTION_MIN <= value <= CONVICTION_MAX:
            msg = f"conviction must be between {CONVICTION_MIN} and {CONVICTION_MAX}, got {value}"
            raise ValueError(msg)
        return value
