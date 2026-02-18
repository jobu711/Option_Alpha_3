import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function Dashboard() {
  return (
    <PageShell title="Dashboard">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <Card title="Market Overview">
          <p
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Market data will appear here once the backend is connected.
          </p>
        </Card>
        <Card title="Recent Scans">
          <p
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            No recent scans.
          </p>
        </Card>
        <Card title="Watchlist">
          <p
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            No watchlist items.
          </p>
        </Card>
      </div>
    </PageShell>
  )
}
