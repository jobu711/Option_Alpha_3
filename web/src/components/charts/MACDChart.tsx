/**
 * MACD (Moving Average Convergence/Divergence) chart.
 *
 * Features:
 * - MACD line + Signal line as line traces
 * - Histogram as bar chart with green/red coloring
 * - Histogram bars: green when positive, red when negative
 * - Uses PlotlyWrapper for consistent Bloomberg dark styling
 */
import type { Data } from 'plotly.js'
import { PlotlyWrapper } from './PlotlyWrapper'

interface MACDChartProps {
  /** MACD line values */
  macdLine: number[]
  /** Signal line values */
  signalLine: number[]
  /** Histogram values (MACD - Signal) */
  histogram: number[]
  /** Optional date labels for the x-axis */
  labels?: string[]
  /** Chart height in pixels */
  height?: number
}

export function MACDChart({
  macdLine,
  signalLine,
  histogram,
  labels,
  height = 200,
}: MACDChartProps) {
  const xAxis = labels ?? macdLine.map((_, i) => String(i + 1))

  const histogramColors = histogram.map((v) =>
    v >= 0 ? 'rgba(0, 200, 83, 0.7)' : 'rgba(255, 23, 68, 0.7)',
  )

  const data: Data[] = [
    // Histogram bars
    {
      x: xAxis,
      y: histogram,
      type: 'bar',
      marker: { color: histogramColors },
      name: 'Histogram',
      hovertemplate: 'Hist: %{y:.4f}<extra></extra>',
    },
    // MACD line
    {
      x: xAxis,
      y: macdLine,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#5B9CF6', width: 1.5 },
      name: 'MACD',
      hovertemplate: 'MACD: %{y:.4f}<extra></extra>',
    },
    // Signal line
    {
      x: xAxis,
      y: signalLine,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#FFD600', width: 1.5 },
      name: 'Signal',
      hovertemplate: 'Signal: %{y:.4f}<extra></extra>',
    },
  ]

  return (
    <PlotlyWrapper
      data={data}
      height={height}
      layout={{
        title: {
          text: 'MACD (12, 26, 9)',
          font: { size: 11, color: '#8B95A5' },
        },
        showlegend: true,
        legend: {
          orientation: 'h',
          y: -0.15,
          x: 0.5,
          xanchor: 'center',
        },
        barmode: 'relative',
        margin: { l: 50, r: 15, t: 30, b: 40 },
      }}
    />
  )
}
