import { useState, useEffect, useRef } from 'react'

const BASE_URL = '/api'

const MAX_RECONNECT_DELAY_MS = 30_000
const INITIAL_RECONNECT_DELAY_MS = 1_000

interface UseSSEOptions {
  /** Base URL override (defaults to /api) */
  baseUrl?: string
  /** Disable auto-connect */
  skip?: boolean
}

interface UseSSEResult<T> {
  data: T | null
  connected: boolean
  error: string | null
}

export function useSSE<T>(
  url: string,
  options: UseSSEOptions = {},
): UseSSEResult<T> {
  const { baseUrl = BASE_URL, skip = false } = options
  const [data, setData] = useState<T | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY_MS)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (skip) {
      return
    }

    function cleanup() {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
    }

    function connect() {
      cleanup()

      const fullUrl = `${baseUrl}${url}`
      const source = new EventSource(fullUrl)
      eventSourceRef.current = source

      source.onopen = () => {
        setConnected(true)
        setError(null)
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY_MS
      }

      source.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data as string) as T
          setData(parsed)
        } catch {
          setError('Failed to parse SSE message')
        }
      }

      source.onerror = () => {
        setConnected(false)
        source.close()
        eventSourceRef.current = null

        // Exponential backoff reconnect
        const delay = reconnectDelayRef.current
        setError(
          `Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`,
        )
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(
            delay * 2,
            MAX_RECONNECT_DELAY_MS,
          )
          connect()
        }, delay)
      }
    }

    connect()

    return cleanup
  }, [baseUrl, url, skip])

  return { data, connected, error }
}
