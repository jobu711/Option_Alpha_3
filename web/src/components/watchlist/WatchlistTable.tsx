import { useNavigate } from 'react-router-dom'
import { Button } from '../common'

interface WatchlistTableProps {
  tickers: string[]
  onRemove: (ticker: string) => void
  removing: string | null
}

export function WatchlistTable({ tickers, onRemove, removing }: WatchlistTableProps) {
  const navigate = useNavigate()

  if (tickers.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-8">
        <span
          className="font-data text-sm font-semibold"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          EMPTY WATCHLIST
        </span>
        <span
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Add tickers to track their options activity.
        </span>
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse" data-testid="watchlist-table">
        <thead>
          <tr>
            <th
              className="font-data border-b px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wider"
              style={{
                borderColor: 'var(--color-border-default)',
                color: 'var(--color-text-secondary)',
                backgroundColor: 'var(--color-bg-secondary)',
              }}
            >
              Ticker
            </th>
            <th
              className="font-data border-b px-2 py-1.5 text-right text-xs font-semibold uppercase tracking-wider"
              style={{
                borderColor: 'var(--color-border-default)',
                color: 'var(--color-text-secondary)',
                backgroundColor: 'var(--color-bg-secondary)',
              }}
            >
              Actions
            </th>
          </tr>
        </thead>
        <tbody>
          {tickers.map((ticker) => (
            <tr
              key={ticker}
              className="cursor-pointer transition-colors"
              style={{ backgroundColor: 'transparent' }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = 'transparent')
              }
              onClick={() => navigate(`/ticker/${ticker}`)}
            >
              <td
                className="font-data border-b px-2 py-1.5 text-xs font-semibold"
                style={{
                  borderColor: 'var(--color-border-subtle)',
                  color: 'var(--color-text-accent)',
                }}
              >
                {ticker}
              </td>
              <td
                className="border-b px-2 py-1.5 text-right"
                style={{ borderColor: 'var(--color-border-subtle)' }}
              >
                <Button
                  variant="danger"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRemove(ticker)
                  }}
                  disabled={removing === ticker}
                >
                  {removing === ticker ? 'REMOVING...' : 'REMOVE'}
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
