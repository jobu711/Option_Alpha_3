import type { TradeThesis } from '../../types/debate'
import { Card } from '../common'

interface TradeThesisSectionProps {
  thesis: TradeThesis
  className?: string
}

function DirectionIndicator({ direction }: { direction: string }) {
  const color =
    direction === 'bullish'
      ? 'var(--color-bull)'
      : direction === 'bearish'
        ? 'var(--color-bear)'
        : 'var(--color-risk)'

  return (
    <span
      className="font-data text-xs font-bold uppercase"
      style={{ color }}
    >
      {direction}
    </span>
  )
}

function MetricRow({
  label,
  value,
  valueColor,
}: {
  label: string
  value: string
  valueColor?: string
}) {
  return (
    <div className="flex items-baseline justify-between border-b py-1.5" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <span
        className="font-data text-xs font-semibold uppercase tracking-wider"
        style={{ color: 'var(--color-text-muted)' }}
      >
        {label}
      </span>
      <span
        className="font-data text-xs font-medium"
        style={{ color: valueColor ?? 'var(--color-text-primary)' }}
      >
        {value}
      </span>
    </div>
  )
}

export function TradeThesisSection({
  thesis,
  className = '',
}: TradeThesisSectionProps) {
  const convictionPct = Math.round(thesis.conviction * 100)
  const durationSec = (thesis.duration_ms / 1000).toFixed(1)

  return (
    <div className={`grid grid-cols-1 gap-3 lg:grid-cols-2 ${className}`} data-testid="trade-thesis">
      {/* Left column: Direction & Action */}
      <Card title="Trade Thesis">
        <MetricRow
          label="Direction"
          value={thesis.direction.toUpperCase()}
          valueColor={
            thesis.direction === 'bullish'
              ? 'var(--color-bull)'
              : thesis.direction === 'bearish'
                ? 'var(--color-bear)'
                : 'var(--color-risk)'
          }
        />
        <MetricRow label="Conviction" value={`${convictionPct}%`} />
        <MetricRow label="Model" value={thesis.model_used} />
        <MetricRow label="Tokens" value={thesis.total_tokens.toLocaleString()} />
        <MetricRow label="Duration" value={`${durationSec}s`} />

        <div className="mt-3">
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Recommended Action
          </span>
          <p
            className="mt-1 text-xs leading-relaxed"
            style={{ color: 'var(--color-text-primary)' }}
            data-testid="recommended-action"
          >
            {thesis.recommended_action}
          </p>
        </div>

        <div className="mt-3">
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Entry Rationale
          </span>
          <p
            className="mt-1 text-xs leading-relaxed whitespace-pre-wrap"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {thesis.entry_rationale}
          </p>
        </div>
      </Card>

      {/* Right column: Risk & Summaries */}
      <div className="flex flex-col gap-3">
        <Card title="Risk Factors">
          {thesis.risk_factors.length > 0 ? (
            <ul className="space-y-1">
              {thesis.risk_factors.map((factor, i) => (
                <li
                  key={i}
                  className="flex items-start gap-1.5 text-xs"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  <span
                    className="mt-0.5 shrink-0"
                    style={{ color: 'var(--color-bear)' }}
                  >
                    {'\u2022'}
                  </span>
                  {factor}
                </li>
              ))}
            </ul>
          ) : (
            <span
              className="font-data text-xs"
              style={{ color: 'var(--color-text-muted)' }}
            >
              No risk factors identified
            </span>
          )}
        </Card>

        <Card title="Agent Summaries">
          <div className="space-y-2">
            <div>
              <div className="flex items-center gap-1.5">
                <DirectionIndicator direction="bullish" />
                <span
                  className="font-data text-xs font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Bull Case
                </span>
              </div>
              <p
                className="mt-0.5 text-xs leading-relaxed"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {thesis.bull_summary}
              </p>
            </div>
            <div
              className="border-t pt-2"
              style={{ borderColor: 'var(--color-border-subtle)' }}
            >
              <div className="flex items-center gap-1.5">
                <DirectionIndicator direction="bearish" />
                <span
                  className="font-data text-xs font-semibold uppercase tracking-wider"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Bear Case
                </span>
              </div>
              <p
                className="mt-0.5 text-xs leading-relaxed"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                {thesis.bear_summary}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Disclaimer — full width */}
      {thesis.disclaimer && (
        <div
          className="col-span-1 border-t pt-2 lg:col-span-2"
          style={{ borderColor: 'var(--color-border-subtle)' }}
        >
          <span
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Disclaimer
          </span>
          <p
            className="mt-1 text-xs leading-relaxed"
            style={{ color: 'var(--color-text-muted)' }}
            data-testid="disclaimer"
          >
            {thesis.disclaimer}
          </p>
        </div>
      )}
    </div>
  )
}
