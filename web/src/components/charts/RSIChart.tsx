/**
 * RSI (Relative Strength Index) line chart with overbought/oversold zones.
 *
 * Features:
 * - RSI line (14-period)
 * - Horizontal lines at overbought (70) and oversold (30)
 * - Green fill zone below 30, red fill zone above 70
 * - Y-axis fixed 0-100
 * - Uses PlotlyWrapper for consistent Bloomberg dark styling
 */
import type { Data } from 'plotly.js'
import { PlotlyWrapper } from './PlotlyWrapper'

const RSI_OVERBOUGHT = 70
const RSI_OVERSOLD = 30

interface RSIChartProps {
  /** Array of RSI values (0-100) */
  values: number[]
  /** Optional date labels for the x-axis */
  labels?: string[]
  /** Chart height in pixels */
  height?: number
}

export function RSIChart({ values, labels, height = 200 }: RSIChartProps) {
  const xAxis = labels ?? values.map((_, i) => String(i + 1))

  const data: Data[] = [
    // Overbought zone fill (above 70)
    {
      x: xAxis,
      y: values.map((v) => (v > RSI_OVERBOUGHT ? v : RSI_OVERBOUGHT)),
      type: 'scatter',
      mode: 'lines',
      fill: 'none',
      line: { color: 'transparent', width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    {
      x: xAxis,
      y: Array(values.length).fill(RSI_OVERBOUGHT) as number[],
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      fillcolor: 'rgba(255, 23, 68, 0.12)',
      line: { color: 'transparent', width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    // Oversold zone fill (below 30)
    {
      x: xAxis,
      y: values.map((v) => (v < RSI_OVERSOLD ? v : RSI_OVERSOLD)),
      type: 'scatter',
      mode: 'lines',
      fill: 'none',
      line: { color: 'transparent', width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    {
      x: xAxis,
      y: Array(values.length).fill(RSI_OVERSOLD) as number[],
      type: 'scatter',
      mode: 'lines',
      fill: 'tonexty',
      fillcolor: 'rgba(0, 200, 83, 0.12)',
      line: { color: 'transparent', width: 0 },
      showlegend: false,
      hoverinfo: 'skip',
    },
    // Overbought threshold line
    {
      x: xAxis,
      y: Array(values.length).fill(RSI_OVERBOUGHT) as number[],
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(255, 23, 68, 0.5)', width: 1, dash: 'dash' },
      name: `Overbought (${RSI_OVERBOUGHT})`,
      hoverinfo: 'skip',
    },
    // Oversold threshold line
    {
      x: xAxis,
      y: Array(values.length).fill(RSI_OVERSOLD) as number[],
      type: 'scatter',
      mode: 'lines',
      line: { color: 'rgba(0, 200, 83, 0.5)', width: 1, dash: 'dash' },
      name: `Oversold (${RSI_OVERSOLD})`,
      hoverinfo: 'skip',
    },
    // RSI line
    {
      x: xAxis,
      y: values,
      type: 'scatter',
      mode: 'lines',
      line: { color: '#5B9CF6', width: 1.5 },
      name: 'RSI (14)',
      hovertemplate: 'RSI: %{y:.1f}<extra></extra>',
    },
  ]

  return (
    <PlotlyWrapper
      data={data}
      height={height}
      layout={{
        title: { text: 'RSI (14)', font: { size: 11, color: '#8B95A5' } },
        yaxis: {
          range: [0, 100],
          dtick: 10,
        },
        showlegend: false,
        margin: { l: 40, r: 15, t: 30, b: 30 },
      }}
    />
  )
}
