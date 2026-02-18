import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function Watchlist() {
  return (
    <PageShell title="Watchlist">
      <Card title="Watched Tickers">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Your watchlist is empty. Add tickers to track their options activity.
        </p>
      </Card>
    </PageShell>
  )
}
