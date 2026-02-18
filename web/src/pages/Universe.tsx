import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Badge, Button, Card, Spinner } from '../components/common'
import { api } from '../api/client'
import type { UniverseListResponse, UniverseTickerInfo } from '../api/client'

const PAGE_SIZE = 50

export function Universe() {
  const navigate = useNavigate()
  const [data, setData] = useState<UniverseListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    document.title = 'Universe | Option Alpha'
    return () => {
      document.title = 'Option Alpha'
    }
  }, [])

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery)
      setOffset(0)
    }, 300)
    return () => clearTimeout(timer)
  }, [searchQuery])

  const fetchUniverse = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.universe.list({
        limit: PAGE_SIZE,
        offset,
        q: debouncedQuery || undefined,
      })
      setData(result)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load universe'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [offset, debouncedQuery])

  useEffect(() => {
    void fetchUniverse()
  }, [fetchUniverse])

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    try {
      await api.universe.refresh()
      // Show success briefly then refetch
      setError(null)
      setTimeout(() => {
        void fetchUniverse()
        setRefreshing(false)
      }, 2000)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to refresh universe'
      setError(message)
      setRefreshing(false)
    }
  }, [fetchUniverse])

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <PageShell title="Universe">
      <div className="flex flex-col gap-3">
        {/* Stats bar */}
        {data && (
          <Card>
            <div className="flex flex-wrap items-center gap-4">
              <StatField label="Total Tickers" value={String(data.stats.total)} />
              <StatField
                label="Last Refresh"
                value={
                  data.stats.last_refresh
                    ? new Date(data.stats.last_refresh).toLocaleDateString()
                    : 'Never'
                }
              />
              <StatField label="Showing" value={`${data.tickers.length} of ${data.total}`} />
              <div className="ml-auto">
                <Button
                  variant="primary"
                  onClick={() => void handleRefresh()}
                  disabled={refreshing}
                >
                  {refreshing ? 'REFRESHING...' : 'REFRESH UNIVERSE'}
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* Refresh accepted notification */}
        {refreshing && (
          <Card>
            <div className="flex items-center gap-2">
              <Spinner size="sm" />
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-risk)' }}
              >
                Universe refresh enqueued (202 Accepted). Refreshing in
                background...
              </span>
            </div>
          </Card>
        )}

        {/* Search bar */}
        <Card>
          <div className="flex items-center gap-2">
            <label
              htmlFor="universe-search"
              className="font-data text-xs uppercase tracking-wider"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Search:
            </label>
            <input
              id="universe-search"
              type="text"
              placeholder="Filter by symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="font-data w-48 border px-2 py-1 text-xs uppercase"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                borderColor: 'var(--color-border-default)',
                color: 'var(--color-text-primary)',
              }}
              maxLength={10}
            />
          </div>
        </Card>

        {/* Error display */}
        {error && (
          <Card>
            <div className="flex items-center justify-between">
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-bear)' }}
              >
                {error}
              </span>
              <Button
                variant="secondary"
                onClick={() => void fetchUniverse()}
              >
                RETRY
              </Button>
            </div>
          </Card>
        )}

        {/* Loading */}
        {loading && (
          <Card>
            <div className="flex items-center justify-center gap-2 py-8">
              <Spinner size="md" />
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Loading universe...
              </span>
            </div>
          </Card>
        )}

        {/* Ticker table */}
        {!loading && data && (
          <Card title="Optionable Universe">
            {data.tickers.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-8">
                <span
                  className="font-data text-sm font-semibold"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  NO TICKERS FOUND
                </span>
                <span
                  className="font-data text-xs"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  {debouncedQuery
                    ? `No results for "${debouncedQuery}".`
                    : 'Refresh the universe to load tickers from CBOE.'}
                </span>
              </div>
            ) : (
              <>
                <UniverseTable
                  tickers={data.tickers}
                  onNavigate={(symbol) => navigate(`/ticker/${symbol}`)}
                />

                {/* Pagination */}
                {totalPages > 1 && (
                  <div
                    className="mt-3 flex items-center justify-between border-t pt-2"
                    style={{ borderColor: 'var(--color-border-subtle)' }}
                  >
                    <Button
                      variant="secondary"
                      onClick={() =>
                        setOffset(Math.max(0, offset - PAGE_SIZE))
                      }
                      disabled={offset === 0}
                    >
                      PREV
                    </Button>
                    <span
                      className="font-data text-xs"
                      style={{ color: 'var(--color-text-secondary)' }}
                    >
                      Page {currentPage} of {totalPages}
                    </span>
                    <Button
                      variant="secondary"
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                      disabled={offset + PAGE_SIZE >= data.total}
                    >
                      NEXT
                    </Button>
                  </div>
                )}
              </>
            )}
          </Card>
        )}
      </div>
    </PageShell>
  )
}

// ---------------------------------------------------------------------------
// Internal components
// ---------------------------------------------------------------------------

function StatField({ label, value }: { label: string; value: string }) {
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

function UniverseTable({
  tickers,
  onNavigate,
}: {
  tickers: UniverseTickerInfo[]
  onNavigate: (symbol: string) => void
}) {
  return (
    <div className="overflow-auto">
      <table
        className="w-full border-collapse"
        data-testid="universe-table"
      >
        <thead>
          <tr>
            {['Symbol', 'Name', 'Sector', 'Cap Tier', 'Status'].map(
              (header) => (
                <th
                  key={header}
                  className="font-data border-b px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wider"
                  style={{
                    borderColor: 'var(--color-border-default)',
                    color: 'var(--color-text-secondary)',
                    backgroundColor: 'var(--color-bg-secondary)',
                  }}
                >
                  {header}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => (
            <tr
              key={ticker.symbol}
              className="cursor-pointer transition-colors"
              style={{ backgroundColor: 'transparent' }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = 'transparent')
              }
              onClick={() => onNavigate(ticker.symbol)}
            >
              <td
                className="font-data border-b px-2 py-1 text-xs font-semibold"
                style={{
                  borderColor: 'var(--color-border-subtle)',
                  color: 'var(--color-text-accent)',
                }}
              >
                {ticker.symbol}
              </td>
              <td
                className="font-data border-b px-2 py-1 text-xs"
                style={{
                  borderColor: 'var(--color-border-subtle)',
                  color: 'var(--color-text-primary)',
                }}
              >
                {ticker.name}
              </td>
              <td
                className="font-data border-b px-2 py-1 text-xs"
                style={{
                  borderColor: 'var(--color-border-subtle)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {ticker.sector}
              </td>
              <td
                className="border-b px-2 py-1"
                style={{ borderColor: 'var(--color-border-subtle)' }}
              >
                <Badge variant="info">{ticker.market_cap_tier}</Badge>
              </td>
              <td
                className="border-b px-2 py-1"
                style={{ borderColor: 'var(--color-border-subtle)' }}
              >
                <Badge
                  variant={
                    ticker.status === 'active' ? 'bullish' : 'neutral'
                  }
                >
                  {ticker.status.toUpperCase()}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
