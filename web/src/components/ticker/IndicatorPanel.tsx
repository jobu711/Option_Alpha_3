/**
 * Technical indicator values panel.
 *
 * Displays all computed indicator values in a structured grid,
 * grouped by category: Momentum, Trend, Volatility, Volume.
 * Null values show as "N/A".
 */
import { Card } from '../common'
import type { IndicatorValues } from '../../types/ticker'

interface IndicatorPanelProps {
  indicators: IndicatorValues
}

interface IndicatorItem {
  label: string
  value: number | null
  format: (v: number) => string
}

function formatPercent(v: number): string {
  return `${v.toFixed(1)}%`
}

function formatDecimal(v: number): string {
  return v.toFixed(4)
}

function formatFloat(v: number): string {
  return v.toFixed(2)
}

function getIndicatorColor(label: string, value: number): string {
  // RSI-based coloring
  if (label === 'RSI' || label === 'Stoch RSI') {
    if (value >= 70) return 'var(--color-bear)'
    if (value <= 30) return 'var(--color-bull)'
    return 'var(--color-text-primary)'
  }
  // Williams %R (inverted scale, -100 to 0)
  if (label === 'Williams %R') {
    if (value >= -20) return 'var(--color-bear)'
    if (value <= -80) return 'var(--color-bull)'
    return 'var(--color-text-primary)'
  }
  // ADX
  if (label === 'ADX') {
    if (value >= 25) return 'var(--color-bull)'
    return 'var(--color-text-muted)'
  }
  return 'var(--color-text-primary)'
}

function buildGroups(
  indicators: IndicatorValues,
): Record<string, IndicatorItem[]> {
  return {
    Momentum: [
      { label: 'RSI', value: indicators.rsi, format: formatFloat },
      { label: 'Stoch RSI', value: indicators.stoch_rsi, format: formatFloat },
      {
        label: 'Williams %R',
        value: indicators.williams_r,
        format: formatFloat,
      },
      { label: 'ROC', value: indicators.roc, format: formatPercent },
    ],
    Trend: [
      { label: 'ADX', value: indicators.adx, format: formatFloat },
      {
        label: 'Supertrend',
        value: indicators.supertrend,
        format: formatFloat,
      },
      {
        label: 'SMA Alignment',
        value: indicators.sma_alignment,
        format: formatDecimal,
      },
      {
        label: 'VWAP Dev',
        value: indicators.vwap_deviation,
        format: formatPercent,
      },
    ],
    Volatility: [
      { label: 'ATR %', value: indicators.atr_percent, format: formatPercent },
      { label: 'BB Width', value: indicators.bb_width, format: formatDecimal },
      {
        label: 'Keltner Width',
        value: indicators.keltner_width,
        format: formatDecimal,
      },
    ],
    Volume: [
      {
        label: 'OBV Trend',
        value: indicators.obv_trend,
        format: formatDecimal,
      },
      { label: 'A/D Trend', value: indicators.ad_trend, format: formatDecimal },
      {
        label: 'Rel Volume',
        value: indicators.relative_volume,
        format: formatFloat,
      },
    ],
  }
}

export function IndicatorPanel({ indicators }: IndicatorPanelProps) {
  const groups = buildGroups(indicators)

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Object.entries(groups).map(([groupName, items]) => (
        <Card key={groupName} title={groupName}>
          <div className="flex flex-col gap-1.5">
            {items.map((item) => (
              <div
                key={item.label}
                className="flex items-center justify-between"
              >
                <span
                  className="font-data text-xs"
                  style={{ color: 'var(--color-text-secondary)' }}
                >
                  {item.label}
                </span>
                <span
                  className="font-data text-xs font-semibold"
                  style={{
                    color:
                      item.value !== null
                        ? getIndicatorColor(item.label, item.value)
                        : 'var(--color-text-muted)',
                  }}
                >
                  {item.value !== null ? item.format(item.value) : 'N/A'}
                </span>
              </div>
            ))}
          </div>
        </Card>
      ))}
    </div>
  )
}
