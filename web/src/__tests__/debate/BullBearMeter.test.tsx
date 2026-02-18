import { render, screen } from '@testing-library/react'
import { BullBearMeter } from '../../components/charts/BullBearMeter'

describe('BullBearMeter', () => {
  it('renders the meter container', () => {
    render(<BullBearMeter direction="bullish" conviction={0.7} />)
    expect(screen.getByTestId('bull-bear-meter')).toBeInTheDocument()
  })

  it('displays conviction percentage for bullish', () => {
    render(<BullBearMeter direction="bullish" conviction={0.75} />)
    expect(screen.getByTestId('meter-score')).toHaveTextContent('75%')
  })

  it('displays conviction percentage for bearish', () => {
    render(<BullBearMeter direction="bearish" conviction={0.6} />)
    expect(screen.getByTestId('meter-score')).toHaveTextContent('60%')
  })

  it('shows "Strongly Bullish" label for high bullish conviction', () => {
    render(<BullBearMeter direction="bullish" conviction={0.9} />)
    expect(screen.getByText('Strongly Bullish')).toBeInTheDocument()
  })

  it('shows "Bullish" label for moderate bullish conviction', () => {
    render(<BullBearMeter direction="bullish" conviction={0.3} />)
    expect(screen.getByText('Bullish')).toBeInTheDocument()
  })

  it('shows "Neutral" label for neutral direction', () => {
    render(<BullBearMeter direction="neutral" conviction={0.5} />)
    expect(screen.getByText('Neutral')).toBeInTheDocument()
  })

  it('shows "Bearish" label for moderate bearish conviction', () => {
    render(<BullBearMeter direction="bearish" conviction={0.3} />)
    expect(screen.getByText('Bearish')).toBeInTheDocument()
  })

  it('shows "Strongly Bearish" label for high bearish conviction', () => {
    render(<BullBearMeter direction="bearish" conviction={0.9} />)
    expect(screen.getByText('Strongly Bearish')).toBeInTheDocument()
  })

  it('has accessible aria-label on the SVG', () => {
    render(<BullBearMeter direction="bullish" conviction={0.82} />)
    const svg = screen.getByRole('img')
    expect(svg).toHaveAttribute(
      'aria-label',
      'Bull Bear Meter: bullish with 82% conviction',
    )
  })

  it('renders BEAR and BULL labels in the gauge', () => {
    render(<BullBearMeter direction="neutral" conviction={0.5} />)
    // SVG text elements
    expect(screen.getByText('BEAR')).toBeInTheDocument()
    expect(screen.getByText('BULL')).toBeInTheDocument()
  })
})
