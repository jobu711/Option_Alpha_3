"""Tests for Repository: all CRUD operations against an in-memory SQLite database."""

import datetime
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from Option_Alpha.data.database import Database
from Option_Alpha.data.repository import Repository
from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.models.scan import ScanRun, TickerScore


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[Database]:
    """Provide a connected in-memory Database for each test, with cleanup."""
    database = Database(db_path=":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest_asyncio.fixture()
async def repo(db: Database) -> Repository:
    """Provide a Repository backed by the in-memory Database."""
    return Repository(db)


@pytest.fixture()
def sample_scan() -> ScanRun:
    """A sample ScanRun for testing."""
    return ScanRun(
        id="scan-001",
        started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
        completed_at=datetime.datetime(2025, 1, 15, 9, 35, 0, tzinfo=datetime.UTC),
        status="completed",
        preset="high_iv",
        sectors=["Technology", "Healthcare"],
        ticker_count=50,
        top_n=10,
    )


@pytest.fixture()
def sample_scores() -> list[TickerScore]:
    """Sample TickerScores for testing batch insert."""
    return [
        TickerScore(
            ticker="AAPL",
            score=82.5,
            signals={"iv_rank": 45.2, "rsi_momentum": 22.3, "volume_surge": 15.0},
            rank=1,
        ),
        TickerScore(
            ticker="MSFT",
            score=75.3,
            signals={"iv_rank": 38.0, "rsi_momentum": 20.1, "volume_surge": 17.2},
            rank=2,
        ),
        TickerScore(
            ticker="GOOG",
            score=68.1,
            signals={"iv_rank": 52.0, "rsi_momentum": 10.5, "volume_surge": 5.6},
            rank=3,
        ),
    ]


@pytest.fixture()
def sample_thesis() -> TradeThesis:
    """A sample TradeThesis for testing."""
    return TradeThesis(
        direction=SignalDirection.BULLISH,
        conviction=0.72,
        entry_rationale="RSI at 55 with bullish MACD crossover suggests upward momentum.",
        risk_factors=["Earnings in 30 days", "IV rank elevated at 45%"],
        recommended_action="Buy 185 call expiring Feb 21",
        bull_summary="Technical momentum favors upside with support at 184.",
        bear_summary="Elevated IV may compress post-earnings, capping gains.",
        model_used="llama3.1:8b",
        total_tokens=1500,
        duration_ms=3200,
    )


# ------------------------------------------------------------------
# Scan operations
# ------------------------------------------------------------------


class TestScanOperations:
    """Tests for save_scan_run, get_latest_scan, get_scan_by_id."""

    @pytest.mark.asyncio()
    async def test_save_and_get_scan_by_id(self, repo: Repository, sample_scan: ScanRun) -> None:
        """Saving a scan run and retrieving by ID should return the same data."""
        await repo.save_scan_run(sample_scan)
        result = await repo.get_scan_by_id("scan-001")
        assert result is not None
        assert result.id == sample_scan.id
        assert result.status == sample_scan.status
        assert result.preset == sample_scan.preset
        assert result.sectors == sample_scan.sectors
        assert result.ticker_count == sample_scan.ticker_count
        assert result.top_n == sample_scan.top_n

    @pytest.mark.asyncio()
    async def test_get_scan_by_id_not_found(self, repo: Repository) -> None:
        """get_scan_by_id for a non-existent ID should return None."""
        result = await repo.get_scan_by_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio()
    async def test_get_latest_scan_empty(self, repo: Repository) -> None:
        """get_latest_scan on an empty database should return None."""
        result = await repo.get_latest_scan()
        assert result is None

    @pytest.mark.asyncio()
    async def test_get_latest_scan_returns_most_recent(self, repo: Repository) -> None:
        """get_latest_scan should return the scan with the latest started_at."""
        scan_old = ScanRun(
            id="scan-old",
            started_at=datetime.datetime(2025, 1, 14, 9, 0, 0, tzinfo=datetime.UTC),
            completed_at=datetime.datetime(2025, 1, 14, 9, 5, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="default",
            sectors=["Energy"],
            ticker_count=20,
            top_n=5,
        )
        scan_new = ScanRun(
            id="scan-new",
            started_at=datetime.datetime(2025, 1, 15, 9, 0, 0, tzinfo=datetime.UTC),
            completed_at=datetime.datetime(2025, 1, 15, 9, 5, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="high_iv",
            sectors=["Technology"],
            ticker_count=50,
            top_n=10,
        )
        await repo.save_scan_run(scan_old)
        await repo.save_scan_run(scan_new)
        result = await repo.get_latest_scan()
        assert result is not None
        assert result.id == "scan-new"

    @pytest.mark.asyncio()
    async def test_scan_run_with_null_completed_at(self, repo: Repository) -> None:
        """A scan with completed_at=None should roundtrip correctly."""
        scan = ScanRun(
            id="scan-running",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            completed_at=None,
            status="running",
            preset="default",
            sectors=["Financials"],
            ticker_count=30,
            top_n=5,
        )
        await repo.save_scan_run(scan)
        result = await repo.get_scan_by_id("scan-running")
        assert result is not None
        assert result.completed_at is None
        assert result.status == "running"


# ------------------------------------------------------------------
# Ticker score operations
# ------------------------------------------------------------------


class TestTickerScoreOperations:
    """Tests for save_ticker_scores, get_scores_for_scan, and ticker history."""

    @pytest.mark.asyncio()
    async def test_save_and_get_scores_for_scan(
        self,
        repo: Repository,
        sample_scan: ScanRun,
        sample_scores: list[TickerScore],
    ) -> None:
        """Saving scores and retrieving them should return all scores in rank order."""
        await repo.save_scan_run(sample_scan)
        await repo.save_ticker_scores(sample_scan.id, sample_scores)
        results = await repo.get_scores_for_scan(sample_scan.id)
        assert len(results) == 3
        assert results[0].ticker == "AAPL"
        assert results[0].rank == 1
        assert results[1].ticker == "MSFT"
        assert results[2].ticker == "GOOG"

    @pytest.mark.asyncio()
    async def test_scores_preserve_signals_dict(
        self,
        repo: Repository,
        sample_scan: ScanRun,
        sample_scores: list[TickerScore],
    ) -> None:
        """The signals dict should roundtrip through JSON serialization."""
        await repo.save_scan_run(sample_scan)
        await repo.save_ticker_scores(sample_scan.id, sample_scores)
        results = await repo.get_scores_for_scan(sample_scan.id)
        assert results[0].signals == pytest.approx(
            {"iv_rank": 45.2, "rsi_momentum": 22.3, "volume_surge": 15.0}
        )

    @pytest.mark.asyncio()
    async def test_scores_preserve_composite_score(
        self,
        repo: Repository,
        sample_scan: ScanRun,
        sample_scores: list[TickerScore],
    ) -> None:
        """The composite score should be accurately stored and retrieved."""
        await repo.save_scan_run(sample_scan)
        await repo.save_ticker_scores(sample_scan.id, sample_scores)
        results = await repo.get_scores_for_scan(sample_scan.id)
        assert results[0].score == pytest.approx(82.5)
        assert results[1].score == pytest.approx(75.3)

    @pytest.mark.asyncio()
    async def test_get_scores_for_nonexistent_scan(self, repo: Repository) -> None:
        """get_scores_for_scan with no matching scan should return empty list."""
        results = await repo.get_scores_for_scan("nonexistent")
        assert results == []

    @pytest.mark.asyncio()
    async def test_save_empty_scores_list(self, repo: Repository, sample_scan: ScanRun) -> None:
        """Saving an empty scores list should not error."""
        await repo.save_scan_run(sample_scan)
        await repo.save_ticker_scores(sample_scan.id, [])
        results = await repo.get_scores_for_scan(sample_scan.id)
        assert results == []


# ------------------------------------------------------------------
# Ticker history
# ------------------------------------------------------------------


class TestTickerHistory:
    """Tests for get_ticker_history and get_batch_ticker_history."""

    @pytest.mark.asyncio()
    async def test_get_ticker_history_across_scans(self, repo: Repository) -> None:
        """get_ticker_history should return scores from multiple scans."""
        scan1 = ScanRun(
            id="scan-h1",
            started_at=datetime.datetime(2025, 1, 14, 9, 0, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="default",
            sectors=["Technology"],
            ticker_count=10,
            top_n=5,
        )
        scan2 = ScanRun(
            id="scan-h2",
            started_at=datetime.datetime(2025, 1, 15, 9, 0, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="default",
            sectors=["Technology"],
            ticker_count=10,
            top_n=5,
        )
        await repo.save_scan_run(scan1)
        await repo.save_scan_run(scan2)
        score1 = TickerScore(ticker="AAPL", score=70.0, signals={"iv_rank": 30.0}, rank=1)
        score2 = TickerScore(ticker="AAPL", score=80.0, signals={"iv_rank": 40.0}, rank=1)
        await repo.save_ticker_scores("scan-h1", [score1])
        await repo.save_ticker_scores("scan-h2", [score2])

        history = await repo.get_ticker_history("AAPL", limit=10)
        assert len(history) == 2
        # Most recent scan first
        assert history[0].score == pytest.approx(80.0)
        assert history[1].score == pytest.approx(70.0)

    @pytest.mark.asyncio()
    async def test_get_ticker_history_respects_limit(self, repo: Repository) -> None:
        """get_ticker_history should respect the limit parameter."""
        for i in range(5):
            scan = ScanRun(
                id=f"scan-lim-{i}",
                started_at=datetime.datetime(2025, 1, 10 + i, 9, 0, 0, tzinfo=datetime.UTC),
                status="completed",
                preset="default",
                sectors=["Technology"],
                ticker_count=10,
                top_n=5,
            )
            await repo.save_scan_run(scan)
            score = TickerScore(ticker="AAPL", score=float(60 + i * 5), signals={"x": 1.0}, rank=1)
            await repo.save_ticker_scores(f"scan-lim-{i}", [score])

        history = await repo.get_ticker_history("AAPL", limit=3)
        assert len(history) == 3

    @pytest.mark.asyncio()
    async def test_get_ticker_history_empty(self, repo: Repository) -> None:
        """get_ticker_history for an unknown ticker should return empty list."""
        history = await repo.get_ticker_history("UNKNOWN")
        assert history == []

    @pytest.mark.asyncio()
    async def test_get_batch_ticker_history(self, repo: Repository) -> None:
        """get_batch_ticker_history should return a dict of ticker -> scores."""
        scan = ScanRun(
            id="scan-batch",
            started_at=datetime.datetime(2025, 1, 15, 9, 0, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="default",
            sectors=["Technology"],
            ticker_count=10,
            top_n=5,
        )
        await repo.save_scan_run(scan)
        scores = [
            TickerScore(ticker="AAPL", score=80.0, signals={"x": 1.0}, rank=1),
            TickerScore(ticker="MSFT", score=75.0, signals={"x": 2.0}, rank=2),
        ]
        await repo.save_ticker_scores("scan-batch", scores)

        result = await repo.get_batch_ticker_history(["AAPL", "MSFT", "UNKNOWN"])
        assert "AAPL" in result
        assert "MSFT" in result
        assert "UNKNOWN" not in result
        assert len(result["AAPL"]) == 1


# ------------------------------------------------------------------
# AI thesis operations
# ------------------------------------------------------------------


class TestAIThesisOperations:
    """Tests for save_ai_thesis and get_debate_history."""

    @pytest.mark.asyncio()
    async def test_save_and_retrieve_thesis(
        self, repo: Repository, sample_thesis: TradeThesis
    ) -> None:
        """Saving a thesis and retrieving it should roundtrip all fields."""
        await repo.save_ai_thesis("AAPL", sample_thesis)
        results = await repo.get_debate_history("AAPL")
        assert len(results) == 1
        thesis = results[0]
        assert thesis.direction == SignalDirection.BULLISH
        assert thesis.conviction == pytest.approx(0.72)
        assert thesis.entry_rationale == sample_thesis.entry_rationale
        assert thesis.risk_factors == sample_thesis.risk_factors
        assert thesis.recommended_action == sample_thesis.recommended_action
        assert thesis.bull_summary == sample_thesis.bull_summary
        assert thesis.bear_summary == sample_thesis.bear_summary
        assert thesis.model_used == sample_thesis.model_used
        assert thesis.total_tokens == sample_thesis.total_tokens
        assert thesis.duration_ms == sample_thesis.duration_ms

    @pytest.mark.asyncio()
    async def test_get_debate_history_filter_by_direction(self, repo: Repository) -> None:
        """get_debate_history with direction filter should return only matching theses."""
        bullish_thesis = TradeThesis(
            direction=SignalDirection.BULLISH,
            conviction=0.80,
            entry_rationale="Strong upward momentum.",
            risk_factors=["Earnings risk"],
            recommended_action="Buy calls",
            bull_summary="Bullish summary.",
            bear_summary="Bear summary.",
            model_used="llama3.1:8b",
            total_tokens=1000,
            duration_ms=2000,
        )
        bearish_thesis = TradeThesis(
            direction=SignalDirection.BEARISH,
            conviction=0.65,
            entry_rationale="Declining momentum.",
            risk_factors=["Support break"],
            recommended_action="Buy puts",
            bull_summary="Bull counter.",
            bear_summary="Bearish trend.",
            model_used="llama3.1:8b",
            total_tokens=1200,
            duration_ms=2500,
        )
        await repo.save_ai_thesis("AAPL", bullish_thesis)
        await repo.save_ai_thesis("AAPL", bearish_thesis)

        bullish_results = await repo.get_debate_history("AAPL", direction=SignalDirection.BULLISH)
        assert len(bullish_results) == 1
        assert bullish_results[0].direction == SignalDirection.BULLISH

        bearish_results = await repo.get_debate_history("AAPL", direction=SignalDirection.BEARISH)
        assert len(bearish_results) == 1
        assert bearish_results[0].direction == SignalDirection.BEARISH

        all_results = await repo.get_debate_history("AAPL")
        assert len(all_results) == 2

    @pytest.mark.asyncio()
    async def test_get_debate_history_respects_limit(self, repo: Repository) -> None:
        """get_debate_history should respect the limit parameter."""
        for i in range(5):
            thesis = TradeThesis(
                direction=SignalDirection.BULLISH,
                conviction=0.50 + i * 0.05,
                entry_rationale=f"Rationale {i}",
                risk_factors=[f"Risk {i}"],
                recommended_action=f"Action {i}",
                bull_summary=f"Bull {i}",
                bear_summary=f"Bear {i}",
                model_used="llama3.1:8b",
                total_tokens=1000 + i * 100,
                duration_ms=2000 + i * 200,
            )
            await repo.save_ai_thesis("AAPL", thesis)

        results = await repo.get_debate_history("AAPL", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio()
    async def test_get_debate_history_empty(self, repo: Repository) -> None:
        """get_debate_history for an unknown ticker should return empty list."""
        results = await repo.get_debate_history("UNKNOWN")
        assert results == []

    @pytest.mark.asyncio()
    async def test_thesis_json_roundtrip_via_full_thesis(
        self, repo: Repository, sample_thesis: TradeThesis
    ) -> None:
        """The full_thesis JSON column should preserve all TradeThesis data."""
        await repo.save_ai_thesis("AAPL", sample_thesis)
        results = await repo.get_debate_history("AAPL")
        assert len(results) == 1
        # Verify the entire model roundtripped
        assert results[0] == sample_thesis


# ------------------------------------------------------------------
# Watchlist CRUD
# ------------------------------------------------------------------


class TestWatchlistOperations:
    """Tests for watchlist create, add/remove tickers, list, delete."""

    @pytest.mark.asyncio()
    async def test_create_watchlist_returns_id(self, repo: Repository) -> None:
        """create_watchlist should return a positive integer ID."""
        watchlist_id = await repo.create_watchlist("Tech Favorites")
        assert isinstance(watchlist_id, int)
        assert watchlist_id > 0

    @pytest.mark.asyncio()
    async def test_list_watchlists(self, repo: Repository) -> None:
        """list_watchlists should return all created watchlists."""
        await repo.create_watchlist("Alpha")
        await repo.create_watchlist("Beta")
        watchlists = await repo.list_watchlists()
        assert len(watchlists) == 2
        names = [w.name for w in watchlists]
        assert "Alpha" in names
        assert "Beta" in names

    @pytest.mark.asyncio()
    async def test_list_watchlists_empty(self, repo: Repository) -> None:
        """list_watchlists on empty database should return empty list."""
        watchlists = await repo.list_watchlists()
        assert watchlists == []

    @pytest.mark.asyncio()
    async def test_add_and_get_tickers(self, repo: Repository) -> None:
        """Adding tickers to a watchlist and retrieving them should work."""
        wl_id = await repo.create_watchlist("Tech")
        await repo.add_tickers_to_watchlist(wl_id, ["AAPL", "MSFT", "GOOG"])
        tickers = await repo.get_watchlist_tickers(wl_id)
        assert tickers == ["AAPL", "GOOG", "MSFT"]  # sorted alphabetically

    @pytest.mark.asyncio()
    async def test_add_duplicate_tickers_ignored(self, repo: Repository) -> None:
        """Adding a duplicate ticker to a watchlist should be silently ignored."""
        wl_id = await repo.create_watchlist("Dupes")
        await repo.add_tickers_to_watchlist(wl_id, ["AAPL"])
        await repo.add_tickers_to_watchlist(wl_id, ["AAPL"])  # Duplicate
        tickers = await repo.get_watchlist_tickers(wl_id)
        assert tickers == ["AAPL"]

    @pytest.mark.asyncio()
    async def test_remove_tickers(self, repo: Repository) -> None:
        """Removing tickers from a watchlist should work correctly."""
        wl_id = await repo.create_watchlist("Remove Test")
        await repo.add_tickers_to_watchlist(wl_id, ["AAPL", "MSFT", "GOOG"])
        await repo.remove_tickers_from_watchlist(wl_id, ["MSFT"])
        tickers = await repo.get_watchlist_tickers(wl_id)
        assert tickers == ["AAPL", "GOOG"]

    @pytest.mark.asyncio()
    async def test_remove_nonexistent_ticker_is_safe(self, repo: Repository) -> None:
        """Removing a ticker that doesn't exist should not error."""
        wl_id = await repo.create_watchlist("Safe Remove")
        await repo.remove_tickers_from_watchlist(wl_id, ["NONEXISTENT"])
        tickers = await repo.get_watchlist_tickers(wl_id)
        assert tickers == []

    @pytest.mark.asyncio()
    async def test_delete_watchlist(self, repo: Repository) -> None:
        """Deleting a watchlist should remove it from the list."""
        wl_id = await repo.create_watchlist("To Delete")
        await repo.delete_watchlist(wl_id)
        watchlists = await repo.list_watchlists()
        assert len(watchlists) == 0

    @pytest.mark.asyncio()
    async def test_delete_watchlist_cascades_tickers(self, repo: Repository, db: Database) -> None:
        """Deleting a watchlist should also remove its ticker associations."""
        wl_id = await repo.create_watchlist("Cascade Test")
        await repo.add_tickers_to_watchlist(wl_id, ["AAPL", "MSFT"])
        await repo.delete_watchlist(wl_id)
        # Verify tickers are gone by checking the database directly
        conn = db.connection
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM watchlist_tickers WHERE watchlist_id = ?",
            (wl_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 0

    @pytest.mark.asyncio()
    async def test_get_watchlist_tickers_empty(self, repo: Repository) -> None:
        """get_watchlist_tickers for a watchlist with no tickers should return empty."""
        wl_id = await repo.create_watchlist("Empty")
        tickers = await repo.get_watchlist_tickers(wl_id)
        assert tickers == []

    @pytest.mark.asyncio()
    async def test_create_duplicate_watchlist_name_raises(self, repo: Repository) -> None:
        """Creating two watchlists with the same name should raise an error."""
        import sqlite3

        await repo.create_watchlist("Unique Name")
        with pytest.raises(sqlite3.IntegrityError):
            await repo.create_watchlist("Unique Name")
