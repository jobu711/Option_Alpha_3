"""Tests for ServiceCache: in-memory, SQLite, TTL, market hours, and cleanup.

Covers:
- In-memory get/set/invalidate
- TTL expiration (mocked datetime)
- SQLite get/set/invalidate (real aiosqlite with in-memory DB)
- invalidate_pattern() with wildcard
- is_market_hours() for open, close, and weekend
- get_ttl() returns correct values per data type
- get_ttl() differs during/outside market hours
- _should_use_sqlite() routing logic
- Lazy cleanup triggers after LAZY_CLEANUP_INTERVAL accesses
- Permanent TTL (0) entries never expire
- Cache miss returns None
"""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest

from Option_Alpha.data.database import Database
from Option_Alpha.services.cache import (
    DATA_TYPE_CHAIN,
    DATA_TYPE_EARNINGS,
    DATA_TYPE_FUNDAMENTALS,
    DATA_TYPE_IV_RANK,
    DATA_TYPE_OHLCV,
    DATA_TYPE_QUOTE,
    LAZY_CLEANUP_INTERVAL,
    TTL_EARNINGS,
    TTL_FUNDAMENTALS,
    TTL_INTRADAY_QUOTE_AFTER,
    TTL_INTRADAY_QUOTE_MARKET,
    TTL_IV_RANK,
    TTL_OHLCV_PERMANENT,
    TTL_OPTION_CHAIN_AFTER,
    TTL_OPTION_CHAIN_MARKET,
    CacheEntry,
    ServiceCache,
)


@pytest.fixture()
def memory_cache() -> ServiceCache:
    """ServiceCache with no SQLite backend (memory only)."""
    return ServiceCache(database=None)


class TestInMemoryCache:
    """Tests for basic in-memory cache operations."""

    @pytest.mark.asyncio()
    async def test_set_and_get_returns_value(self, memory_cache: ServiceCache) -> None:
        """set() stores a value that get() can retrieve."""
        await memory_cache.set("yf:quote:AAPL", '{"price": 186.5}', 300)
        result = await memory_cache.get("yf:quote:AAPL")
        assert result == '{"price": 186.5}'

    @pytest.mark.asyncio()
    async def test_get_returns_none_on_miss(self, memory_cache: ServiceCache) -> None:
        """get() returns None for a key that was never set."""
        result = await memory_cache.get("nonexistent:key")
        assert result is None

    @pytest.mark.asyncio()
    async def test_invalidate_removes_key(self, memory_cache: ServiceCache) -> None:
        """invalidate() removes a previously set key."""
        await memory_cache.set("yf:quote:AAPL", "data", 300)
        await memory_cache.invalidate("yf:quote:AAPL")
        result = await memory_cache.get("yf:quote:AAPL")
        assert result is None

    @pytest.mark.asyncio()
    async def test_invalidate_nonexistent_key_is_safe(self, memory_cache: ServiceCache) -> None:
        """invalidate() on a missing key does not raise."""
        await memory_cache.invalidate("nonexistent:key")  # Should not raise


class TestTTLExpiration:
    """Tests for cache entry TTL and expiration behavior."""

    @pytest.mark.asyncio()
    async def test_expired_entry_returns_none(self, memory_cache: ServiceCache) -> None:
        """get() returns None when the cached entry has expired."""
        # Set a value with 60-second TTL
        await memory_cache.set("yf:quote:AAPL", "data", 60)

        # Mock datetime.now to be 120 seconds in the future
        future = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=120)
        with patch("Option_Alpha.services.cache.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = future
            mock_dt.UTC = datetime.UTC
            # CacheEntry.is_expired() also uses datetime.datetime.now
            # We need to patch at the module level since CacheEntry imports it
            result = await memory_cache.get("yf:quote:AAPL")

        assert result is None

    def test_cache_entry_is_expired_when_ttl_exceeded(self) -> None:
        """CacheEntry.is_expired() returns True when age > ttl_seconds."""
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=120)
        entry = CacheEntry(
            key="test",
            value="data",
            created_at=old_time,
            ttl_seconds=60,
        )
        assert entry.is_expired() is True

    def test_cache_entry_not_expired_within_ttl(self) -> None:
        """CacheEntry.is_expired() returns False when age < ttl_seconds."""
        recent = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=10)
        entry = CacheEntry(
            key="test",
            value="data",
            created_at=recent,
            ttl_seconds=60,
        )
        assert entry.is_expired() is False

    def test_permanent_ttl_never_expires(self) -> None:
        """CacheEntry with ttl_seconds=0 never expires (permanent data)."""
        ancient = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=365)
        entry = CacheEntry(
            key="test",
            value="permanent",
            created_at=ancient,
            ttl_seconds=0,
        )
        assert entry.is_expired() is False


class TestSQLiteCache:
    """Tests for SQLite-backed cache operations using a real in-memory DB."""

    @pytest.mark.asyncio()
    async def test_sqlite_set_and_get(self) -> None:
        """Values stored in SQLite can be retrieved."""
        async with Database(db_path=":memory:") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()

            # OHLCV data routes to SQLite
            key = "yf:ohlcv:AAPL:1y"
            await cache.set(key, '{"bars": []}', 0)

            result = await cache.get(key)
            assert result == '{"bars": []}'

    @pytest.mark.asyncio()
    async def test_sqlite_invalidate(self) -> None:
        """invalidate() removes a key from SQLite."""
        async with Database(db_path=":memory:") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()

            key = "yf:ohlcv:AAPL:1y"
            await cache.set(key, "data", 0)
            await cache.invalidate(key)

            result = await cache.get(key)
            assert result is None

    @pytest.mark.asyncio()
    async def test_sqlite_expired_entry_returns_none(self) -> None:
        """Expired SQLite entries return None and are cleaned up."""
        async with Database(db_path=":memory:") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()

            # Store with a short TTL
            key = "yf:fundamentals:AAPL"
            await cache.set(key, "old_data", 1)

            # Force expiration by waiting
            import asyncio

            await asyncio.sleep(1.1)

            result = await cache.get(key)
            assert result is None


class TestInvalidatePattern:
    """Tests for invalidate_pattern() with wildcard matching."""

    @pytest.mark.asyncio()
    async def test_invalidate_pattern_with_wildcard(self, memory_cache: ServiceCache) -> None:
        """invalidate_pattern('yf:chain:AAPL:*') removes all matching keys."""
        await memory_cache.set("yf:chain:AAPL:2025-04-18", "data1", 300)
        await memory_cache.set("yf:chain:AAPL:2025-05-16", "data2", 300)
        await memory_cache.set("yf:chain:MSFT:2025-04-18", "data3", 300)

        await memory_cache.invalidate_pattern("yf:chain:AAPL:*")

        assert await memory_cache.get("yf:chain:AAPL:2025-04-18") is None
        assert await memory_cache.get("yf:chain:AAPL:2025-05-16") is None
        # MSFT should remain
        assert await memory_cache.get("yf:chain:MSFT:2025-04-18") == "data3"

    @pytest.mark.asyncio()
    async def test_invalidate_pattern_exact_match(self, memory_cache: ServiceCache) -> None:
        """invalidate_pattern() without wildcard does exact match."""
        await memory_cache.set("yf:quote:AAPL", "data1", 300)
        await memory_cache.set("yf:quote:AAPL:extra", "data2", 300)

        await memory_cache.invalidate_pattern("yf:quote:AAPL")

        assert await memory_cache.get("yf:quote:AAPL") is None
        # Key with extra suffix should remain (not a wildcard match)
        assert await memory_cache.get("yf:quote:AAPL:extra") == "data2"

    @pytest.mark.asyncio()
    async def test_invalidate_pattern_sqlite_wildcard(self) -> None:
        """invalidate_pattern with wildcard also clears SQLite entries."""
        async with Database(db_path=":memory:") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()

            await cache.set("yf:ohlcv:AAPL:1y", "d1", 0)
            await cache.set("yf:ohlcv:AAPL:6mo", "d2", 0)
            await cache.set("yf:ohlcv:MSFT:1y", "d3", 0)

            await cache.invalidate_pattern("yf:ohlcv:AAPL:*")

            assert await cache.get("yf:ohlcv:AAPL:1y") is None
            assert await cache.get("yf:ohlcv:AAPL:6mo") is None
            assert await cache.get("yf:ohlcv:MSFT:1y") == "d3"


class TestIsMarketHours:
    """Tests for is_market_hours() with mocked datetime."""

    @pytest.mark.asyncio()
    async def test_market_hours_during_trading(self, memory_cache: ServiceCache) -> None:
        """is_market_hours() returns True during trading hours (Mon-Fri 9:30-16:00 ET)."""
        # Wednesday at 11:00 AM ET
        mock_now = datetime.datetime(
            2025,
            1,
            15,
            11,
            0,
            0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        with patch("Option_Alpha.services.cache.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = mock_now
            mock_dt.UTC = datetime.UTC
            assert memory_cache.is_market_hours() is True

    @pytest.mark.asyncio()
    async def test_market_hours_before_open(self, memory_cache: ServiceCache) -> None:
        """is_market_hours() returns False before 9:30 AM ET."""
        # Wednesday at 8:00 AM ET
        mock_now = datetime.datetime(
            2025,
            1,
            15,
            8,
            0,
            0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        with patch("Option_Alpha.services.cache.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = mock_now
            mock_dt.UTC = datetime.UTC
            assert memory_cache.is_market_hours() is False

    @pytest.mark.asyncio()
    async def test_market_hours_after_close(self, memory_cache: ServiceCache) -> None:
        """is_market_hours() returns False after 4:00 PM ET."""
        # Wednesday at 5:00 PM ET
        mock_now = datetime.datetime(
            2025,
            1,
            15,
            17,
            0,
            0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        with patch("Option_Alpha.services.cache.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = mock_now
            mock_dt.UTC = datetime.UTC
            assert memory_cache.is_market_hours() is False

    @pytest.mark.asyncio()
    async def test_market_hours_on_weekend(self, memory_cache: ServiceCache) -> None:
        """is_market_hours() returns False on Saturday/Sunday."""
        # Saturday at 11:00 AM ET
        mock_now = datetime.datetime(
            2025,
            1,
            18,
            11,
            0,
            0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        with patch("Option_Alpha.services.cache.datetime") as mock_dt:
            mock_dt.datetime.now.return_value = mock_now
            mock_dt.UTC = datetime.UTC
            assert memory_cache.is_market_hours() is False


class TestGetTTL:
    """Tests for get_ttl() data type TTL selection."""

    def test_ohlcv_ttl_is_permanent(self, memory_cache: ServiceCache) -> None:
        """OHLCV data has permanent TTL (0)."""
        with patch.object(memory_cache, "is_market_hours", return_value=True):
            assert memory_cache.get_ttl(DATA_TYPE_OHLCV) == TTL_OHLCV_PERMANENT

    def test_chain_ttl_during_market_hours(self, memory_cache: ServiceCache) -> None:
        """Chain TTL is shorter during market hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=True):
            assert memory_cache.get_ttl(DATA_TYPE_CHAIN) == TTL_OPTION_CHAIN_MARKET

    def test_chain_ttl_after_hours(self, memory_cache: ServiceCache) -> None:
        """Chain TTL is longer after market hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=False):
            assert memory_cache.get_ttl(DATA_TYPE_CHAIN) == TTL_OPTION_CHAIN_AFTER

    def test_quote_ttl_during_market_hours(self, memory_cache: ServiceCache) -> None:
        """Quote TTL is short during market hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=True):
            assert memory_cache.get_ttl(DATA_TYPE_QUOTE) == TTL_INTRADAY_QUOTE_MARKET

    def test_quote_ttl_after_hours(self, memory_cache: ServiceCache) -> None:
        """Quote TTL is longer after market hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=False):
            assert memory_cache.get_ttl(DATA_TYPE_QUOTE) == TTL_INTRADAY_QUOTE_AFTER

    def test_iv_rank_ttl(self, memory_cache: ServiceCache) -> None:
        """IV rank TTL is fixed (1 hour) regardless of market hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=True):
            assert memory_cache.get_ttl(DATA_TYPE_IV_RANK) == TTL_IV_RANK

    def test_fundamentals_ttl(self, memory_cache: ServiceCache) -> None:
        """Fundamentals TTL is 24 hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=False):
            assert memory_cache.get_ttl(DATA_TYPE_FUNDAMENTALS) == TTL_FUNDAMENTALS

    def test_earnings_ttl(self, memory_cache: ServiceCache) -> None:
        """Earnings TTL is 24 hours."""
        with patch.object(memory_cache, "is_market_hours", return_value=False):
            assert memory_cache.get_ttl(DATA_TYPE_EARNINGS) == TTL_EARNINGS

    def test_unknown_data_type_returns_default(self, memory_cache: ServiceCache) -> None:
        """Unknown data types get a default 5-minute TTL."""
        with patch.object(memory_cache, "is_market_hours", return_value=True):
            default_ttl = 5 * 60
            assert memory_cache.get_ttl("unknown_type") == default_ttl


class TestShouldUseSQLite:
    """Tests for _should_use_sqlite() routing logic."""

    def test_ohlcv_routes_to_sqlite(self, memory_cache: ServiceCache) -> None:
        """OHLCV keys route to SQLite (persistent data)."""
        assert memory_cache._should_use_sqlite("yf:ohlcv:AAPL:1y") is True

    def test_fundamentals_routes_to_sqlite(self, memory_cache: ServiceCache) -> None:
        """Fundamentals keys route to SQLite."""
        assert memory_cache._should_use_sqlite("yf:fundamentals:AAPL") is True

    def test_iv_rank_routes_to_sqlite(self, memory_cache: ServiceCache) -> None:
        """IV rank keys route to SQLite."""
        assert memory_cache._should_use_sqlite("yf:iv_rank:AAPL") is True

    def test_earnings_routes_to_sqlite(self, memory_cache: ServiceCache) -> None:
        """Earnings keys route to SQLite."""
        assert memory_cache._should_use_sqlite("yf:earnings:AAPL") is True

    def test_chain_routes_to_memory(self, memory_cache: ServiceCache) -> None:
        """Chain keys stay in memory (short-lived data)."""
        assert memory_cache._should_use_sqlite("yf:chain:AAPL:2025-04-18") is False

    def test_quote_routes_to_memory(self, memory_cache: ServiceCache) -> None:
        """Quote keys stay in memory (short-lived data)."""
        assert memory_cache._should_use_sqlite("yf:quote:AAPL") is False

    def test_short_key_routes_to_memory(self, memory_cache: ServiceCache) -> None:
        """Keys with fewer than 2 colon-separated parts go to memory."""
        assert memory_cache._should_use_sqlite("nocolon") is False


class TestLazyCleanup:
    """Tests for lazy cleanup triggered by access count."""

    @pytest.mark.asyncio()
    async def test_cleanup_triggers_at_interval(self, memory_cache: ServiceCache) -> None:
        """Expired entries are cleaned up after LAZY_CLEANUP_INTERVAL accesses."""
        # Store an entry that is already expired
        old_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=120)
        entry = CacheEntry(
            key="yf:quote:OLD",
            value="stale",
            created_at=old_time,
            ttl_seconds=60,
        )
        memory_cache._memory_cache["yf:quote:OLD"] = entry

        # Access the cache LAZY_CLEANUP_INTERVAL times to trigger cleanup
        for i in range(LAZY_CLEANUP_INTERVAL):
            await memory_cache.get(f"miss:{i}")

        # The expired entry should have been evicted
        assert "yf:quote:OLD" not in memory_cache._memory_cache

    @pytest.mark.asyncio()
    async def test_cleanup_does_not_remove_valid_entries(self, memory_cache: ServiceCache) -> None:
        """Lazy cleanup preserves entries that have not expired."""
        await memory_cache.set("yf:quote:FRESH", "good_data", 3600)

        # Trigger cleanup
        for i in range(LAZY_CLEANUP_INTERVAL):
            await memory_cache.get(f"miss:{i}")

        assert "yf:quote:FRESH" in memory_cache._memory_cache


class TestSQLiteFallback:
    """Tests for SQLite fallback behavior."""

    @pytest.mark.asyncio()
    async def test_sqlite_key_falls_back_to_memory_when_no_db(
        self, memory_cache: ServiceCache
    ) -> None:
        """When no database is configured, SQLite-destined keys go to memory."""
        await memory_cache.set("yf:ohlcv:AAPL:1y", "data", 0)
        result = await memory_cache.get("yf:ohlcv:AAPL:1y")
        assert result == "data"
        # Verify it's in memory
        assert "yf:ohlcv:AAPL:1y" in memory_cache._memory_cache

    @pytest.mark.asyncio()
    async def test_initialize_is_idempotent(self) -> None:
        """Calling initialize() multiple times is safe."""
        async with Database(db_path=":memory:") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()
            await cache.initialize()  # Should not raise
            # Verify the table exists
            cursor = await db.connection.execute(
                "SELECT name FROM sqlite_master WHERE name='service_cache'"
            )
            row = await cursor.fetchone()
            assert row is not None
