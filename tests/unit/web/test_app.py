"""Tests for app factory, custom Jinja2 filters, and static file mounting."""

from __future__ import annotations

import datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Option_Alpha.web.app import (
    create_app,
    money_filter,
    pct_filter,
    pct_raw_filter,
    signal_color_filter,
    timeago_filter,
)

# ---------------------------------------------------------------------------
# App factory tests
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for create_app() factory function."""

    def test_creates_fastapi_instance(self) -> None:
        """create_app returns a FastAPI instance with correct title."""
        app = create_app()
        assert isinstance(app, FastAPI)
        assert app.title == "Option Alpha"

    def test_docs_disabled(self) -> None:
        """Swagger/ReDoc docs are disabled (no docs_url or redoc_url)."""
        app = create_app()
        assert app.docs_url is None
        assert app.redoc_url is None

    def test_api_health_check_endpoint(self, client: TestClient) -> None:
        """GET /api/health returns JSON with status ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "ok"}

    def test_static_files_mounted(self, client: TestClient) -> None:
        """Static files are accessible at /static/."""
        response = client.get("/static/css/app.css")
        assert response.status_code == 200

    def test_static_js_accessible(self, client: TestClient) -> None:
        """JavaScript files are accessible at /static/js/."""
        response = client.get("/static/js/htmx.min.js")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Jinja2 filter unit tests
# ---------------------------------------------------------------------------


class TestMoneyFilter:
    """Tests for the money Jinja2 filter."""

    def test_formats_decimal(self) -> None:
        """Formats Decimal as currency."""
        result = money_filter(Decimal("185.00"))
        assert result == "$185.00"

    def test_formats_string(self) -> None:
        """Formats numeric string as currency."""
        result = money_filter("42.50")
        assert result == "$42.50"

    def test_none_returns_em_dash(self) -> None:
        """None renders as em dash."""
        result = money_filter(None)
        assert result == "\u2014"

    def test_invalid_returns_original(self) -> None:
        """Non-numeric input returns the original string."""
        result = money_filter("not-a-number")
        assert result == "not-a-number"

    def test_formats_large_number_with_commas(self) -> None:
        """Large numbers include comma separators."""
        result = money_filter(Decimal("1234567.89"))
        assert result == "$1,234,567.89"


class TestPctFilter:
    """Tests for the pct Jinja2 filter (0-1 range)."""

    def test_converts_fraction_to_percent(self) -> None:
        """0.723 renders as 72.3%."""
        result = pct_filter(0.723)
        assert result == "72.3%"

    def test_zero(self) -> None:
        """0.0 renders as 0.0%."""
        result = pct_filter(0.0)
        assert result == "0.0%"

    def test_one(self) -> None:
        """1.0 renders as 100.0%."""
        result = pct_filter(1.0)
        assert result == "100.0%"

    def test_none_returns_em_dash(self) -> None:
        """None renders as em dash."""
        result = pct_filter(None)
        assert result == "\u2014"


class TestPctRawFilter:
    """Tests for the pct_raw Jinja2 filter (already percentage)."""

    def test_formats_already_percentage(self) -> None:
        """72.3 renders as 72.3%."""
        result = pct_raw_filter(72.3)
        assert result == "72.3%"

    def test_none_returns_em_dash(self) -> None:
        """None renders as em dash."""
        result = pct_raw_filter(None)
        assert result == "\u2014"


class TestTimeagoFilter:
    """Tests for the timeago Jinja2 filter."""

    def test_none_returns_em_dash(self) -> None:
        """None renders as em dash."""
        result = timeago_filter(None)
        assert result == "\u2014"

    def test_just_now(self) -> None:
        """A datetime within the last minute returns 'just now'."""
        now = datetime.datetime.now(datetime.UTC)
        result = timeago_filter(now)
        assert result == "just now"

    def test_minutes_ago(self) -> None:
        """A datetime 5 minutes ago returns '5 mins ago'."""
        five_min_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
        result = timeago_filter(five_min_ago)
        assert result == "5 mins ago"

    def test_hours_ago(self) -> None:
        """A datetime 3 hours ago returns '3 hours ago'."""
        three_hours_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=3)
        result = timeago_filter(three_hours_ago)
        assert result == "3 hours ago"

    def test_days_ago(self) -> None:
        """A datetime 7 days ago returns '7 days ago'."""
        seven_days_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)
        result = timeago_filter(seven_days_ago)
        assert result == "7 days ago"

    def test_months_ago(self) -> None:
        """A datetime 60 days ago returns '2 months ago'."""
        sixty_days_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=60)
        result = timeago_filter(sixty_days_ago)
        assert result == "2 months ago"

    def test_naive_datetime_treated_as_utc(self) -> None:
        """A naive datetime (no tzinfo) is treated as UTC."""
        naive = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        result = timeago_filter(naive)
        assert result == "just now"


class TestSignalColorFilter:
    """Tests for the signal_color Jinja2 filter."""

    def test_bullish_returns_emerald(self) -> None:
        """BULLISH maps to emerald color class."""
        assert signal_color_filter("BULLISH") == "text-emerald-400"

    def test_bearish_returns_red(self) -> None:
        """BEARISH maps to red color class."""
        assert signal_color_filter("BEARISH") == "text-red-400"

    def test_neutral_returns_zinc(self) -> None:
        """NEUTRAL maps to zinc color class."""
        assert signal_color_filter("NEUTRAL") == "text-zinc-400"

    def test_none_returns_zinc(self) -> None:
        """None returns default zinc color."""
        assert signal_color_filter(None) == "text-zinc-400"

    def test_case_insensitive(self) -> None:
        """Filter is case-insensitive."""
        assert signal_color_filter("bullish") == "text-emerald-400"

    def test_unknown_returns_zinc(self) -> None:
        """Unknown direction returns default zinc."""
        assert signal_color_filter("SIDEWAYS") == "text-zinc-400"
