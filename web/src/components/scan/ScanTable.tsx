import { useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
} from '@tanstack/react-table'
import { Badge, Button, Card } from '../common'

export interface TickerScoreRow {
  ticker: string
  score: number
  signals: Record<string, number>
  rank: number
}

interface ScanTableProps {
  data: TickerScoreRow[]
  onDebate: (ticker: string) => void
}

const PAGE_SIZE = 25

const columnHelper = createColumnHelper<TickerScoreRow>()

function getDirection(signals: Record<string, number>): string {
  const rsi = signals['rsi'] ?? 50
  const smaAlignment = signals['sma_alignment'] ?? 0
  const roc = signals['roc'] ?? 0

  // Simple heuristic: count bullish vs bearish signals
  let bullCount = 0
  let bearCount = 0

  if (rsi > 50) bullCount++
  else if (rsi < 50) bearCount++

  if (smaAlignment > 0) bullCount++
  else if (smaAlignment < 0) bearCount++

  if (roc > 0) bullCount++
  else if (roc < 0) bearCount++

  if (bullCount > bearCount) return 'Bullish'
  if (bearCount > bullCount) return 'Bearish'
  return 'Neutral'
}

function getDirectionVariant(
  direction: string,
): 'bullish' | 'bearish' | 'neutral' {
  if (direction === 'Bullish') return 'bullish'
  if (direction === 'Bearish') return 'bearish'
  return 'neutral'
}

function getScoreColor(score: number): string {
  if (score >= 70) return 'var(--color-bull)'
  if (score >= 40) return 'var(--color-risk)'
  return 'var(--color-bear)'
}

export function ScanTable({ data, onDebate }: ScanTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'rank', desc: false },
  ])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [directionFilter, setDirectionFilter] = useState<string>('all')
  const navigate = useNavigate()

  const handleRowClick = useCallback(
    (ticker: string) => {
      navigate(`/ticker/${ticker}`)
    },
    [navigate],
  )

  const handleDebateClick = useCallback(
    (e: React.MouseEvent, ticker: string) => {
      e.stopPropagation()
      onDebate(ticker)
    },
    [onDebate],
  )

  const columns = useMemo(
    () => [
      columnHelper.accessor('rank', {
        header: '#',
        cell: (info) => (
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            {info.getValue()}
          </span>
        ),
        size: 40,
      }),
      columnHelper.accessor('ticker', {
        header: 'Ticker',
        cell: (info) => (
          <span
            className="font-data text-xs font-semibold"
            style={{ color: 'var(--color-text-accent)' }}
          >
            {info.getValue()}
          </span>
        ),
        size: 80,
      }),
      columnHelper.accessor('score', {
        header: 'Score',
        cell: (info) => {
          const value = info.getValue()
          return (
            <span
              className="font-data text-xs font-semibold"
              style={{ color: getScoreColor(value) }}
            >
              {value.toFixed(1)}
            </span>
          )
        },
        size: 70,
      }),
      columnHelper.display({
        id: 'direction',
        header: 'Direction',
        cell: (info) => {
          const dir = getDirection(info.row.original.signals)
          return <Badge variant={getDirectionVariant(dir)}>{dir}</Badge>
        },
        size: 90,
        filterFn: (row, _columnId, filterValue: string) => {
          if (filterValue === 'all') return true
          const dir = getDirection(row.original.signals)
          return dir === filterValue
        },
      }),
      columnHelper.accessor(
        (row) => row.signals['iv_rank'] ?? row.signals['bb_width'] ?? 0,
        {
          id: 'ivRank',
          header: 'IV Rank',
          cell: (info) => (
            <span className="font-data text-xs">
              {info.getValue() > 0 ? info.getValue().toFixed(1) : '--'}
            </span>
          ),
          size: 70,
        },
      ),
      columnHelper.accessor((row) => row.signals['relative_volume'] ?? 0, {
        id: 'volume',
        header: 'Rel Vol',
        cell: (info) => (
          <span className="font-data text-xs">
            {info.getValue() > 0 ? `${info.getValue().toFixed(2)}x` : '--'}
          </span>
        ),
        size: 70,
      }),
      columnHelper.accessor((row) => row.signals['rsi'] ?? 0, {
        id: 'rsi',
        header: 'RSI',
        cell: (info) => {
          const val = info.getValue()
          let rsiColor = 'var(--color-text-primary)'
          if (val >= 70) rsiColor = 'var(--color-bear)'
          else if (val <= 30) rsiColor = 'var(--color-bull)'
          return (
            <span className="font-data text-xs" style={{ color: rsiColor }}>
              {val > 0 ? val.toFixed(1) : '--'}
            </span>
          )
        },
        size: 60,
      }),
      columnHelper.display({
        id: 'actions',
        header: '',
        cell: (info) => (
          <Button
            variant="secondary"
            onClick={(e) => handleDebateClick(e, info.row.original.ticker)}
          >
            DEBATE
          </Button>
        ),
        size: 80,
      }),
    ],
    [handleDebateClick],
  )

  // Apply direction filter
  const filteredData = useMemo(() => {
    if (directionFilter === 'all') return data
    return data.filter((row) => getDirection(row.signals) === directionFilter)
  }, [data, directionFilter])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table is compatible
  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting, columnFilters },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: PAGE_SIZE },
    },
  })

  return (
    <Card title={`Results (${filteredData.length})`}>
      {/* Filter bar */}
      <div
        className="mb-2 flex items-center gap-3 border-b pb-2"
        style={{ borderColor: 'var(--color-border-subtle)' }}
      >
        <span
          className="font-data text-xs uppercase tracking-wider"
          style={{ color: 'var(--color-text-muted)' }}
        >
          Direction:
        </span>
        {['all', 'Bullish', 'Bearish', 'Neutral'].map((filter) => (
          <button
            key={filter}
            onClick={() => setDirectionFilter(filter)}
            className="font-data cursor-pointer border px-2 py-0.5 text-xs transition-opacity hover:opacity-80"
            style={{
              backgroundColor:
                directionFilter === filter
                  ? 'var(--color-bg-hover)'
                  : 'transparent',
              borderColor:
                directionFilter === filter
                  ? 'var(--color-border-strong)'
                  : 'var(--color-border-default)',
              color:
                directionFilter === filter
                  ? 'var(--color-text-primary)'
                  : 'var(--color-text-secondary)',
            }}
          >
            {filter === 'all' ? 'ALL' : filter.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-auto">
        <table className="w-full border-collapse">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={header.column.getToggleSortingHandler()}
                    className="font-data cursor-pointer border-b px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wider select-none"
                    style={{
                      borderColor: 'var(--color-border-default)',
                      color: 'var(--color-text-secondary)',
                      backgroundColor: 'var(--color-bg-secondary)',
                      width: header.getSize(),
                    }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                    {header.column.getIsSorted() === 'asc'
                      ? ' \u25B2'
                      : header.column.getIsSorted() === 'desc'
                        ? ' \u25BC'
                        : ''}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, idx) => (
              <tr
                key={row.id}
                onClick={() => handleRowClick(row.original.ticker)}
                className="cursor-pointer transition-colors"
                style={{
                  backgroundColor:
                    idx % 2 === 0 ? 'transparent' : 'var(--color-bg-secondary)',
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.backgroundColor =
                    'var(--color-bg-hover)')
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.backgroundColor =
                    idx % 2 === 0 ? 'transparent' : 'var(--color-bg-secondary)')
                }
              >
                {row.getVisibleCells().map((cell) => (
                  <td
                    key={cell.id}
                    className="font-data border-b px-2 py-1 text-xs"
                    style={{
                      borderColor: 'var(--color-border-subtle)',
                      color: 'var(--color-text-primary)',
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {table.getPageCount() > 1 && (
        <div
          className="mt-2 flex items-center justify-between border-t pt-2"
          style={{ borderColor: 'var(--color-border-subtle)' }}
        >
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-muted)' }}
          >
            Page {table.getState().pagination.pageIndex + 1} of{' '}
            {table.getPageCount()}
          </span>
          <div className="flex gap-1">
            <Button
              variant="secondary"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              PREV
            </Button>
            <Button
              variant="secondary"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              NEXT
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}
