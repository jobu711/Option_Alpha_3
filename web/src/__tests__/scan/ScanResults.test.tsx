import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Mock } from 'vitest'
import { ScanResults } from '../../pages/ScanResults'

// Mock the API client
vi.mock('../../api/client', () => ({
  api: {
    scan: {
      start: vi.fn(),
      get: vi.fn(),
      list: vi.fn(),
    },
    debate: {
      start: vi.fn(),
      get: vi.fn(),
      list: vi.fn(),
    },
  },
}))

// Mock the useApi hook
vi.mock('../../hooks/useApi', () => ({
  useApi: vi.fn(),
}))

// Mock the useSSE hook
vi.mock('../../hooks/useSSE', () => ({
  useSSE: vi.fn(),
}))

import { useApi } from '../../hooks/useApi'
import { useSSE } from '../../hooks/useSSE'
import { api } from '../../api/client'

const mockUseApi = vi.mocked(useApi)
const mockUseSSE = vi.mocked(useSSE)
const mockScanStart = api.scan.start as Mock
const mockScanGet = api.scan.get as Mock

function renderScanResults() {
  return render(
    <MemoryRouter>
      <ScanResults />
    </MemoryRouter>,
  )
}

describe('ScanResults', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default: empty scan list, no SSE connection
    mockUseApi.mockReturnValue({
      data: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    mockUseSSE.mockReturnValue({
      data: null,
      connected: false,
      error: null,
    })
  })

  it('renders the page with title', () => {
    renderScanResults()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Scan Results',
    )
  })

  it('renders the scan configuration panel', () => {
    renderScanResults()

    expect(screen.getByLabelText(/top n/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /start scan/i }),
    ).toBeInTheDocument()
  })

  it('shows empty state when no scans exist', () => {
    renderScanResults()

    expect(screen.getByText('NO SCAN DATA')).toBeInTheDocument()
    expect(
      screen.getByText(/Run a scan to analyze the option universe/i),
    ).toBeInTheDocument()
  })

  it('shows recent scans sidebar', () => {
    renderScanResults()

    expect(screen.getByText('Recent Scans')).toBeInTheDocument()
  })

  it('shows no scan history message when list is empty', () => {
    renderScanResults()

    expect(screen.getByText('No scan history yet.')).toBeInTheDocument()
  })

  it('displays recent scan history when scans exist', () => {
    mockUseApi.mockReturnValue({
      data: [
        {
          id: 'scan-1',
          started_at: '2025-01-15T10:00:00Z',
          completed_at: '2025-01-15T10:05:00Z',
          status: 'completed',
          preset: 'api',
          sectors: [],
          ticker_count: 100,
          top_n: 10,
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    renderScanResults()

    expect(screen.getByText('COMPLETED')).toBeInTheDocument()
    expect(screen.getByText(/100 tickers/)).toBeInTheDocument()
  })

  it('starts a scan when form is submitted', async () => {
    mockScanStart.mockResolvedValue({
      id: 'new-scan-id',
      started_at: '2025-01-15T10:00:00Z',
      completed_at: null,
      status: 'running',
      preset: 'api',
      sectors: [],
      ticker_count: 0,
      top_n: 10,
    })

    renderScanResults()

    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    await waitFor(() => {
      expect(mockScanStart).toHaveBeenCalledWith({ top_n: 10 })
    })
  })

  it('shows error message when scan fails to start', async () => {
    mockScanStart.mockRejectedValue(new Error('Server unavailable'))

    renderScanResults()

    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    await waitFor(() => {
      expect(screen.getByText('Server unavailable')).toBeInTheDocument()
    })
  })

  it('shows loading spinner in sidebar when loading history', () => {
    mockUseApi.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: vi.fn(),
    })

    renderScanResults()

    // Spinner is a div with role="status"
    const spinners = screen.getAllByRole('status')
    expect(spinners.length).toBeGreaterThanOrEqual(1)
  })

  it('dismisses error when dismiss button is clicked', async () => {
    mockScanStart.mockRejectedValue(new Error('Test error'))

    renderScanResults()

    // Trigger error
    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    await waitFor(() => {
      expect(screen.getByText('Test error')).toBeInTheDocument()
    })

    // Dismiss error
    fireEvent.click(screen.getByRole('button', { name: /dismiss/i }))

    expect(screen.queryByText('Test error')).not.toBeInTheDocument()
  })
})

// Suppress unused variable warning for mockScanGet
void mockScanGet
