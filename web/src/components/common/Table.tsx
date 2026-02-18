import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'

interface TableProps<TData> {
  data: TData[]
  columns: ColumnDef<TData, unknown>[]
}

export function Table<TData>({ data, columns }: TableProps<TData>) {
  const [sorting, setSorting] = useState<SortingState>([])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table is compatible
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
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
                  }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                  {header.column.getIsSorted() === 'asc'
                    ? ' ^'
                    : header.column.getIsSorted() === 'desc'
                      ? ' v'
                      : ''}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="transition-colors"
              style={{ backgroundColor: 'transparent' }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.backgroundColor =
                  'var(--color-bg-hover)')
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.backgroundColor = 'transparent')
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
  )
}
