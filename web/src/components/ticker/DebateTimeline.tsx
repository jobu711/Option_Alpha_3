/**
 * Debate history timeline for a ticker.
 *
 * Displays a list of past debates showing:
 * - Date of debate
 * - Verdict (BULLISH/BEARISH/NEUTRAL) with color-coded badge
 * - Conviction score
 * - Click navigates to /debate/:id
 *
 * Shows empty state when no debates exist.
 */
import { useNavigate } from 'react-router-dom'
import { Badge } from '../common'
import type { DebateHistoryEntry } from '../../types/ticker'

interface DebateTimelineProps {
  debates: DebateHistoryEntry[]
}

function formatDate(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getVerdictVariant(
  direction: string,
): 'bullish' | 'bearish' | 'neutral' {
  if (direction === 'bullish') return 'bullish'
  if (direction === 'bearish') return 'bearish'
  return 'neutral'
}

function getConvictionBar(conviction: number): string {
  if (conviction >= 0.8) return 'var(--color-bull)'
  if (conviction >= 0.5) return 'var(--color-risk)'
  return 'var(--color-text-muted)'
}

export function DebateTimeline({ debates }: DebateTimelineProps) {
  const navigate = useNavigate()

  if (debates.length === 0) {
    return (
      <div className="flex items-center justify-center py-6">
        <span
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          No debates for this ticker yet
        </span>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1" data-testid="debate-timeline">
      {debates.map((debate) => (
        <button
          key={debate.id}
          onClick={() => navigate(`/debate/${debate.id}`)}
          className="flex w-full cursor-pointer items-center justify-between border-b px-2 py-2 text-left transition-colors"
          style={{
            borderColor: 'var(--color-border-subtle)',
            backgroundColor: 'transparent',
            border: 'none',
            borderBottom: '1px solid var(--color-border-subtle)',
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)')
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.backgroundColor = 'transparent')
          }
        >
          {/* Date */}
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)', minWidth: '150px' }}
          >
            {formatDate(debate.created_at)}
          </span>

          {/* Verdict badge */}
          <Badge variant={getVerdictVariant(debate.direction)}>
            {debate.direction.toUpperCase()}
          </Badge>

          {/* Conviction */}
          <div
            className="flex items-center gap-2"
            style={{ minWidth: '120px' }}
          >
            <div
              className="h-1.5 flex-1 overflow-hidden"
              style={{ backgroundColor: 'var(--color-bg-primary)' }}
            >
              <div
                className="h-full transition-all"
                style={{
                  width: `${debate.conviction * 100}%`,
                  backgroundColor: getConvictionBar(debate.conviction),
                }}
              />
            </div>
            <span
              className="font-data text-xs"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              {(debate.conviction * 100).toFixed(0)}%
            </span>
          </div>
        </button>
      ))}
    </div>
  )
}
