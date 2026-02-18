"""Repository layer for all database query operations.

Provides typed CRUD operations backed by a Database instance. All queries use
parameterized SQL (no string interpolation). JSON columns are serialized with
json.dumps() and deserialized with json.loads().
"""

import datetime
import json
import logging
import sqlite3

from Option_Alpha.data.database import Database
from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.models.scan import ScanRun, TickerScore, WatchlistSummary

logger = logging.getLogger(__name__)


class Repository:
    """Query interface for the Option Alpha persistence layer.

    All methods operate through the provided Database instance's connection.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Scan operations
    # ------------------------------------------------------------------

    async def save_scan_run(self, scan: ScanRun) -> None:
        """Persist a ScanRun record.

        Uses ``INSERT OR REPLACE`` so that an initial "running" row can be
        updated to "completed" or "failed" without a separate update method.
        """
        conn = self._db.connection
        await conn.execute(
            "INSERT OR REPLACE INTO scan_runs "
            "(id, started_at, completed_at, status, preset, sectors, ticker_count, top_n) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                scan.id,
                scan.started_at.isoformat(),
                scan.completed_at.isoformat() if scan.completed_at else None,
                scan.status,
                scan.preset,
                json.dumps(scan.sectors),
                scan.ticker_count,
                scan.top_n,
            ),
        )
        await conn.commit()

    async def save_ticker_scores(self, scan_run_id: str, scores: list[TickerScore]) -> None:
        """Batch-insert ticker scores for a scan run.

        The TickerScore model has no direction field, so we derive direction
        from the overall score: positive => bullish, negative => bearish,
        zero => neutral.
        """
        conn = self._db.connection
        rows = [
            (
                scan_run_id,
                score.ticker,
                score.score,
                _derive_direction(score.score),
                json.dumps(score.signals),
                score.rank,
            )
            for score in scores
        ]
        await conn.executemany(
            "INSERT INTO ticker_scores "
            "(scan_run_id, ticker, composite_score, direction, score_breakdown, rank) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        await conn.commit()

    async def get_latest_scan(self) -> ScanRun | None:
        """Return the most recent ScanRun by started_at, or None if empty."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT id, started_at, completed_at, status, preset, sectors, "
            "ticker_count, top_n FROM scan_runs ORDER BY started_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_scan_run(row)

    async def get_scan_by_id(self, scan_id: str) -> ScanRun | None:
        """Return a ScanRun by its ID, or None if not found."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT id, started_at, completed_at, status, preset, sectors, "
            "ticker_count, top_n FROM scan_runs WHERE id = ?",
            (scan_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_scan_run(row)

    async def list_scan_runs(self, *, limit: int = 20, offset: int = 0) -> list[ScanRun]:
        """Return scan runs ordered by most recent, with pagination."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT id, started_at, completed_at, status, preset, sectors, "
            "ticker_count, top_n FROM scan_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_scan_run(row) for row in rows]

    async def get_scores_for_scan(self, scan_run_id: str) -> list[TickerScore]:
        """Return all TickerScores for a given scan run, ordered by rank."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT ticker, composite_score, score_breakdown, rank "
            "FROM ticker_scores WHERE scan_run_id = ? ORDER BY rank",
            (scan_run_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_ticker_score(row) for row in rows]

    # ------------------------------------------------------------------
    # Ticker history
    # ------------------------------------------------------------------

    async def get_ticker_history(self, ticker: str, limit: int = 10) -> list[TickerScore]:
        """Return recent TickerScores for a ticker across all scans."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT ts.ticker, ts.composite_score, ts.score_breakdown, ts.rank "
            "FROM ticker_scores ts "
            "JOIN scan_runs sr ON ts.scan_run_id = sr.id "
            "WHERE ts.ticker = ? "
            "ORDER BY sr.started_at DESC LIMIT ?",
            (ticker, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_ticker_score(row) for row in rows]

    async def get_batch_ticker_history(
        self, tickers: list[str], limit: int = 10
    ) -> dict[str, list[TickerScore]]:
        """Return recent TickerScores for multiple tickers.

        Returns a dict mapping ticker -> list[TickerScore]. Tickers with no
        history are omitted from the result.
        """
        result: dict[str, list[TickerScore]] = {}
        for ticker in tickers:
            scores = await self.get_ticker_history(ticker, limit=limit)
            if scores:
                result[ticker] = scores
        return result

    # ------------------------------------------------------------------
    # AI thesis
    # ------------------------------------------------------------------

    async def save_ai_thesis(self, ticker: str, thesis: TradeThesis) -> None:
        """Persist an AI-generated TradeThesis for a ticker."""
        conn = self._db.connection
        timestamp = datetime.datetime.now(datetime.UTC).isoformat()
        full_thesis_json = thesis.model_dump_json()
        await conn.execute(
            "INSERT INTO ai_theses "
            "(ticker, timestamp, direction, conviction, model_used, total_tokens, "
            "duration_ms, entry_rationale, risk_factors, recommended_action, "
            "bull_summary, bear_summary, disclaimer, full_thesis) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticker,
                timestamp,
                thesis.direction.value,
                thesis.conviction,
                thesis.model_used,
                thesis.total_tokens,
                thesis.duration_ms,
                thesis.entry_rationale,
                json.dumps(thesis.risk_factors),
                thesis.recommended_action,
                thesis.bull_summary,
                thesis.bear_summary,
                thesis.disclaimer,
                full_thesis_json,
            ),
        )
        await conn.commit()

    async def get_thesis_raw_by_id(self, debate_id: int) -> tuple[str, str] | None:
        """Return ``(ticker, full_thesis_json)`` for a debate by its database row ID.

        Unlike :meth:`get_debate_by_id` which deserializes immediately, this
        returns the raw ticker and JSON string so that callers (e.g. the report
        endpoint) can build additional context before deserialization.
        """
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT ticker, full_thesis FROM ai_theses WHERE id = ?",
            (debate_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return (str(row[0]), str(row[1]))

    async def get_debate_by_id(self, debate_id: int) -> TradeThesis | None:
        """Return a single AI thesis by its database row ID, or None if not found."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT full_thesis FROM ai_theses WHERE id = ?",
            (debate_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return TradeThesis.model_validate_json(row[0])

    async def list_debates(self, *, limit: int = 20, offset: int = 0) -> list[TradeThesis]:
        """Return recent AI theses across all tickers, with pagination."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT full_thesis FROM ai_theses ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [TradeThesis.model_validate_json(row[0]) for row in rows]

    async def get_debate_history(
        self,
        ticker: str,
        *,
        direction: SignalDirection | None = None,
        limit: int = 10,
    ) -> list[TradeThesis]:
        """Return recent AI theses for a ticker, optionally filtered by direction."""
        conn = self._db.connection
        if direction is not None:
            cursor = await conn.execute(
                "SELECT full_thesis FROM ai_theses "
                "WHERE ticker = ? AND direction = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (ticker, direction.value, limit),
            )
        else:
            cursor = await conn.execute(
                "SELECT full_thesis FROM ai_theses "
                "WHERE ticker = ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (ticker, limit),
            )
        rows = await cursor.fetchall()
        return [TradeThesis.model_validate_json(row[0]) for row in rows]

    # ------------------------------------------------------------------
    # Watchlist CRUD
    # ------------------------------------------------------------------

    async def create_watchlist(self, name: str) -> int:
        """Create a new watchlist and return its ID."""
        conn = self._db.connection
        created_at = datetime.datetime.now(datetime.UTC).isoformat()
        cursor = await conn.execute(
            "INSERT INTO watchlists (name, created_at) VALUES (?, ?)",
            (name, created_at),
        )
        await conn.commit()
        watchlist_id = cursor.lastrowid
        if watchlist_id is None:
            msg = "Failed to retrieve lastrowid after watchlist insert."
            raise RuntimeError(msg)
        return watchlist_id

    async def add_tickers_to_watchlist(self, watchlist_id: int, tickers: list[str]) -> None:
        """Add tickers to a watchlist. Duplicates are silently ignored."""
        conn = self._db.connection
        added_at = datetime.datetime.now(datetime.UTC).isoformat()
        rows = [(watchlist_id, ticker, added_at) for ticker in tickers]
        await conn.executemany(
            "INSERT OR IGNORE INTO watchlist_tickers (watchlist_id, ticker, added_at) "
            "VALUES (?, ?, ?)",
            rows,
        )
        await conn.commit()

    async def remove_tickers_from_watchlist(self, watchlist_id: int, tickers: list[str]) -> None:
        """Remove tickers from a watchlist."""
        conn = self._db.connection
        for ticker in tickers:
            await conn.execute(
                "DELETE FROM watchlist_tickers WHERE watchlist_id = ? AND ticker = ?",
                (watchlist_id, ticker),
            )
        await conn.commit()

    async def list_watchlists(self) -> list[WatchlistSummary]:
        """Return all watchlists as typed WatchlistSummary models."""
        conn = self._db.connection
        cursor = await conn.execute("SELECT id, name, created_at FROM watchlists ORDER BY name")
        rows = await cursor.fetchall()
        return [WatchlistSummary(id=row[0], name=row[1], created_at=row[2]) for row in rows]

    async def get_watchlist_tickers(self, watchlist_id: int) -> list[str]:
        """Return all ticker symbols in a watchlist, sorted alphabetically."""
        conn = self._db.connection
        cursor = await conn.execute(
            "SELECT ticker FROM watchlist_tickers WHERE watchlist_id = ? ORDER BY ticker",
            (watchlist_id,),
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def delete_watchlist(self, watchlist_id: int) -> None:
        """Delete a watchlist and all its ticker associations (CASCADE)."""
        conn = self._db.connection
        await conn.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
        await conn.commit()


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _derive_direction(score: float) -> str:
    """Derive a direction string from a composite score.

    Positive scores are bullish, negative are bearish, zero is neutral.
    """
    if score > 0:
        return SignalDirection.BULLISH.value
    if score < 0:
        return SignalDirection.BEARISH.value
    return SignalDirection.NEUTRAL.value


def _row_to_scan_run(row: sqlite3.Row) -> ScanRun:
    """Convert a database row tuple to a ScanRun model."""
    return ScanRun(
        id=row[0],
        started_at=datetime.datetime.fromisoformat(row[1]),
        completed_at=(datetime.datetime.fromisoformat(row[2]) if row[2] is not None else None),
        status=row[3],
        preset=row[4],
        sectors=json.loads(row[5]),
        ticker_count=row[6],
        top_n=row[7],
    )


def _row_to_ticker_score(row: sqlite3.Row) -> TickerScore:
    """Convert a database row tuple to a TickerScore model."""
    return TickerScore(
        ticker=row[0],
        score=row[1],
        signals=json.loads(row[2]),
        rank=row[3],
    )
