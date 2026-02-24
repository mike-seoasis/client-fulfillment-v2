import { Component, ReactNode } from 'react'
import { reportError } from '@/lib/errorReporting'

interface ErrorBoundaryProps {
  /** Content to render when no error */
  children: ReactNode
  /** Custom fallback UI to show on error */
  fallback?: ReactNode
  /** Optional callback when error is caught */
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
  /** Component name for error context */
  componentName?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

/**
 * React Error Boundary for catching and logging render errors
 *
 * Wrap route components or major UI sections with this boundary
 * to prevent the entire app from crashing on errors.
 *
 * @example
 * <ErrorBoundary componentName="Dashboard">
 *   <Dashboard />
 * </ErrorBoundary>
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log error with component stack
    console.error('[ErrorBoundary] Caught error:', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      componentName: this.props.componentName,
    })

    // Report to error service
    reportError(error, {
      component: this.props.componentName,
      extra: {
        componentStack: errorInfo.componentStack,
      },
    })

    // Call optional callback
    this.props.onError?.(error, errorInfo)
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      // Custom fallback
      if (this.props.fallback) {
        return this.props.fallback
      }

      // Default error UI
      return (
        <div
          style={{
            padding: '2rem',
            textAlign: 'center',
            fontFamily: 'system-ui, sans-serif',
          }}
        >
          <h2 style={{ color: '#b91c1c', marginBottom: '1rem' }}>
            Something went wrong
          </h2>
          <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={this.handleRetry}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '0.375rem',
              cursor: 'pointer',
              fontSize: '1rem',
            }}
          >
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Higher-order component to wrap a component with ErrorBoundary
 */
export function withErrorBoundary<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  componentName: string,
): React.FC<P> {
  const WithErrorBoundary: React.FC<P> = (props) => (
    <ErrorBoundary componentName={componentName}>
      <WrappedComponent {...props} />
    </ErrorBoundary>
  )

  WithErrorBoundary.displayName = `withErrorBoundary(${componentName})`
  return WithErrorBoundary
}
