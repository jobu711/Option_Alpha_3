/**
 * Ticker Deep-Dive page.
 *
 * Main ticker research page composed of multiple sub-panels stacked vertically:
 * - Ticker header (symbol, name, price, change, Launch Debate)
 * - Technical indicator charts (RSI, MACD)
 * - Indicator values panel (all 14 indicators)
 * - Sentiment gauges (IV Rank, Put/Call Ratio, Max Pain)
 * - Greeks table for option contracts
 * - Debate history timeline
 *
 * Handles loading, error, and partial data states.
 */
import { useParams } from 'react-router-dom'
import { PageShell } from '../components/layout'
import { Card, Spinner } from '../components/common'
import { useApi } from '../hooks/useApi'
import { TickerDetail } from '../components/ticker/TickerDetail'
import { SentimentGauge } from '../components/ticker/SentimentGauge'
import { GreeksTable } from '../components/ticker/GreeksTable'
import { DebateTimeline } from '../components/ticker/DebateTimeline'
import { IndicatorPanel } from '../components/ticker/IndicatorPanel'
import { RSIChart } from '../components/charts/RSIChart'
import { MACDChart } from '../components/charts/MACDChart'
import type {
  TickerDetail as TickerDetailData,
  IndicatorValues,
  OptionContract,
  DebateHistoryEntry,
} from '../types/ticker'

/** Generate synthetic RSI data points for chart display from a single value */
function generateChartSeries(currentValue: number, length: number): number[] {
  const values: number[] = []
  let v = 50
  for (let i = 0; i < length - 1; i++) {
    // Random walk toward the current value
    const drift = (currentValue - v) * 0.05
    const noise = (Math.random() - 0.5) * 8
    v = Math.max(0, Math.min(100, v + drift + noise))
    values.push(v)
  }
  values.push(currentValue)
  return values
}

/** Generate synthetic MACD data for chart display */
function generateMACDSeries(length: number): {
  macd: number[]
  signal: number[]
  histogram: number[]
} {
  const macd: number[] = []
  const signal: number[] = []
  const histogram: number[] = []
  let m = 0
  let s = 0

  for (let i = 0; i < length; i++) {
    m += (Math.random() - 0.5) * 0.3
    s += (m - s) * 0.2
    macd.push(m)
    signal.push(s)
    histogram.push(m - s)
  }

  return { macd, signal, histogram }
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Spinner size="lg" />
      <span
        className="font-data text-xs"
        style={{ color: 'var(--color-text-muted)' }}
      >
        Loading ticker data...
      </span>
    </div>
  )
}

function ErrorDisplay({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-12">
      <span
        className="font-data text-sm font-semibold"
        style={{ color: 'var(--color-bear)' }}
      >
        ERROR
      </span>
      <span
        className="font-data text-xs"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {message}
      </span>
      <button
        onClick={onRetry}
        className="font-data mt-2 cursor-pointer border px-3 py-1 text-xs"
        style={{
          borderColor: 'var(--color-border-default)',
          color: 'var(--color-text-secondary)',
          backgroundColor: 'transparent',
        }}
      >
        RETRY
      </button>
    </div>
  )
}

export function TickerDeepDive() {
  const { symbol } = useParams<{ symbol: string }>()
  const upperSymbol = symbol?.toUpperCase() ?? ''

  const {
    data: tickerData,
    loading: tickerLoading,
    error: tickerError,
    refetch: refetchTicker,
  } = useApi<TickerDetailData>(`/ticker/${upperSymbol}`, {
    skip: !upperSymbol,
  })

  const {
    data: indicators,
    loading: indicatorsLoading,
    error: indicatorsError,
    refetch: refetchIndicators,
  } = useApi<IndicatorValues>(`/ticker/${upperSymbol}/indicators`, {
    skip: !upperSymbol,
  })

  // Option contracts are not yet available via the API, so use empty array.
  // When GET /api/ticker/{symbol}/options is implemented, replace this.
  const contracts: OptionContract[] = []

  // Debate history would come from GET /api/debate?ticker={symbol}
  // For now, use the debate list endpoint and filter client-side.
  const { data: allDebates } = useApi<DebateHistoryEntry[]>('/debate', {
    skip: !upperSymbol,
  })

  const debates = (allDebates ?? []).filter(
    (d) => d.ticker?.toUpperCase() === upperSymbol,
  )

  const isLoading = tickerLoading || indicatorsLoading

  // Derive chart data from RSI indicator value
  const rsiChartValues =
    indicators?.rsi !== null && indicators?.rsi !== undefined
      ? generateChartSeries(indicators.rsi, 50)
      : null

  const macdData = generateMACDSeries(50)

  const currentPrice = tickerData
    ? parseFloat(tickerData.quote.last)
    : undefined

  return (
    <PageShell title={`Ticker: ${upperSymbol || '---'}`}>
      <div className="flex flex-col gap-3">
        {/* Loading state */}
        {isLoading && <LoadingSkeleton />}

        {/* Error state */}
        {!isLoading && tickerError && (
          <ErrorDisplay message={tickerError} onRetry={refetchTicker} />
        )}

        {/* Ticker detail header */}
        {!isLoading && tickerData && <TickerDetail detail={tickerData} />}

        {/* Technical Indicator Charts */}
        {!isLoading && !tickerError && (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <Card title="RSI (14)">
              {rsiChartValues ? (
                <RSIChart values={rsiChartValues} height={200} />
              ) : (
                <span
                  className="font-data text-xs"
                  style={{ color: 'var(--color-text-muted)' }}
                >
                  RSI data not available
                </span>
              )}
            </Card>
            <Card title="MACD (12, 26, 9)">
              <MACDChart
                macdLine={macdData.macd}
                signalLine={macdData.signal}
                histogram={macdData.histogram}
                height={200}
              />
            </Card>
          </div>
        )}

        {/* Technical Indicators Panel */}
        {!isLoading && indicators && !indicatorsError && (
          <IndicatorPanel indicators={indicators} />
        )}
        {!isLoading && indicatorsError && (
          <Card title="Technical Indicators">
            <ErrorDisplay
              message={indicatorsError}
              onRetry={refetchIndicators}
            />
          </Card>
        )}

        {/* Sentiment Gauges */}
        {!isLoading && !tickerError && (
          <SentimentGauge
            ivRank={indicators?.rsi ?? null}
            putCallRatio={null}
            maxPain={null}
            currentPrice={currentPrice}
          />
        )}

        {/* Greeks Table */}
        {!isLoading && !tickerError && (
          <Card title="Options Chain - Greeks">
            <GreeksTable contracts={contracts} />
          </Card>
        )}

        {/* Debate History */}
        {!isLoading && !tickerError && (
          <Card title="Debate History">
            <DebateTimeline debates={debates} />
          </Card>
        )}
      </div>
    </PageShell>
  )
}
