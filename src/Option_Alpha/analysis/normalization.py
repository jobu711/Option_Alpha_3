"""Percentile-rank normalization across a scanned universe of tickers.

Transforms raw indicator values into percentile ranks (0-100) so that
indicators with different scales become comparable. Inverted indicators
(where higher raw value = worse signal) are flipped after normalization.
"""

import logging
import math

logger = logging.getLogger(__name__)

# Indicators where higher raw value indicates a worse (less favorable) signal.
# After percentile normalization, these are inverted: rank = 100 - rank.
INVERTED_INDICATORS: frozenset[str] = frozenset(
    {"bb_width", "atr_percent", "relative_volume", "keltner_width"}
)


def percentile_rank_normalize(
    universe_indicators: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Convert raw indicator values to percentile ranks across the universe.

    For each indicator, all tickers that have a value are ranked. The percentile
    is computed as ``(rank / count) * 100`` where rank uses 1-based ordinal
    ranking (ties receive the same rank, the next rank skips accordingly).

    Tickers missing an indicator are excluded from that indicator's output
    so that :func:`~Option_Alpha.analysis.scoring.composite_score` only
    weights indicators the ticker actually has data for.

    Args:
        universe_indicators: Outer key is ticker, inner key is indicator name,
            value is the raw indicator value. ``NaN`` values are treated as
            missing.

    Returns:
        Same structure with values replaced by percentile ranks in [0, 100].
    """
    if not universe_indicators:
        return {}

    # Collect all indicator names across the entire universe.
    all_indicators: set[str] = set()
    for indicators in universe_indicators.values():
        all_indicators.update(indicators.keys())

    # For each indicator, gather valid (non-NaN) values with their tickers.
    indicator_ranks: dict[str, dict[str, float]] = {}
    for indicator_name in all_indicators:
        # Collect (ticker, value) pairs where value is finite.
        ticker_values: list[tuple[str, float]] = []
        for ticker, indicators in universe_indicators.items():
            value = indicators.get(indicator_name)
            if value is not None and not math.isnan(value):
                ticker_values.append((ticker, value))

        count = len(ticker_values)
        if count == 0:
            # No valid values for this indicator across the entire universe.
            # Skip entirely — don't populate DEFAULT_PERCENTILE so the
            # indicator is absent from the output and composite_score()
            # renormalizes the remaining weights automatically.
            logger.debug(
                "Indicator '%s' has no valid values — excluded from normalization",
                indicator_name,
            )
            continue

        # Sort ascending by value to assign ranks.
        ticker_values.sort(key=lambda tv: tv[1])

        # Assign ranks with tie handling: identical values get the same rank.
        ranks: dict[str, float] = {}
        idx = 0
        while idx < count:
            # Find the run of identical values.
            run_start = idx
            while idx < count and ticker_values[idx][1] == ticker_values[run_start][1]:
                idx += 1
            # All items in the run share the same rank (average of positions).
            avg_rank = (run_start + 1 + idx) / 2.0
            for j in range(run_start, idx):
                ranks[ticker_values[j][0]] = avg_rank

        # Convert ranks to percentiles: (rank / count) * 100.
        # Tickers missing this indicator are skipped (not assigned
        # DEFAULT_PERCENTILE) so composite_score() only weights
        # indicators the ticker actually has data for.
        for ticker in universe_indicators:
            if ticker in ranks:
                percentile = (ranks[ticker] / count) * 100.0
                indicator_ranks.setdefault(ticker, {})[indicator_name] = percentile

    return indicator_ranks


def invert_indicators(
    normalized: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Flip inverted indicators so that higher percentile = better signal.

    For indicators in :data:`INVERTED_INDICATORS`, the percentile rank is
    replaced with ``100 - rank``.

    Args:
        normalized: Percentile-ranked indicators from
            :func:`percentile_rank_normalize`.

    Returns:
        Same structure with inverted indicators flipped.
    """
    result: dict[str, dict[str, float]] = {}
    for ticker, indicators in normalized.items():
        adjusted: dict[str, float] = {}
        for name, value in indicators.items():
            if name in INVERTED_INDICATORS:
                adjusted[name] = 100.0 - value
            else:
                adjusted[name] = value
        result[ticker] = adjusted
    return result
