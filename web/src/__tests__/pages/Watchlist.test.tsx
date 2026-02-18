import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Watchlist } from '../../pages/Watchlist'

function renderWatchlist() {
  return render(
    <MemoryRouter>
      <Watchlist />
    </MemoryRouter>,
  )
}

const mockWatchlistResponse = {
  watchlist: { id: 1, name: 'default', created_at: '2024-12-15T10:00:00Z' },
  tickers: ['AAPL', 'MSFT', 'TSLA'],
}

const emptyWatchlistResponse = {
  watchlist: { id: 1, name: 'default', created_at: '2024-12-15T10:00:00Z' },
  tickers: [],
}

describe('Watchlist page', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the page title', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderWatchlist()
    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toHaveTextContent('Watchlist')
  })

  it('shows loading spinner while fetching', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderWatchlist()
    expect(screen.getByText(/loading watchlist/i)).toBeInTheDocument()
  })

  it('displays watchlist tickers after loading', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByTestId('watchlist-table')).toBeInTheDocument()
    })

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
  })

  it('shows empty state when watchlist is empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => emptyWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByText('EMPTY WATCHLIST')).toBeInTheDocument()
    })
  })

  it('displays the ticker count in the card title', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByText('Watched Tickers (3)')).toBeInTheDocument()
    })
  })

  it('renders the add ticker form', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByTestId('add-ticker-form')).toBeInTheDocument()
    })

    expect(screen.getByLabelText(/add ticker/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^add$/i })).toBeInTheDocument()
  })

  it('renders the scan watchlist button', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /scan watchlist/i }),
      ).toBeEnabled()
    })
  })

  it('disables scan watchlist button when empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => emptyWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /scan watchlist/i }),
      ).toBeDisabled()
    })
  })

  it('renders remove buttons for each ticker', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      const removeButtons = screen.getAllByRole('button', { name: /remove/i })
      expect(removeButtons).toHaveLength(3)
    })
  })

  it('shows error on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(
      new Error('Network error'),
    )

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByText(/Network error/i)).toBeInTheDocument()
    })
  })

  it('validates ticker input - rejects empty', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByTestId('add-ticker-form')).toBeInTheDocument()
    })

    // Click add with empty input
    fireEvent.click(screen.getByRole('button', { name: /^add$/i }))

    await waitFor(() => {
      expect(screen.getByTestId('add-ticker-error')).toHaveTextContent(
        'Ticker symbol is required.',
      )
    })
  })

  it('validates ticker input - rejects invalid symbols', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockWatchlistResponse,
    } as Response)

    renderWatchlist()

    await waitFor(() => {
      expect(screen.getByTestId('add-ticker-form')).toBeInTheDocument()
    })

    const input = screen.getByLabelText(/add ticker/i)
    fireEvent.change(input, { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: /^add$/i }))

    await waitFor(() => {
      expect(screen.getByTestId('add-ticker-error')).toHaveTextContent(
        'Invalid ticker',
      )
    })
  })
})
