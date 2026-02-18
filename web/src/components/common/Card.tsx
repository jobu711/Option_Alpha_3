import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  children: ReactNode
  className?: string
}

export function Card({ title, children, className = '' }: CardProps) {
  return (
    <div
      className={`border ${className}`}
      style={{
        backgroundColor: 'var(--color-bg-card)',
        borderColor: 'var(--color-border-default)',
      }}
    >
      {title && (
        <div
          className="border-b px-3 py-1.5"
          style={{ borderColor: 'var(--color-border-default)' }}
        >
          <h3
            className="font-data text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {title}
          </h3>
        </div>
      )}
      <div className="p-3">{children}</div>
    </div>
  )
}
