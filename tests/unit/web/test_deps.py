"""Tests for FastAPI dependency injection providers.

Verifies that each dependency provider returns the correct type and that
the ticker symbol validator correctly validates and normalizes input.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.services.cache import ServiceCache
from Option_Alpha.services.health import HealthService
from Option_Alpha.services.market_data import MarketDataService
from Option_Alpha.services.options_data import OptionsDataService
from Option_Alpha.services.rate_limiter import RateLimiter
from Option_Alpha.web.deps import (
    get_database,
    get_health_service,
    get_market_data_service,
    get_options_data_service,
    get_repository,
    validate_ticker_symbol,
)


class TestGetDatabase:
    """Test the get_database dependency."""

    @pytest.mark.asyncio
    async def test_yields_database_from_app_state(self) -> None:
        """get_database should yield the Database from request.app.state."""
        mock_db = MagicMock(spec=Database)
        mock_request = MagicMock()
        mock_request.app.state.database = mock_db

        gen = get_database(mock_request)
        db = await gen.__anext__()
        assert db is mock_db


class TestGetRepository:
    """Test the get_repository dependency."""

    @pytest.mark.asyncio
    async def test_returns_repository_instance(self) -> None:
        """get_repository should return a Repository backed by the given Database."""
        mock_db = MagicMock(spec=Database)
        repo = await get_repository(mock_db)
        assert isinstance(repo, Repository)


def _mock_request_with_state() -> MagicMock:
    """Create a mock Request with app.state.rate_limiter and app.state.cache set."""
    mock_request = MagicMock()
    mock_request.app.state.rate_limiter = RateLimiter()
    mock_request.app.state.cache = ServiceCache()
    return mock_request


class TestGetMarketDataService:
    """Test the get_market_data_service dependency."""

    @pytest.mark.asyncio
    async def test_returns_market_data_service(self) -> None:
        """get_market_data_service should return a MarketDataService instance."""
        mock_request = _mock_request_with_state()
        service = await get_market_data_service(mock_request)
        assert isinstance(service, MarketDataService)


class TestGetOptionsDataService:
    """Test the get_options_data_service dependency."""

    @pytest.mark.asyncio
    async def test_returns_options_data_service(self) -> None:
        """get_options_data_service should return an OptionsDataService instance."""
        mock_request = _mock_request_with_state()
        service = await get_options_data_service(mock_request)
        assert isinstance(service, OptionsDataService)


class TestGetHealthService:
    """Test the get_health_service dependency."""

    @pytest.mark.asyncio
    async def test_returns_health_service(self) -> None:
        """get_health_service should return a HealthService with the given Database."""
        mock_db = MagicMock(spec=Database)
        # HealthService creates an httpx.AsyncClient internally, which is fine
        service = await get_health_service(mock_db)
        assert isinstance(service, HealthService)


class TestValidateTickerSymbol:
    """Test the ticker symbol path parameter validator."""

    @pytest.mark.asyncio
    async def test_valid_uppercase_symbol(self) -> None:
        """Valid uppercase symbols should pass through unchanged."""
        result = await validate_ticker_symbol("AAPL")
        assert result == "AAPL"

    @pytest.mark.asyncio
    async def test_lowercase_normalized_to_uppercase(self) -> None:
        """Lowercase input should be normalized to uppercase."""
        result = await validate_ticker_symbol("aapl")
        assert result == "AAPL"

    @pytest.mark.asyncio
    async def test_mixed_case_normalized(self) -> None:
        """Mixed case input should be normalized to uppercase."""
        result = await validate_ticker_symbol("aApL")
        assert result == "AAPL"

    @pytest.mark.asyncio
    async def test_single_character_valid(self) -> None:
        """Single character symbols should be valid."""
        result = await validate_ticker_symbol("F")
        assert result == "F"

    @pytest.mark.asyncio
    async def test_five_character_valid(self) -> None:
        """Five character symbols should be valid."""
        result = await validate_ticker_symbol("GOOGL")
        assert result == "GOOGL"

    @pytest.mark.asyncio
    async def test_numeric_characters_valid(self) -> None:
        """Alphanumeric symbols should be valid."""
        result = await validate_ticker_symbol("BRK1")
        assert result == "BRK1"

    @pytest.mark.asyncio
    async def test_empty_string_raises_422(self) -> None:
        """Empty string should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_ticker_symbol("")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_too_long_raises_422(self) -> None:
        """Symbols longer than 5 characters should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_ticker_symbol("TOOLNG")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_special_characters_raises_422(self) -> None:
        """Symbols with special characters should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_ticker_symbol("AA-PL")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_spaces_raises_422(self) -> None:
        """Symbols with spaces should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_ticker_symbol("AA PL")
        assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_dot_in_symbol_raises_422(self) -> None:
        """Symbols with dots should raise HTTP 422."""
        with pytest.raises(HTTPException) as exc_info:
            await validate_ticker_symbol("BRK.B")
        assert exc_info.value.status_code == 422
