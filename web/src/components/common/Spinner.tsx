interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZES: Record<string, string> = {
  sm: 'h-3 w-3 border',
  md: 'h-5 w-5 border-2',
  lg: 'h-8 w-8 border-2',
}

export function Spinner({ size = 'md', className = '' }: SpinnerProps) {
  return (
    <div
      className={`animate-spin rounded-full border-solid ${SIZES[size]} ${className}`}
      style={{
        borderColor: 'var(--color-border-default)',
        borderTopColor: 'var(--color-interactive)',
      }}
      role="status"
      aria-label="Loading"
    />
  )
}
