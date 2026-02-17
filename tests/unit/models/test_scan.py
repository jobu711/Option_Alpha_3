"""Tests for scan models: ScanRun, TickerScore.

Covers:
- JSON roundtrip
- Valid construction
- Frozen immutability
"""

import datetime

import pytest
from pydantic import ValidationError

from Option_Alpha.models.scan import ScanRun, TickerScore


class TestScanRun:
    """Tests for the ScanRun model."""

    def test_valid_construction(self, sample_scan_run: ScanRun) -> None:
        """ScanRun can be constructed with valid data."""
        assert sample_scan_run.id == "scan-20250115-001"
        assert sample_scan_run.status == "completed"
        assert sample_scan_run.preset == "high_iv"
        assert sample_scan_run.sectors == ["Technology", "Healthcare"]
        assert sample_scan_run.ticker_count == 50
        assert sample_scan_run.top_n == 10

    def test_json_roundtrip(self, sample_scan_run: ScanRun) -> None:
        """ScanRun survives a full JSON serialize/deserialize cycle."""
        json_str = sample_scan_run.model_dump_json()
        restored = ScanRun.model_validate_json(json_str)
        assert restored == sample_scan_run

    def test_frozen_immutability(self, sample_scan_run: ScanRun) -> None:
        """ScanRun is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_scan_run.status = "failed"  # type: ignore[misc]

    def test_completed_at_none(self) -> None:
        """completed_at can be None (scan still running)."""
        run = ScanRun(
            id="scan-20250115-002",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            completed_at=None,
            status="running",
            preset="default",
            sectors=["Technology"],
            ticker_count=25,
            top_n=5,
        )
        assert run.completed_at is None

    def test_empty_sectors_list(self) -> None:
        """Empty sectors list is valid (scan all sectors)."""
        run = ScanRun(
            id="scan-20250115-003",
            started_at=datetime.datetime(2025, 1, 15, 9, 30, 0, tzinfo=datetime.UTC),
            status="completed",
            preset="all",
            sectors=[],
            ticker_count=100,
            top_n=20,
        )
        assert run.sectors == []

    def test_timestamps_serialization(self, sample_scan_run: ScanRun) -> None:
        """Datetime fields are correctly serialized and deserialized."""
        json_str = sample_scan_run.model_dump_json()
        restored = ScanRun.model_validate_json(json_str)
        assert restored.started_at == sample_scan_run.started_at
        assert restored.completed_at == sample_scan_run.completed_at


class TestTickerScore:
    """Tests for the TickerScore model."""

    def test_valid_construction(self, sample_ticker_score: TickerScore) -> None:
        """TickerScore can be constructed with valid data."""
        assert sample_ticker_score.ticker == "AAPL"
        assert sample_ticker_score.score == pytest.approx(82.5, abs=0.01)
        assert sample_ticker_score.rank == 1
        assert "iv_rank" in sample_ticker_score.signals

    def test_json_roundtrip(self, sample_ticker_score: TickerScore) -> None:
        """TickerScore survives a full JSON serialize/deserialize cycle."""
        json_str = sample_ticker_score.model_dump_json()
        restored = TickerScore.model_validate_json(json_str)
        assert restored.ticker == sample_ticker_score.ticker
        assert restored.score == pytest.approx(sample_ticker_score.score, abs=0.01)
        assert restored.rank == sample_ticker_score.rank
        assert restored.signals == sample_ticker_score.signals

    def test_frozen_immutability(self, sample_ticker_score: TickerScore) -> None:
        """TickerScore is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_ticker_score.score = 99.9  # type: ignore[misc]

    def test_signals_dict_values(self, sample_ticker_score: TickerScore) -> None:
        """Signal values are floats in the signals dict."""
        for signal_name, signal_value in sample_ticker_score.signals.items():
            assert isinstance(signal_name, str)
            assert isinstance(signal_value, float)

    def test_empty_signals_dict(self) -> None:
        """Empty signals dict is valid (no signals contributed)."""
        score = TickerScore(
            ticker="UNKNOWN",
            score=0.0,
            signals={},
            rank=100,
        )
        assert score.signals == {}

    def test_zero_score(self) -> None:
        """Score of 0.0 is valid."""
        score = TickerScore(
            ticker="LOW",
            score=0.0,
            signals={"iv_rank": 0.0},
            rank=50,
        )
        assert score.score == pytest.approx(0.0, abs=0.01)
