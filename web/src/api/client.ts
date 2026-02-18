const BASE_URL = '/api'

class ApiError extends Error {
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

export const api = {
  scan: {
    start: (params?: unknown) => post<unknown>('/scan', params),
    get: (id: string) => get<unknown>(`/scan/${id}`),
    list: () => get<unknown[]>('/scan'),
  },

  debate: {
    start: (ticker: string) =>
      post<import('../types/debate').DebateStarted>(`/debate/${ticker}`),
    get: (id: string) =>
      get<import('../types/debate').DebateResult>(`/debate/${id}`),
    list: () =>
      get<import('../types/debate').DebateResult[]>('/debate'),
  },

  ticker: {
    get: (symbol: string) => get<unknown>(`/ticker/${symbol}`),
    indicators: (symbol: string) =>
      get<unknown>(`/ticker/${symbol}/indicators`),
  },

  watchlist: {
    list: () => get<unknown[]>('/watchlist'),
    add: (symbol: string) => post<unknown>('/watchlist', { symbol }),
    remove: (symbol: string) => del<unknown>(`/watchlist/${symbol}`),
  },

  universe: {
    get: () => get<unknown>('/universe'),
    refresh: () => post<unknown>('/universe/refresh'),
  },

  settings: {
    get: () => get<unknown>('/settings'),
    update: (settings: unknown) => put<unknown>('/settings', settings),
  },

  health: {
    check: () => get<unknown>('/health'),
  },
} as const
