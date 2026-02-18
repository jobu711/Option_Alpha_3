/**
 * TypeScript interfaces matching the backend Pydantic models for debate data.
 *
 * These mirror:
 *   - Option_Alpha.models.analysis.AgentResponse
 *   - Option_Alpha.models.analysis.TradeThesis
 *   - Option_Alpha.models.analysis.GreeksCited
 *   - Option_Alpha.models.enums.SignalDirection
 */

/** Matches SignalDirection StrEnum */
export type SignalDirection = 'bullish' | 'bearish' | 'neutral'

/** Matches GreeksCited model */
export interface GreeksCited {
  delta: number | null
  gamma: number | null
  theta: number | null
  vega: number | null
  rho: number | null
}

/** Matches AgentResponse model */
export interface AgentResponse {
  agent_role: string
  analysis: string
  key_points: string[]
  conviction: number
  contracts_referenced: string[]
  greeks_cited: GreeksCited
  model_used: string
  input_tokens: number
  output_tokens: number
}

/** Matches TradeThesis model */
export interface TradeThesis {
  direction: SignalDirection
  conviction: number
  entry_rationale: string
  risk_factors: string[]
  recommended_action: string
  bull_summary: string
  bear_summary: string
  model_used: string
  total_tokens: number
  duration_ms: number
  disclaimer: string
}

/**
 * Full debate result returned by GET /api/debate/{id}.
 *
 * The backend returns a TradeThesis directly. Agent responses
 * may be stored separately or embedded — this interface covers
 * the full display shape expected by the UI.
 */
export interface DebateResult {
  id: number
  ticker: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  thesis: TradeThesis | null
  agents: {
    bull: AgentResponse | null
    bear: AgentResponse | null
    risk: AgentResponse | null
  }
  is_fallback: boolean
  created_at: string
}

/** Response from POST /api/debate/{ticker} */
export interface DebateStarted {
  ticker: string
  status: string
  message: string
}
