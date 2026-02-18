import type { DebateResult } from '../../types/debate'
import { AgentCard } from './AgentCard'
import { VerdictBadge } from './VerdictBadge'

interface DebateViewProps {
  debate: DebateResult
  className?: string
}

export function DebateView({ debate, className = '' }: DebateViewProps) {
  const thesis = debate.thesis
  const winnerRole =
    thesis?.direction === 'bullish'
      ? 'bull'
      : thesis?.direction === 'bearish'
        ? 'bear'
        : null

  return (
    <div className={`flex flex-col gap-4 ${className}`} data-testid="debate-view">
      {/* Verdict banner */}
      {thesis && (
        <VerdictBadge
          direction={thesis.direction}
          conviction={thesis.conviction}
          isFallback={debate.is_fallback}
        />
      )}

      {/* Three-column agent layout */}
      <div
        className="grid grid-cols-1 gap-3 lg:grid-cols-3"
        data-testid="agent-columns"
      >
        <AgentCard
          role="bull"
          response={debate.agents.bull}
          isWinner={winnerRole === 'bull'}
        />
        <AgentCard
          role="bear"
          response={debate.agents.bear}
          isWinner={winnerRole === 'bear'}
        />
        <AgentCard
          role="risk"
          response={debate.agents.risk}
        />
      </div>
    </div>
  )
}
