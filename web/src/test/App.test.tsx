import { render, screen, waitFor } from '@testing-library/react'
import App from '../App'

describe('App', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    // Mock fetch for Dashboard API calls to prevent errors
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () =>
        new Promise((resolve) =>
          resolve({
            ok: true,
            status: 200,
            json: async () => [],
            text: async () => '',
          } as Response),
        ),
    )
  })

  it('renders the dashboard page title in the top bar', async () => {
    render(<App />)
    // Wait for lazy-loaded Dashboard to render
    await waitFor(() => {
      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toHaveTextContent('Dashboard')
    })
  })

  it('renders the sidebar brand', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('OPTION ALPHA')).toBeInTheDocument()
    })
  })

  it('renders navigation links in the sidebar', async () => {
    render(<App />)
    await waitFor(() => {
      const navLinks = screen.getAllByRole('link')
      const navTexts = navLinks.map((link) => link.textContent?.trim())
      expect(navTexts).toContain('DDashboard')
      expect(navTexts).toContain('SScan')
      expect(navTexts).toContain('WWatchlist')
      expect(navTexts).toContain('UUniverse')
      expect(navTexts).toContain('GSettings')
    })
  })
})
