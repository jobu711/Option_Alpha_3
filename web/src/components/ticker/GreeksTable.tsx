/**
 * Greeks table displaying option contracts with their Greeks.
 *
 * Columns: Strike, Type, DTE, Delta, Gamma, Theta, Vega, Rho, Bid, Ask, Volume, OI
 * - Sortable by any column via the common Table component
 * - Dollar-impact formatting for theta/vega
 * - Monospace font for all data cells
 */
import { type ColumnDef } from '@tanstack/react-table'
import { Table } from '../common'
import type { OptionContract } from '../../types/ticker'

/** Format a number as dollar impact (e.g., "-$0.08/day") */
function formatDollarImpact(value: number, suffix: string): string {
  const sign = value < 0 ? '-' : ''
  return `${sign}$${Math.abs(value).toFixed(4)}${suffix}`
}

const columns: ColumnDef<OptionContract, unknown>[] = [
  {
    accessorKey: 'strike',
    header: 'Strike',
    cell: (info) => `$${parseFloat(info.getValue() as string).toFixed(2)}`,
  },
  {
    accessorKey: 'option_type',
    header: 'Type',
    cell: (info) => (info.getValue() as string).toUpperCase(),
  },
  {
    accessorKey: 'dte',
    header: 'DTE',
  },
  {
    accessorFn: (row) => row.greeks?.delta ?? null,
    id: 'delta',
    header: 'Delta',
    cell: (info) => {
      const v = info.getValue() as number | null
      return v !== null ? v.toFixed(4) : 'N/A'
    },
  },
  {
    accessorFn: (row) => row.greeks?.gamma ?? null,
    id: 'gamma',
    header: 'Gamma',
    cell: (info) => {
      const v = info.getValue() as number | null
      return v !== null ? v.toFixed(4) : 'N/A'
    },
  },
  {
    accessorFn: (row) => row.greeks?.theta ?? null,
    id: 'theta',
    header: 'Theta',
    cell: (info) => {
      const v = info.getValue() as number | null
      if (v === null) return 'N/A'
      return (
        <span
          style={{ color: v < 0 ? 'var(--color-bear)' : 'var(--color-bull)' }}
        >
          {formatDollarImpact(v, '/day')}
        </span>
      )
    },
  },
  {
    accessorFn: (row) => row.greeks?.vega ?? null,
    id: 'vega',
    header: 'Vega',
    cell: (info) => {
      const v = info.getValue() as number | null
      if (v === null) return 'N/A'
      return (
        <span style={{ color: 'var(--color-text-accent)' }}>
          {formatDollarImpact(v, '/1%IV')}
        </span>
      )
    },
  },
  {
    accessorFn: (row) => row.greeks?.rho ?? null,
    id: 'rho',
    header: 'Rho',
    cell: (info) => {
      const v = info.getValue() as number | null
      return v !== null ? v.toFixed(4) : 'N/A'
    },
  },
  {
    accessorKey: 'bid',
    header: 'Bid',
    cell: (info) => `$${parseFloat(info.getValue() as string).toFixed(2)}`,
  },
  {
    accessorKey: 'ask',
    header: 'Ask',
    cell: (info) => `$${parseFloat(info.getValue() as string).toFixed(2)}`,
  },
  {
    accessorKey: 'volume',
    header: 'Volume',
    cell: (info) => (info.getValue() as number).toLocaleString(),
  },
  {
    accessorKey: 'open_interest',
    header: 'OI',
    cell: (info) => (info.getValue() as number).toLocaleString(),
  },
]

interface GreeksTableProps {
  contracts: OptionContract[]
}

export function GreeksTable({ contracts }: GreeksTableProps) {
  if (contracts.length === 0) {
    return (
      <div className="flex items-center justify-center py-6">
        <span
          className="font-data text-xs"
          style={{ color: 'var(--color-text-muted)' }}
        >
          No option contracts available
        </span>
      </div>
    )
  }

  return <Table data={contracts} columns={columns} />
}
