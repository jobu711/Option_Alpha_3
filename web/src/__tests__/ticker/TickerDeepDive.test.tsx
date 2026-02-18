import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { TickerDeepDive } from '../../pages/TickerDeepDive'

// Mock react-plotly.js
vi.mock('react-plotly.js', () => ({
  default: function MockPlot() {
    return <div data-testid="mock-plotly" />
  },
}))

// Mock useApi hook to return controlled data
const mockTickerData = {
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

const mockIndicators = {
  ticker: 'AAPL',
  rsi: 55.3,
  stoch_rsi: 42.1,
  williams_r: -45.2,
  adx: 28.5,
  roc: 3.2,
  supertrend: 190.5,
  atr_percent: 2.1,
  bb_width: 0.045,
  keltner_width: 0.038,
  obv_trend: 0.012,
  ad_trend: -0.003,
  relative_volume: 1.15,
  sma_alignment: 0.95,
  vwap_deviation: 0.8,
}

vi.mock('../../hooks/useApi', () => ({
  useApi: (url: string) => {
    if (url.includes('/indicators')) {
      return {
        data: mockIndicators,
        loading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    if (url.startsWith('/ticker/')) {
      return {
        data: mockTickerData,
        loading: false,
        error: null,
        refetch: vi.fn(),
      }
    }
    // Debate list
    return {
      data: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    }
  },
}))

function renderPage(symbol = 'AAPL') {
  return render(
    <MemoryRouter initialEntries={[`/ticker/${symbol}`]}>
      <Routes>
        <Route path="/ticker/:symbol" element={<TickerDeepDive />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TickerDeepDive page', () => {
  it('renders the page title with ticker symbol', () => {
    renderPage()
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Ticker: AAPL')
  })

  it('renders the ticker detail header', () => {
    renderPage()
    expect(screen.getByTestId('ticker-detail')).toBeInTheDocument()
    expect(screen.getByTestId('ticker-symbol')).toHaveTextContent('AAPL')
  })

  it('renders the RSI chart section', () => {
    renderPage()
    expect(screen.getByText('RSI (14)')).toBeInTheDocument()
  })

  it('renders the MACD chart section', () => {
    renderPage()
    expect(screen.getByText('MACD (12, 26, 9)')).toBeInTheDocument()
  })

  it('renders sentiment gauges', () => {
    renderPage()
    expect(screen.getByTestId('sentiment-gauges')).toBeInTheDocument()
    expect(screen.getByText('IV Rank')).toBeInTheDocument()
    expect(screen.getByText('Put/Call Ratio')).toBeInTheDocument()
    expect(screen.getByText('Max Pain')).toBeInTheDocument()
  })

  it('renders the options chain / greeks section', () => {
    renderPage()
    expect(screen.getByText('Options Chain - Greeks')).toBeInTheDocument()
  })

  it('renders the debate history section', () => {
    renderPage()
    expect(screen.getByText('Debate History')).toBeInTheDocument()
  })

  it('shows empty state for debate timeline', () => {
    renderPage()
    expect(
      screen.getByText('No debates for this ticker yet'),
    ).toBeInTheDocument()
  })

  it('shows empty state for options contracts', () => {
    renderPage()
    expect(
      screen.getByText('No option contracts available'),
    ).toBeInTheDocument()
  })

  it('renders indicator panel with values', () => {
    renderPage()
    // Check indicator group headers
    expect(screen.getByText('Momentum')).toBeInTheDocument()
    expect(screen.getByText('Trend')).toBeInTheDocument()
    expect(screen.getByText('Volatility')).toBeInTheDocument()
    expect(screen.getByText('Volume')).toBeInTheDocument()
  })

  it('renders the current price', () => {
    renderPage()
    expect(screen.getByTestId('ticker-price')).toHaveTextContent('$195.05')
  })
})
