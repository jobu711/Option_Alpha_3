import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Settings } from '../../pages/Settings'

function renderSettings() {
  return render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  )
}

const mockSettings = {
  ollama_endpoint: 'http://localhost:11434',
  ollama_model: 'llama3.1:8b',
  scan_top_n: 10,
  scan_min_volume: 100,
  default_dte_min: 20,
  default_dte_max: 60,
}

describe('Settings page', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the page title', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderSettings()
    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toHaveTextContent('Settings')
  })

  it('shows loading spinner while fetching', () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      () => new Promise(() => {}),
    )
    renderSettings()
    expect(screen.getByText(/loading settings/i)).toBeInTheDocument()
  })

  it('displays settings form after loading', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByLabelText(/endpoint/i)).toBeInTheDocument()
    })

    expect(screen.getByLabelText(/model/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/top n/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/min volume/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/dte min/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/dte max/i)).toBeInTheDocument()
  })

  it('populates fields with fetched values', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByLabelText(/endpoint/i)).toHaveValue(
        'http://localhost:11434',
      )
    })

    expect(screen.getByLabelText(/model/i)).toHaveValue('llama3.1:8b')
    // Number inputs return numeric values
    expect(screen.getByLabelText(/top n/i)).toHaveValue(10)
    expect(screen.getByLabelText(/min volume/i)).toHaveValue(100)
    expect(screen.getByLabelText(/dte min/i)).toHaveValue(20)
    expect(screen.getByLabelText(/dte max/i)).toHaveValue(60)
  })

  it('renders save and reset buttons', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /save settings/i }),
      ).toBeInTheDocument()
    })

    expect(
      screen.getByRole('button', { name: /reset to defaults/i }),
    ).toBeInTheDocument()
  })

  it('allows changing field values', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByLabelText(/model/i)).toBeInTheDocument()
    })

    const modelInput = screen.getByLabelText(/model/i)
    fireEvent.change(modelInput, { target: { value: 'llama3.2:8b' } })
    expect(modelInput).toHaveValue('llama3.2:8b')
  })

  it('saves settings on save button click', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    // First call: GET settings
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /save settings/i }),
      ).toBeInTheDocument()
    })

    // Second call: PUT settings
    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    fireEvent.click(screen.getByRole('button', { name: /save settings/i }))

    await waitFor(() => {
      expect(screen.getByTestId('settings-success')).toHaveTextContent(
        'Settings saved successfully.',
      )
    })
  })

  it('resets to default values on reset button click', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        ...mockSettings,
        ollama_model: 'custom-model',
        scan_top_n: 25,
      }),
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(screen.getByLabelText(/model/i)).toHaveValue('custom-model')
    })

    fireEvent.click(
      screen.getByRole('button', { name: /reset to defaults/i }),
    )

    expect(screen.getByLabelText(/model/i)).toHaveValue('llama3.1:8b')
    expect(screen.getByLabelText(/top n/i)).toHaveValue(10)
  })

  it('shows error on fetch failure', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(
      new Error('Connection refused'),
    )

    renderSettings()

    await waitFor(() => {
      expect(
        screen.getByText(/Connection refused/i),
      ).toBeInTheDocument()
    })
  })

  it('shows error on save failure', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    fetchSpy.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockSettings,
    } as Response)

    renderSettings()

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /save settings/i }),
      ).toBeInTheDocument()
    })

    fetchSpy.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      text: async () => 'Server error',
    } as Response)

    fireEvent.click(screen.getByRole('button', { name: /save settings/i }))

    await waitFor(() => {
      expect(screen.getByText(/Server error/i)).toBeInTheDocument()
    })
  })
})
