import { useParams } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function ScanDetail() {
  const { id } = useParams<{ id: string }>()

  return (
    <PageShell title={`Scan #${id ?? '—'}`}>
      <Card title="Scan Detail">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Details for scan {id} will appear here.
        </p>
      </Card>
    </PageShell>
  )
}
