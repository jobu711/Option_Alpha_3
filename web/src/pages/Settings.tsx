import { useCallback, useEffect, useState } from 'react'
import { PageShell } from '../components/layout'
import { Button, Card, Spinner } from '../components/common'
import { api } from '../api/client'
import type { WebSettings } from '../api/client'

const DEFAULT_SETTINGS: WebSettings = {
  ollama_endpoint: 'http://localhost:11434',
  ollama_model: 'llama3.1:8b',
  scan_top_n: 10,
  scan_min_volume: 100,
  default_dte_min: 20,
  default_dte_max: 60,
}

export function Settings() {
  const [settings, setSettings] = useState<WebSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    document.title = 'Settings | Option Alpha'
    return () => {
      document.title = 'Option Alpha'
    }
  }, [])

  const fetchSettings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.settings.get()
      setSettings(data)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to load settings'
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchSettings()
  }, [fetchSettings])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const saved = await api.settings.update(settings)
      setSettings(saved)
      setSuccess('Settings saved successfully.')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Failed to save settings'
      setError(message)
    } finally {
      setSaving(false)
    }
  }, [settings])

  const handleReset = useCallback(() => {
    setSettings(DEFAULT_SETTINGS)
    setError(null)
    setSuccess(null)
  }, [])

  function updateField<K extends keyof WebSettings>(
    field: K,
    value: WebSettings[K],
  ) {
    setSettings((prev) => ({ ...prev, [field]: value }))
    setSuccess(null)
  }

  return (
    <PageShell title="Settings">
      <div className="flex flex-col gap-3">
        {/* Status messages */}
        {error && (
          <Card>
            <div className="flex items-center justify-between">
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-bear)' }}
              >
                {error}
              </span>
              <Button variant="secondary" onClick={() => setError(null)}>
                DISMISS
              </Button>
            </div>
          </Card>
        )}

        {success && (
          <Card>
            <span
              className="font-data text-xs"
              style={{ color: 'var(--color-bull)' }}
              data-testid="settings-success"
            >
              {success}
            </span>
          </Card>
        )}

        {loading && (
          <Card>
            <div className="flex items-center justify-center gap-2 py-8">
              <Spinner size="md" />
              <span
                className="font-data text-xs"
                style={{ color: 'var(--color-text-secondary)' }}
              >
                Loading settings...
              </span>
            </div>
          </Card>
        )}

        {!loading && (
          <>
            {/* Ollama Settings */}
            <Card title="Ollama Configuration">
              <div className="flex flex-col gap-3">
                <SettingsField
                  id="ollama-endpoint"
                  label="Endpoint"
                  type="text"
                  value={settings.ollama_endpoint}
                  onChange={(v) => updateField('ollama_endpoint', v)}
                  placeholder="http://localhost:11434"
                />
                <SettingsField
                  id="ollama-model"
                  label="Model"
                  type="text"
                  value={settings.ollama_model}
                  onChange={(v) => updateField('ollama_model', v)}
                  placeholder="llama3.1:8b"
                />
              </div>
            </Card>

            {/* Scan Settings */}
            <Card title="Scan Configuration">
              <div className="flex flex-wrap gap-4">
                <SettingsField
                  id="scan-top-n"
                  label="Top N"
                  type="number"
                  value={String(settings.scan_top_n)}
                  onChange={(v) =>
                    updateField('scan_top_n', parseInt(v, 10) || 10)
                  }
                  min={1}
                  max={100}
                  width="w-20"
                />
                <SettingsField
                  id="scan-min-volume"
                  label="Min Volume"
                  type="number"
                  value={String(settings.scan_min_volume)}
                  onChange={(v) =>
                    updateField('scan_min_volume', parseInt(v, 10) || 100)
                  }
                  min={0}
                  width="w-24"
                />
              </div>
            </Card>

            {/* DTE Settings */}
            <Card title="DTE Range">
              <div className="flex flex-wrap gap-4">
                <SettingsField
                  id="dte-min"
                  label="DTE Min"
                  type="number"
                  value={String(settings.default_dte_min)}
                  onChange={(v) =>
                    updateField('default_dte_min', parseInt(v, 10) || 20)
                  }
                  min={0}
                  max={365}
                  width="w-20"
                />
                <SettingsField
                  id="dte-max"
                  label="DTE Max"
                  type="number"
                  value={String(settings.default_dte_max)}
                  onChange={(v) =>
                    updateField('default_dte_max', parseInt(v, 10) || 60)
                  }
                  min={1}
                  max={365}
                  width="w-20"
                />
              </div>
            </Card>

            {/* Action buttons */}
            <div className="flex gap-2">
              <Button
                variant="primary"
                onClick={() => void handleSave()}
                disabled={saving}
              >
                {saving ? 'SAVING...' : 'SAVE SETTINGS'}
              </Button>
              <Button variant="secondary" onClick={handleReset}>
                RESET TO DEFAULTS
              </Button>
            </div>
          </>
        )}
      </div>
    </PageShell>
  )
}

// ---------------------------------------------------------------------------
// Internal components
// ---------------------------------------------------------------------------

interface SettingsFieldProps {
  id: string
  label: string
  type: 'text' | 'number'
  value: string
  onChange: (value: string) => void
  placeholder?: string
  min?: number
  max?: number
  width?: string
}

function SettingsField({
  id,
  label,
  type,
  value,
  onChange,
  placeholder,
  min,
  max,
  width = 'w-64',
}: SettingsFieldProps) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="font-data text-xs uppercase tracking-wider"
        style={{ color: 'var(--color-text-secondary)' }}
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        min={min}
        max={max}
        className={`font-data border px-2 py-1 text-xs ${width}`}
        style={{
          backgroundColor: 'var(--color-bg-elevated)',
          borderColor: 'var(--color-border-default)',
          color: 'var(--color-text-primary)',
        }}
      />
    </div>
  )
}
