"""Tests for debate routes (GET /debate, GET /debate/{ticker}, OHLCV API)."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from Option_Alpha.models.analysis import TradeThesis
from Option_Alpha.models.market_data import OHLCV, Quote
from Option_Alpha.utils.exceptions import DataFetchError, TickerNotFoundError


def _ticker_not_found(ticker: str) -> TickerNotFoundError:
    """Create a TickerNotFoundError with required keyword args."""
    return TickerNotFoundError(f"Ticker '{ticker}' not found.", ticker=ticker, source="yfinance")


def _data_fetch_error(message: str) -> DataFetchError:
    """Create a DataFetchError with required keyword args."""
    return DataFetchError(message, ticker="AAPL", source="yfinance")


class TestDebateLanding:
    """Tests for GET /debate (landing page)."""

    def test_debate_landing_returns_200(self, client: TestClient) -> None:
        """GET /debate returns 200."""
        response = client.get("/debate")
        assert response.status_code == 200

    def test_debate_landing_shows_ticker_input(self, client: TestClient) -> None:
        """GET /debate shows a ticker input form."""
        response = client.get("/debate")
        assert "ticker" in response.text.lower()
        assert 'placeholder="e.g. AAPL"' in response.text

    def test_debate_landing_includes_analyze_button(self, client: TestClient) -> None:
        """GET /debate includes the Analyze button."""
        response = client.get("/debate")
        assert "Analyze" in response.text


class TestDebatePage:
    """Tests for GET /debate/{ticker} (ticker debate view)."""

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_ticker_page_returns_200(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/AAPL returns 200."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/AAPL")
        assert response.status_code == 200

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_ticker_shows_ticker_name(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/AAPL shows the ticker symbol in the page."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/AAPL")
        assert "AAPL" in response.text

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_empty_state(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/{ticker} shows empty state when no debates exist."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/TSLA")
        assert response.status_code == 200
        assert "No debate results" in response.text

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_shows_run_debate_button(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/{ticker} shows Run AI Debate button when no thesis."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/AAPL")
        assert "Run AI Debate" in response.text

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_with_history(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
        sample_trade_thesis: TradeThesis,
    ) -> None:
        """GET /debate/{ticker} renders thesis when debate history exists."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[sample_trade_thesis])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/AAPL")
        assert response.status_code == 200
        # SignalDirection.BULLISH has value "bullish" (lowercase StrEnum)
        assert "bullish" in response.text

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_ticker_uppercased(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/aapl uppercases the ticker to AAPL."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/aapl")
        assert response.status_code == 200
        assert "AAPL" in response.text

    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_debate_includes_chart_container(
        self,
        mock_repo_cls: AsyncMock,
        client: TestClient,
    ) -> None:
        """GET /debate/{ticker} includes a price chart container."""
        mock_repo = AsyncMock()
        mock_repo.get_debate_history = AsyncMock(return_value=[])
        mock_repo_cls.return_value = mock_repo

        response = client.get("/debate/AAPL")
        assert 'id="price-chart"' in response.text


class TestTickerOhlcvEndpoint:
    """Tests for GET /api/ticker/{ticker}/ohlcv."""

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_returns_json(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
        sample_ohlcv_bars: list[OHLCV],
    ) -> None:
        """GET /api/ticker/AAPL/ohlcv returns JSON with candles and volume."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_bars)
        mock_mds_cls.return_value = mock_service

        response = client.get("/api/ticker/AAPL/ohlcv")
        assert response.status_code == 200
        data = response.json()
        assert "candles" in data
        assert "volume" in data
        assert len(data["candles"]) == 3

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_returns_float_values(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
        sample_ohlcv_bars: list[OHLCV],
    ) -> None:
        """OHLCV endpoint returns float values, not Decimal strings."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_bars)
        mock_mds_cls.return_value = mock_service

        response = client.get("/api/ticker/AAPL/ohlcv")
        data = response.json()
        candle = data["candles"][0]
        assert isinstance(candle["open"], float)
        assert isinstance(candle["high"], float)
        assert isinstance(candle["low"], float)
        assert isinstance(candle["close"], float)

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_volume_has_color(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
        sample_ohlcv_bars: list[OHLCV],
    ) -> None:
        """Volume entries include color based on close vs open."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_bars)
        mock_mds_cls.return_value = mock_service

        response = client.get("/api/ticker/AAPL/ohlcv")
        data = response.json()
        vol = data["volume"][0]
        assert "color" in vol
        # First bar: close (185.50) >= open (184.00) => green
        assert vol["color"].startswith("#34d399")

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_ticker_not_found(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """OHLCV endpoint returns 404 for unknown ticker."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(side_effect=_ticker_not_found("FAKE"))
        mock_mds_cls.return_value = mock_service

        response = client.get("/api/ticker/FAKE/ohlcv")
        assert response.status_code == 404
        assert "not found" in response.json()["error"]

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_data_fetch_error(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """OHLCV endpoint returns 502 on data fetch failure."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(side_effect=_data_fetch_error("Network error"))
        mock_mds_cls.return_value = mock_service

        response = client.get("/api/ticker/AAPL/ohlcv")
        assert response.status_code == 502

    def test_ohlcv_invalid_period(self, client: TestClient) -> None:
        """OHLCV endpoint returns 400 for invalid period parameter."""
        response = client.get("/api/ticker/AAPL/ohlcv?period=5y")
        assert response.status_code == 400
        assert "Invalid period" in response.json()["error"]

    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    def test_ohlcv_valid_period_parameter(
        self,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        client: TestClient,
        sample_ohlcv_bars: list[OHLCV],
    ) -> None:
        """OHLCV endpoint accepts valid period values."""
        mock_service = AsyncMock()
        mock_service.fetch_ohlcv = AsyncMock(return_value=sample_ohlcv_bars)
        mock_mds_cls.return_value = mock_service

        for period in ["1mo", "3mo", "6mo", "1y", "2y"]:
            response = client.get(f"/api/ticker/AAPL/ohlcv?period={period}")
            assert response.status_code == 200


class TestRunDebate:
    """Tests for POST /debate/{ticker}/run."""

    @patch("Option_Alpha.web.routes.debate.DebateOrchestrator")
    @patch("Option_Alpha.web.routes.debate.LLMClient")
    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_run_debate_data_fetch_failure(
        self,
        mock_repo_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        mock_llm_cls: MagicMock,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /debate/{ticker}/run returns error partial when data fetch fails."""
        mock_service = AsyncMock()
        mock_service.fetch_quote = AsyncMock(side_effect=_ticker_not_found("FAKE"))
        mock_mds_cls.return_value = mock_service

        response = client.post("/debate/FAKE/run")
        assert response.status_code == 404
        assert "Could not fetch market data" in response.text

    @patch("Option_Alpha.web.routes.debate.DebateOrchestrator")
    @patch("Option_Alpha.web.routes.debate.LLMClient")
    @patch("Option_Alpha.web.routes.debate.MarketDataService")
    @patch("Option_Alpha.web.routes.debate.ServiceCache")
    @patch("Option_Alpha.web.routes.debate.RateLimiter")
    @patch("Option_Alpha.web.routes.debate.Repository")
    def test_run_debate_ollama_failure(
        self,
        mock_repo_cls: MagicMock,
        mock_rl_cls: MagicMock,
        mock_cache_cls: MagicMock,
        mock_mds_cls: MagicMock,
        mock_llm_cls: MagicMock,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """POST /debate/{ticker}/run returns error when Ollama is unreachable."""
        mock_quote = Quote(
            ticker="AAPL",
            bid=Decimal("185.00"),
            ask=Decimal("185.10"),
            last=Decimal("185.05"),
            volume=1_000_000,
            timestamp=datetime.datetime(2025, 1, 15, 12, 0, 0, tzinfo=datetime.UTC),
        )
        mock_service = AsyncMock()
        mock_service.fetch_quote = AsyncMock(return_value=mock_quote)
        mock_mds_cls.return_value = mock_service

        mock_orch = AsyncMock()
        mock_orch.run_debate = AsyncMock(side_effect=ConnectionError("Ollama down"))
        mock_orch_cls.return_value = mock_orch

        response = client.post("/debate/AAPL/run")
        assert response.status_code == 500
        assert "Ollama may be unreachable" in response.text
