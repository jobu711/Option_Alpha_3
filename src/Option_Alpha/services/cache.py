"""In-memory and SQLite caching layer with TTL and market-hours awareness.

Provides a cache-first pattern for data fetching: check cache, fetch on miss,
store, and return. Short-lived data (option chains, quotes) lives in memory;
persistent data (OHLCV, fundamentals) goes to SQLite via the Database class.
TTLs automatically lengthen outside US market hours.
"""

from __future__ import annotations

import datetime
import logging
from typing import Final
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from Option_Alpha.data.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — TTL values in seconds
# ---------------------------------------------------------------------------

# Permanent data (effectively infinite TTL)
TTL_OHLCV_PERMANENT: Final[int] = 0  # 0 means never expires

# Market-hours TTLs
TTL_OPTION_CHAIN_MARKET: Final[int] = 5 * 60  # 5 minutes
TTL_OPTION_CHAIN_AFTER: Final[int] = 60 * 60  # 1 hour
TTL_INTRADAY_QUOTE_MARKET: Final[int] = 1 * 60  # 1 minute
TTL_INTRADAY_QUOTE_AFTER: Final[int] = 5 * 60  # 5 minutes

# Fixed TTLs (same regardless of market hours)
TTL_IV_RANK: Final[int] = 60 * 60  # 1 hour
TTL_FUNDAMENTALS: Final[int] = 24 * 60 * 60  # 24 hours
TTL_EARNINGS: Final[int] = 24 * 60 * 60  # 24 hours
TTL_FAILURE: Final[int] = 24 * 60 * 60  # 24 hours

# Market hours constants
MARKET_OPEN_HOUR: Final[int] = 9
MARKET_OPEN_MINUTE: Final[int] = 30
MARKET_CLOSE_HOUR: Final[int] = 16
MARKET_CLOSE_MINUTE: Final[int] = 0

# Data type string constants
DATA_TYPE_OHLCV: Final[str] = "ohlcv"
DATA_TYPE_CHAIN: Final[str] = "chain"
DATA_TYPE_QUOTE: Final[str] = "quote"
DATA_TYPE_IV_RANK: Final[str] = "iv_rank"
DATA_TYPE_IV_PERCENTILE: Final[str] = "iv_percentile"
DATA_TYPE_FUNDAMENTALS: Final[str] = "fundamentals"
DATA_TYPE_EARNINGS: Final[str] = "earnings"
DATA_TYPE_FAILURE: Final[str] = "failure"

# Lazy cleanup: run eviction at most every N accesses
LAZY_CLEANUP_INTERVAL: Final[int] = 100

# SQLite cache table DDL
_CACHE_TABLE_DDL: Final[str] = (
    "CREATE TABLE IF NOT EXISTS service_cache ("
    "  key TEXT PRIMARY KEY,"
    "  value TEXT NOT NULL,"
    "  created_at TEXT NOT NULL,"
    "  ttl_seconds INTEGER NOT NULL"
    ")"
)

ET_TIMEZONE: Final[ZoneInfo] = ZoneInfo("America/New_York")


class CacheEntry(BaseModel):
    """A single cached value with metadata for expiration checking."""

    model_config = ConfigDict(frozen=True)

    key: str
    value: str  # JSON-serialized payload
    created_at: datetime.datetime
    ttl_seconds: int

    def is_expired(self) -> bool:
        """Return True if this entry has exceeded its TTL.

        A ttl_seconds of 0 means the entry never expires (permanent data).
        """
        if self.ttl_seconds == 0:
            return False
        now = datetime.datetime.now(datetime.UTC)
        age = (now - self.created_at).total_seconds()
        return age > self.ttl_seconds


class ServiceCache:
    """Two-tier cache: in-memory dict for short-lived data, SQLite for persistent.

    Usage::

        async with Database("data/options.db") as db:
            cache = ServiceCache(database=db)
            await cache.initialize()

            # Check cache
            cached = await cache.get("yf:chain:AAPL:2025-04-18")
            if cached is None:
                data = await fetch_option_chain("AAPL", "2025-04-18")
                await cache.set(
                    "yf:chain:AAPL:2025-04-18",
                    json.dumps(data),
                    cache.get_ttl(DATA_TYPE_CHAIN),
                )
    """

    def __init__(self, database: Database | None = None) -> None:
        self._database = database
        self._memory_cache: dict[str, CacheEntry] = {}
        self._access_count: int = 0
        self._sqlite_initialized: bool = False

        logger.info(
            "ServiceCache initialized: sqlite=%s",
            "enabled" if database is not None else "disabled",
        )

    async def initialize(self) -> None:
        """Create the SQLite cache table if a database is configured.

        Must be called after the database connection is open. Safe to call
        multiple times (idempotent).
        """
        if self._database is not None and not self._sqlite_initialized:
            conn = self._database.connection
            await conn.execute(_CACHE_TABLE_DDL)
            await conn.commit()
            self._sqlite_initialized = True
            logger.info("SQLite cache table initialized.")

    async def get(self, key: str) -> str | None:
        """Retrieve a cached value by key.

        Checks in-memory first, then SQLite. Returns None on miss or if the
        entry has expired. Expired entries are lazily removed.
        """
        self._increment_access_count()

        # Check in-memory cache first
        entry = self._memory_cache.get(key)
        if entry is not None:
            if entry.is_expired():
                del self._memory_cache[key]
                logger.debug("Memory cache expired: %s", key)
                return None
            logger.debug("Memory cache hit: %s", key)
            return entry.value

        # Check SQLite cache
        if self._database is not None and self._sqlite_initialized:
            entry = await self._sqlite_get(key)
            if entry is not None:
                if entry.is_expired():
                    await self._sqlite_delete(key)
                    logger.debug("SQLite cache expired: %s", key)
                    return None
                logger.debug("SQLite cache hit: %s", key)
                return entry.value

        logger.debug("Cache miss: %s", key)
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store a value in the cache.

        Short-TTL data (option chains, quotes) is stored in memory only.
        Persistent data (OHLCV, fundamentals, IV rank, earnings, failures)
        is stored in SQLite. The routing is determined by the data type
        extracted from the key.
        """
        now = datetime.datetime.now(datetime.UTC)
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=now,
            ttl_seconds=ttl_seconds,
        )

        if self._should_use_sqlite(key):
            if self._database is not None and self._sqlite_initialized:
                await self._sqlite_set(entry)
                logger.debug("SQLite cache set: %s (ttl=%ds)", key, ttl_seconds)
            else:
                # Fall back to memory if SQLite is not available
                self._memory_cache[key] = entry
                logger.debug(
                    "Memory cache set (sqlite fallback): %s (ttl=%ds)",
                    key,
                    ttl_seconds,
                )
        else:
            self._memory_cache[key] = entry
            logger.debug("Memory cache set: %s (ttl=%ds)", key, ttl_seconds)

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from both cache tiers."""
        self._memory_cache.pop(key, None)

        if self._database is not None and self._sqlite_initialized:
            await self._sqlite_delete(key)

        logger.debug("Cache invalidated: %s", key)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Remove all keys matching a pattern from both cache tiers.

        Supports simple glob patterns with ``*`` as a wildcard suffix.
        For example, ``"yf:chain:AAPL:*"`` removes all AAPL chain entries.
        """
        # Handle memory cache
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            keys_to_remove = [k for k in self._memory_cache if k.startswith(prefix)]
        else:
            keys_to_remove = [k for k in self._memory_cache if k == pattern]

        for key in keys_to_remove:
            del self._memory_cache[key]

        # Handle SQLite cache
        if self._database is not None and self._sqlite_initialized:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                conn = self._database.connection
                await conn.execute(
                    "DELETE FROM service_cache WHERE key LIKE ?",
                    (prefix + "%",),
                )
                await conn.commit()
            else:
                await self._sqlite_delete(pattern)

        removed_count = len(keys_to_remove)
        logger.debug(
            "Cache invalidated pattern '%s': %d memory entries removed",
            pattern,
            removed_count,
        )

    def is_market_hours(self) -> bool:
        """Return True if US equity markets are currently open.

        Market hours: 9:30 AM - 4:00 PM ET, Monday through Friday.
        Does not account for market holidays.
        """
        now_et = datetime.datetime.now(ET_TIMEZONE)

        # Check weekday (0=Monday, 6=Sunday)
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False

        market_open = now_et.replace(
            hour=MARKET_OPEN_HOUR,
            minute=MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0,
        )
        market_close = now_et.replace(
            hour=MARKET_CLOSE_HOUR,
            minute=MARKET_CLOSE_MINUTE,
            second=0,
            microsecond=0,
        )

        return market_open <= now_et < market_close

    def get_ttl(self, data_type: str) -> int:
        """Return the appropriate TTL in seconds for a data type.

        Market-hours-sensitive types (chains, quotes) return shorter TTLs
        during trading hours and longer TTLs after hours.

        Args:
            data_type: One of the DATA_TYPE_* constants.

        Returns:
            TTL in seconds. 0 means permanent (never expires).
        """
        during_market = self.is_market_hours()

        match data_type:
            case "ohlcv":
                return TTL_OHLCV_PERMANENT
            case "chain":
                return TTL_OPTION_CHAIN_MARKET if during_market else TTL_OPTION_CHAIN_AFTER
            case "quote":
                return TTL_INTRADAY_QUOTE_MARKET if during_market else TTL_INTRADAY_QUOTE_AFTER
            case "iv_rank" | "iv_percentile":
                return TTL_IV_RANK
            case "fundamentals":
                return TTL_FUNDAMENTALS
            case "earnings":
                return TTL_EARNINGS
            case "failure":
                return TTL_FAILURE
            case _:
                logger.warning("Unknown data type '%s', using 5-minute TTL", data_type)
                default_ttl: int = 5 * 60
                return default_ttl

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_use_sqlite(self, key: str) -> bool:
        """Determine whether a key should be stored in SQLite.

        Keys containing these data types go to SQLite (persistent):
        - ohlcv, iv_rank, iv_percentile, fundamentals, earnings, failure

        Keys containing these data types stay in memory (short-lived):
        - chain, quote
        """
        parts = key.split(":")
        if len(parts) < 2:  # noqa: PLR2004
            return False

        data_type = parts[1]
        sqlite_types = {
            DATA_TYPE_OHLCV,
            DATA_TYPE_IV_RANK,
            DATA_TYPE_IV_PERCENTILE,
            DATA_TYPE_FUNDAMENTALS,
            DATA_TYPE_EARNINGS,
            DATA_TYPE_FAILURE,
        }
        return data_type in sqlite_types

    def _increment_access_count(self) -> None:
        """Track accesses and trigger lazy cleanup when threshold is reached."""
        self._access_count += 1
        if self._access_count >= LAZY_CLEANUP_INTERVAL:
            self._access_count = 0
            self._evict_expired_memory_entries()

    def _evict_expired_memory_entries(self) -> None:
        """Remove expired entries from the in-memory cache.

        Called lazily rather than on every access to reduce overhead.
        """
        expired_keys = [k for k, v in self._memory_cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._memory_cache[key]

        if expired_keys:
            logger.debug(
                "Lazy cleanup: evicted %d expired memory entries",
                len(expired_keys),
            )

    # ------------------------------------------------------------------
    # SQLite operations
    # ------------------------------------------------------------------

    async def _sqlite_get(self, key: str) -> CacheEntry | None:
        """Retrieve a CacheEntry from the SQLite cache table."""
        if self._database is None:
            return None

        conn = self._database.connection
        cursor = await conn.execute(
            "SELECT key, value, created_at, ttl_seconds FROM service_cache WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        return CacheEntry(
            key=row[0],
            value=row[1],
            created_at=datetime.datetime.fromisoformat(row[2]),
            ttl_seconds=row[3],
        )

    async def _sqlite_set(self, entry: CacheEntry) -> None:
        """Insert or replace a CacheEntry in the SQLite cache table."""
        if self._database is None:
            return

        conn = self._database.connection
        await conn.execute(
            "INSERT OR REPLACE INTO service_cache (key, value, created_at, ttl_seconds) "
            "VALUES (?, ?, ?, ?)",
            (
                entry.key,
                entry.value,
                entry.created_at.isoformat(),
                entry.ttl_seconds,
            ),
        )
        await conn.commit()

    async def _sqlite_delete(self, key: str) -> None:
        """Delete a single key from the SQLite cache table."""
        if self._database is None:
            return

        conn = self._database.connection
        await conn.execute("DELETE FROM service_cache WHERE key = ?", (key,))
        await conn.commit()
