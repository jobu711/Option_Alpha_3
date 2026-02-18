/**
 * Ticker header component displaying symbol, name, price, and change.
 *
 * Shows:
 * - Large ticker symbol + company name
 * - Current price with change ($ and %)
 * - Price change color: green if positive, red if negative
 * - Volume and market cap tier
 * - "Launch Debate" button that calls POST /api/debate/{ticker}
 */
import { useState } from 'react'
import { Button } from '../common'
import type { TickerDetail as TickerDetailData } from '../../types/ticker'
import { api } from '../../api/client'

interface TickerDetailProps {
  detail: TickerDetailData
}

export function TickerDetail({ detail }: TickerDetailProps) {
  const [debateLoading, setDebateLoading] = useState(false)
  const [debateMessage, setDebateMessage] = useState<string | null>(null)

  const { info, quote } = detail
  const lastPrice = parseFloat(quote.last)
  const bidPrice = parseFloat(quote.bid)

  // Approximate change from mid to last (best available without previous close)
  const midPrice = parseFloat(quote.mid)
  const change = lastPrice - midPrice
  const changePercent = midPrice !== 0 ? (change / midPrice) * 100 : 0
  const isPositive = change >= 0

  async function handleLaunchDebate() {
    setDebateLoading(true)
    setDebateMessage(null)
    try {
      await api.debate.start(info.symbol)
      setDebateMessage(`Debate started for ${info.symbol}`)
    } catch {
      setDebateMessage('Failed to start debate')
    } finally {
      setDebateLoading(false)
    }
  }

  return (
    <div
      className="flex flex-wrap items-start justify-between gap-4 border-b pb-3"
      style={{ borderColor: 'var(--color-border-default)' }}
      data-testid="ticker-detail"
    >
      {/* Left: Symbol, name, price */}
      <div className="flex flex-col gap-1">
        <div className="flex items-baseline gap-2">
          <span
            className="font-data text-xl font-bold tracking-wider"
            style={{ color: 'var(--color-text-primary)' }}
            data-testid="ticker-symbol"
          >
            {info.symbol}
          </span>
          <span
            className="text-sm"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {info.name}
          </span>
        </div>

        <div className="flex items-baseline gap-3">
          <span
            className="font-data text-lg font-semibold"
            style={{ color: 'var(--color-text-primary)' }}
            data-testid="ticker-price"
          >
            ${lastPrice.toFixed(2)}
          </span>
          <span
            className="font-data text-sm font-medium"
            style={{
              color: isPositive ? 'var(--color-bull)' : 'var(--color-bear)',
            }}
            data-testid="ticker-change"
          >
            {isPositive ? '+' : ''}
            {change.toFixed(2)} ({isPositive ? '+' : ''}
            {changePercent.toFixed(2)}%)
          </span>
        </div>

        <div className="flex gap-4">
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            VOL: {quote.volume.toLocaleString()}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            BID: ${bidPrice.toFixed(2)}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            ASK: ${parseFloat(quote.ask).toFixed(2)}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            SPREAD: ${parseFloat(quote.spread).toFixed(2)}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            TIER: {info.market_cap_tier.toUpperCase()}
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            SECTOR: {info.sector}
          </span>
        </div>
      </div>

      {/* Right: Launch Debate */}
      <div className="flex flex-col items-end gap-1">
        <Button
          variant="primary"
          onClick={handleLaunchDebate}
          disabled={debateLoading}
        >
          {debateLoading ? 'STARTING...' : 'LAUNCH DEBATE'}
        </Button>
        {debateMessage && (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {debateMessage}
          </span>
        )}
      </div>
    </div>
  )
}
