"""Earnings date proximity scoring for catalyst-aware analysis.

Assigns a score (0-100) based on how close the next earnings date is, and
provides an adjustment function to blend catalyst proximity into a composite
score.
"""

import datetime
import logging

logger = logging.getLogger(__name__)

# Weight applied to catalyst score when blending with the base composite score.
CATALYST_WEIGHT: float = 0.15

# Day-range boundaries for earnings proximity buckets.
EARNINGS_IMMINENT_DAYS: int = 7
EARNINGS_UPCOMING_DAYS: int = 14
EARNINGS_MODERATE_DAYS: int = 30
EARNINGS_DISTANT_DAYS: int = 60

# Scores for each earnings proximity bucket.
_SCORE_NO_EARNINGS: float = 50.0
_SCORE_PAST_EARNINGS: float = 30.0
_SCORE_IMMINENT: float = 90.0
_SCORE_UPCOMING: float = 75.0
_SCORE_MODERATE: float = 60.0
_SCORE_DISTANT: float = 45.0
_SCORE_VERY_DISTANT: float = 35.0


def catalyst_proximity_score(
    next_earnings: datetime.date | None,
    reference_date: datetime.date,
) -> float:
    """Score the proximity of the next earnings date on a 0-100 scale.

    Args:
        next_earnings: The next known earnings date, or ``None`` if unknown.
        reference_date: The date from which to measure days-until-earnings.

    Returns:
        A float score in [0.0, 100.0]:
        - No earnings date: 50.0 (neutral)
        - Past earnings (days <= 0): 30.0 (penalize stale data)
        - 1-7 days: 90.0 (imminent catalyst)
        - 8-14 days: 75.0 (upcoming catalyst)
        - 15-30 days: 60.0 (moderate catalyst)
        - 31-60 days: 45.0 (distant)
        - >60 days: 35.0 (very distant)
    """
    if next_earnings is None:
        return _SCORE_NO_EARNINGS

    days_until = (next_earnings - reference_date).days

    if days_until <= 0:
        return _SCORE_PAST_EARNINGS
    if days_until <= EARNINGS_IMMINENT_DAYS:
        return _SCORE_IMMINENT
    if days_until <= EARNINGS_UPCOMING_DAYS:
        return _SCORE_UPCOMING
    if days_until <= EARNINGS_MODERATE_DAYS:
        return _SCORE_MODERATE
    if days_until <= EARNINGS_DISTANT_DAYS:
        return _SCORE_DISTANT
    return _SCORE_VERY_DISTANT


def apply_catalyst_adjustment(
    base_score: float,
    catalyst_score: float,
    catalyst_weight: float = CATALYST_WEIGHT,
) -> float:
    """Blend a catalyst proximity score into a base composite score.

    Formula::

        adjusted = base_score * (1 - catalyst_weight) + catalyst_score * catalyst_weight

    The result is clamped to [0.0, 100.0].

    Args:
        base_score: The composite score before catalyst adjustment.
        catalyst_score: The catalyst proximity score (0-100).
        catalyst_weight: Weight given to the catalyst score (default
            :data:`CATALYST_WEIGHT`).

    Returns:
        Adjusted score clamped to [0.0, 100.0].
    """
    adjusted = base_score * (1.0 - catalyst_weight) + catalyst_score * catalyst_weight
    return max(0.0, min(100.0, adjusted))
