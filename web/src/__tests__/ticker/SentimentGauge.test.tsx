import { render, screen } from '@testing-library/react'
import { SentimentGauge } from '../../components/ticker/SentimentGauge'

// Mock react-plotly.js since Plotly requires a DOM canvas context
vi.mock('react-plotly.js', () => ({
  default: function MockPlot(props: Record<string, unknown>) {
    return <div data-testid="mock-plotly" data-props={JSON.stringify(props)} />
  },
}))

describe('SentimentGauge', () => {
  it('renders all three gauge cards', () => {
    render(
      <SentimentGauge
        ivRank={65}
        putCallRatio={1.2}
        maxPain={195.0}
        currentPrice={192.5}
      />,
    )
    expect(screen.getByTestId('sentiment-gauges')).toBeInTheDocument()
    expect(screen.getByText('IV Rank')).toBeInTheDocument()
    expect(screen.getByText('Put/Call Ratio')).toBeInTheDocument()
    expect(screen.getByText('Max Pain')).toBeInTheDocument()
  })

  it('displays IV Rank interpretation', () => {
    render(<SentimentGauge ivRank={65} putCallRatio={null} maxPain={null} />)
    expect(screen.getByTestId('iv-rank-label')).toHaveTextContent('HIGH')
  })

  it('displays Put/Call Ratio value and interpretation', () => {
    render(<SentimentGauge ivRank={null} putCallRatio={1.2} maxPain={null} />)
    expect(screen.getByTestId('pcr-value')).toHaveTextContent('1.20')
    expect(screen.getByTestId('pcr-label')).toHaveTextContent('BEARISH')
  })

  it('displays Max Pain value', () => {
    render(
      <SentimentGauge
        ivRank={null}
        putCallRatio={null}
        maxPain={195.0}
        currentPrice={192.5}
      />,
    )
    expect(screen.getByTestId('max-pain-value')).toHaveTextContent('$195.00')
  })

  it('displays max pain context relative to current price', () => {
    render(
      <SentimentGauge
        ivRank={null}
        putCallRatio={null}
        maxPain={195.0}
        currentPrice={192.5}
      />,
    )
    expect(screen.getByTestId('max-pain-context')).toHaveTextContent(
      '$2.50 BELOW',
    )
  })

  it('shows N/A when IV Rank is null', () => {
    render(<SentimentGauge ivRank={null} putCallRatio={null} maxPain={null} />)
    // All three should show N/A
    const naElements = screen.getAllByText('N/A')
    expect(naElements).toHaveLength(3)
  })

  it('shows VERY LOW for IV Rank below 20', () => {
    render(<SentimentGauge ivRank={10} putCallRatio={null} maxPain={null} />)
    expect(screen.getByTestId('iv-rank-label')).toHaveTextContent('VERY LOW')
  })

  it('shows VERY BULLISH for PCR below 0.5', () => {
    render(<SentimentGauge ivRank={null} putCallRatio={0.3} maxPain={null} />)
    expect(screen.getByTestId('pcr-label')).toHaveTextContent('VERY BULLISH')
  })

  it('shows AT MAX PAIN when price equals max pain', () => {
    render(
      <SentimentGauge
        ivRank={null}
        putCallRatio={null}
        maxPain={195.0}
        currentPrice={195.0}
      />,
    )
    expect(screen.getByTestId('max-pain-context')).toHaveTextContent(
      'AT MAX PAIN',
    )
  })
})
