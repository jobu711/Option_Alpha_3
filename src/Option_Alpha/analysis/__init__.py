"""Analysis and scoring engine for options universe.

Re-exports all public functions so consumers can import directly:
    from Option_Alpha.analysis import composite_score, determine_direction
"""

from Option_Alpha.analysis.bsm import bsm_greeks, bsm_price, implied_volatility
from Option_Alpha.analysis.catalysts import apply_catalyst_adjustment, catalyst_proximity_score
from Option_Alpha.analysis.contracts import (
    filter_contracts,
    filter_liquid_tickers,
    recommend_contract,
    select_by_delta,
    select_expiration,
)
from Option_Alpha.analysis.direction import determine_direction
from Option_Alpha.analysis.normalization import invert_indicators, percentile_rank_normalize
from Option_Alpha.analysis.scoring import composite_score, score_universe

__all__ = [
    # BSM
    "bsm_greeks",
    "bsm_price",
    "implied_volatility",
    # Catalysts
    "apply_catalyst_adjustment",
    "catalyst_proximity_score",
    # Contracts
    "filter_contracts",
    "filter_liquid_tickers",
    "recommend_contract",
    "select_by_delta",
    "select_expiration",
    # Direction
    "determine_direction",
    # Normalization
    "invert_indicators",
    "percentile_rank_normalize",
    # Scoring
    "composite_score",
    "score_universe",
]
