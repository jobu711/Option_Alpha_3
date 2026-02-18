import type { SignalDirection } from '../../types/debate'

interface VerdictBadgeProps {
  direction: SignalDirection
  conviction: number
  isFallback?: boolean
  className?: string
}

const DIRECTION_STYLES: Record<
  SignalDirection,
  { bg: string; glow: string; text: string; label: string }
> = {
  bullish: {
    bg: 'var(--color-bull)',
    glow: '0 0 24px rgba(0, 200, 83, 0.3)',
    text: '#FFFFFF',
    label: 'BULLISH',
  },
  bearish: {
    bg: 'var(--color-bear)',
    glow: '0 0 24px rgba(255, 23, 68, 0.3)',
    text: '#FFFFFF',
    label: 'BEARISH',
  },
  neutral: {
    bg: 'var(--color-risk)',
    glow: '0 0 24px rgba(255, 214, 0, 0.3)',
    text: '#0A0E17',
    label: 'NEUTRAL',
  },
}

export function VerdictBadge({
  direction,
  conviction,
  isFallback = false,
  className = '',
}: VerdictBadgeProps) {
  const style = DIRECTION_STYLES[direction]
  const convictionPct = Math.round(conviction * 100)

  return (
    <div
      className={`flex flex-col items-center gap-2 px-6 py-4 ${className}`}
      style={{
        backgroundColor: style.bg,
        boxShadow: style.glow,
      }}
      data-testid="verdict-badge"
    >
      <span
        className="font-data text-2xl font-black tracking-widest"
        style={{ color: style.text }}
        data-testid="verdict-direction"
      >
        {style.label}
      </span>

      <div className="flex items-center gap-3">
        <span
          className="font-data text-sm font-semibold"
          style={{ color: style.text, opacity: 0.9 }}
        >
          CONVICTION
        </span>
        <span
          className="font-data text-xl font-bold"
          style={{ color: style.text }}
          data-testid="verdict-conviction"
        >
          {convictionPct}%
        </span>
      </div>

      {isFallback && (
        <span
          className="font-data mt-1 border px-2 py-0.5 text-xs font-semibold uppercase tracking-wider"
          style={{
            borderColor: style.text,
            color: style.text,
            opacity: 0.8,
          }}
          data-testid="verdict-fallback"
        >
          Data-Driven Fallback
        </span>
      )}
    </div>
  )
}
