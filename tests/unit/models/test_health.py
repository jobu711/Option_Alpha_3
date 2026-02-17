"""Tests for HealthStatus model.

Covers:
- JSON roundtrip
- Valid construction
- Frozen immutability
- Default values if any
"""

import datetime

import pytest
from pydantic import ValidationError

from Option_Alpha.models.health import HealthStatus


class TestHealthStatus:
    """Tests for the HealthStatus model."""

    def test_valid_construction(self, sample_health_status: HealthStatus) -> None:
        """HealthStatus can be constructed with valid data."""
        assert sample_health_status.ollama_available is True
        assert sample_health_status.yfinance_available is True
        assert sample_health_status.sqlite_available is True
        assert sample_health_status.ollama_models == ["llama3:70b", "mistral:7b"]

    def test_json_roundtrip(self, sample_health_status: HealthStatus) -> None:
        """HealthStatus survives a full JSON serialize/deserialize cycle."""
        json_str = sample_health_status.model_dump_json()
        restored = HealthStatus.model_validate_json(json_str)
        assert restored == sample_health_status

    def test_frozen_immutability(self, sample_health_status: HealthStatus) -> None:
        """HealthStatus is frozen -- assigning to a field raises an error."""
        with pytest.raises(ValidationError, match="frozen"):
            sample_health_status.ollama_available = False  # type: ignore[misc]

    def test_all_services_unavailable(self) -> None:
        """HealthStatus with all services down is valid."""
        status = HealthStatus(
            ollama_available=False,
            anthropic_available=False,
            yfinance_available=False,
            sqlite_available=False,
            ollama_models=[],
            last_check=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert status.ollama_available is False
        assert status.anthropic_available is False
        assert status.yfinance_available is False
        assert status.sqlite_available is False
        assert status.ollama_models == []

    def test_empty_ollama_models_list(self) -> None:
        """Empty ollama_models list is valid (Ollama installed but no models pulled)."""
        status = HealthStatus(
            ollama_available=True,
            anthropic_available=True,
            yfinance_available=True,
            sqlite_available=True,
            ollama_models=[],
            last_check=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert status.ollama_models == []

    def test_last_check_timestamp(self, sample_health_status: HealthStatus) -> None:
        """last_check timestamp is preserved correctly."""
        expected = datetime.datetime(2025, 1, 15, 15, 30, 0, tzinfo=datetime.UTC)
        assert sample_health_status.last_check == expected

    def test_multiple_ollama_models(self) -> None:
        """Multiple Ollama model names are stored correctly."""
        status = HealthStatus(
            ollama_available=True,
            anthropic_available=True,
            yfinance_available=True,
            sqlite_available=True,
            ollama_models=["llama3:70b", "llama3:8b", "mistral:7b", "codellama:34b"],
            last_check=datetime.datetime(2025, 1, 15, 15, 0, 0, tzinfo=datetime.UTC),
        )
        assert len(status.ollama_models) == 4
        assert "codellama:34b" in status.ollama_models
