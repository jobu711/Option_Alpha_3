import { render, screen } from '@testing-library/react'
import { AgentCard } from '../../components/debate/AgentCard'
import {
  sampleBullResponse,
  sampleBearResponse,
  sampleRiskResponse,
} from './fixtures'

describe('AgentCard', () => {
  describe('with response data', () => {
    it('displays the bull role label', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(screen.getByTestId('agent-role-bull')).toHaveTextContent('BULL')
    })

    it('displays the bear role label', () => {
      render(<AgentCard role="bear" response={sampleBearResponse} />)
      expect(screen.getByTestId('agent-role-bear')).toHaveTextContent('BEAR')
    })

    it('displays the risk role label', () => {
      render(<AgentCard role="risk" response={sampleRiskResponse} />)
      expect(screen.getByTestId('agent-role-risk')).toHaveTextContent('RISK')
    })

    it('renders the analysis text', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(screen.getByTestId('agent-analysis-bull')).toHaveTextContent(
        'AAPL shows strong bullish momentum',
      )
    })

    it('renders key points as list items', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(
        screen.getByText('RSI at 62 — bullish but not overbought'),
      ).toBeInTheDocument()
      expect(
        screen.getByText('Positive MACD crossover confirmed'),
      ).toBeInTheDocument()
    })

    it('renders contracts referenced', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(
        screen.getByText('AAPL 2024-03-15 185C'),
      ).toBeInTheDocument()
      expect(
        screen.getByText('AAPL 2024-03-15 190C'),
      ).toBeInTheDocument()
    })

    it('renders greeks when present', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(screen.getByText(/delta: 0\.450/)).toBeInTheDocument()
      expect(screen.getByText(/gamma: 0\.032/)).toBeInTheDocument()
    })

    it('displays model name', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(screen.getByText('llama3.1:8b')).toBeInTheDocument()
    })

    it('displays token usage', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      // Total tokens: 1250 + 480 = 1730
      expect(screen.getByText('Tokens: 1730')).toBeInTheDocument()
    })

    it('shows conviction bar fill', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      const fill = screen.getByTestId('conviction-bar-fill')
      expect(fill.style.width).toBe('78%')
    })
  })

  describe('winner state', () => {
    it('shows Winner badge when isWinner is true', () => {
      render(
        <AgentCard role="bull" response={sampleBullResponse} isWinner={true} />,
      )
      expect(screen.getByText('Winner')).toBeInTheDocument()
    })

    it('does not show Winner badge by default', () => {
      render(<AgentCard role="bull" response={sampleBullResponse} />)
      expect(screen.queryByText('Winner')).not.toBeInTheDocument()
    })

    it('applies accent border color when winner', () => {
      render(
        <AgentCard role="bull" response={sampleBullResponse} isWinner={true} />,
      )
      const card = screen.getByTestId('agent-card-bull')
      expect(card.style.borderColor).toBe('var(--color-bull)')
    })
  })

  describe('null response (awaiting)', () => {
    it('renders awaiting message when response is null', () => {
      render(<AgentCard role="bull" response={null} />)
      expect(screen.getByText('Awaiting analysis...')).toBeInTheDocument()
    })

    it('still renders the card with correct testid', () => {
      render(<AgentCard role="bear" response={null} />)
      expect(screen.getByTestId('agent-card-bear')).toBeInTheDocument()
    })
  })
})
