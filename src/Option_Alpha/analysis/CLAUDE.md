<claude_instructions>
# CLAUDE.md — Analysis & Scoring

## Purpose
Scoring engine that normalizes indicator outputs, computes composite scores, determines
directional signals, recommends contracts, and provides BSM Greeks fallback. Consumes
typed models from `models/` and indicator output. No direct API calls.

## Files
- `normalization.py` — Percentile-rank normalization across scanned universe, inverted indicators
- `scoring.py` — Weighted geometric mean composite score, universe scoring pipeline
- `direction.py` — Signal direction classification (BULLISH/BEARISH/NEUTRAL)
- `contracts.py` — Contract filtering by liquidity/spread/delta, recommendation pipeline
- `bsm.py` — Black-Scholes-Merton pricing, Greeks computation, implied volatility solver

## Architecture Rules
- **No API calls** — data comes from `services/` via the caller, never fetched here
- **Typed models everywhere** — consume and return Pydantic models from `models/`
- **No raw dicts** from public functions (normalization internals use `dict[str, dict[str, float]]`
  for indicator data interchange, but final output is always `TickerScore` or other typed models)
- **Constants, not magic numbers** — all thresholds, weights, and bounds are module-level uppercase

## Key Constants
| Module | Constant | Value | Purpose |
|--------|----------|-------|---------|
| `scoring.py` | `MIN_COMPOSITE_SCORE` | 50.0 | Inclusion threshold |
| `scoring.py` | `INDICATOR_WEIGHTS` | dict | All 18 indicator weights (sum to 1.0) |
| `normalization.py` | `INVERTED_INDICATORS` | frozenset | bb_width, atr_percent, relative_volume, keltner_width |
| `direction.py` | `ADX_TREND_THRESHOLD` | 15.0 | Below = NEUTRAL |
| `contracts.py` | `MIN_AVG_DOLLAR_VOLUME` | 10_000_000.0 | Ticker-level $10M/day pre-filter |
| `contracts.py` | `MIN_STOCK_PRICE` | 10.0 | Ticker-level min price pre-filter |
| `contracts.py` | `MIN_OPEN_INTEREST` | 100 | Contract-level liquidity filter |
| `contracts.py` | `MAX_SPREAD_PCT` | 0.30 | 30% max spread |
| `contracts.py` | `DEFAULT_DELTA_TARGET` | 0.35 | Midpoint of 0.20-0.50 range |
| `bsm.py` | `BSM_MAX_ITERATIONS` | 50 | Newton-Raphson iteration cap |

## Data Flow
```
Raw indicators (dict[str, dict[str, float]])
    → percentile_rank_normalize() → invert_indicators()
    → composite_score() per ticker → score_universe() → list[TickerScore]
    → determine_direction(adx, rsi, sma_alignment) → SignalDirection
    → filter_liquid_tickers(scored, ohlcv, top_n) → list[TickerScore]  (pre-filter)
    → filter_contracts() → select_expiration() → select_by_delta() → OptionContract | None
```

## BSM Module
- Standard European Black-Scholes using `scipy.stats.norm`
- Returns `OptionGreeks` model (same type as market Greeks)
- IV solver: Newton-Raphson (50 iter) with bisection fallback (100 iter)
- Uses European lower bound (not naive intrinsic) to reject impossible prices

## What Claude Gets Wrong Here (Fix These)
- Don't call APIs from analysis code — data comes from the caller
- Don't return raw dicts from public functions — use typed models
- Don't use magic numbers — reference the named constants
- Don't confuse weighted arithmetic mean with weighted geometric mean
- Don't forget to clamp composite scores to [0, 100]
- Don't use `ddof=1` anywhere — this module doesn't compute standard deviations
- Don't forget that theta is per-day (divided by 365), not annual
- Don't mix up IV Rank and IV Percentile weights
</claude_instructions>
