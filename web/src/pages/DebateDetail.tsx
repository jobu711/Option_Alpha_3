import { useParams } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function DebateDetail() {
  const { id } = useParams<{ id: string }>()

  return (
    <PageShell title={`Debate #${id ?? '—'}`}>
      <Card title="Debate">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          AI debate details for debate {id} will appear here. The Bull, Bear,
          and Risk agents will present their analysis.
        </p>
      </Card>
    </PageShell>
  )
}
