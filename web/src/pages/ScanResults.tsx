import { useState, useCallback, useEffect, useRef } from 'react'
import { PageShell } from '../components/layout'
import { Button, Card, Spinner } from '../components/common'
import {
  ScanConfig,
  ScanProgress,
  ScanTable,
  type ScanConfigValues,
  type TickerScoreRow,
} from '../components/scan'
import { useApi } from '../hooks/useApi'
import { useSSE } from '../hooks/useSSE'
import { api } from '../api/client'
import type { ScanRunResponse } from '../api/client'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ScanResults() {
  const [activeScanId, setActiveScanId] = useState<string | null>(null)
  const [scanRunning, setScanRunning] = useState(false)
  const [scores, setScores] = useState<TickerScoreRow[]>([])
  const [loadingResults, setLoadingResults] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedScanId, setSelectedScanId] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'Scan Results | Option Alpha'
    return () => {
      document.title = 'Option Alpha'
    }
  }, [])

  // Fetch recent scan history
  const {
    data: recentScans,
    loading: loadingHistory,
    refetch: refetchHistory,
  } = useApi<ScanRunResponse[]>('/scan')

  // Start a new scan
  const handleStartScan = useCallback(async (config: ScanConfigValues) => {
    setError(null)
    setScanRunning(true)
    setScores([])

    try {
      const body: { top_n: number; tickers?: string[] } = {
        top_n: config.topN,
      }
      if (config.tickers.length > 0) {
        body.tickers = config.tickers
      }

      const result = await api.scan.start(body)
      setActiveScanId(result.id)
      setSelectedScanId(result.id)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to start scan'
      setError(message)
      setScanRunning(false)
    }
  }, [])

  // Poll for results after SSE indicates completion
  const handleScanComplete = useCallback(
    async (scanId: string) => {
      setLoadingResults(true)
      try {
        const result = await api.scan.get(scanId)
        setScores(
          result.scores.map((s) => ({
            ticker: s.ticker,
            score: s.score,
            signals: s.signals,
            rank: s.rank,
          })),
        )
        refetchHistory()
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'Failed to fetch results'
        setError(message)
      } finally {
        setLoadingResults(false)
        setScanRunning(false)
        setActiveScanId(null)
      }
    },
    [refetchHistory],
  )

  // Load a past scan's results
  const handleLoadScan = useCallback(async (scanId: string) => {
    setError(null)
    setLoadingResults(true)
    setSelectedScanId(scanId)
    setScores([])

    try {
      const result = await api.scan.get(scanId)
      setScores(
        result.scores.map((s) => ({
          ticker: s.ticker,
          score: s.score,
          signals: s.signals,
          rank: s.rank,
        })),
      )
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load scan'
      setError(message)
    } finally {
      setLoadingResults(false)
    }
  }, [])

  // Start a debate for a ticker
  const handleDebate = useCallback(async (ticker: string) => {
    try {
      await api.debate.start(ticker)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to start debate'
      setError(message)
    }
  }, [])

  return (
    <PageShell title="Scan Results">
      <div className="flex flex-col gap-3">
        {/* Scan Configuration */}
        <ScanConfig onStartScan={handleStartScan} disabled={scanRunning} />

        {/* Active Scan Progress */}
        {activeScanId && (
          <ScanProgressWithCompletion
            scanId={activeScanId}
            onComplete={() => handleScanComplete(activeScanId)}
          />
        )}

        {/* Error Display */}
        {error && (
          <Card>
            <div className="flex items-center justify-between">
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-bear)' }}
              >
                {error}
              </span>
              <Button variant="secondary" onClick={() => setError(null)}>
                DISMISS
              </Button>
            </div>
          </Card>
        )}

        {/* Main Content Area */}
        <div className="flex gap-3">
          {/* Results Table */}
          <div className="min-w-0 flex-1">
            {loadingResults && (
              <Card>
                <div className="flex items-center justify-center gap-2 py-8">
                  <Spinner size="md" />
                  <span
                    className="font-data text-xs"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    Loading results...
                  </span>
                </div>
              </Card>
            )}

            {!loadingResults && scores.length > 0 && (
              <ScanTable data={scores} onDebate={handleDebate} />
            )}

            {!loadingResults &&
              scores.length === 0 &&
              !scanRunning &&
              !activeScanId && (
                <Card>
                  <div className="flex flex-col items-center gap-3 py-8">
                    <span
                      className="font-data text-sm font-semibold"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      NO SCAN DATA
                    </span>
                    <span
                      className="font-data text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      Run a scan to analyze the option universe and rank tickers
                      by composite score.
                    </span>
                  </div>
                </Card>
              )}
          </div>

          {/* Recent Scans Sidebar */}
          <div className="w-56 shrink-0">
            <Card title="Recent Scans">
              {loadingHistory && (
                <div className="flex justify-center py-4">
                  <Spinner size="sm" />
                </div>
              )}
              {!loadingHistory &&
                (!recentScans || recentScans.length === 0) && (
                  <span
                    className="font-data text-xs"
                    style={{ color: 'var(--color-text-muted)' }}
                  >
                    No scan history yet.
                  </span>
                )}
              {!loadingHistory && recentScans && recentScans.length > 0 && (
                <div className="flex flex-col gap-1">
                  {recentScans.slice(0, 10).map((scan) => (
                    <button
                      key={scan.id}
                      onClick={() => handleLoadScan(scan.id)}
                      className="flex cursor-pointer flex-col border px-2 py-1.5 text-left transition-colors"
                      style={{
                        backgroundColor:
                          selectedScanId === scan.id
                            ? 'var(--color-bg-hover)'
                            : 'transparent',
                        borderColor:
                          selectedScanId === scan.id
                            ? 'var(--color-border-strong)'
                            : 'var(--color-border-subtle)',
                      }}
                    >
                      <span
                        className="font-data text-xs font-semibold"
                        style={{
                          color:
                            scan.status === 'completed'
                              ? 'var(--color-bull)'
                              : scan.status === 'failed'
                                ? 'var(--color-bear)'
                                : 'var(--color-risk)',
                        }}
                      >
                        {scan.status.toUpperCase()}
                      </span>
                      <span
                        className="font-data text-xs"
                        style={{ color: 'var(--color-text-muted)' }}
                      >
                        {scan.ticker_count} tickers &middot;{' '}
                        {new Date(scan.started_at).toLocaleDateString()}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>
      </div>
    </PageShell>
  )
}

// ---------------------------------------------------------------------------
// ScanProgressWithCompletion — wraps ScanProgress and detects completion
// ---------------------------------------------------------------------------

interface ScanProgressWithCompletionProps {
  scanId: string
  onComplete: () => void
}

function ScanProgressWithCompletion({
  scanId,
  onComplete,
}: ScanProgressWithCompletionProps) {
  const { data } = useSSEWithCompletion(scanId, onComplete)

  // If SSE data shows complete, the onComplete callback has already been called
  if (data?.phase === 'complete') {
    return null
  }

  return <ScanProgress scanId={scanId} />
}

// ---------------------------------------------------------------------------
// useSSEWithCompletion — hook that calls onComplete when scan finishes
// ---------------------------------------------------------------------------

interface SSEProgressData {
  phase: string
  current: number
  total: number
  pct: number
}

function useSSEWithCompletion(
  scanId: string,
  onComplete: () => void,
): { data: SSEProgressData | null } {
  const { data } = useSSE<SSEProgressData>(`/scan/${scanId}/stream`)
  const calledRef = useRef(false)

  useEffect(() => {
    if (data?.phase === 'complete' && !calledRef.current) {
      calledRef.current = true
      onComplete()
    }
  }, [data, onComplete])

  return { data }
}
