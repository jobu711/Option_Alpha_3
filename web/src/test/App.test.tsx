import { render, screen } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  it('renders the dashboard page title in the top bar', () => {
    render(<App />)
    // The TopBar renders an h1 with the page title
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Dashboard')
  })

  it('renders the sidebar brand', () => {
    render(<App />)
    expect(screen.getByText('OPTION ALPHA')).toBeInTheDocument()
  })

  it('renders navigation links in the sidebar', () => {
    render(<App />)
    // Navigation links are <a> elements
    const navLinks = screen.getAllByRole('link')
    const navTexts = navLinks.map((link) => link.textContent?.trim())
    expect(navTexts).toContain('DDashboard')
    expect(navTexts).toContain('SScan')
    expect(navTexts).toContain('WWatchlist')
    expect(navTexts).toContain('UUniverse')
    expect(navTexts).toContain('GSettings')
  })
})
