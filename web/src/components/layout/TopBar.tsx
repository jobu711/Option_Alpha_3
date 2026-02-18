interface TopBarProps {
  title: string
  status?: 'connected' | 'disconnected' | 'degraded'
}

const STATUS_STYLES: Record<
  string,
  { color: string; label: string }
> = {
  connected: { color: 'var(--color-bull)', label: 'CONNECTED' },
  disconnected: { color: 'var(--color-bear)', label: 'DISCONNECTED' },
  degraded: { color: 'var(--color-risk)', label: 'DEGRADED' },
}

export function TopBar({ title, status = 'connected' }: TopBarProps) {
  const statusInfo = STATUS_STYLES[status]

  return (
    <header
      className="flex items-center justify-between border-b px-4 py-2"
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border-default)',
      }}
    >
      <h1
        className="font-data text-sm font-semibold uppercase tracking-wide"
        style={{ color: 'var(--color-text-primary)' }}
      >
        {title}
      </h1>

      <div className="flex items-center gap-2">
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: statusInfo.color }}
        />
        <span
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {statusInfo.label}
        </span>
      </div>
    </header>
  )
}
