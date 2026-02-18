/**
 * Test fixtures for debate UI components.
 *
 * Provides realistic sample data matching the backend Pydantic model shapes.
 */

import type {
  AgentResponse,
  DebateResult,
  GreeksCited,
  TradeThesis,
} from '../../types/debate'

export const sampleGreeks: GreeksCited = {
  delta: 0.45,
  gamma: 0.032,
  theta: -0.085,
  vega: 0.152,
  rho: 0.021,
}

export const sampleBullResponse: AgentResponse = {
  agent_role: 'bull',
  analysis:
    'AAPL shows strong bullish momentum with RSI at 62 and positive MACD crossover. ' +
    'The stock is trading above its 50-day and 200-day moving averages, indicating ' +
    'a sustained uptrend. IV rank at 35 suggests options are relatively cheap, ' +
    'making this a favorable entry point for long call positions.',
  key_points: [
    'RSI at 62 — bullish but not overbought',
    'Positive MACD crossover confirmed',
    'Trading above 50-day and 200-day SMA',
    'IV rank at 35 — options are cheap relative to history',
  ],
  conviction: 0.78,
  contracts_referenced: ['AAPL 2024-03-15 185C', 'AAPL 2024-03-15 190C'],
  greeks_cited: sampleGreeks,
  model_used: 'llama3.1:8b',
  input_tokens: 1250,
  output_tokens: 480,
}

export const sampleBearResponse: AgentResponse = {
  agent_role: 'bear',
  analysis:
    'Despite the bullish technical picture, AAPL faces significant headwinds. ' +
    'The put/call ratio at 1.2 suggests institutional hedging activity. ' +
    'Earnings are approaching in 12 days, creating binary event risk. ' +
    'The stock is near its 52-week high with limited upside potential.',
  key_points: [
    'Put/call ratio at 1.2 — institutional hedging',
    'Earnings in 12 days — binary event risk',
    'Near 52-week high — limited upside',
    'Sector rotation concerns in technology',
  ],
  conviction: 0.55,
  contracts_referenced: ['AAPL 2024-03-15 180P', 'AAPL 2024-03-15 175P'],
  greeks_cited: {
    delta: -0.35,
    gamma: 0.028,
    theta: -0.065,
    vega: 0.14,
    rho: null,
  },
  model_used: 'llama3.1:8b',
  input_tokens: 1180,
  output_tokens: 420,
}

export const sampleRiskResponse: AgentResponse = {
  agent_role: 'risk',
  analysis:
    'The primary risk is the upcoming earnings event. Position sizing should be ' +
    'conservative (2% of portfolio max). A defined-risk spread is recommended ' +
    'over naked calls to cap potential losses. The IV crush post-earnings could ' +
    'erase gains even if direction is correct.',
  key_points: [
    'Earnings event risk — position size 2% max',
    'Use defined-risk spreads, not naked options',
    'IV crush risk post-earnings',
    'Set stop-loss at -50% of premium',
  ],
  conviction: 0.65,
  contracts_referenced: ['AAPL 2024-03-15 185/190 Bull Call Spread'],
  greeks_cited: {
    delta: null,
    gamma: null,
    theta: -0.04,
    vega: 0.08,
    rho: null,
  },
  model_used: 'llama3.1:8b',
  input_tokens: 1100,
  output_tokens: 380,
}

export const sampleThesis: TradeThesis = {
  direction: 'bullish',
  conviction: 0.72,
  entry_rationale:
    'Bullish momentum confirmed by technical indicators with reasonable risk/reward. ' +
    'IV rank makes long calls attractive. Recommend defined-risk spread to manage earnings event risk.',
  risk_factors: [
    'Upcoming earnings in 12 days — binary event risk',
    'IV crush post-earnings could erase gains',
    'Near 52-week high — potential resistance',
    'Sector rotation risk in technology',
  ],
  recommended_action:
    'Buy AAPL 185/190 Bull Call Spread expiring 2024-03-15. Max risk $2.50, max reward $2.50. ' +
    'Enter at net debit of $2.45-$2.55.',
  bull_summary:
    'Strong technicals: RSI 62, MACD bullish crossover, above key moving averages. IV rank 35 makes options cheap.',
  bear_summary:
    'Elevated put/call ratio, earnings event risk in 12 days, near 52-week high resistance.',
  model_used: 'llama3.1:8b',
  total_tokens: 4810,
  duration_ms: 12450,
  disclaimer:
    'This analysis is for educational purposes only and does not constitute investment advice. ' +
    'Options trading involves significant risk of loss. Past performance does not guarantee future results.',
}

export const sampleCompletedDebate: DebateResult = {
  id: 42,
  ticker: 'AAPL',
  status: 'completed',
  thesis: sampleThesis,
  agents: {
    bull: sampleBullResponse,
    bear: sampleBearResponse,
    risk: sampleRiskResponse,
  },
  is_fallback: false,
  created_at: '2024-12-15T10:30:00Z',
}

export const sampleFallbackDebate: DebateResult = {
  ...sampleCompletedDebate,
  id: 43,
  is_fallback: true,
  thesis: {
    ...sampleThesis,
    model_used: 'data-driven-fallback',
  },
}

export const samplePendingDebate: DebateResult = {
  id: 44,
  ticker: 'TSLA',
  status: 'running',
  thesis: null,
  agents: {
    bull: null,
    bear: null,
    risk: null,
  },
  is_fallback: false,
  created_at: '2024-12-15T10:31:00Z',
}

export const sampleBearishDebate: DebateResult = {
  ...sampleCompletedDebate,
  id: 45,
  thesis: {
    ...sampleThesis,
    direction: 'bearish',
    conviction: 0.68,
  },
}

export const sampleNeutralDebate: DebateResult = {
  ...sampleCompletedDebate,
  id: 46,
  thesis: {
    ...sampleThesis,
    direction: 'neutral',
    conviction: 0.5,
  },
}

export const sampleFailedDebate: DebateResult = {
  id: 47,
  ticker: 'GME',
  status: 'failed',
  thesis: null,
  agents: {
    bull: null,
    bear: null,
    risk: null,
  },
  is_fallback: false,
  created_at: '2024-12-15T10:32:00Z',
}
