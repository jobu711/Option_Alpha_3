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
 * Full debate result used by the UI.
 *
 * The backend GET /api/debate/{id} and GET /api/debate return raw TradeThesis
 * objects without wrapper metadata (id, ticker, status, agents). This interface
 * represents the UI display shape; the API client transforms the backend
 * response into this shape via {@link toDebateResult}.
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

/**
 * Transform a raw TradeThesis from the backend into a DebateResult for the UI.
 *
 * The backend debate endpoints return TradeThesis directly without wrapper
 * fields. This function infers the missing metadata:
 * - `id`: passed explicitly (from the URL parameter or list index)
 * - `ticker`: not available in TradeThesis; defaults to empty string
 * - `status`: always 'completed' (only persisted theses are returned)
 * - `agents`: not returned by the backend; set to null placeholders
 * - `is_fallback`: inferred from model_used containing 'fallback'
 * - `created_at`: not in TradeThesis; defaults to empty string
 */
export function toDebateResult(
  thesis: TradeThesis,
  id: number,
): DebateResult {
  return {
    id,
    ticker: '',
    status: 'completed',
    thesis,
    agents: {
      bull: null,
      bear: null,
      risk: null,
    },
    is_fallback: thesis.model_used.toLowerCase().includes('fallback'),
    created_at: '',
  }
}

/** Response from POST /api/debate/{ticker} */
export interface DebateStarted {
  ticker: string
  status: string
  message: string
}
