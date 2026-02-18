import { useState, useEffect, useCallback, useRef } from 'react'

const BASE_URL = '/api'

interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

interface UseApiOptions {
  /** Skip the initial fetch on mount */
  skip?: boolean
  /** Base URL override (defaults to /api) */
  baseUrl?: string
}

interface UseApiResult<T> extends ApiState<T> {
  refetch: () => void
}

export function useApi<T>(
  url: string,
  options: UseApiOptions = {},
): UseApiResult<T> {
  const { skip = false, baseUrl = BASE_URL } = options
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: !skip,
    error: null,
  })
  const abortControllerRef = useRef<AbortController | null>(null)

  const fetchData = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setState((prev) => ({ ...prev, loading: true, error: null }))

    try {
      const response = await fetch(`${baseUrl}${url}`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      })

      if (!response.ok) {
        const errorBody = await response.text().catch(() => '')
        throw new Error(
          `HTTP ${response.status}: ${errorBody || response.statusText}`,
        )
      }

      const data = (await response.json()) as T
      if (!controller.signal.aborted) {
        setState({ data, loading: false, error: null })
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return
      }
      const message = err instanceof Error ? err.message : 'Unknown error'
      if (!controller.signal.aborted) {
        setState((prev) => ({ ...prev, loading: false, error: message }))
      }
    }
  }, [baseUrl, url])

  useEffect(() => {
    if (!skip) {
      void fetchData()
    }
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [fetchData, skip])

  return { ...state, refetch: fetchData }
}
