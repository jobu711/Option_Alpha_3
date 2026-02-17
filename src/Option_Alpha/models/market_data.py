"""Market data models: OHLCV bars, live quotes, and ticker metadata.

All price fields use Decimal (constructed from strings) with custom
serializers to prevent silent float conversion in JSON roundtrips.
"""

import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field, field_serializer


class OHLCV(BaseModel):
    """A single OHLCV (open-high-low-close-volume) price bar.

    Frozen because historical price data should never be mutated after creation.
    """

    model_config = ConfigDict(frozen=True)

    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int

    @field_serializer("open", "high", "low", "close")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)


class Quote(BaseModel):
    """Real-time or delayed quote snapshot for a ticker.

    Frozen because a quote is a point-in-time snapshot.
    """

    model_config = ConfigDict(frozen=True)

    ticker: str
    bid: Decimal
    ask: Decimal
    last: Decimal
    volume: int
    timestamp: datetime.datetime

    @field_serializer("bid", "ask", "last")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize Decimal fields as strings to preserve precision."""
        return str(value)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def mid(self) -> Decimal:
        """Mid price: (bid + ask) / 2, a better fair value estimate than last."""
        return (self.bid + self.ask) / 2

    @computed_field  # type: ignore[prop-decorator]
    @property
    def spread(self) -> Decimal:
        """Bid-ask spread. Wide spread indicates illiquidity."""
        return self.ask - self.bid


class TickerInfo(BaseModel):
    """Metadata about a tracked ticker symbol.

    Frozen because ticker metadata is a snapshot from the discovery/scan process.
    """

    model_config = ConfigDict(frozen=True)

    symbol: str
    name: str
    sector: str
    market_cap_tier: str
    asset_type: str
    source: str
    tags: list[str]
    status: str
    discovered_at: datetime.datetime
    last_scanned_at: datetime.datetime | None = None
    consecutive_misses: int = 0
