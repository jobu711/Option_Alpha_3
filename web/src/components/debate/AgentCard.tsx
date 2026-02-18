import type { AgentResponse } from '../../types/debate'

type AgentRole = 'bull' | 'bear' | 'risk'

interface AgentCardProps {
  role: AgentRole
  response: AgentResponse | null
  isWinner?: boolean
  className?: string
}

const ROLE_CONFIG: Record<
  AgentRole,
  { color: string; mutedBg: string; label: string; icon: string }
> = {
  bull: {
    color: 'var(--color-bull)',
    mutedBg: 'var(--color-bull-muted)',
    label: 'BULL',
    icon: '\u25B2', // upward triangle
  },
  bear: {
    color: 'var(--color-bear)',
    mutedBg: 'var(--color-bear-muted)',
    label: 'BEAR',
    icon: '\u25BC', // downward triangle
  },
  risk: {
    color: 'var(--color-risk)',
    mutedBg: 'var(--color-risk-muted)',
    label: 'RISK',
    icon: '\u26A0', // warning triangle
  },
}

function ConvictionBar({
  conviction,
  color,
}: {
  conviction: number
  color: string
}) {
  const pct = Math.round(conviction * 100)
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 flex-1"
        style={{ backgroundColor: 'var(--color-bg-primary)' }}
      >
        <div
          className="h-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            backgroundColor: color,
          }}
          data-testid="conviction-bar-fill"
        />
      </div>
      <span
        className="font-data text-xs font-bold tabular-nums"
        style={{ color, minWidth: '2.5rem', textAlign: 'right' }}
      >
        {pct}%
      </span>
    </div>
  )
}

function GreeksDisplay({
  greeks,
  color,
}: {
  greeks: AgentResponse['greeks_cited']
  color: string
}) {
  const entries = Object.entries(greeks).filter(
    ([, val]) => val !== null && val !== undefined,
  )

  if (entries.length === 0) return null

  return (
    <div className="mt-3">
      <span
        className="font-data text-xs font-semibold uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Greeks Cited
      </span>
      <div className="mt-1 flex flex-wrap gap-2">
        {entries.map(([key, val]) => (
          <span
            key={key}
            className="font-data border px-1.5 py-0.5 text-xs"
            style={{
              borderColor: 'var(--color-border-default)',
              color,
            }}
          >
            {key}: {typeof val === 'number' ? val.toFixed(3) : String(val)}
          </span>
        ))}
      </div>
    </div>
  )
}

export function AgentCard({
  role,
  response,
  isWinner = false,
  className = '',
}: AgentCardProps) {
  const config = ROLE_CONFIG[role]

  if (!response) {
    return (
      <div
        className={`flex flex-col border ${className}`}
        style={{
          backgroundColor: 'var(--color-bg-card)',
          borderColor: 'var(--color-border-default)',
        }}
        data-testid={`agent-card-${role}`}
      >
        <div
          className="border-b px-3 py-2"
          style={{ borderColor: 'var(--color-border-default)' }}
        >
          <div className="flex items-center gap-2">
            <span style={{ color: config.color }}>{config.icon}</span>
            <span
              className="font-data text-xs font-bold uppercase tracking-wider"
              style={{ color: config.color }}
            >
              {config.label}
            </span>
          </div>
        </div>
        <div className="flex flex-1 items-center justify-center p-6">
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Awaiting analysis...
          </span>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`flex flex-col border ${className}`}
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderColor: isWinner ? config.color : 'var(--color-border-default)',
        boxShadow: isWinner ? `0 0 12px ${config.color}33` : 'none',
      }}
      data-testid={`agent-card-${role}`}
    >
      {/* Header with role badge */}
      <div
        className="border-b px-3 py-2"
        style={{
          borderColor: isWinner
            ? config.color
            : 'var(--color-border-default)',
          backgroundColor: isWinner ? `${config.mutedBg}` : 'transparent',
        }}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span style={{ color: config.color }}>{config.icon}</span>
            <span
              className="font-data text-xs font-bold uppercase tracking-wider"
              style={{ color: config.color }}
              data-testid={`agent-role-${role}`}
            >
              {config.label}
            </span>
            {isWinner && (
              <span
                className="font-data px-1.5 py-0.5 text-xs font-semibold uppercase"
                style={{
                  backgroundColor: config.color,
                  color: role === 'risk' ? '#0A0E17' : '#FFFFFF',
                }}
              >
                Winner
              </span>
            )}
          </div>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {response.model_used}
          </span>
        </div>
      </div>

      {/* Conviction score */}
      <div className="px-3 pt-2">
        <span
          className="font-data text-xs font-semibold uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Conviction
        </span>
        <div className="mt-1">
          <ConvictionBar conviction={response.conviction} color={config.color} />
        </div>
      </div>

      {/* Analysis text */}
      <div className="flex-1 px-3 py-2">
        <div
          className="text-xs leading-relaxed whitespace-pre-wrap"
          style={{ color: 'var(--color-text-primary)' }}
          data-testid={`agent-analysis-${role}`}
        >
          {response.analysis}
        </div>
      </div>

      {/* Key points */}
      {response.key_points.length > 0 && (
        <div className="border-t px-3 py-2" style={{ borderColor: 'var(--color-border-subtle)' }}>
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Key Points
          </span>
          <ul className="mt-1 space-y-0.5">
            {response.key_points.map((point, i) => (
              <li
                key={i}
                className="flex items-start gap-1.5 text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                <span style={{ color: config.color }} className="mt-0.5 shrink-0">
                  {'\u2022'}
                </span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Contracts referenced */}
      {response.contracts_referenced.length > 0 && (
        <div className="border-t px-3 py-2" style={{ borderColor: 'var(--color-border-subtle)' }}>
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Contracts
          </span>
          <div className="mt-1 flex flex-wrap gap-1">
            {response.contracts_referenced.map((contract, i) => (
              <span
                key={i}
                className="font-data border px-1.5 py-0.5 text-xs"
                style={{
                  borderColor: 'var(--color-border-default)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                {contract}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Greeks cited */}
      <div className="border-t px-3 py-2" style={{ borderColor: 'var(--color-border-subtle)' }}>
        <GreeksDisplay greeks={response.greeks_cited} color={config.color} />
      </div>

      {/* Token usage footer */}
      <div
        className="border-t px-3 py-1.5"
        style={{
          borderColor: 'var(--color-border-subtle)',
          backgroundColor: 'var(--color-bg-secondary)',
        }}
      >
        <div className="flex justify-between">
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Tokens: {response.input_tokens + response.output_tokens}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            In: {response.input_tokens} / Out: {response.output_tokens}
          </span>
        </div>
      </div>
    </div>
  )
}
