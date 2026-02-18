import { useState } from 'react'
import type { FormEvent } from 'react'
import { Button } from '../common'

interface AddTickerModalProps {
  onAdd: (ticker: string) => Promise<void>
  disabled: boolean
}

export function AddTickerModal({ onAdd, disabled }: AddTickerModalProps) {
  const [ticker, setTicker] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const normalized = ticker.trim().toUpperCase()

    if (!normalized) {
      setError('Ticker symbol is required.')
      return
    }

    if (!/^[A-Z]{1,5}$/.test(normalized)) {
      setError('Invalid ticker: 1-5 uppercase letters.')
      return
    }

    setError(null)
    setSubmitting(true)

    try {
      await onAdd(normalized)
      setTicker('')
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to add ticker'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="flex items-end gap-2"
      data-testid="add-ticker-form"
    >
      <div className="flex flex-col gap-1">
        <label
          htmlFor="add-ticker-input"
          className="font-data text-xs uppercase tracking-wider"
          style={{ color: 'var(--color-text-secondary)' }}
        >
          Add Ticker
        </label>
        <input
          id="add-ticker-input"
          type="text"
          placeholder="AAPL"
          value={ticker}
          onChange={(e) => {
            setTicker(e.target.value)
            setError(null)
          }}
          disabled={disabled || submitting}
          className="font-data w-28 border px-2 py-1 text-xs uppercase"
          style={{
            backgroundColor: 'var(--color-bg-elevated)',
            borderColor: error
              ? 'var(--color-bear)'
              : 'var(--color-border-default)',
            color: 'var(--color-text-primary)',
          }}
          maxLength={5}
        />
        {error && (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-bear)' }}
            data-testid="add-ticker-error"
          >
            {error}
          </span>
        )}
      </div>
      <Button
        type="submit"
        variant="primary"
        disabled={disabled || submitting}
      >
        {submitting ? 'ADDING...' : 'ADD'}
      </Button>
    </form>
  )
}
