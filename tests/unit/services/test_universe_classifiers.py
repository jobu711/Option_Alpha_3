"""Tests for UniverseService classifier methods.

_classify_asset_type is a static method tested directly.
_classify_market_cap_tier is an instance method that uses self._sp500_symbols;
tests construct a service with mock dependencies and pre-populated symbols.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from Option_Alpha.services.universe import _FALLBACK_LARGE_CAPS, UniverseService

# ---------------------------------------------------------------------------
# _classify_asset_type
# ---------------------------------------------------------------------------


class TestClassifyAssetType:
    """Direct tests for the _classify_asset_type static method."""

    def test_well_known_etf_spy(self) -> None:
        assert UniverseService._classify_asset_type("SPY", "SPDR S&P 500 ETF") == "etf"

    def test_well_known_etf_qqq(self) -> None:
        assert UniverseService._classify_asset_type("QQQ", "Invesco QQQ Trust") == "etf"

    def test_well_known_etf_iwm(self) -> None:
        assert UniverseService._classify_asset_type("IWM", "iShares Russell 2000 ETF") == "etf"

    def test_well_known_etf_gld(self) -> None:
        assert UniverseService._classify_asset_type("GLD", "SPDR Gold Shares") == "etf"

    def test_well_known_etf_arkk(self) -> None:
        assert UniverseService._classify_asset_type("ARKK", "ARK Innovation ETF") == "etf"

    def test_equity_aapl(self) -> None:
        assert UniverseService._classify_asset_type("AAPL", "Apple Inc.") == "equity"

    def test_equity_msft(self) -> None:
        assert UniverseService._classify_asset_type("MSFT", "Microsoft Corp.") == "equity"

    def test_name_keyword_etf(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Some ETF Name") == "etf"

    def test_name_keyword_ishares(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "iShares Core Bond") == "etf"

    def test_name_keyword_vanguard(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Vanguard Total Stock") == "etf"

    def test_name_keyword_trust(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Some Trust Fund") == "etf"

    def test_name_keyword_index(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "S&P 500 Index") == "etf"

    def test_name_keyword_spdr(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "SPDR Sector Select") == "etf"

    def test_name_keyword_fund(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Growth Fund") == "etf"

    def test_case_insensitive_name(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "vanguard small cap") == "etf"

    def test_empty_name_unknown_symbol(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "") == "equity"

    def test_unknown_symbol_plain_name(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Acme Corp") == "equity"

    def test_well_known_etf_vxx(self) -> None:
        assert UniverseService._classify_asset_type("VXX", "iPath Series B S&P 500") == "etf"


# ---------------------------------------------------------------------------
# _classify_market_cap_tier
# ---------------------------------------------------------------------------


def _make_service() -> UniverseService:
    """Create a UniverseService with mock deps and fallback SP500 symbols."""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    rate_limiter = MagicMock()
    svc = UniverseService(cache=cache, rate_limiter=rate_limiter)
    # Pre-populate with fallback so tests don't need async setup
    svc._sp500_symbols = set(_FALLBACK_LARGE_CAPS)
    return svc


class TestClassifyMarketCapTier:
    """Direct tests for the _classify_market_cap_tier instance method."""

    def test_etf_bypass(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("SPY", "etf") == "etf"

    def test_etf_bypass_any_symbol(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("XYZW", "etf") == "etf"

    def test_large_cap_aapl(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("AAPL", "equity") == "large_cap"

    def test_large_cap_msft(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("MSFT", "equity") == "large_cap"

    def test_large_cap_tsla(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("TSLA", "equity") == "large_cap"

    def test_large_cap_nvda(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("NVDA", "equity") == "large_cap"

    def test_large_cap_jpm(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("JPM", "equity") == "large_cap"

    def test_unknown_symbol_default_mid_cap(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("XYZW", "equity") == "mid_cap"

    def test_small_company_default_mid_cap(self) -> None:
        svc = _make_service()
        assert svc._classify_market_cap_tier("SMALLCO", "equity") == "mid_cap"

    def test_etf_check_before_large_cap(self) -> None:
        """ETF check runs before symbol lookup."""
        svc = _make_service()
        assert svc._classify_market_cap_tier("AAPL", "etf") == "etf"

    def test_empty_sp500_uses_fallback(self) -> None:
        """When _sp500_symbols is empty, falls back to _FALLBACK_LARGE_CAPS."""
        svc = _make_service()
        svc._sp500_symbols = set()
        assert svc._classify_market_cap_tier("AAPL", "equity") == "large_cap"

    def test_custom_sp500_set(self) -> None:
        """Custom SP500 set is respected over fallback."""
        svc = _make_service()
        svc._sp500_symbols = {"XYZW"}
        assert svc._classify_market_cap_tier("XYZW", "equity") == "large_cap"
        assert svc._classify_market_cap_tier("AAPL", "equity") == "mid_cap"
