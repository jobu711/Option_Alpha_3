import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function Universe() {
  return (
    <PageShell title="Universe">
      <Card title="Optionable Universe">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          The optionable ticker universe sourced from CBOE. Refresh to update
          the list.
        </p>
      </Card>
    </PageShell>
  )
}
