import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { DebateTimeline } from '../../components/ticker/DebateTimeline'
import type { DebateHistoryEntry } from '../../types/ticker'

const mockDebates: DebateHistoryEntry[] = [
  {
    id: 1,
    ticker: 'AAPL',
    direction: 'bullish',
    conviction: 0.75,
    created_at: '2024-06-15T14:30:00Z',
  },
  {
    id: 2,
    ticker: 'AAPL',
    direction: 'bearish',
    conviction: 0.6,
    created_at: '2024-06-10T10:00:00Z',
  },
  {
    id: 3,
    ticker: 'AAPL',
    direction: 'neutral',
    conviction: 0.45,
    created_at: '2024-06-05T09:15:00Z',
  },
]

function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('DebateTimeline', () => {
  it('renders empty state when no debates', () => {
    renderWithRouter(<DebateTimeline debates={[]} />)
    expect(
      screen.getByText('No debates for this ticker yet'),
    ).toBeInTheDocument()
  })

  it('renders debate entries', () => {
    renderWithRouter(<DebateTimeline debates={mockDebates} />)
    expect(screen.getByTestId('debate-timeline')).toBeInTheDocument()
    expect(screen.getByText('BULLISH')).toBeInTheDocument()
    expect(screen.getByText('BEARISH')).toBeInTheDocument()
    expect(screen.getByText('NEUTRAL')).toBeInTheDocument()
  })

  it('renders conviction scores as percentages', () => {
    renderWithRouter(<DebateTimeline debates={mockDebates} />)
    expect(screen.getByText('75%')).toBeInTheDocument()
    expect(screen.getByText('60%')).toBeInTheDocument()
    expect(screen.getByText('45%')).toBeInTheDocument()
  })

  it('renders clickable entries', () => {
    renderWithRouter(<DebateTimeline debates={mockDebates} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(3)
  })
})
