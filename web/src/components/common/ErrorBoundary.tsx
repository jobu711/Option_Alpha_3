import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ErrorBoundary caught:', error, info)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div
          className="flex flex-col items-center justify-center gap-2 p-8"
          style={{ color: 'var(--color-bear)' }}
        >
          <span className="font-data text-sm font-semibold">
            RUNTIME ERROR
          </span>
          <span
            className="font-data text-xs"
            style={{ color: 'var(--color-text-secondary)' }}
          >
            {this.state.error?.message ?? 'An unexpected error occurred'}
          </span>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="font-data mt-2 border px-3 py-1 text-xs"
            style={{
              borderColor: 'var(--color-border-default)',
              color: 'var(--color-text-secondary)',
            }}
          >
            RETRY
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
