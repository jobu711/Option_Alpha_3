import { render, screen } from '@testing-library/react'
import { PlotlyWrapper } from '../../components/charts/PlotlyWrapper'
import { RSIChart } from '../../components/charts/RSIChart'
import { MACDChart } from '../../components/charts/MACDChart'

// Mock react-plotly.js since Plotly requires a DOM canvas context
vi.mock('react-plotly.js', () => ({
  default: function MockPlot(props: Record<string, unknown>) {
    return <div data-testid="mock-plotly" data-props={JSON.stringify(props)} />
  },
}))

describe('PlotlyWrapper', () => {
  it('renders the wrapper container', () => {
    render(
      <PlotlyWrapper
        data={[{ x: [1, 2, 3], y: [10, 20, 30], type: 'scatter' }]}
      />,
    )
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders the mock Plot component', () => {
    render(
      <PlotlyWrapper
        data={[{ x: [1, 2, 3], y: [10, 20, 30], type: 'scatter' }]}
      />,
    )
    expect(screen.getByTestId('mock-plotly')).toBeInTheDocument()
  })

  it('applies custom className', () => {
    render(<PlotlyWrapper data={[]} className="custom-class" />)
    const wrapper = screen.getByTestId('plotly-wrapper')
    expect(wrapper.className).toContain('custom-class')
  })
})

describe('RSIChart', () => {
  const sampleValues = [45, 50, 55, 60, 65, 70, 75, 72, 68, 62]

  it('renders without errors', () => {
    render(<RSIChart values={sampleValues} />)
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders with custom labels', () => {
    const labels = sampleValues.map(
      (_, i) => `2024-01-${String(i + 1).padStart(2, '0')}`,
    )
    render(<RSIChart values={sampleValues} labels={labels} />)
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders with custom height', () => {
    render(<RSIChart values={sampleValues} height={300} />)
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders with empty data', () => {
    render(<RSIChart values={[]} />)
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })
})

describe('MACDChart', () => {
  const sampleMacd = [0.1, 0.2, 0.15, -0.05, -0.1, 0.05, 0.3]
  const sampleSignal = [0.05, 0.1, 0.12, 0.05, -0.02, 0.01, 0.15]
  const sampleHistogram = sampleMacd.map((m, i) => m - sampleSignal[i])

  it('renders without errors', () => {
    render(
      <MACDChart
        macdLine={sampleMacd}
        signalLine={sampleSignal}
        histogram={sampleHistogram}
      />,
    )
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders with custom labels', () => {
    const labels = sampleMacd.map(
      (_, i) => `2024-01-${String(i + 1).padStart(2, '0')}`,
    )
    render(
      <MACDChart
        macdLine={sampleMacd}
        signalLine={sampleSignal}
        histogram={sampleHistogram}
        labels={labels}
      />,
    )
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })

  it('renders with custom height', () => {
    render(
      <MACDChart
        macdLine={sampleMacd}
        signalLine={sampleSignal}
        histogram={sampleHistogram}
        height={350}
      />,
    )
    expect(screen.getByTestId('plotly-wrapper')).toBeInTheDocument()
  })
})
