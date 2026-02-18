"""Tests for the /api/report endpoints.

Uses httpx.AsyncClient with ASGITransport for async route testing.
Repository is mocked — no real database calls. Verifies that reports
include the mandatory disclaimer.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.enums import SignalDirection
from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT
from Option_Alpha.web.app import create_app
from Option_Alpha.web.deps import get_repository


def _mock_thesis() -> TradeThesis:
    """Create a realistic TradeThesis for testing."""
    return TradeThesis(
        direction=SignalDirection.BULLISH,
        conviction=0.75,
        entry_rationale="Strong momentum with RSI at 35, suggesting oversold conditions.",
        risk_factors=["Earnings in 10 days", "Elevated IV Rank at 72"],
        recommended_action="Buy 45-DTE call at 0.30 delta",
        bull_summary="Technical indicators show oversold bounce potential.",
        bear_summary="Elevated IV and pending earnings create risk.",
        model_used="llama3.1:8b",
        total_tokens=5000,
        duration_ms=3200,
        disclaimer=DISCLAIMER_TEXT,
    )


def _create_test_app(
    thesis: TradeThesis | None = None,
    ticker: str = "AAPL",
    has_row: bool = True,
) -> FastAPI:
    """Create a FastAPI app with mocked repository for testing."""
    app = create_app()

    mock_repo = AsyncMock()

    # Mock the new Repository.get_thesis_raw_by_id method that report.py now uses
    if has_row:
        t = thesis or _mock_thesis()
        mock_repo.get_thesis_raw_by_id = AsyncMock(
            return_value=(ticker, t.model_dump_json()),
        )
    else:
        mock_repo.get_thesis_raw_by_id = AsyncMock(return_value=None)

    async def mock_get_repository() -> AsyncMock:  # type: ignore[type-arg]
        return mock_repo

    app.dependency_overrides[get_repository] = mock_get_repository

    return app


class TestDownloadReport:
    """Tests for GET /api/report/{debate_id}."""

    @pytest.mark.asyncio
    async def test_returns_200(self) -> None:
        """GET /api/report/1 should return HTTP 200."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_content_type_markdown(self) -> None:
        """Response should have text/markdown content type."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")
        assert "text/markdown" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_content_disposition_attachment(self) -> None:
        """Response should include Content-Disposition with filename."""
        app = _create_test_app(ticker="AAPL")
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "AAPL" in disposition
        assert ".md" in disposition

    @pytest.mark.asyncio
    async def test_report_contains_disclaimer(self) -> None:
        """Report content MUST include the full disclaimer text."""
        app = _create_test_app()
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        content = response.text
        assert DISCLAIMER_TEXT in content

    @pytest.mark.asyncio
    async def test_report_contains_ticker(self) -> None:
        """Report should reference the ticker symbol."""
        app = _create_test_app(ticker="MSFT")
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        content = response.text
        assert "MSFT" in content

    @pytest.mark.asyncio
    async def test_report_contains_direction(self) -> None:
        """Report should contain the thesis direction."""
        thesis = _mock_thesis()
        app = _create_test_app(thesis=thesis)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        content = response.text
        assert "BULLISH" in content

    @pytest.mark.asyncio
    async def test_debate_not_found_returns_404(self) -> None:
        """Non-existent debate ID should return HTTP 404."""
        app = _create_test_app(has_row=False)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_debate_not_found_error_detail(self) -> None:
        """404 response should include an informative error detail."""
        app = _create_test_app(has_row=False)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/999")

        body = response.json()
        assert "999" in body["detail"]

    @pytest.mark.asyncio
    async def test_report_contains_bull_summary(self) -> None:
        """Report should contain the bull case summary."""
        thesis = _mock_thesis()
        app = _create_test_app(thesis=thesis)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        content = response.text
        assert thesis.bull_summary in content

    @pytest.mark.asyncio
    async def test_report_contains_bear_summary(self) -> None:
        """Report should contain the bear case summary."""
        thesis = _mock_thesis()
        app = _create_test_app(thesis=thesis)
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        content = response.text
        assert thesis.bear_summary in content

    @pytest.mark.asyncio
    async def test_filename_includes_direction(self) -> None:
        """Report filename should include the direction."""
        thesis = _mock_thesis()
        app = _create_test_app(thesis=thesis, ticker="TSLA")
        transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/report/1")

        disposition = response.headers.get("content-disposition", "")
        assert "bullish" in disposition
        assert "TSLA" in disposition
