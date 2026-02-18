import type { DebateResult, DebateStarted } from '../types/debate'

const BASE_URL = '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${BASE_URL}${path}`
  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (!response.ok) {
    const errorBody = await response.text().catch(() => '')
    throw new ApiError(
      response.status,
      errorBody || `HTTP ${response.status}: ${response.statusText}`,
    )
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

function get<T>(path: string): Promise<T> {
  return request<T>('GET', path)
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('POST', path, body)
}

function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>('PUT', path, body)
}

function del<T>(path: string): Promise<T> {
  return request<T>('DELETE', path)
}

// ---------------------------------------------------------------------------
// Typed API response interfaces (matching backend Pydantic models)
// ---------------------------------------------------------------------------

export interface ScanRunResponse {
  id: string
  started_at: string
  completed_at: string | null
  status: string
  preset: string
  sectors: string[]
  ticker_count: number
  top_n: number
}

export interface TickerScoreResponse {
  ticker: string
  score: number
  signals: Record<string, number>
  rank: number
}

export interface WatchlistResponse {
  watchlist: {
    id: number
    name: string
    created_at: string
  }
  tickers: string[]
}

export interface WatchlistItem {
  ticker: string
}

export interface UniverseTickerInfo {
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

export interface UniverseListResponse {
  stats: {
    total: number
    by_sector: Record<string, number>
    by_market_cap: Record<string, number>
    last_refresh: string | null
  }
  tickers: UniverseTickerInfo[]
  total: number
  limit: number
  offset: number
}

export interface UniverseRefreshResponse {
  status: string
}

export interface WebSettings {
  ollama_endpoint: string
  ollama_model: string
  scan_top_n: number
  scan_min_volume: number
  default_dte_min: number
  default_dte_max: number
}

export interface HealthStatus {
  ollama: boolean
  anthropic: boolean
  yfinance: boolean
  sqlite: boolean
  overall: boolean
  checked_at: string
}

export const api = {
  scan: {
    start: (params?: unknown) => post<ScanRunResponse>('/scan', params),
    get: (id: string) =>
      get<{ scan_run: ScanRunResponse; scores: TickerScoreResponse[] }>(
        `/scan/${id}`,
      ),
    list: () => get<ScanRunResponse[]>('/scan'),
  },

  debate: {
    start: (ticker: string) => post<DebateStarted>(`/debate/${ticker}`),
    get: (id: string) => get<DebateResult>(`/debate/${id}`),
    list: () => get<DebateResult[]>('/debate'),
  },

  ticker: {
    get: (symbol: string) => get<unknown>(`/ticker/${symbol}`),
    indicators: (symbol: string) =>
      get<unknown>(`/ticker/${symbol}/indicators`),
  },

  watchlist: {
    list: () => get<WatchlistResponse>('/watchlist'),
    add: (ticker: string) => post<WatchlistItem>('/watchlist', { ticker }),
    remove: (symbol: string) => del<void>(`/watchlist/${symbol}`),
  },

  universe: {
    list: (params?: { limit?: number; offset?: number; q?: string }) => {
      const searchParams = new URLSearchParams()
      if (params?.limit !== undefined)
        searchParams.set('limit', String(params.limit))
      if (params?.offset !== undefined)
        searchParams.set('offset', String(params.offset))
      if (params?.q) searchParams.set('q', params.q)
      const qs = searchParams.toString()
      return get<UniverseListResponse>(`/universe${qs ? `?${qs}` : ''}`)
    },
    refresh: () => post<UniverseRefreshResponse>('/universe/refresh'),
  },

  settings: {
    get: () => get<WebSettings>('/settings'),
    update: (settings: WebSettings) => put<WebSettings>('/settings', settings),
  },

  health: {
    check: () => get<HealthStatus>('/health'),
  },

  report: {
    download: async (debateId: number): Promise<Blob> => {
      const response = await fetch(
        `${BASE_URL}/report/${debateId}?format=md`,
        {
          headers: { Accept: 'text/markdown' },
        },
      )
      if (!response.ok) {
        const errorBody = await response.text().catch(() => '')
        throw new ApiError(
          response.status,
          errorBody || `HTTP ${response.status}: ${response.statusText}`,
        )
      }
      return response.blob()
    },
  },
} as const
