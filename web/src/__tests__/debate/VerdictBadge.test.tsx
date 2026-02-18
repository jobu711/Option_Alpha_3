import { render, screen } from '@testing-library/react'
import { VerdictBadge } from '../../components/debate/VerdictBadge'

describe('VerdictBadge', () => {
  it('displays BULLISH direction label', () => {
    render(<VerdictBadge direction="bullish" conviction={0.75} />)
    expect(screen.getByTestId('verdict-direction')).toHaveTextContent('BULLISH')
  })

  it('displays BEARISH direction label', () => {
    render(<VerdictBadge direction="bearish" conviction={0.6} />)
    expect(screen.getByTestId('verdict-direction')).toHaveTextContent('BEARISH')
  })

  it('displays NEUTRAL direction label', () => {
    render(<VerdictBadge direction="neutral" conviction={0.5} />)
    expect(screen.getByTestId('verdict-direction')).toHaveTextContent('NEUTRAL')
  })

  it('displays conviction as percentage', () => {
    render(<VerdictBadge direction="bullish" conviction={0.82} />)
    expect(screen.getByTestId('verdict-conviction')).toHaveTextContent('82%')
  })

  it('rounds conviction percentage to integer', () => {
    render(<VerdictBadge direction="bearish" conviction={0.667} />)
    expect(screen.getByTestId('verdict-conviction')).toHaveTextContent('67%')
  })

  it('does not show fallback badge by default', () => {
    render(<VerdictBadge direction="bullish" conviction={0.7} />)
    expect(screen.queryByTestId('verdict-fallback')).not.toBeInTheDocument()
  })

  it('shows Data-Driven Fallback badge when isFallback is true', () => {
    render(
      <VerdictBadge direction="bullish" conviction={0.7} isFallback={true} />,
    )
    expect(screen.getByTestId('verdict-fallback')).toHaveTextContent(
      'Data-Driven Fallback',
    )
  })

  it('applies green background for bullish', () => {
    render(<VerdictBadge direction="bullish" conviction={0.7} />)
    const badge = screen.getByTestId('verdict-badge')
    expect(badge.style.backgroundColor).toBe('var(--color-bull)')
  })

  it('applies red background for bearish', () => {
    render(<VerdictBadge direction="bearish" conviction={0.6} />)
    const badge = screen.getByTestId('verdict-badge')
    expect(badge.style.backgroundColor).toBe('var(--color-bear)')
  })

  it('applies amber background for neutral', () => {
    render(<VerdictBadge direction="neutral" conviction={0.5} />)
    const badge = screen.getByTestId('verdict-badge')
    expect(badge.style.backgroundColor).toBe('var(--color-risk)')
  })
})
