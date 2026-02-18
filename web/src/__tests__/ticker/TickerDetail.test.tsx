import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { TickerDetail } from '../../components/ticker/TickerDetail'
import type { TickerDetail as TickerDetailData } from '../../types/ticker'

const mockDetail: TickerDetailData = {
  info: {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    sector: 'Technology',
    market_cap_tier: 'mega',
    asset_type: 'stock',
    source: 'cboe',
    tags: ['sp500'],
    status: 'active',
    discovered_at: '2024-01-01T00:00:00Z',
    last_scanned_at: '2024-06-15T12:00:00Z',
    consecutive_misses: 0,
  },
  quote: {
    ticker: 'AAPL',
    bid: '195.00',
    ask: '195.10',
    last: '195.05',
    volume: 52340000,
    timestamp: '2024-06-15T16:00:00Z',
    mid: '195.05',
    spread: '0.10',
  },
}

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('TickerDetail', () => {
  it('renders the ticker symbol', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByTestId('ticker-symbol')).toHaveTextContent('AAPL')
  })

  it('renders the company name', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
  })

  it('renders the current price', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByTestId('ticker-price')).toHaveTextContent('$195.05')
  })

  it('renders the sector', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByText(/SECTOR: Technology/)).toBeInTheDocument()
  })

  it('renders the market cap tier', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByText(/TIER: MEGA/)).toBeInTheDocument()
  })

  it('renders the volume', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByText(/VOL: 52,340,000/)).toBeInTheDocument()
  })

  it('renders the Launch Debate button', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(
      screen.getByRole('button', { name: 'LAUNCH DEBATE' }),
    ).toBeInTheDocument()
  })

  it('renders bid and ask prices', () => {
    renderWithRouter(<TickerDetail detail={mockDetail} />)
    expect(screen.getByText(/BID: \$195.00/)).toBeInTheDocument()
    expect(screen.getByText(/ASK: \$195.10/)).toBeInTheDocument()
  })
})
