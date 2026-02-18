import { useParams } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function TickerDeepDive() {
  const { symbol } = useParams<{ symbol: string }>()

  return (
    <PageShell title={`Ticker: ${symbol?.toUpperCase() ?? '—'}`}>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Card title="Price & Indicators">
          <p
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Technical indicators and price chart for {symbol?.toUpperCase()}.
          </p>
        </Card>
        <Card title="Options Chain">
          <p
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Options chain data will appear here.
          </p>
        </Card>
      </div>
    </PageShell>
  )
}
