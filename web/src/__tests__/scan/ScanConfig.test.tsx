import { render, screen, fireEvent } from '@testing-library/react'
import { ScanConfig } from '../../components/scan/ScanConfig'

describe('ScanConfig', () => {
  it('renders the form with default values', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={false} />)

    expect(screen.getByLabelText(/top n/i)).toHaveValue(10)
    expect(screen.getByPlaceholderText(/AAPL, MSFT, TSLA/i)).toHaveValue('')
    expect(screen.getByRole('button', { name: /start scan/i })).toBeEnabled()
  })

  it('disables inputs and button when disabled prop is true', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={true} />)

    expect(screen.getByLabelText(/top n/i)).toBeDisabled()
    expect(screen.getByPlaceholderText(/AAPL, MSFT, TSLA/i)).toBeDisabled()
    expect(screen.getByRole('button', { name: /scanning/i })).toBeDisabled()
  })

  it('shows SCANNING... text when disabled', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={true} />)

    expect(screen.getByRole('button', { name: /scanning/i })).toHaveTextContent(
      'SCANNING...',
    )
  })

  it('calls onStartScan with default config when submitted empty', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={false} />)

    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    expect(onStartScan).toHaveBeenCalledWith({
      topN: 10,
      tickers: [],
    })
  })

  it('parses comma-separated tickers and uppercases them', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={false} />)

    const tickerInput = screen.getByPlaceholderText(/AAPL, MSFT, TSLA/i)
    fireEvent.change(tickerInput, {
      target: { value: 'aapl, msft, tsla' },
    })
    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    expect(onStartScan).toHaveBeenCalledWith({
      topN: 10,
      tickers: ['AAPL', 'MSFT', 'TSLA'],
    })
  })

  it('allows changing the top N value', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={false} />)

    const topNInput = screen.getByLabelText(/top n/i)
    fireEvent.change(topNInput, { target: { value: '25' } })
    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    expect(onStartScan).toHaveBeenCalledWith({
      topN: 25,
      tickers: [],
    })
  })

  it('filters out empty strings from ticker input', () => {
    const onStartScan = vi.fn()
    render(<ScanConfig onStartScan={onStartScan} disabled={false} />)

    const tickerInput = screen.getByPlaceholderText(/AAPL, MSFT, TSLA/i)
    fireEvent.change(tickerInput, {
      target: { value: 'AAPL, , , MSFT,' },
    })
    fireEvent.click(screen.getByRole('button', { name: /start scan/i }))

    expect(onStartScan).toHaveBeenCalledWith({
      topN: 10,
      tickers: ['AAPL', 'MSFT'],
    })
  })
})
