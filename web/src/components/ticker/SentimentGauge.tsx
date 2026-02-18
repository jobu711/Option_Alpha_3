/**
 * Options sentiment indicators displayed as Plotly gauge charts.
 *
 * Shows three gauges in a row:
 * - IV Rank gauge: 0-100 scale, color gradient (green=low, red=high)
 * - Put/Call Ratio: indicator with interpretation text
 * - Max Pain: display max pain price level
 *
 * All gauges use Bloomberg dark styling.
 */
import Plot from 'react-plotly.js'
import { Card } from '../common'

const GAUGE_FONT = '"JetBrains Mono", "Fira Code", "Consolas", monospace'
const GAUGE_BG = '#131928'
const GAUGE_TEXT_COLOR = '#8B95A5'

interface SentimentGaugeProps {
  /** IV Rank (0-100), null if unavailable */
  ivRank: number | null
  /** Put/Call Ratio, null if unavailable */
  putCallRatio: number | null
  /** Max Pain price level, null if unavailable */
  maxPain: number | null
  /** Current stock price for max pain context */
  currentPrice?: number
}

function getIVRankInterpretation(value: number): string {
  if (value >= 80) return 'VERY HIGH'
  if (value >= 60) return 'HIGH'
  if (value >= 40) return 'MODERATE'
  if (value >= 20) return 'LOW'
  return 'VERY LOW'
}

function getPCRInterpretation(value: number): string {
  if (value >= 1.5) return 'VERY BEARISH'
  if (value >= 1.1) return 'BEARISH'
  if (value >= 0.9) return 'NEUTRAL'
  if (value >= 0.5) return 'BULLISH'
  return 'VERY BULLISH'
}

function getPCRColor(value: number): string {
  if (value >= 1.1) return 'var(--color-bear)'
  if (value >= 0.9) return 'var(--color-risk)'
  return 'var(--color-bull)'
}

export function SentimentGauge({
  ivRank,
  putCallRatio,
  maxPain,
  currentPrice,
}: SentimentGaugeProps) {
  return (
    <div
      className="grid grid-cols-1 gap-3 md:grid-cols-3"
      data-testid="sentiment-gauges"
    >
      {/* IV Rank Gauge */}
      <Card title="IV Rank">
        {ivRank !== null ? (
          <div className="flex flex-col items-center">
            <Plot
              data={[
                {
                  type: 'indicator',
                  mode: 'gauge+number',
                  value: ivRank,
                  number: {
                    suffix: '%',
                    font: { family: GAUGE_FONT, size: 24, color: '#E8ECF1' },
                  },
                  gauge: {
                    axis: {
                      range: [0, 100],
                      tickfont: {
                        family: GAUGE_FONT,
                        size: 9,
                        color: GAUGE_TEXT_COLOR,
                      },
                      tickcolor: '#1E2A3A',
                    },
                    bar: { color: '#5B9CF6', thickness: 0.6 },
                    bgcolor: '#0A0E17',
                    borderwidth: 0,
                    steps: [
                      { range: [0, 20], color: 'rgba(0, 200, 83, 0.2)' },
                      { range: [20, 40], color: 'rgba(0, 200, 83, 0.1)' },
                      { range: [40, 60], color: 'rgba(255, 214, 0, 0.1)' },
                      { range: [60, 80], color: 'rgba(255, 23, 68, 0.1)' },
                      { range: [80, 100], color: 'rgba(255, 23, 68, 0.2)' },
                    ],
                    threshold: {
                      line: { color: '#E8ECF1', width: 2 },
                      thickness: 0.75,
                      value: ivRank,
                    },
                  },
                },
              ]}
              layout={{
                autosize: true,
                height: 140,
                margin: { l: 20, r: 20, t: 10, b: 0 },
                paper_bgcolor: GAUGE_BG,
                plot_bgcolor: GAUGE_BG,
                font: { family: GAUGE_FONT, color: GAUGE_TEXT_COLOR },
              }}
              config={{ displayModeBar: false, responsive: true }}
              useResizeHandler={true}
              style={{ width: '100%', height: '140px' }}
            />
            <span
              className="font-data text-xs font-semibold"
              style={{
                color:
                  ivRank >= 60
                    ? 'var(--color-bear)'
                    : ivRank >= 40
                      ? 'var(--color-risk)'
                      : 'var(--color-bull)',
              }}
              data-testid="iv-rank-label"
            >
              {getIVRankInterpretation(ivRank)}
            </span>
          </div>
        ) : (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            N/A
          </span>
        )}
      </Card>

      {/* Put/Call Ratio */}
      <Card title="Put/Call Ratio">
        {putCallRatio !== null ? (
          <div className="flex flex-col items-center gap-2 py-3">
            <span
              className="font-data text-2xl font-bold"
              style={{ color: 'var(--color-text-primary)' }}
              data-testid="pcr-value"
            >
              {putCallRatio.toFixed(2)}
            </span>
            <span
              className="font-data text-xs font-semibold"
              style={{ color: getPCRColor(putCallRatio) }}
              data-testid="pcr-label"
            >
              {getPCRInterpretation(putCallRatio)}
            </span>
            <div
              className="mt-1 h-1.5 w-full overflow-hidden"
              style={{ backgroundColor: '#0A0E17' }}
            >
              <div
                className="h-full transition-all"
                style={{
                  width: `${Math.min(putCallRatio / 2, 1) * 100}%`,
                  backgroundColor: getPCRColor(putCallRatio),
                }}
              />
            </div>
            <div
              className="flex w-full justify-between"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <span className="font-data text-[9px]">BULLISH</span>
              <span className="font-data text-[9px]">BEARISH</span>
            </div>
          </div>
        ) : (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            N/A
          </span>
        )}
      </Card>

      {/* Max Pain */}
      <Card title="Max Pain">
        {maxPain !== null ? (
          <div className="flex flex-col items-center gap-2 py-3">
            <span
              className="font-data text-2xl font-bold"
              style={{ color: 'var(--color-text-primary)' }}
              data-testid="max-pain-value"
            >
              ${maxPain.toFixed(2)}
            </span>
            {currentPrice !== undefined && (
              <>
                <span
                  className="font-data text-xs"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  Current: ${currentPrice.toFixed(2)}
                </span>
                <span
                  className="font-data text-xs font-semibold"
                  style={{
                    color:
                      currentPrice > maxPain
                        ? 'var(--color-bear)'
                        : currentPrice < maxPain
                          ? 'var(--color-bull)'
                          : 'var(--color-risk)',
                  }}
                  data-testid="max-pain-context"
                >
                  {currentPrice > maxPain
                    ? `$${(currentPrice - maxPain).toFixed(2)} ABOVE`
                    : currentPrice < maxPain
                      ? `$${(maxPain - currentPrice).toFixed(2)} BELOW`
                      : 'AT MAX PAIN'}
                </span>
              </>
            )}
          </div>
        ) : (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            N/A
          </span>
        )}
      </Card>
    </div>
  )
}
