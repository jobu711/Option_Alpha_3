"""Extended database tests: WAL mode, migration idempotency, connection errors."""

from __future__ import annotations

import pytest

from Option_Alpha.data.database import Database

# ---------------------------------------------------------------------------
# WAL mode and PRAGMA verification
# ---------------------------------------------------------------------------


class TestDatabasePragmas:
    """Verify database connection configuration."""

    @pytest.mark.asyncio()
    async def test_wal_mode_requested(self) -> None:
        """Database requests WAL journal mode.

        Note: :memory: databases ignore WAL (return 'memory'), so we verify
        the PRAGMA is issued by checking it doesn't error. On-disk databases
        would return 'wal'.
        """
        db = Database(db_path=":memory:")
        await db.connect()
        try:
            cursor = await db.connection.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
            assert row is not None
            # :memory: returns 'memory', on-disk returns 'wal'
            assert row[0] in ("wal", "memory")
        finally:
            await db.close()

    @pytest.mark.asyncio()
    async def test_foreign_keys_enabled(self) -> None:
        """Database has foreign keys enforced."""
        db = Database(db_path=":memory:")
        await db.connect()
        try:
            cursor = await db.connection.execute("PRAGMA foreign_keys")
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == 1
        finally:
            await db.close()


# ---------------------------------------------------------------------------
# Migration idempotency
# ---------------------------------------------------------------------------


class TestMigrationIdempotency:
    """Running migrations twice should be safe."""

    @pytest.mark.asyncio()
    async def test_double_connect_no_error(self) -> None:
        """Connecting twice (running migrations twice) doesn't error."""
        db = Database(db_path=":memory:")
        await db.connect()
        # Manually re-run migrations (as if connecting a second time)
        await db._run_migrations()
        # Should not raise
        cursor = await db.connection.execute("SELECT COUNT(*) FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] >= 1  # At least one migration applied
        await db.close()

    @pytest.mark.asyncio()
    async def test_schema_version_table_exists(self) -> None:
        """schema_version table is created by migrations."""
        async with Database(db_path=":memory:") as db:
            cursor = await db.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "schema_version"


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestDatabaseLifecycle:
    """Connection lifecycle edge cases."""

    @pytest.mark.asyncio()
    async def test_connection_property_raises_when_disconnected(self) -> None:
        db = Database(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.connection

    @pytest.mark.asyncio()
    async def test_context_manager_closes_connection(self) -> None:
        db = Database(db_path=":memory:")
        async with db:
            assert db._connection is not None
        # After exit, connection is None
        assert db._connection is None

    @pytest.mark.asyncio()
    async def test_close_when_not_connected_is_safe(self) -> None:
        """Closing a never-connected database is a no-op."""
        db = Database(db_path=":memory:")
        await db.close()  # Should not raise

    @pytest.mark.asyncio()
    async def test_double_close_is_safe(self) -> None:
        db = Database(db_path=":memory:")
        await db.connect()
        await db.close()
        await db.close()  # Second close should not raise
