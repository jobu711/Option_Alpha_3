"""Tests for earnings catalyst proximity scoring and adjustment."""

import datetime

import pytest

from Option_Alpha.analysis.catalysts import (
    CATALYST_WEIGHT,
    EARNINGS_DISTANT_DAYS,
    EARNINGS_IMMINENT_DAYS,
    EARNINGS_MODERATE_DAYS,
    EARNINGS_UPCOMING_DAYS,
    apply_catalyst_adjustment,
    catalyst_proximity_score,
)


class TestCatalystProximityScore:
    """Tests for catalyst_proximity_score()."""

    def test_no_earnings_date_returns_neutral(self) -> None:
        """No earnings date produces a neutral score of 50.0."""
        reference = datetime.date(2025, 6, 15)
        score = catalyst_proximity_score(None, reference)
        assert score == pytest.approx(50.0, rel=1e-4)

    def test_past_earnings_returns_30(self) -> None:
        """Earnings in the past (days <= 0) produce a penalty score of 30.0."""
        reference = datetime.date(2025, 6, 15)
        # Earnings was yesterday.
        past = datetime.date(2025, 6, 14)
        score = catalyst_proximity_score(past, reference)
        assert score == pytest.approx(30.0, rel=1e-4)

    def test_earnings_same_day_returns_30(self) -> None:
        """Earnings on the reference date (days = 0) counts as past."""
        reference = datetime.date(2025, 6, 15)
        score = catalyst_proximity_score(reference, reference)
        assert score == pytest.approx(30.0, rel=1e-4)

    def test_imminent_earnings_1_day(self) -> None:
        """Earnings 1 day away returns imminent score of 90.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 6, 16)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(90.0, rel=1e-4)

    def test_imminent_earnings_7_days(self) -> None:
        """Earnings exactly 7 days away returns imminent score of 90.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 6, 22)
        assert (earnings - reference).days == EARNINGS_IMMINENT_DAYS
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(90.0, rel=1e-4)

    def test_upcoming_earnings_8_days(self) -> None:
        """Earnings 8 days away returns upcoming score of 75.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 6, 23)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(75.0, rel=1e-4)

    def test_upcoming_earnings_14_days(self) -> None:
        """Earnings exactly 14 days away returns upcoming score of 75.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 6, 29)
        assert (earnings - reference).days == EARNINGS_UPCOMING_DAYS
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(75.0, rel=1e-4)

    def test_moderate_earnings_15_days(self) -> None:
        """Earnings 15 days away returns moderate score of 60.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 6, 30)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(60.0, rel=1e-4)

    def test_moderate_earnings_30_days(self) -> None:
        """Earnings exactly 30 days away returns moderate score of 60.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 7, 15)
        assert (earnings - reference).days == EARNINGS_MODERATE_DAYS
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(60.0, rel=1e-4)

    def test_distant_earnings_31_days(self) -> None:
        """Earnings 31 days away returns distant score of 45.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 7, 16)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(45.0, rel=1e-4)

    def test_distant_earnings_60_days(self) -> None:
        """Earnings exactly 60 days away returns distant score of 45.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 8, 14)
        assert (earnings - reference).days == EARNINGS_DISTANT_DAYS
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(45.0, rel=1e-4)

    def test_very_distant_earnings_61_days(self) -> None:
        """Earnings 61 days away returns very distant score of 35.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 8, 15)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(35.0, rel=1e-4)

    def test_very_distant_earnings_180_days(self) -> None:
        """Earnings 180 days away returns very distant score of 35.0."""
        reference = datetime.date(2025, 1, 1)
        earnings = datetime.date(2025, 6, 30)
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(35.0, rel=1e-4)

    def test_far_past_earnings(self) -> None:
        """Earnings far in the past still returns 30.0."""
        reference = datetime.date(2025, 6, 15)
        earnings = datetime.date(2025, 1, 1)  # ~165 days ago
        score = catalyst_proximity_score(earnings, reference)
        assert score == pytest.approx(30.0, rel=1e-4)


class TestApplyCatalystAdjustment:
    """Tests for apply_catalyst_adjustment()."""

    def test_formula_correctness(self) -> None:
        """Verify the blending formula: base*(1-w) + catalyst*w."""
        base = 70.0
        catalyst = 90.0
        weight = CATALYST_WEIGHT  # 0.15
        expected = base * (1.0 - weight) + catalyst * weight
        result = apply_catalyst_adjustment(base, catalyst)
        assert result == pytest.approx(expected, rel=1e-4)

    def test_custom_weight(self) -> None:
        """Custom catalyst_weight parameter overrides default."""
        base = 60.0
        catalyst = 80.0
        custom_weight = 0.30
        expected = base * (1.0 - custom_weight) + catalyst * custom_weight
        result = apply_catalyst_adjustment(base, catalyst, custom_weight)
        assert result == pytest.approx(expected, rel=1e-4)

    def test_zero_catalyst_weight(self) -> None:
        """With zero catalyst weight, result equals base score."""
        base = 75.0
        catalyst = 90.0
        result = apply_catalyst_adjustment(base, catalyst, catalyst_weight=0.0)
        assert result == pytest.approx(base, rel=1e-4)

    def test_full_catalyst_weight(self) -> None:
        """With catalyst weight 1.0, result equals catalyst score."""
        base = 75.0
        catalyst = 90.0
        result = apply_catalyst_adjustment(base, catalyst, catalyst_weight=1.0)
        assert result == pytest.approx(catalyst, rel=1e-4)

    def test_clamped_to_100(self) -> None:
        """Result cannot exceed 100.0."""
        # Both at 100 with any weight -> 100
        result = apply_catalyst_adjustment(100.0, 100.0)
        assert result <= 100.0

    def test_clamped_to_0(self) -> None:
        """Result cannot go below 0.0."""
        result = apply_catalyst_adjustment(0.0, 0.0)
        assert result >= 0.0

    def test_neutral_catalyst_minimal_change(self) -> None:
        """A neutral catalyst (50.0) applied to a base of 50.0 returns 50.0."""
        result = apply_catalyst_adjustment(50.0, 50.0)
        assert result == pytest.approx(50.0, rel=1e-4)

    def test_catalyst_weight_constant_value(self) -> None:
        """CATALYST_WEIGHT constant is 0.15."""
        assert pytest.approx(0.15, rel=1e-4) == CATALYST_WEIGHT
