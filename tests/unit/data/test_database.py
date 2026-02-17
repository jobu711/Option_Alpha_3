"""Tests for the Database class: connection lifecycle, pragmas, and migrations."""

import pytest
import pytest_asyncio

from Option_Alpha.data.database import Database


@pytest_asyncio.fixture()
async def memory_db() -> Database:
    """Create a Database with an in-memory SQLite backend."""
    return Database(db_path=":memory:")


class TestDatabaseConnect:
    """Tests for Database.connect() and connection properties."""

    @pytest.mark.asyncio()
    async def test_connect_creates_connection(self, memory_db: Database) -> None:
        """connect() should create a live connection."""
        await memory_db.connect()
        assert memory_db._connection is not None
        await memory_db.close()

    @pytest.mark.asyncio()
    async def test_connection_property_raises_when_not_connected(
        self, memory_db: Database
    ) -> None:
        """Accessing .connection before connect() should raise RuntimeError."""
        with pytest.raises(RuntimeError, match="not connected"):
            _ = memory_db.connection

    @pytest.mark.asyncio()
    async def test_wal_mode_enabled(self, memory_db: Database) -> None:
        """WAL journal mode should be active after connect."""
        await memory_db.connect()
        cursor = await memory_db.connection.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row is not None
        # In-memory databases may report "memory" instead of "wal",
        # but for file-backed DBs it would be "wal". For :memory:,
        # SQLite cannot use WAL, so we just verify the pragma ran without error.
        assert row[0] in ("wal", "memory")
        await memory_db.close()

    @pytest.mark.asyncio()
    async def test_foreign_keys_enabled(self, memory_db: Database) -> None:
        """PRAGMA foreign_keys should be ON after connect."""
        await memory_db.connect()
        cursor = await memory_db.connection.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1
        await memory_db.close()


class TestDatabaseClose:
    """Tests for Database.close()."""

    @pytest.mark.asyncio()
    async def test_close_sets_connection_to_none(self, memory_db: Database) -> None:
        """close() should set the internal connection to None."""
        await memory_db.connect()
        await memory_db.close()
        assert memory_db._connection is None

    @pytest.mark.asyncio()
    async def test_close_when_not_connected_is_safe(self, memory_db: Database) -> None:
        """close() on a never-connected Database should not raise."""
        await memory_db.close()  # Should not raise


class TestDatabaseContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio()
    async def test_context_manager_connects_and_closes(self) -> None:
        """async with Database() should connect on enter and close on exit."""
        db = Database(db_path=":memory:")
        async with db:
            assert db._connection is not None
            # Verify we can execute queries
            cursor = await db.connection.execute("SELECT 1")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1
        # After exit, connection should be closed
        assert db._connection is None


class TestDatabaseMigrations:
    """Tests for the migration runner."""

    @pytest.mark.asyncio()
    async def test_migrations_create_tables(self) -> None:
        """After connect, all expected tables should exist."""
        async with Database(db_path=":memory:") as db:
            conn = db.connection
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            expected_tables = [
                "ai_theses",
                "scan_runs",
                "schema_version",
                "ticker_scores",
                "watchlist_tickers",
                "watchlists",
            ]
            for table in expected_tables:
                assert table in tables, f"Table {table} not found in {tables}"

    @pytest.mark.asyncio()
    async def test_migrations_are_idempotent(self) -> None:
        """Running migrations twice should not raise any errors."""
        db = Database(db_path=":memory:")
        await db.connect()
        # Running migrations again via _run_migrations should be safe
        await db._run_migrations()
        # Verify schema_version has exactly one entry (version 1)
        cursor = await db.connection.execute("SELECT COUNT(*) FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1
        await db.close()

    @pytest.mark.asyncio()
    async def test_schema_version_records_migration(self) -> None:
        """schema_version should contain an entry for the applied migration."""
        async with Database(db_path=":memory:") as db:
            cursor = await db.connection.execute("SELECT version, applied_at FROM schema_version")
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == 1  # version
            assert rows[0][1] is not None  # applied_at is populated

    @pytest.mark.asyncio()
    async def test_indexes_created(self) -> None:
        """Expected indexes should exist after migration."""
        async with Database(db_path=":memory:") as db:
            cursor = await db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
            )
            indexes = [row[0] for row in await cursor.fetchall()]
            expected_indexes = [
                "idx_ai_theses_direction",
                "idx_ai_theses_ticker",
                "idx_ticker_scores_scan_run",
                "idx_ticker_scores_ticker",
            ]
            for index in expected_indexes:
                assert index in indexes, f"Index {index} not found in {indexes}"
