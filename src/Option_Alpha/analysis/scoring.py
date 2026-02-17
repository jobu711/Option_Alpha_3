"""Weighted geometric mean composite scoring for the ticker universe.

Takes percentile-ranked (and inverted) indicator values and produces a single
composite score per ticker using a weighted geometric mean. Tickers scoring
above :data:`MIN_COMPOSITE_SCORE` are returned as :class:`TickerScore` models,
sorted descending with 1-based ranks assigned.
"""

import logging
import math

from Option_Alpha.analysis.normalization import (
    invert_indicators,
    percentile_rank_normalize,
)
from Option_Alpha.models.scan import TickerScore

logger = logging.getLogger(__name__)

# --- Indicator Weights ---

# Oscillators
WEIGHT_RSI: float = 0.08
WEIGHT_STOCH_RSI: float = 0.05
WEIGHT_WILLIAMS_R: float = 0.05

# Trend
WEIGHT_ADX: float = 0.08
WEIGHT_ROC: float = 0.05
WEIGHT_SUPERTREND: float = 0.05

# Volatility
WEIGHT_ATR_PERCENT: float = 0.05
WEIGHT_BB_WIDTH: float = 0.05
WEIGHT_KELTNER_WIDTH: float = 0.04

# Volume
WEIGHT_OBV_TREND: float = 0.05
WEIGHT_AD_TREND: float = 0.05
WEIGHT_RELATIVE_VOLUME: float = 0.05

# Moving Averages
WEIGHT_SMA_ALIGNMENT: float = 0.08
WEIGHT_VWAP_DEVIATION: float = 0.05

# Options-Specific
WEIGHT_IV_RANK: float = 0.06
WEIGHT_IV_PERCENTILE: float = 0.06
WEIGHT_PUT_CALL_RATIO: float = 0.05
WEIGHT_MAX_PAIN: float = 0.05

# Thresholds
MIN_COMPOSITE_SCORE: float = 50.0

# Weight mapping: indicator name -> weight
INDICATOR_WEIGHTS: dict[str, float] = {
    "rsi": WEIGHT_RSI,
    "stoch_rsi": WEIGHT_STOCH_RSI,
    "williams_r": WEIGHT_WILLIAMS_R,
    "adx": WEIGHT_ADX,
    "roc": WEIGHT_ROC,
    "supertrend": WEIGHT_SUPERTREND,
    "atr_percent": WEIGHT_ATR_PERCENT,
    "bb_width": WEIGHT_BB_WIDTH,
    "keltner_width": WEIGHT_KELTNER_WIDTH,
    "obv_trend": WEIGHT_OBV_TREND,
    "ad_trend": WEIGHT_AD_TREND,
    "relative_volume": WEIGHT_RELATIVE_VOLUME,
    "sma_alignment": WEIGHT_SMA_ALIGNMENT,
    "vwap_deviation": WEIGHT_VWAP_DEVIATION,
    "iv_rank": WEIGHT_IV_RANK,
    "iv_percentile": WEIGHT_IV_PERCENTILE,
    "put_call_ratio": WEIGHT_PUT_CALL_RATIO,
    "max_pain": WEIGHT_MAX_PAIN,
}

# Floor value substituted for percentile ranks <= 0 to avoid log(0).
_FLOOR_VALUE: float = 1.0


def composite_score(normalized_indicators: dict[str, float]) -> float:
    """Compute a weighted geometric mean composite score.

    The score is ``exp(sum(w_i * ln(x_i)) / sum(w_i))`` where *w_i* is the
    weight for indicator *i* and *x_i* is the percentile rank.

    Indicators not present in :data:`INDICATOR_WEIGHTS` or missing from the
    input are silently skipped. If *x_i* <= 0, it is replaced with
    :data:`_FLOOR_VALUE` to avoid ``log(0)``.

    Args:
        normalized_indicators: Indicator name to percentile rank mapping for
            a single ticker (already normalized and inverted).

    Returns:
        Composite score clamped to [0.0, 100.0].
    """
    weighted_log_sum: float = 0.0
    weight_sum: float = 0.0

    for name, value in normalized_indicators.items():
        weight = INDICATOR_WEIGHTS.get(name)
        if weight is None:
            continue
        clamped_value = value if value > 0.0 else _FLOOR_VALUE
        weighted_log_sum += weight * math.log(clamped_value)
        weight_sum += weight

    if weight_sum == 0.0:
        return 0.0

    raw_score = math.exp(weighted_log_sum / weight_sum)
    return max(0.0, min(100.0, raw_score))


def score_universe(
    universe_indicators: dict[str, dict[str, float]],
) -> list[TickerScore]:
    """Score, filter, rank, and return the universe as :class:`TickerScore` models.

    Pipeline:
        1. Percentile-rank normalize all indicators across the universe.
        2. Invert indicators where higher raw value = worse signal.
        3. Compute composite score per ticker.
        4. Filter tickers below :data:`MIN_COMPOSITE_SCORE`.
        5. Sort descending by score.
        6. Assign 1-based ranks.

    Args:
        universe_indicators: Outer key is ticker, inner key is indicator name,
            value is the raw indicator value.

    Returns:
        List of :class:`TickerScore` sorted by score descending, with ranks
        starting at 1. Only tickers meeting the minimum score threshold are
        included.
    """
    if not universe_indicators:
        return []

    # Step 1-2: Normalize and invert.
    normalized = percentile_rank_normalize(universe_indicators)
    inverted = invert_indicators(normalized)

    # Step 3: Composite score per ticker.
    scored: list[tuple[str, float, dict[str, float]]] = []
    for ticker, indicators in inverted.items():
        score = composite_score(indicators)
        if score >= MIN_COMPOSITE_SCORE:
            scored.append((ticker, score, indicators))

    # Step 4-5: Sort descending by score.
    scored.sort(key=lambda t: t[1], reverse=True)

    # Step 6: Assign 1-based ranks and build TickerScore models.
    results: list[TickerScore] = []
    for rank, (ticker, score, signals) in enumerate(scored, start=1):
        results.append(
            TickerScore(
                ticker=ticker,
                score=score,
                signals=signals,
                rank=rank,
            )
        )

    return results
