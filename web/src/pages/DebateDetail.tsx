import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Spinner } from '../components/common'
import { BullBearMeter } from '../components/charts/BullBearMeter'
import { DebateView, TradeThesisSection } from '../components/debate'
import { PageShell } from '../components/layout'
import type { DebateResult } from '../types/debate'

/** Polling interval when debate is still running (ms) */
const POLL_INTERVAL_MS = 3000

/** Maximum number of poll attempts before giving up */
const MAX_POLL_ATTEMPTS = 100

export function DebateDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [debate, setDebate] = useState<DebateResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pollCount, setPollCount] = useState(0)

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const fetchDebate = useCallback(async () => {
    if (!id) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch(`/api/debate/${id}`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      })

      if (!response.ok) {
        const errorBody = await response.text().catch(() => '')
        throw new Error(
          `HTTP ${response.status}: ${errorBody || response.statusText}`,
        )
      }

      const data = (await response.json()) as DebateResult

      if (!controller.signal.aborted) {
        setDebate(data)
        setLoading(false)
        setError(null)

        // Continue polling if still running
        if (
          (data.status === 'pending' || data.status === 'running') &&
          pollCount < MAX_POLL_ATTEMPTS
        ) {
          pollTimerRef.current = setTimeout(() => {
            setPollCount((c) => c + 1)
          }, POLL_INTERVAL_MS)
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return

      const message = err instanceof Error ? err.message : 'Unknown error'
      if (!controller.signal.aborted) {
        setError(message)
        setLoading(false)
      }
    }
  }, [id, pollCount])

  useEffect(() => {
    void fetchDebate()

    return () => {
      abortRef.current?.abort()
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
    }
  }, [fetchDebate])

  const handleRetry = () => {
    setLoading(true)
    setError(null)
    setPollCount(0)
    void fetchDebate()
  }

  const isPolling =
    debate !== null &&
    (debate.status === 'pending' || debate.status === 'running')

  return (
    <PageShell title={`Debate #${id ?? '\u2014'}`}>
      {/* Back navigation */}
      <div className="mb-3">
        <Button
          variant="secondary"
          onClick={() => navigate(-1)}
        >
          &larr; Back
        </Button>
      </div>

      {/* Loading state */}
      {loading && !debate && (
        <div
          className="flex flex-col items-center justify-center gap-3 py-16"
          data-testid="debate-loading"
        >
          <Spinner size="lg" />
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Loading debate...
          </span>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div
          className="flex flex-col items-center justify-center gap-3 border py-12"
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderColor: 'var(--color-bear)',
          }}
          data-testid="debate-error"
        >
          <span
            className="font-data text-sm font-semibold"
            style={{ color: 'var(--color-bear)' }}
          >
            FAILED TO LOAD DEBATE
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {error}
          </span>
          <Button variant="secondary" onClick={handleRetry}>
            Retry
          </Button>
        </div>
      )}

      {/* Polling indicator */}
      {isPolling && (
        <div
          className="mb-3 flex items-center gap-2 border px-3 py-2"
          style={{
            backgroundColor: 'var(--color-bg-card)',
            borderColor: 'var(--color-interactive)',
          }}
          data-testid="debate-polling"
        >
          <Spinner size="sm" />
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            Debate in progress... agents are analyzing
            {debate.ticker ? ` ${debate.ticker}` : ''}
          </span>
        </div>
      )}

      {/* Main debate content */}
      {debate && (
        <div className="flex flex-col gap-4">
          {/* Header row with ticker and meter */}
          {debate.thesis && (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
              <div className="lg:col-span-3">
                <DebateView debate={debate} />
              </div>
              <div
                className="flex flex-col border p-3"
                style={{
                  backgroundColor: 'var(--color-bg-card)',
                  borderColor: 'var(--color-border-default)',
                }}
              >
                <span
                  className="font-data mb-2 text-xs font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  Sentiment Gauge
                </span>
                <BullBearMeter
                  direction={debate.thesis.direction}
                  conviction={debate.thesis.conviction}
                />
              </div>
            </div>
          )}

          {/* Trade thesis section */}
          {debate.thesis && (
            <TradeThesisSection thesis={debate.thesis} />
          )}

          {/* No thesis yet (still pending/running or failed) */}
          {!debate.thesis && debate.status === 'failed' && (
            <div
              className="flex flex-col items-center gap-3 border py-12"
              style={{
                backgroundColor: 'var(--color-bg-card)',
                borderColor: 'var(--color-bear)',
              }}
            >
              <span
                className="font-data text-sm font-semibold"
                style={{ color: 'var(--color-bear)' }}
              >
                DEBATE FAILED
              </span>
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                The AI debate could not be completed. This may happen when Ollama
                is unreachable and the data-driven fallback also fails.
              </span>
            </div>
          )}

          {!debate.thesis &&
            debate.status !== 'failed' &&
            !isPolling && (
              <DebateView debate={debate} />
            )}
        </div>
      )}
    </PageShell>
  )
}
