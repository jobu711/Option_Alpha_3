import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from '../../pages/Dashboard'

function renderDashboard() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  )
}

// Mock responses for the dashboard API calls
const mockScans = [
  {
    id: 'scan-1',
    started_at: '2024-12-15T10:00:00Z',
    completed_at: '2024-12-15T10:05:00Z',
    status: 'completed',
    preset: 'full',
    sectors: [],
    ticker_count: 50,
    top_n: 10,
  },
]

const mockHealth = {
  ollama: true,
  anthropic: false,
  yfinance: true,
  sqlite: true,
  overall: true,
  checked_at: '2024-12-15T10:30:00Z',
}

const mockDebates = [
  {
    id: 42,
    ticker: 'NVDA',
    status: 'completed',
    thesis: {
      direction: 'bullish',
      conviction: 0.72,
      entry_rationale: 'Strong momentum.',
      risk_factors: ['Earnings risk'],
      recommended_action: 'Buy call spread.',
      bull_summary: 'Bullish technicals.',
      bear_summary: 'Near highs.',
      model_used: 'llama3.1:8b',
      total_tokens: 4810,
      duration_ms: 12450,
      disclaimer: 'For educational purposes only.',
    },
    agents: { bull: null, bear: null, risk: null },
    is_fallback: false,
    created_at: '2024-12-15T10:30:00Z',
  },
]

const mockWatchlist = {
  watchlist: { id: 1, name: 'default', created_at: '2024-12-15T10:00:00Z' },
  tickers: ['GOOG', 'AMZN'],
}

/** Route-based fetch mock that returns the right data per URL */
function mockFetchByUrl() {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString()

      if (url.includes('/scan')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockScans,
        } as Response
      }
      if (url.includes('/health')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockHealth,
        } as Response
      }
      if (url.includes('/debate')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockDebates,
        } as Response
      }
      if (url.includes('/watchlist')) {
        return {
          ok: true,
          status: 200,
          json: async () => mockWatchlist,
        } as Response
      }

      return {
        ok: true,
        status: 200,
        json: async () => [],
      } as Response
    })
}

describe('Dashboard page', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows loading spinners initially', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderDashboard()
    const spinners = screen.getAllByRole('status', { name: /loading/i })
    expect(spinners.length).toBeGreaterThanOrEqual(1)
  })

  it('renders dashboard title', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderDashboard()
    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toHaveTextContent('Dashboard')
  })

  it('renders quick action buttons', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderDashboard()
    expect(
      screen.getByRole('button', { name: /run scan/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /view watchlist/i }),
    ).toBeInTheDocument()
  })

  it('displays scan data after loading', async () => {
    mockFetchByUrl()
    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    })

    expect(screen.getByText('50')).toBeInTheDocument()
  })

  it('displays health status after loading', async () => {
    mockFetchByUrl()
    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('HEALTHY')).toBeInTheDocument()
    })

    // Anthropic is down
    const downElements = screen.getAllByText('DOWN')
    expect(downElements.length).toBeGreaterThanOrEqual(1)
  })

  it('displays recent debates', async () => {
    mockFetchByUrl()
    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('NVDA')).toBeInTheDocument()
    })

    expect(screen.getByText('BULLISH')).toBeInTheDocument()
    expect(screen.getByText('72%')).toBeInTheDocument()
  })

  it('displays watchlist tickers', async () => {
    mockFetchByUrl()
    renderDashboard()

    await waitFor(() => {
      expect(screen.getByText('GOOG')).toBeInTheDocument()
    })

    expect(screen.getByText('AMZN')).toBeInTheDocument()
  })

  it('shows error message on API failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(
      new Error('Network error'),
    )

    renderDashboard()

    await waitFor(() => {
      const errorElements = screen.getAllByText(/Network error/i)
      expect(errorElements.length).toBeGreaterThanOrEqual(1)
    })
  })
})
