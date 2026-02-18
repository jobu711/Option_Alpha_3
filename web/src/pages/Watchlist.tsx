import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Button, Card, Spinner } from '../components/common'
import { WatchlistTable, AddTickerModal } from '../components/watchlist'
import { api } from '../api/client'
import type { WatchlistResponse } from '../api/client'

export function Watchlist() {
  const navigate = useNavigate()
  const [watchlistData, setWatchlistData] = useState<WatchlistResponse | null>(
    null,
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'Watchlist | Option Alpha'
    return () => {
      document.title = 'Option Alpha'
    }
  }, [])

  const fetchWatchlist = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.watchlist.list()
      setWatchlistData(data)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load watchlist'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchWatchlist()
  }, [fetchWatchlist])

  const handleAdd = useCallback(
    async (ticker: string) => {
      await api.watchlist.add(ticker)
      await fetchWatchlist()
    },
    [fetchWatchlist],
  )

  const handleRemove = useCallback(
    async (ticker: string) => {
      setRemoving(ticker)
      try {
        await api.watchlist.remove(ticker)
        await fetchWatchlist()
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'Failed to remove ticker'
        setError(message)
      } finally {
        setRemoving(null)
      }
    },
    [fetchWatchlist],
  )

  const handleScanWatchlist = useCallback(async () => {
    if (!watchlistData || watchlistData.tickers.length === 0) return

    try {
      const result = await api.scan.start({
        tickers: watchlistData.tickers,
        top_n: watchlistData.tickers.length,
      })
      navigate(`/scan`)
      // Scan started, result contains the scan run data
      void result
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to start scan'
      setError(message)
    }
  }, [watchlistData, navigate])

  const tickers = watchlistData?.tickers ?? []

  return (
    <PageShell title="Watchlist">
      <div className="flex flex-col gap-3">
        {/* Actions bar */}
        <Card>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <AddTickerModal onAdd={handleAdd} disabled={loading} />
            <Button
              variant="primary"
              onClick={() => void handleScanWatchlist()}
              disabled={tickers.length === 0}
            >
              SCAN WATCHLIST
            </Button>
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
              <Button variant="secondary" onClick={() => setError(null)}>
                DISMISS
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
                Loading watchlist...
              </span>
            </div>
          </Card>
        )}

        {/* Watchlist table */}
        {!loading && (
          <Card title={`Watched Tickers (${tickers.length})`}>
            <WatchlistTable
              tickers={tickers}
              onRemove={(t) => void handleRemove(t)}
              removing={removing}
            />
          </Card>
        )}
      </div>
    </PageShell>
  )
}
