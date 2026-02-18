import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button, Card } from '../common'

export interface ScanConfigValues {
  topN: number
  tickers: string[]
}

interface ScanConfigProps {
  onStartScan: (config: ScanConfigValues) => void
  disabled: boolean
}

const DEFAULT_TOP_N = 10
const MIN_TOP_N = 1
const MAX_TOP_N = 100

export function ScanConfig({ onStartScan, disabled }: ScanConfigProps) {
  const [topN, setTopN] = useState<number>(DEFAULT_TOP_N)
  const [tickerInput, setTickerInput] = useState<string>('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const tickers = tickerInput
      .split(',')
      .map((t) => t.trim().toUpperCase())
      .filter((t) => t.length > 0)

    onStartScan({ topN, tickers })
  }

  return (
    <Card title="Scan Configuration">
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-4">
          {/* Top N tickers */}
          <div className="flex flex-col gap-1">
            <label
              htmlFor="scan-top-n"
              className="font-data text-xs uppercase tracking-wider"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Top N
            </label>
            <input
              id="scan-top-n"
              type="number"
              min={MIN_TOP_N}
              max={MAX_TOP_N}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              disabled={disabled}
              className="font-data w-20 border px-2 py-1 text-xs"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                borderColor: 'var(--color-border-default)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          {/* Custom tickers */}
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label
              htmlFor="scan-tickers"
              className="font-data text-xs uppercase tracking-wider"
              style={{ color: 'var(--color-text-secondary)' }}
            >
              Custom Tickers (comma-separated, leave blank for full universe)
            </label>
            <input
              id="scan-tickers"
              type="text"
              placeholder="AAPL, MSFT, TSLA"
              value={tickerInput}
              onChange={(e) => setTickerInput(e.target.value)}
              disabled={disabled}
              className="font-data w-full border px-2 py-1 text-xs"
              style={{
                backgroundColor: 'var(--color-bg-elevated)',
                borderColor: 'var(--color-border-default)',
                color: 'var(--color-text-primary)',
              }}
            />
          </div>

          {/* Submit button */}
          <Button type="submit" variant="primary" disabled={disabled}>
            {disabled ? 'SCANNING...' : 'START SCAN'}
          </Button>
        </div>
      </form>
    </Card>
  )
}
