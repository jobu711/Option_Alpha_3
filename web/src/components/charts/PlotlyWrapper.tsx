/**
 * Reusable Plotly chart wrapper with Bloomberg dark theme styling.
 *
 * Provides consistent dark background, grid lines, colors, monospace labels,
 * responsive sizing, and margins across all chart components.
 */
import Plot from 'react-plotly.js'
import type { Data, Layout } from 'plotly.js'

/** Bloomberg dark theme color constants */
const THEME = {
  background: '#0A0E17',
  paper: '#131928',
  gridColor: '#1E2A3A',
  textColor: '#8B95A5',
  axisColor: '#5A6577',
  font: '"JetBrains Mono", "Fira Code", "Consolas", "Courier New", monospace',
} as const

interface PlotlyWrapperProps {
  data: Data[]
  layout?: Partial<Layout>
  height?: number
  className?: string
}

export function PlotlyWrapper({
  data,
  layout = {},
  height = 250,
  className = '',
}: PlotlyWrapperProps) {
  const mergedLayout: Partial<Layout> = {
    autosize: true,
    height,
    margin: { l: 50, r: 20, t: 30, b: 40 },
    paper_bgcolor: THEME.paper,
    plot_bgcolor: THEME.background,
    font: {
      family: THEME.font,
      size: 10,
      color: THEME.textColor,
    },
    xaxis: {
      gridcolor: THEME.gridColor,
      zerolinecolor: THEME.gridColor,
      tickfont: { family: THEME.font, size: 9, color: THEME.axisColor },
      ...(layout.xaxis as object),
    },
    yaxis: {
      gridcolor: THEME.gridColor,
      zerolinecolor: THEME.gridColor,
      tickfont: { family: THEME.font, size: 9, color: THEME.axisColor },
      ...(layout.yaxis as object),
    },
    legend: {
      font: { family: THEME.font, size: 9, color: THEME.textColor },
      bgcolor: 'transparent',
      ...(layout.legend as object),
    },
    ...layout,
    // Ensure axes are not overridden by the spread above
  }

  // Re-apply axis merging after top-level spread
  if (layout.xaxis) {
    mergedLayout.xaxis = {
      gridcolor: THEME.gridColor,
      zerolinecolor: THEME.gridColor,
      tickfont: { family: THEME.font, size: 9, color: THEME.axisColor },
      ...(layout.xaxis as object),
    }
  }
  if (layout.yaxis) {
    mergedLayout.yaxis = {
      gridcolor: THEME.gridColor,
      zerolinecolor: THEME.gridColor,
      tickfont: { family: THEME.font, size: 9, color: THEME.axisColor },
      ...(layout.yaxis as object),
    }
  }

  return (
    <div className={`w-full ${className}`} data-testid="plotly-wrapper">
      <Plot
        data={data}
        layout={mergedLayout}
        config={{
          responsive: true,
          displayModeBar: true,
          displaylogo: false,
          modeBarButtonsToRemove: [
            'select2d',
            'lasso2d',
            'autoScale2d',
            'toggleSpikelines',
          ],
        }}
        useResizeHandler={true}
        style={{ width: '100%', height: `${height}px` }}
      />
    </div>
  )
}
