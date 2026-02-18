import { PageShell } from '../components/layout'
import { Card } from '../components/common'

export function Settings() {
  return (
    <PageShell title="Settings">
      <Card title="Configuration">
        <p
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Configure scan parameters, AI model settings, and display preferences.
        </p>
      </Card>
    </PageShell>
  )
}
