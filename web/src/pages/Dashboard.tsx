import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Badge, Button, Card, Spinner } from '../components/common'
import { useApi } from '../hooks/useApi'
import type { ScanRunResponse, HealthStatus, WatchlistResponse } from '../api/client'
import type { TradeThesis } from '../types/debate'
import { toDebateResult } from '../types/debate'

export function Dashboard() {
  const navigate = useNavigate()

  const {
    data: recentScans,
    loading: loadingScans,
    error: scanError,
    refetch: refetchScans,
  } = useApi<ScanRunResponse[]>('/scan')

  const {
    data: health,
    loading: loadingHealth,
    error: healthError,
    refetch: refetchHealth,
  } = useApi<HealthStatus>('/health', { baseUrl: '' })

  const {
    data: rawDebates,
    loading: loadingDebates,
    error: debateError,
    refetch: refetchDebates,
  } = useApi<TradeThesis[]>('/debate')

  const {
    data: watchlistData,
    loading: loadingWatchlist,
    error: watchlistError,
    refetch: refetchWatchlist,
  } = useApi<WatchlistResponse>('/watchlist')

  useEffect(() => {
    document.title = 'Dashboard | Option Alpha'
    return () => {
      document.title = 'Option Alpha'
    }
  }, [])

  const latestScan =
    recentScans && recentScans.length > 0 ? recentScans[0] : null

  // Transform raw TradeThesis objects from the backend into DebateResult UI shapes.
  // Every persisted thesis is completed, so all pass the filter.
  const debates = useMemo(
    () => (rawDebates ? rawDebates.map((t, i) => toDebateResult(t, i)) : []),
    [rawDebates],
  )

  const recentDebates = debates.slice(0, 5)

  const watchlistTickers = watchlistData?.tickers ?? []

  return (
    <PageShell title="Dashboard">
      <div className="flex flex-col gap-3">
        {/* Quick actions bar */}
        <div className="flex items-center gap-2">
          <Button variant="primary" onClick={() => navigate('/scan')}>
            RUN SCAN
          </Button>
          <Button variant="secondary" onClick={() => navigate('/watchlist')}>
            VIEW WATCHLIST
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {/* Latest Scan Summary */}
          <Card title="Latest Scan">
            {loadingScans && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}
            {scanError && (
              <ErrorDisplay message={scanError} onRetry={refetchScans} />
            )}
            {!loadingScans && !scanError && !latestScan && (
              <EmptyState message="No scans yet. Run a scan to analyze the option universe." />
            )}
            {!loadingScans && !scanError && latestScan && (
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span
                    className="font-data text-xs"
                    style={{ color: 'var(--color-text-secondary)' }}
                  >
                    {new Date(latestScan.started_at).toLocaleString()}
                  </span>
                  <Badge
                    variant={
                      latestScan.status === 'completed'
                        ? 'bullish'
                        : latestScan.status === 'failed'
                          ? 'bearish'
                          : 'neutral'
                    }
                  >
                    {latestScan.status.toUpperCase()}
                  </Badge>
                </div>
                <div className="flex gap-4">
                  <DataField label="Tickers" value={String(latestScan.ticker_count)} />
                  <DataField label="Top N" value={String(latestScan.top_n)} />
                  <DataField label="Preset" value={latestScan.preset} />
                </div>
                <Button
                  variant="secondary"
                  onClick={() => navigate('/scan')}
                  className="mt-1 self-start"
                >
                  VIEW RESULTS
                </Button>
              </div>
            )}
          </Card>

          {/* System Health */}
          <Card title="System Health">
            {loadingHealth && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}
            {healthError && (
              <ErrorDisplay message={healthError} onRetry={refetchHealth} />
            )}
            {!loadingHealth && !healthError && health && (
              <div className="flex flex-col gap-1.5">
                <HealthRow label="Ollama" ok={health.ollama_available} />
                <HealthRow label="Anthropic" ok={health.anthropic_available} />
                <HealthRow label="yfinance" ok={health.yfinance_available} />
                <HealthRow label="SQLite" ok={health.sqlite_available} />
                <div
                  className="mt-1 border-t pt-1.5"
                  style={{ borderColor: 'var(--color-border-subtle)' }}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className="font-data text-xs font-semibold"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Overall
                    </span>
                    <Badge
                      variant={
                        health.ollama_available &&
                        health.yfinance_available &&
                        health.sqlite_available
                          ? 'bullish'
                          : 'bearish'
                      }
                    >
                      {health.ollama_available &&
                      health.yfinance_available &&
                      health.sqlite_available
                        ? 'HEALTHY'
                        : 'DEGRADED'}
                    </Badge>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Recent Debates */}
          <Card title="Recent Debates">
            {loadingDebates && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}
            {debateError && (
              <ErrorDisplay message={debateError} onRetry={refetchDebates} />
            )}
            {!loadingDebates && !debateError && rawDebates && recentDebates.length === 0 && (
              <EmptyState message="No completed debates yet." />
            )}
            {!loadingDebates &&
              !debateError &&
              recentDebates.length > 0 && (
                <div className="flex flex-col gap-1">
                  {recentDebates.map((debate) => (
                    <button
                      key={debate.id}
                      onClick={() => navigate(`/debate/${debate.id}`)}
                      className="flex cursor-pointer items-center justify-between border px-2 py-1.5 text-left transition-colors"
                      style={{
                        backgroundColor: 'transparent',
                        borderColor: 'var(--color-border-subtle)',
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.backgroundColor =
                          'var(--color-bg-hover)')
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.backgroundColor = 'transparent')
                      }
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="font-data text-xs font-semibold"
                          style={{ color: 'var(--color-text-primary)' }}
                        >
                          {debate.ticker}
                        </span>
                        {debate.thesis && (
                          <Badge
                            variant={
                              debate.thesis.direction === 'bullish'
                                ? 'bullish'
                                : debate.thesis.direction === 'bearish'
                                  ? 'bearish'
                                  : 'neutral'
                            }
                          >
                            {debate.thesis.direction.toUpperCase()}
                          </Badge>
                        )}
                      </div>
                      {debate.thesis && (
                        <span
                          className="font-data text-xs"
                          style={{ color: 'var(--color-text-muted)' }}
                        >
                          {(debate.thesis.conviction * 100).toFixed(0)}%
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
          </Card>

          {/* Watchlist Quick View */}
          <Card title="Watchlist">
            {loadingWatchlist && (
              <div className="flex justify-center py-4">
                <Spinner size="sm" />
              </div>
            )}
            {watchlistError && (
              <ErrorDisplay message={watchlistError} onRetry={refetchWatchlist} />
            )}
            {!loadingWatchlist &&
              !watchlistError &&
              watchlistTickers.length === 0 && (
                <EmptyState message="Watchlist is empty. Add tickers to track." />
              )}
            {!loadingWatchlist &&
              !watchlistError &&
              watchlistTickers.length > 0 && (
                <div className="flex flex-col gap-1">
                  {watchlistTickers.slice(0, 8).map((ticker) => (
                    <button
                      key={ticker}
                      onClick={() => navigate(`/ticker/${ticker}`)}
                      className="flex cursor-pointer items-center border px-2 py-1.5 text-left transition-colors"
                      style={{
                        backgroundColor: 'transparent',
                        borderColor: 'var(--color-border-subtle)',
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.backgroundColor =
                          'var(--color-bg-hover)')
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.backgroundColor = 'transparent')
                      }
                    >
                      <span
                        className="font-data text-xs font-semibold"
                        style={{ color: 'var(--color-text-accent)' }}
                      >
                        {ticker}
                      </span>
                    </button>
                  ))}
                  {watchlistTickers.length > 8 && (
                    <span
                      className="font-data text-xs"
                      style={{ color: 'var(--color-text-muted)' }}
                    >
                      +{watchlistTickers.length - 8} more
                    </span>
                  )}
                  <Button
                    variant="secondary"
                    onClick={() => navigate('/watchlist')}
                    className="mt-1 self-start"
                  >
                    MANAGE WATCHLIST
                  </Button>
                </div>
              )}
          </Card>
        </div>
      </div>
    </PageShell>
  )
}

// ---------------------------------------------------------------------------
// Internal helper components
// ---------------------------------------------------------------------------

function DataField({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span
        className="font-data text-xs uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </span>
      <span
        className="font-data text-xs font-semibold"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {value}
      </span>
    </div>
  )
}

function HealthRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span
        className="font-data text-xs"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {label}
      </span>
      <span
        className="font-data text-xs font-semibold"
        style={{ color: ok ? 'var(--color-bull)' : 'var(--color-bear)' }}
      >
        {ok ? 'OK' : 'DOWN'}
      </span>
    </div>
  )
}

function ErrorDisplay({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span
        className="font-data text-xs"
        style={{ color: 'var(--color-bear)' }}
      >
        {message}
      </span>
      <Button variant="secondary" onClick={onRetry}>
        RETRY
      </Button>
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <p
      className="font-data text-xs"
      style={{ color: 'var(--color-text-muted)' }}
    >
      {message}
    </p>
  )
}
