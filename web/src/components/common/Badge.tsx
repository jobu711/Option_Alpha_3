type BadgeVariant = 'bullish' | 'bearish' | 'neutral' | 'info'

interface BadgeProps {
  variant: BadgeVariant
  children: React.ReactNode
  className?: string
}

const VARIANT_STYLES: Record<
  BadgeVariant,
  { bg: string; color: string }
> = {
  bullish: {
    bg: 'var(--color-bull-muted)',
    color: 'var(--color-bull)',
  },
  bearish: {
    bg: 'var(--color-bear-muted)',
    color: 'var(--color-bear)',
  },
  neutral: {
    bg: 'var(--color-risk-muted)',
    color: 'var(--color-risk)',
  },
  info: {
    bg: 'rgba(59, 130, 246, 0.2)',
    color: 'var(--color-interactive)',
  },
}

export function Badge({ variant, children, className = '' }: BadgeProps) {
  const styles = VARIANT_STYLES[variant]

  return (
    <span
      className={`font-data inline-block px-1.5 py-0.5 text-xs font-semibold uppercase ${className}`}
      style={{
        backgroundColor: styles.bg,
        color: styles.color,
      }}
    >
      {children}
    </span>
  )
}
