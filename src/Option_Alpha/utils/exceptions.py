"""Custom exception hierarchy for the Option Alpha application.

All domain-specific exceptions inherit from DataFetchError, which carries
contextual information about what went wrong during data retrieval.
"""


class DataFetchError(Exception):
    """Base exception for all data-fetching failures.

    Attributes:
        ticker: The ticker symbol involved in the failure.
        source: The data source that failed (e.g., "yfinance", "cboe").
        http_status: The HTTP status code, if the failure was HTTP-related.
    """

    def __init__(
        self,
        message: str,
        *,
        ticker: str,
        source: str,
        http_status: int | None = None,
    ) -> None:
        self.ticker = ticker
        self.source = source
        self.http_status = http_status
        super().__init__(message)


class TickerNotFoundError(DataFetchError):
    """Raised when a ticker symbol does not exist in the data source."""


class DataSourceUnavailableError(DataFetchError):
    """Raised when a data source is unreachable or returning errors."""


class InsufficientDataError(DataFetchError):
    """Raised when available data is too sparse for the requested operation."""


class RateLimitExceededError(DataFetchError):
    """Raised when the data source rate limit has been hit."""
