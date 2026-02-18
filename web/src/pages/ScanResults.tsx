import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function ScanResults() {
  return (
    <PageShell title="Scan Results">
      <Card title="Scans">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Run a scan to see results. The scan pipeline will analyze the option
          universe and rank tickers by composite score.
        </p>
      </Card>
    </PageShell>
  )
}
