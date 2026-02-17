"""Database connection management, initialization, and migration runner.

Manages a single aiosqlite connection with WAL mode and foreign key enforcement.
Migrations are read from SQL files in the migrations/ directory and applied in order.
"""

import datetime
import logging
from pathlib import Path
from types import TracebackType

import aiosqlite

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class Database:
    """Async SQLite database with connection lifecycle and migration support.

    Usage::

        async with Database("data/options.db") as db:
            # db.connection is ready, migrations applied
            ...
    """

    def __init__(self, db_path: str = "data/options.db") -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Return the active connection or raise if not connected."""
        if self._connection is None:
            msg = "Database is not connected. Call connect() or use 'async with'."
            raise RuntimeError(msg)
        return self._connection

    async def connect(self) -> None:
        """Open the database connection, enable WAL + foreign keys, run migrations."""
        self._connection = await aiosqlite.connect(self._db_path)
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._run_migrations()
        logger.info("Database connected: %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Database closed: %s", self._db_path)

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def _run_migrations(self) -> None:
        """Apply pending SQL migrations from the migrations directory.

        Each migration file is named NNN_description.sql. The schema_version
        table tracks which versions have been applied. Running twice is safe
        (idempotent).
        """
        conn = self.connection

        # Ensure the schema_version table exists
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        await conn.commit()

        # Determine which versions are already applied
        cursor = await conn.execute("SELECT version FROM schema_version ORDER BY version")
        applied_rows = await cursor.fetchall()
        applied_versions: set[int] = {row[0] for row in applied_rows}

        # Discover and sort migration files
        migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))

        for migration_file in migration_files:
            version = int(migration_file.name.split("_", 1)[0])
            if version in applied_versions:
                logger.debug("Migration %03d already applied, skipping.", version)
                continue

            logger.info("Applying migration %03d: %s", version, migration_file.name)
            sql = migration_file.read_text(encoding="utf-8")
            # NOTE: executescript() auto-commits after each statement, so a failure
            # mid-migration may leave DDL partially applied. However, the version
            # won't be recorded in schema_version, so the migration retries on next
            # connect. For production use, keep each migration file atomic.
            await conn.executescript(sql)
            applied_at = datetime.datetime.now(datetime.UTC).isoformat()
            await conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, applied_at),
            )
            await conn.commit()
            logger.info("Migration %03d applied successfully.", version)
