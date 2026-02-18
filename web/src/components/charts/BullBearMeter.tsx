import type { SignalDirection } from '../../types/debate'

interface BullBearMeterProps {
  direction: SignalDirection
  conviction: number
  className?: string
}

/**
 * Gauge visualization for bull vs bear conviction.
 *
 * Uses a pure CSS/SVG approach for the gauge rather than pulling in Plotly
 * for a single gauge — keeps the component lightweight and avoids bundle bloat.
 * The gauge renders a semicircular arc with a needle pointing to the
 * conviction position on a bearish-to-bullish scale.
 */
export function BullBearMeter({
  direction,
  conviction,
  className = '',
}: BullBearMeterProps) {
  // Convert direction + conviction to a 0-100 scale position
  // 0 = strongly bearish, 50 = neutral, 100 = strongly bullish
  let position: number
  if (direction === 'bullish') {
    position = 50 + conviction * 50
  } else if (direction === 'bearish') {
    position = 50 - conviction * 50
  } else {
    position = 50
  }

  // Needle angle: -90deg (far left/bearish) to +90deg (far right/bullish)
  const needleAngle = (position / 100) * 180 - 90

  // Color for the current position
  const positionColor =
    position > 60
      ? 'var(--color-bull)'
      : position < 40
        ? 'var(--color-bear)'
        : 'var(--color-risk)'

  const convictionPct = Math.round(conviction * 100)

  return (
    <div
      className={`flex flex-col items-center ${className}`}
      style={{ backgroundColor: 'var(--color-bg-card)' }}
      data-testid="bull-bear-meter"
    >
      {/* SVG Gauge */}
      <svg
        viewBox="0 0 200 120"
        className="w-full max-w-xs"
        role="img"
        aria-label={`Bull Bear Meter: ${direction} with ${convictionPct}% conviction`}
      >
        {/* Background arc segments */}
        {/* Bearish zone (red) */}
        <path
          d="M 20 100 A 80 80 0 0 1 60 30"
          fill="none"
          stroke="var(--color-bear)"
          strokeWidth="8"
          strokeLinecap="round"
          opacity="0.3"
        />
        {/* Slightly bearish zone */}
        <path
          d="M 60 30 A 80 80 0 0 1 85 22"
          fill="none"
          stroke="var(--color-bear)"
          strokeWidth="8"
          strokeLinecap="round"
          opacity="0.15"
        />
        {/* Neutral zone (yellow) */}
        <path
          d="M 85 22 A 80 80 0 0 1 115 22"
          fill="none"
          stroke="var(--color-risk)"
          strokeWidth="8"
          strokeLinecap="round"
          opacity="0.3"
        />
        {/* Slightly bullish zone */}
        <path
          d="M 115 22 A 80 80 0 0 1 140 30"
          fill="none"
          stroke="var(--color-bull)"
          strokeWidth="8"
          strokeLinecap="round"
          opacity="0.15"
        />
        {/* Bullish zone (green) */}
        <path
          d="M 140 30 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="var(--color-bull)"
          strokeWidth="8"
          strokeLinecap="round"
          opacity="0.3"
        />

        {/* Needle */}
        <g transform={`rotate(${needleAngle}, 100, 100)`}>
          <line
            x1="100"
            y1="100"
            x2="100"
            y2="30"
            stroke={positionColor}
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          {/* Needle tip */}
          <circle cx="100" cy="30" r="3" fill={positionColor} />
        </g>

        {/* Center dot */}
        <circle
          cx="100"
          cy="100"
          r="5"
          fill="var(--color-bg-elevated)"
          stroke={positionColor}
          strokeWidth="2"
        />

        {/* Labels */}
        <text
          x="15"
          y="115"
          fill="var(--color-bear)"
          fontSize="8"
          fontFamily="var(--font-mono)"
          fontWeight="600"
        >
          BEAR
        </text>
        <text
          x="160"
          y="115"
          fill="var(--color-bull)"
          fontSize="8"
          fontFamily="var(--font-mono)"
          fontWeight="600"
        >
          BULL
        </text>
      </svg>

      {/* Score label */}
      <div className="flex flex-col items-center -mt-2">
        <span
          className="font-data text-lg font-bold"
          style={{ color: positionColor }}
          data-testid="meter-score"
        >
          {convictionPct}%
        </span>
        <span
          className="font-data text-xs uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          {position >= 70
            ? 'Strongly Bullish'
            : position >= 55
              ? 'Bullish'
              : position >= 45
                ? 'Neutral'
                : position >= 30
                  ? 'Bearish'
                  : 'Strongly Bearish'}
        </span>
      </div>
    </div>
  )
}
