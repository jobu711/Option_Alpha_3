import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { DebateDetail } from '../../pages/DebateDetail'
import { sampleCompletedDebate, samplePendingDebate } from './fixtures'

function renderWithRouter(debateId: string = '42') {
  return render(
    <MemoryRouter initialEntries={[`/debate/${debateId}`]}>
      <Routes>
        <Route path="/debate/:id" element={<DebateDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DebateDetail page', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows loading spinner initially', () => {
    // Never resolve to keep loading state
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderWithRouter()
    expect(screen.getByTestId('debate-loading')).toBeInTheDocument()
  })

  it('displays debate data after successful fetch', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => sampleCompletedDebate,
    } as Response)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('debate-view')).toBeInTheDocument()
    })

    expect(screen.getByTestId('verdict-direction')).toHaveTextContent(
      'BULLISH',
    )
    expect(screen.getByTestId('agent-card-bull')).toBeInTheDocument()
    expect(screen.getByTestId('agent-card-bear')).toBeInTheDocument()
    expect(screen.getByTestId('agent-card-risk')).toBeInTheDocument()
  })

  it('shows error message on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
      text: async () => 'Debate not found',
    } as Response)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('debate-error')).toBeInTheDocument()
    })

    expect(
      screen.getByText('FAILED TO LOAD DEBATE'),
    ).toBeInTheDocument()
  })

  it('shows polling indicator for running debates', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => samplePendingDebate,
    } as Response)

    renderWithRouter('44')

    await waitFor(() => {
      expect(screen.getByTestId('debate-polling')).toBeInTheDocument()
    })

    expect(
      screen.getByText(/Debate in progress/),
    ).toBeInTheDocument()
  })

  it('displays trade thesis section for completed debate', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => sampleCompletedDebate,
    } as Response)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('trade-thesis')).toBeInTheDocument()
    })
  })

  it('displays bull-bear meter for completed debate', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => sampleCompletedDebate,
    } as Response)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('bull-bear-meter')).toBeInTheDocument()
    })
  })

  it('renders back button', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => sampleCompletedDebate,
    } as Response)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('debate-view')).toBeInTheDocument()
    })

    const backButton = screen.getByRole('button', { name: /back/i })
    expect(backButton).toBeInTheDocument()
  })
})
