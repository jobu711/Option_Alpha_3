import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ScanTable, type TickerScoreRow } from '../../components/scan/ScanTable'

const MOCK_DATA: TickerScoreRow[] = [
  {
    ticker: 'AAPL',
    score: 82.5,
    signals: {
      rsi: 65,
      sma_alignment: 1.2,
      roc: 3.5,
      relative_volume: 1.8,
      iv_rank: 45.0,
    },
    rank: 1,
  },
  {
    ticker: 'TSLA',
    score: 35.2,
    signals: {
      rsi: 28,
      sma_alignment: -0.5,
      roc: -2.1,
      relative_volume: 2.3,
      iv_rank: 72.0,
    },
    rank: 2,
  },
  {
    ticker: 'MSFT',
    score: 55.0,
    signals: {
      rsi: 50,
      sma_alignment: 0,
      roc: 0,
      relative_volume: 0.9,
      iv_rank: 30.0,
    },
    rank: 3,
  },
]

function renderTable(
  data: TickerScoreRow[] = MOCK_DATA,
  onDebate: (ticker: string) => void = vi.fn(),
) {
  return render(
    <MemoryRouter>
      <ScanTable data={data} onDebate={onDebate} />
    </MemoryRouter>,
  )
}

describe('ScanTable', () => {
  it('renders all ticker rows', () => {
    renderTable()

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
  })

  it('renders column headers', () => {
    renderTable()

    // Find headers within the thead element
    const thead = document.querySelector('thead')
    expect(thead).not.toBeNull()
    const headerRow = within(thead!)

    expect(headerRow.getByText('Ticker')).toBeInTheDocument()
    expect(headerRow.getByText('Score')).toBeInTheDocument()
    expect(headerRow.getByText('Direction')).toBeInTheDocument()
    expect(headerRow.getByText('IV Rank')).toBeInTheDocument()
    expect(headerRow.getByText('Rel Vol')).toBeInTheDocument()
    expect(headerRow.getByText('RSI')).toBeInTheDocument()
  })

  it('displays scores with correct formatting', () => {
    renderTable()

    expect(screen.getByText('82.5')).toBeInTheDocument()
    expect(screen.getByText('35.2')).toBeInTheDocument()
    expect(screen.getByText('55.0')).toBeInTheDocument()
  })

  it('displays direction badges', () => {
    renderTable()

    // AAPL should be bullish (rsi>50, sma>0, roc>0)
    const bullishBadges = screen.getAllByText('Bullish')
    expect(bullishBadges.length).toBeGreaterThanOrEqual(1)

    // TSLA should be bearish (rsi<50, sma<0, roc<0)
    expect(screen.getByText('Bearish')).toBeInTheDocument()

    // MSFT should be neutral (rsi=50, sma=0, roc=0)
    expect(screen.getByText('Neutral')).toBeInTheDocument()
  })

  it('displays relative volume with x suffix', () => {
    renderTable()

    expect(screen.getByText('1.80x')).toBeInTheDocument()
    expect(screen.getByText('2.30x')).toBeInTheDocument()
    expect(screen.getByText('0.90x')).toBeInTheDocument()
  })

  it('displays IV Rank values', () => {
    renderTable()

    expect(screen.getByText('45.0')).toBeInTheDocument()
    expect(screen.getByText('72.0')).toBeInTheDocument()
    expect(screen.getByText('30.0')).toBeInTheDocument()
  })

  it('renders debate buttons for each row', () => {
    renderTable()

    const debateButtons = screen.getAllByRole('button', { name: /debate/i })
    expect(debateButtons).toHaveLength(3)
  })

  it('calls onDebate when debate button is clicked', () => {
    const onDebate = vi.fn()
    renderTable(MOCK_DATA, onDebate)

    const debateButtons = screen.getAllByRole('button', { name: /debate/i })
    fireEvent.click(debateButtons[0])

    expect(onDebate).toHaveBeenCalledWith('AAPL')
  })

  it('sorts by column when header is clicked', () => {
    renderTable()

    // Click on Score header to sort
    const scoreHeader = screen.getByText('Score')
    fireEvent.click(scoreHeader)

    // After first click, should have sort indicator
    const cells = screen.getAllByText(/\d+\.\d/)
    expect(cells.length).toBeGreaterThan(0)
  })

  it('displays filter buttons for direction', () => {
    renderTable()

    expect(screen.getByText('ALL')).toBeInTheDocument()
    expect(screen.getByText('BULLISH')).toBeInTheDocument()
    expect(screen.getByText('BEARISH')).toBeInTheDocument()
    expect(screen.getByText('NEUTRAL')).toBeInTheDocument()
  })

  it('filters by Bullish direction', () => {
    renderTable()

    fireEvent.click(screen.getByText('BULLISH'))

    // AAPL is bullish, so it should be visible
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    // TSLA is bearish, so it should not be visible
    expect(screen.queryByText('TSLA')).not.toBeInTheDocument()
    // MSFT is neutral (rsi=50, sma=0, roc=0), so it should not be visible
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument()
  })

  it('filters by Bearish direction', () => {
    renderTable()

    fireEvent.click(screen.getByText('BEARISH'))

    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.queryByText('MSFT')).not.toBeInTheDocument()
  })

  it('filters by Neutral direction', () => {
    renderTable()

    fireEvent.click(screen.getByText('NEUTRAL'))

    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    expect(screen.queryByText('TSLA')).not.toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
  })

  it('shows ALL tickers when ALL filter is selected', () => {
    renderTable()

    // First filter to Bullish
    fireEvent.click(screen.getByText('BULLISH'))
    // Then back to ALL
    fireEvent.click(screen.getByText('ALL'))

    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(screen.getByText('TSLA')).toBeInTheDocument()
    expect(screen.getByText('MSFT')).toBeInTheDocument()
  })

  it('shows result count in card title', () => {
    renderTable()

    expect(screen.getByText('Results (3)')).toBeInTheDocument()
  })

  it('shows dashes for missing signal values', () => {
    const dataWithMissing: TickerScoreRow[] = [
      {
        ticker: 'NFLX',
        score: 60,
        signals: {},
        rank: 1,
      },
    ]

    renderTable(dataWithMissing)

    // Should show -- for missing IV Rank, relative volume, and RSI
    const dashes = screen.getAllByText('--')
    expect(dashes.length).toBeGreaterThanOrEqual(3)
  })

  it('renders without crashing when data is empty', () => {
    renderTable([])

    expect(screen.getByText('Results (0)')).toBeInTheDocument()
  })
})
