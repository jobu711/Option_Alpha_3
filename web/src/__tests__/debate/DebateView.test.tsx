import { render, screen } from '@testing-library/react'
import { DebateView } from '../../components/debate/DebateView'
import {
  sampleCompletedDebate,
  sampleBearishDebate,
  sampleFallbackDebate,
  samplePendingDebate,
} from './fixtures'

describe('DebateView', () => {
  it('renders three agent columns', () => {
    render(<DebateView debate={sampleCompletedDebate} />)
    expect(screen.getByTestId('agent-columns')).toBeInTheDocument()
    expect(screen.getByTestId('agent-card-bull')).toBeInTheDocument()
    expect(screen.getByTestId('agent-card-bear')).toBeInTheDocument()
    expect(screen.getByTestId('agent-card-risk')).toBeInTheDocument()
  })

  it('renders verdict badge for completed debate', () => {
    render(<DebateView debate={sampleCompletedDebate} />)
    expect(screen.getByTestId('verdict-badge')).toBeInTheDocument()
    expect(screen.getByTestId('verdict-direction')).toHaveTextContent('BULLISH')
  })

  it('marks bull as winner when direction is bullish', () => {
    render(<DebateView debate={sampleCompletedDebate} />)
    const bullCard = screen.getByTestId('agent-card-bull')
    expect(bullCard.style.borderColor).toBe('var(--color-bull)')
    expect(screen.getByText('Winner')).toBeInTheDocument()
  })

  it('marks bear as winner when direction is bearish', () => {
    render(<DebateView debate={sampleBearishDebate} />)
    const bearCard = screen.getByTestId('agent-card-bear')
    expect(bearCard.style.borderColor).toBe('var(--color-bear)')
  })

  it('shows fallback badge for data-driven debates', () => {
    render(<DebateView debate={sampleFallbackDebate} />)
    expect(screen.getByTestId('verdict-fallback')).toHaveTextContent(
      'Data-Driven Fallback',
    )
  })

  it('does not render verdict badge when thesis is null', () => {
    render(<DebateView debate={samplePendingDebate} />)
    expect(screen.queryByTestId('verdict-badge')).not.toBeInTheDocument()
  })

  it('renders awaiting messages for pending agents', () => {
    render(<DebateView debate={samplePendingDebate} />)
    const awaitingMessages = screen.getAllByText('Awaiting analysis...')
    expect(awaitingMessages).toHaveLength(3)
  })
})
