"""Tests for the legal disclaimer module.

Verifies that the single-source-of-truth disclaimer text is present,
contains all required legal phrases, and that get_disclaimer() returns
the identical constant.
"""

from __future__ import annotations

from Option_Alpha.reporting.disclaimer import DISCLAIMER_TEXT, get_disclaimer


class TestDisclaimerText:
    """Tests for the DISCLAIMER_TEXT constant."""

    def test_disclaimer_text_is_string(self) -> None:
        """DISCLAIMER_TEXT must be a plain string."""
        assert isinstance(DISCLAIMER_TEXT, str)

    def test_disclaimer_text_is_not_empty(self) -> None:
        """DISCLAIMER_TEXT must not be empty."""
        assert len(DISCLAIMER_TEXT) > 0

    def test_disclaimer_contains_educational(self) -> None:
        """Disclaimer must mention educational purpose."""
        assert "educational" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_not_investment_advice(self) -> None:
        """Disclaimer must state it does not constitute investment advice."""
        assert "not constitute investment advice" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_risk_of_loss(self) -> None:
        """Disclaimer must mention risk of loss."""
        assert "risk of loss" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_financial_advisor(self) -> None:
        """Disclaimer must recommend consulting a financial advisor."""
        assert "financial advisor" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_not_appropriate_for_all(self) -> None:
        """Disclaimer must note options trading is not for all investors."""
        assert "not appropriate for all investors" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_past_performance(self) -> None:
        """Disclaimer must note past performance does not guarantee results."""
        assert "past performance" in DISCLAIMER_TEXT.lower()

    def test_disclaimer_contains_data_may_be_delayed(self) -> None:
        """Disclaimer must warn that market data may be delayed."""
        assert "delayed" in DISCLAIMER_TEXT.lower()


class TestGetDisclaimer:
    """Tests for get_disclaimer() function."""

    def test_get_disclaimer_returns_same_as_constant(self) -> None:
        """get_disclaimer() must return the identical DISCLAIMER_TEXT."""
        assert get_disclaimer() == DISCLAIMER_TEXT

    def test_get_disclaimer_returns_string(self) -> None:
        """get_disclaimer() must return a string."""
        assert isinstance(get_disclaimer(), str)

    def test_get_disclaimer_is_idempotent(self) -> None:
        """Multiple calls must return the same value."""
        assert get_disclaimer() == get_disclaimer()
