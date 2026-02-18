/**
 * TypeScript interfaces matching the backend Pydantic models for ticker data.
 *
 * These mirror:
 *   - Option_Alpha.models.market_data.TickerInfo
 *   - Option_Alpha.models.market_data.Quote
 *   - Option_Alpha.web.routes.ticker.TickerDetail
 *   - Option_Alpha.web.routes.ticker.IndicatorValues
 *   - Option_Alpha.models.options.OptionGreeks
 *   - Option_Alpha.models.options.OptionContract
 */

/** Matches TickerInfo model */
export interface TickerInfo {
  symbol: string
  name: string
  sector: string
  market_cap_tier: string
  asset_type: string
  source: string
  tags: string[]
  status: string
  discovered_at: string
  last_scanned_at: string | null
  consecutive_misses: number
}

/** Matches Quote model (Decimal fields serialized as strings) */
export interface Quote {
  ticker: string
  bid: string
  ask: string
  last: string
  volume: number
  timestamp: string
  mid: string
  spread: string
}

/** Matches TickerDetail response from GET /api/ticker/{symbol} */
export interface TickerDetail {
  info: TickerInfo
  quote: Quote
}

/** Matches IndicatorValues response from GET /api/ticker/{symbol}/indicators */
export interface IndicatorValues {
  ticker: string
  rsi: number | null
  stoch_rsi: number | null
  williams_r: number | null
  adx: number | null
  roc: number | null
  supertrend: number | null
  atr_percent: number | null
  bb_width: number | null
  keltner_width: number | null
  obv_trend: number | null
  ad_trend: number | null
  relative_volume: number | null
  sma_alignment: number | null
  vwap_deviation: number | null
}

/** Matches OptionGreeks model */
export interface OptionGreeks {
  delta: number
  gamma: number
  theta: number
  vega: number
  rho: number
}

/** Matches OptionContract model (Decimal fields serialized as strings) */
export interface OptionContract {
  ticker: string
  option_type: 'call' | 'put'
  strike: string
  expiration: string
  bid: string
  ask: string
  last: string
  volume: number
  open_interest: number
  implied_volatility: number
  greeks: OptionGreeks | null
  greeks_source: string | null
  mid: string
  spread: string
  dte: number
}

/** Debate history entry for the ticker deep-dive timeline */
export interface DebateHistoryEntry {
  id: number
  ticker: string
  direction: 'bullish' | 'bearish' | 'neutral'
  conviction: number
  created_at: string
}
