import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Universe } from '../../pages/Universe'

function renderUniverse() {
  return render(
    <MemoryRouter>
      <Universe />
    </MemoryRouter>,
  )
}

const mockUniverseResponse = {
  stats: {
    total: 500,
    by_sector: { Technology: 120, Healthcare: 80 },
    by_market_cap: { large: 200, mid: 150, small: 150 },
    last_refresh: '2024-12-15T10:00:00Z',
  },
  tickers: [
    {
      symbol: 'AAPL',
      name: 'Apple Inc.',
      sector: 'Technology',
      market_cap_tier: 'large',
      asset_type: 'equity',
      source: 'cboe',
      tags: [],
      status: 'active',
      discovered_at: '2024-01-01T00:00:00Z',
      last_scanned_at: null,
      consecutive_misses: 0,
    },
    {
      symbol: 'MSFT',
      name: 'Microsoft Corporation',
      sector: 'Technology',
      market_cap_tier: 'large',
      asset_type: 'equity',
      source: 'cboe',
      tags: [],
      status: 'active',
      discovered_at: '2024-01-01T00:00:00Z',
      last_scanned_at: null,
      consecutive_misses: 0,
    },
  ],
  total: 500,
  limit: 50,
  offset: 0,
}

const emptyUniverseResponse = {
  stats: {
    total: 0,
    by_sector: {},
    by_market_cap: {},
    last_refresh: null,
  },
  tickers: [],
  total: 0,
  limit: 50,
  offset: 0,
}

describe('Universe page', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the page title', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderUniverse()
    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toHaveTextContent('Universe')
  })

  it('shows loading state initially', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderUniverse()
    expect(screen.getByText(/loading universe/i)).toBeInTheDocument()
  })

  it('displays universe stats and tickers after loading', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByText('500')).toBeInTheDocument()
    })

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
  })

  it('displays pagination when there are many results', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByText(/Page 1 of/i)).toBeInTheDocument()
    })
  })

  it('has a search input', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByLabelText(/search/i)).toBeInTheDocument()
    })
  })

  it('renders the refresh universe button', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /refresh universe/i }),
      ).toBeInTheDocument()
    })
  })

  it('shows empty state when no tickers found', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => emptyUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByText('NO TICKERS FOUND')).toBeInTheDocument()
    })
  })

  it('shows error on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(
      new Error('Connection refused'),
    )

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByText(/Connection refused/i)).toBeInTheDocument()
    })
  })

  it('renders ticker universe table', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByTestId('universe-table')).toBeInTheDocument()
    })
  })

  it('displays sector and cap tier for tickers', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      const techCells = screen.getAllByText('Technology')
      expect(techCells.length).toBeGreaterThanOrEqual(1)
    })

    const largeBadges = screen.getAllByText('large')
    expect(largeBadges.length).toBeGreaterThanOrEqual(1)
  })

  it('handles next/prev page navigation', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /prev/i }),
      ).toBeDisabled()
    })

    // NEXT should be enabled since total (500) > page size (50)
    expect(
      screen.getByRole('button', { name: /next/i }),
    ).toBeEnabled()
  })

  it('triggers search on typing', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockUniverseResponse,
    } as Response)

    renderUniverse()

    await waitFor(() => {
      expect(screen.getByLabelText(/search/i)).toBeInTheDocument()
    })

    const searchInput = screen.getByLabelText(/search/i)
    fireEvent.change(searchInput, { target: { value: 'AAPL' } })

    // After debounce, a new fetch should be triggered
    await waitFor(
      () => {
        // First fetch is initial load, second is search
        expect(fetchSpy).toHaveBeenCalledTimes(2)
      },
      { timeout: 1000 },
    )
  })
})
