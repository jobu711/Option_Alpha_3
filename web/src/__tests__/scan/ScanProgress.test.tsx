import { render, screen } from '@testing-library/react'
import { ScanProgress } from '../../components/scan/ScanProgress'

// Mock the useSSE hook
vi.mock('../../hooks/useSSE', () => ({
  useSSE: vi.fn(),
}))

import { useSSE } from '../../hooks/useSSE'

const mockUseSSE = vi.mocked(useSSE)

describe('ScanProgress', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders progress bar with phase label and percentage', () => {
    mockUseSSE.mockReturnValue({
      data: { phase: 'fetch_prices', current: 50, total: 200, pct: 25 },
      connected: true,
      error: null,
    })

    render(<ScanProgress scanId="test-id-123" />)

    expect(screen.getByText('Fetching Prices')).toBeInTheDocument()
    expect(screen.getByText('50 / 200')).toBeInTheDocument()
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('renders the progress bar element with correct ARIA attributes', () => {
    mockUseSSE.mockReturnValue({
      data: { phase: 'compute_indicators', current: 10, total: 100, pct: 10 },
      connected: true,
      error: null,
    })

    render(<ScanProgress scanId="test-id-123" />)

    const progressBar = screen.getByRole('progressbar')
    expect(progressBar).toHaveAttribute('aria-valuenow', '10')
    expect(progressBar).toHaveAttribute('aria-valuemin', '0')
    expect(progressBar).toHaveAttribute('aria-valuemax', '100')
  })

  it('shows Connecting... when not connected and no error', () => {
    mockUseSSE.mockReturnValue({
      data: null,
      connected: false,
      error: null,
    })

    render(<ScanProgress scanId="test-id-123" />)

    expect(screen.getByText('Connecting...')).toBeInTheDocument()
  })

  it('shows error message when SSE has an error', () => {
    mockUseSSE.mockReturnValue({
      data: { phase: 'fetch_prices', current: 10, total: 100, pct: 10 },
      connected: false,
      error: 'Connection lost. Reconnecting in 2s...',
    })

    render(<ScanProgress scanId="test-id-123" />)

    expect(
      screen.getByText('Connection lost. Reconnecting in 2s...'),
    ).toBeInTheDocument()
  })

  it('returns null when phase is complete', () => {
    mockUseSSE.mockReturnValue({
      data: { phase: 'complete', current: 1, total: 1, pct: 100 },
      connected: true,
      error: null,
    })

    const { container } = render(<ScanProgress scanId="test-id-123" />)

    expect(container.innerHTML).toBe('')
  })

  it('shows correct phase labels for all phases', () => {
    const phases = [
      { phase: 'fetch_prices', label: 'Fetching Prices' },
      { phase: 'compute_indicators', label: 'Computing Indicators' },
      { phase: 'scoring', label: 'Scoring Universe' },
      { phase: 'catalysts', label: 'Catalyst Analysis' },
      { phase: 'persisting', label: 'Persisting Results' },
    ]

    for (const { phase, label } of phases) {
      mockUseSSE.mockReturnValue({
        data: { phase, current: 1, total: 10, pct: 10 },
        connected: true,
        error: null,
      })

      const { unmount } = render(<ScanProgress scanId="test-id" />)
      expect(screen.getByText(label)).toBeInTheDocument()
      unmount()
    }
  })

  it('passes the correct URL to useSSE', () => {
    mockUseSSE.mockReturnValue({
      data: null,
      connected: false,
      error: null,
    })

    render(<ScanProgress scanId="abc-123" />)

    expect(mockUseSSE).toHaveBeenCalledWith('/scan/abc-123/stream')
  })

  it('shows ellipsis when total is zero', () => {
    mockUseSSE.mockReturnValue({
      data: { phase: 'fetch_prices', current: 0, total: 0, pct: 0 },
      connected: true,
      error: null,
    })

    render(<ScanProgress scanId="test-id" />)

    expect(screen.getByText('...')).toBeInTheDocument()
  })
})
