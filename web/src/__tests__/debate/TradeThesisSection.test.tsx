import { render, screen } from '@testing-library/react'
import { TradeThesisSection } from '../../components/debate/TradeThesisSection'
import { sampleThesis } from './fixtures'

describe('TradeThesisSection', () => {
  it('renders the trade thesis container', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(screen.getByTestId('trade-thesis')).toBeInTheDocument()
  })

  it('displays the recommended action', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(screen.getByTestId('recommended-action')).toHaveTextContent(
      'Buy AAPL 185/190 Bull Call Spread',
    )
  })

  it('displays the entry rationale', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(
      screen.getByText(/Bullish momentum confirmed by technical indicators/),
    ).toBeInTheDocument()
  })

  it('renders risk factors as list items', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(
      screen.getByText(/Upcoming earnings in 12 days/),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/IV crush post-earnings/),
    ).toBeInTheDocument()
  })

  it('displays bull case summary', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(
      screen.getByText(/Strong technicals: RSI 62/),
    ).toBeInTheDocument()
  })

  it('displays bear case summary', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(
      screen.getByText(/Elevated put\/call ratio/),
    ).toBeInTheDocument()
  })

  it('displays the disclaimer', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(screen.getByTestId('disclaimer')).toHaveTextContent(
      'This analysis is for educational purposes only',
    )
  })

  it('displays conviction as percentage', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    // 0.72 * 100 = 72%
    expect(screen.getByText('72%')).toBeInTheDocument()
  })

  it('displays model used', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    expect(screen.getByText('llama3.1:8b')).toBeInTheDocument()
  })

  it('displays duration in seconds', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    // 12450ms / 1000 = 12.45 -> toFixed(1) = "12.4"
    expect(screen.getByText('12.4s')).toBeInTheDocument()
  })

  it('displays total tokens formatted', () => {
    render(<TradeThesisSection thesis={sampleThesis} />)
    // 4810 formatted
    expect(screen.getByText('4,810')).toBeInTheDocument()
  })

  it('handles empty risk factors', () => {
    const noRiskThesis = { ...sampleThesis, risk_factors: [] }
    render(<TradeThesisSection thesis={noRiskThesis} />)
    expect(
      screen.getByText('No risk factors identified'),
    ).toBeInTheDocument()
  })
})
