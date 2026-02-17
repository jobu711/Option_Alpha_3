"""Extended scan model tests: WatchlistSummary, ScanRun edge cases, TickerScore edge cases."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from Option_Alpha.models.scan import ScanRun, TickerScore, WatchlistSummary

# ---------------------------------------------------------------------------
# WatchlistSummary
# ---------------------------------------------------------------------------


class TestWatchlistSummary:
    """Unit tests for the WatchlistSummary model — previously untested."""

    def test_valid_construction(self) -> None:
        wl = WatchlistSummary(
            id=1,
            name="High IV Setups",
            created_at="2025-01-15T10:00:00Z",
        )
        assert wl.id == 1
        assert wl.name == "High IV Setups"
        assert wl.created_at == "2025-01-15T10:00:00Z"

    def test_json_roundtrip(self) -> None:
        original = WatchlistSummary(
            id=42,
            name="Earnings Plays",
            created_at="2025-01-10T08:30:00Z",
        )
        restored = WatchlistSummary.model_validate_json(original.model_dump_json())
        assert restored == original

    def test_frozen_immutability(self) -> None:
        wl = WatchlistSummary(id=1, name="Test", created_at="2025-01-15")
        with pytest.raises(ValidationError, match="frozen"):
            wl.name = "Changed"  # type: ignore[misc]

    def test_string_id_coerced_to_int(self) -> None:
        # Pydantic coerces "1" -> 1 for int fields
        wl = WatchlistSummary(id="1", name="Coerced", created_at="2025-01-15")  # type: ignore[arg-type]
        assert wl.id == 1

    def test_created_at_is_plain_string(self) -> None:
        """created_at is a str field, not datetime — any string is valid."""
        wl = WatchlistSummary(id=1, name="Test", created_at="not-a-date")
        assert wl.created_at == "not-a-date"

    def test_empty_name(self) -> None:
        wl = WatchlistSummary(id=1, name="", created_at="2025-01-15")
        assert wl.name == ""

    def test_negative_id_accepted(self) -> None:
        """No validator constrains id to positive."""
        wl = WatchlistSummary(id=-1, name="Negative", created_at="2025-01-15")
        assert wl.id == -1


# ---------------------------------------------------------------------------
# ScanRun edge cases
# ---------------------------------------------------------------------------


class TestScanRunEdgeCases:
    """Additional ScanRun edge cases."""

    def test_completed_at_none(self) -> None:
        scan = ScanRun(
            id="scan-001",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            completed_at=None,
            status="running",
            preset="high_iv",
            sectors=["Technology"],
            ticker_count=100,
            top_n=10,
        )
        assert scan.completed_at is None
        assert scan.status == "running"

    def test_empty_sectors(self) -> None:
        scan = ScanRun(
            id="scan-002",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="full",
            sectors=[],
            ticker_count=500,
            top_n=20,
        )
        assert scan.sectors == []

    def test_json_roundtrip_with_completed_at(self) -> None:
        original = ScanRun(
            id="scan-003",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            completed_at=datetime.datetime(2025, 1, 15, 9, 35, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="sp500",
            sectors=["Technology", "Healthcare"],
            ticker_count=50,
            top_n=10,
        )
        restored = ScanRun.model_validate_json(original.model_dump_json())
        assert restored == original


# ---------------------------------------------------------------------------
# TickerScore edge cases
# ---------------------------------------------------------------------------


class TestTickerScoreEdgeCases:
    """Additional TickerScore edge cases."""

    def test_empty_signals(self) -> None:
        score = TickerScore(
            ticker="XYZ",
            score=0.0,
            signals={},
            rank=1,
        )
        assert score.signals == {}

    def test_many_signals(self) -> None:
        signals = {
            "iv_rank": 45.2,
            "rsi_momentum": 22.3,
            "volume_surge": 15.0,
            "macd_signal": 10.5,
            "bb_squeeze": 8.2,
            "earnings_proximity": 5.0,
        }
        score = TickerScore(
            ticker="AAPL",
            score=82.5,
            signals=signals,
            rank=1,
        )
        assert len(score.signals) == 6

    def test_zero_score(self) -> None:
        score = TickerScore(
            ticker="DEAD",
            score=0.0,
            signals={"iv_rank": 0.0},
            rank=999,
        )
        assert score.score == pytest.approx(0.0, abs=1e-9)

    def test_json_roundtrip(self) -> None:
        original = TickerScore(
            ticker="SPY",
            score=91.3,
            signals={"iv_rank": 30.0, "volume_surge": 25.0},
            rank=1,
        )
        restored = TickerScore.model_validate_json(original.model_dump_json())
        assert restored == original
