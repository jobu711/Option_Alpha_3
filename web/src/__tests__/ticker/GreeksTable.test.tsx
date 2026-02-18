import { render, screen } from '@testing-library/react'
import { GreeksTable } from '../../components/ticker/GreeksTable'
import type { OptionContract } from '../../types/ticker'

const mockContracts: OptionContract[] = [
  {
    ticker: 'AAPL',
    option_type: 'call',
    strike: '195.00',
    expiration: '2024-07-19',
    bid: '5.20',
    ask: '5.40',
    last: '5.30',
    volume: 1250,
    open_interest: 8400,
    implied_volatility: 0.28,
    greeks: {
      delta: 0.52,
      gamma: 0.035,
      theta: -0.08,
      vega: 0.15,
      rho: 0.04,
    },
    greeks_source: 'calculated',
    mid: '5.30',
    spread: '0.20',
    dte: 34,
  },
  {
    ticker: 'AAPL',
    option_type: 'put',
    strike: '190.00',
    expiration: '2024-07-19',
    bid: '3.10',
    ask: '3.30',
    last: '3.20',
    volume: 890,
    open_interest: 5200,
    implied_volatility: 0.31,
    greeks: {
      delta: -0.38,
      gamma: 0.028,
      theta: -0.06,
      vega: 0.12,
      rho: -0.03,
    },
    greeks_source: 'calculated',
    mid: '3.20',
    spread: '0.20',
    dte: 34,
  },
]

describe('GreeksTable', () => {
  it('renders empty state when no contracts', () => {
    render(<GreeksTable contracts={[]} />)
    expect(
      screen.getByText('No option contracts available'),
    ).toBeInTheDocument()
  })

  it('renders table headers', () => {
    render(<GreeksTable contracts={mockContracts} />)
    expect(screen.getByText('Strike')).toBeInTheDocument()
    expect(screen.getByText('Type')).toBeInTheDocument()
    expect(screen.getByText('DTE')).toBeInTheDocument()
    expect(screen.getByText('Delta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
    expect(screen.getByText('Theta')).toBeInTheDocument()
    expect(screen.getByText('Vega')).toBeInTheDocument()
    expect(screen.getByText('Rho')).toBeInTheDocument()
    expect(screen.getByText('Bid')).toBeInTheDocument()
    expect(screen.getByText('Ask')).toBeInTheDocument()
    expect(screen.getByText('OI')).toBeInTheDocument()
  })

  it('renders contract rows', () => {
    render(<GreeksTable contracts={mockContracts} />)
    expect(screen.getByText('$195.00')).toBeInTheDocument()
    expect(screen.getByText('$190.00')).toBeInTheDocument()
  })

  it('renders option types in uppercase', () => {
    render(<GreeksTable contracts={mockContracts} />)
    expect(screen.getByText('CALL')).toBeInTheDocument()
    expect(screen.getByText('PUT')).toBeInTheDocument()
  })

  it('renders volume with locale formatting', () => {
    render(<GreeksTable contracts={mockContracts} />)
    expect(screen.getByText('1,250')).toBeInTheDocument()
    expect(screen.getByText('890')).toBeInTheDocument()
  })

  it('renders greeks values', () => {
    render(<GreeksTable contracts={mockContracts} />)
    expect(screen.getByText('0.5200')).toBeInTheDocument()
    expect(screen.getByText('-0.3800')).toBeInTheDocument()
  })
})
