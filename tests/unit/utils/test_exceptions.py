"""Tests for custom exception hierarchy.

Covers:
- Inheritance: all exceptions are subclasses of DataFetchError -> Exception
- Attributes: ticker, source, http_status accessible
- Each exception can be caught by its own type and by parent type
- String representation includes useful info
- http_status defaults to None when not provided
"""

import pytest

from Option_Alpha.utils.exceptions import (
    DataFetchError,
    DataSourceUnavailableError,
    InsufficientDataError,
    RateLimitExceededError,
    TickerNotFoundError,
)


class TestDataFetchErrorBase:
    """Tests for the base DataFetchError exception."""

    def test_is_subclass_of_exception(self) -> None:
        assert issubclass(DataFetchError, Exception)

    def test_attributes_accessible(self) -> None:
        exc = DataFetchError(
            "Data fetch failed",
            ticker="AAPL",
            source="yfinance",
            http_status=500,
        )
        assert exc.ticker == "AAPL"
        assert exc.source == "yfinance"
        assert exc.http_status == 500

    def test_http_status_defaults_to_none(self) -> None:
        exc = DataFetchError(
            "Data fetch failed",
            ticker="MSFT",
            source="cboe",
        )
        assert exc.http_status is None

    def test_message_in_string_representation(self) -> None:
        exc = DataFetchError(
            "Connection timeout",
            ticker="TSLA",
            source="yfinance",
        )
        assert "Connection timeout" in str(exc)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(DataFetchError, match="test error"):
            raise DataFetchError("test error", ticker="SPY", source="test")


class TestTickerNotFoundError:
    """Tests for TickerNotFoundError."""

    def test_is_subclass_of_data_fetch_error(self) -> None:
        assert issubclass(TickerNotFoundError, DataFetchError)

    def test_is_subclass_of_exception(self) -> None:
        assert issubclass(TickerNotFoundError, Exception)

    def test_can_be_raised_and_caught_by_own_type(self) -> None:
        with pytest.raises(TickerNotFoundError):
            raise TickerNotFoundError(
                "Ticker FAKE not found",
                ticker="FAKE",
                source="yfinance",
                http_status=404,
            )

    def test_can_be_caught_as_data_fetch_error(self) -> None:
        with pytest.raises(DataFetchError):
            raise TickerNotFoundError(
                "Ticker FAKE not found",
                ticker="FAKE",
                source="yfinance",
                http_status=404,
            )

    def test_attributes_inherited(self) -> None:
        exc = TickerNotFoundError(
            "Not found",
            ticker="XYZ",
            source="cboe",
            http_status=404,
        )
        assert exc.ticker == "XYZ"
        assert exc.source == "cboe"
        assert exc.http_status == 404

    def test_string_representation(self) -> None:
        exc = TickerNotFoundError(
            "Ticker FAKE not found in yfinance",
            ticker="FAKE",
            source="yfinance",
        )
        assert "FAKE" in str(exc)
        assert "yfinance" in str(exc)


class TestDataSourceUnavailableError:
    """Tests for DataSourceUnavailableError."""

    def test_is_subclass_of_data_fetch_error(self) -> None:
        assert issubclass(DataSourceUnavailableError, DataFetchError)

    def test_can_be_raised_and_caught_by_own_type(self) -> None:
        with pytest.raises(DataSourceUnavailableError):
            raise DataSourceUnavailableError(
                "Service down",
                ticker="AAPL",
                source="yfinance",
                http_status=503,
            )

    def test_can_be_caught_as_data_fetch_error(self) -> None:
        with pytest.raises(DataFetchError):
            raise DataSourceUnavailableError(
                "Service down",
                ticker="AAPL",
                source="yfinance",
                http_status=503,
            )

    def test_attributes_accessible(self) -> None:
        exc = DataSourceUnavailableError(
            "Timeout",
            ticker="MSFT",
            source="cboe",
            http_status=504,
        )
        assert exc.ticker == "MSFT"
        assert exc.source == "cboe"
        assert exc.http_status == 504


class TestInsufficientDataError:
    """Tests for InsufficientDataError."""

    def test_is_subclass_of_data_fetch_error(self) -> None:
        assert issubclass(InsufficientDataError, DataFetchError)

    def test_can_be_raised_and_caught_by_own_type(self) -> None:
        with pytest.raises(InsufficientDataError):
            raise InsufficientDataError(
                "Need 200 days, only got 50",
                ticker="AAPL",
                source="yfinance",
            )

    def test_can_be_caught_as_data_fetch_error(self) -> None:
        with pytest.raises(DataFetchError):
            raise InsufficientDataError(
                "Need 200 days, only got 50",
                ticker="AAPL",
                source="yfinance",
            )

    def test_http_status_defaults_to_none(self) -> None:
        """InsufficientDataError often has no HTTP status (it's a data quality issue)."""
        exc = InsufficientDataError(
            "Not enough data",
            ticker="SPY",
            source="yfinance",
        )
        assert exc.http_status is None


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError."""

    def test_is_subclass_of_data_fetch_error(self) -> None:
        assert issubclass(RateLimitExceededError, DataFetchError)

    def test_can_be_raised_and_caught_by_own_type(self) -> None:
        with pytest.raises(RateLimitExceededError):
            raise RateLimitExceededError(
                "Rate limit exceeded",
                ticker="AAPL",
                source="yfinance",
                http_status=429,
            )

    def test_can_be_caught_as_data_fetch_error(self) -> None:
        with pytest.raises(DataFetchError):
            raise RateLimitExceededError(
                "Rate limit exceeded",
                ticker="AAPL",
                source="yfinance",
                http_status=429,
            )

    def test_typical_http_status(self) -> None:
        exc = RateLimitExceededError(
            "Too many requests",
            ticker="TSLA",
            source="cboe",
            http_status=429,
        )
        assert exc.http_status == 429


class TestExceptionHierarchyComprehensive:
    """Cross-cutting tests for the full exception hierarchy."""

    ALL_EXCEPTION_CLASSES = [
        TickerNotFoundError,
        DataSourceUnavailableError,
        InsufficientDataError,
        RateLimitExceededError,
    ]

    def test_all_are_subclasses_of_data_fetch_error(self) -> None:
        for exc_class in self.ALL_EXCEPTION_CLASSES:
            assert issubclass(exc_class, DataFetchError), (
                f"{exc_class.__name__} should be a subclass of DataFetchError"
            )

    def test_all_are_subclasses_of_exception(self) -> None:
        for exc_class in self.ALL_EXCEPTION_CLASSES:
            assert issubclass(exc_class, Exception), (
                f"{exc_class.__name__} should be a subclass of Exception"
            )

    def test_all_carry_required_keyword_args(self) -> None:
        """Every child exception requires ticker and source keyword args."""
        for exc_class in self.ALL_EXCEPTION_CLASSES:
            exc = exc_class(
                "test message",
                ticker="TEST",
                source="test_source",
            )
            assert exc.ticker == "TEST"
            assert exc.source == "test_source"
            assert exc.http_status is None

    def test_catch_any_child_as_parent(self) -> None:
        """A single except DataFetchError block catches all children."""
        for exc_class in self.ALL_EXCEPTION_CLASSES:
            with pytest.raises(DataFetchError):
                raise exc_class(
                    "caught by parent",
                    ticker="AAPL",
                    source="test",
                )
