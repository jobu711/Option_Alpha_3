import { useSSE } from '../../hooks/useSSE'
import { Card } from '../common'

interface ScanProgressEvent {
  phase: string
  current: number
  total: number
  pct: number
}

interface ScanProgressProps {
  scanId: string
}

const PHASE_LABELS: Record<string, string> = {
  fetch_prices: 'Fetching Prices',
  compute_indicators: 'Computing Indicators',
  scoring: 'Scoring Universe',
  catalysts: 'Catalyst Analysis',
  persisting: 'Persisting Results',
  complete: 'Complete',
}

function getPhaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase
}

export function ScanProgress({ scanId }: ScanProgressProps) {
  const { data, connected, error } = useSSE<ScanProgressEvent>(
    `/scan/${scanId}/stream`,
  )

  const isComplete = data?.phase === 'complete'
  const pct = data?.pct ?? 0
  const phase = data?.phase ?? 'initializing'
  const current = data?.current ?? 0
  const total = data?.total ?? 0

  if (isComplete) {
    return null
  }

  return (
    <Card title="Scan Progress">
      <div className="flex flex-col gap-2">
        {/* Phase label and counter */}
        <div className="flex items-center justify-between">
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-accent)' }}
          >
            {getPhaseLabel(phase)}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {total > 0 ? `${current} / ${total}` : '...'}
          </span>
        </div>

        {/* Progress bar */}
        <div
          className="h-1.5 w-full overflow-hidden"
          style={{ backgroundColor: 'var(--color-bg-elevated)' }}
          role="progressbar"
          aria-valuenow={Math.round(pct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Scan progress: ${Math.round(pct)}%`}
        >
          <div
            className="h-full transition-all duration-300"
            style={{
              width: `${Math.min(pct, 100)}%`,
              backgroundColor: 'var(--color-interactive)',
            }}
          />
        </div>

        {/* Percentage and status */}
        <div className="flex items-center justify-between">
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {Math.round(pct)}%
          </span>
          {error && (
            <span
              className="font-data text-xs"
              style={{ color: 'var(--color-bear)' }}
            >
              {error}
            </span>
          )}
          {!error && !connected && !isComplete && (
            <span
              className="font-data text-xs"
              style={{ color: 'var(--color-risk)' }}
            >
              Connecting...
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}
