"""Tests for UniverseService static classifier methods.

_classify_asset_type and _classify_market_cap_tier were only tested
indirectly through CSV parsing. These tests verify the static methods directly.
"""

from __future__ import annotations

from Option_Alpha.services.universe import UniverseService

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
        assert UniverseService._classify_asset_type("MSFT", "Microsoft Corporation") == "equity"

    def test_name_keyword_etf(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Some ETF Fund") == "etf"

    def test_name_keyword_ishares(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "iShares Core U.S. Aggregate") == "etf"

    def test_name_keyword_vanguard(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Vanguard Total Stock Fund") == "etf"

    def test_name_keyword_trust(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "ProShares UltraPro Trust") == "etf"

    def test_name_keyword_index(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "S&P 500 Index Fund") == "etf"

    def test_name_keyword_spdr(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "SPDR Technology Select") == "etf"

    def test_name_keyword_fund(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Fidelity Growth Fund") == "etf"

    def test_case_insensitive_name(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "invesco etf shares") == "etf"

    def test_empty_name_unknown_symbol(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "") == "equity"

    def test_unknown_symbol_plain_name(self) -> None:
        assert UniverseService._classify_asset_type("XYZW", "Acme Corp") == "equity"

    def test_well_known_etf_vxx(self) -> None:
        assert UniverseService._classify_asset_type("VXX", "iPath Series B S&P 500") == "etf"


# ---------------------------------------------------------------------------
# _classify_market_cap_tier
# ---------------------------------------------------------------------------


class TestClassifyMarketCapTier:
    """Direct tests for the _classify_market_cap_tier static method."""

    def test_etf_bypass(self) -> None:
        assert UniverseService._classify_market_cap_tier("SPY", "etf") == "etf"

    def test_etf_bypass_any_symbol(self) -> None:
        assert UniverseService._classify_market_cap_tier("XYZW", "etf") == "etf"

    def test_large_cap_aapl(self) -> None:
        assert UniverseService._classify_market_cap_tier("AAPL", "equity") == "large_cap"

    def test_large_cap_msft(self) -> None:
        assert UniverseService._classify_market_cap_tier("MSFT", "equity") == "large_cap"

    def test_large_cap_tsla(self) -> None:
        assert UniverseService._classify_market_cap_tier("TSLA", "equity") == "large_cap"

    def test_large_cap_nvda(self) -> None:
        assert UniverseService._classify_market_cap_tier("NVDA", "equity") == "large_cap"

    def test_large_cap_jpm(self) -> None:
        assert UniverseService._classify_market_cap_tier("JPM", "equity") == "large_cap"

    def test_unknown_symbol_default_mid_cap(self) -> None:
        assert UniverseService._classify_market_cap_tier("XYZW", "equity") == "mid_cap"

    def test_small_company_default_mid_cap(self) -> None:
        assert UniverseService._classify_market_cap_tier("SMALLCO", "equity") == "mid_cap"

    def test_etf_check_before_large_cap(self) -> None:
        """ETF check runs before symbol lookup."""
        assert UniverseService._classify_market_cap_tier("AAPL", "etf") == "etf"
