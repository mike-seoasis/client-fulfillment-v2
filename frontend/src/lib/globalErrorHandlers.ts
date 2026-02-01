/**
 * Global error handlers for uncaught exceptions and unhandled promise rejections
 *
 * These catch errors that escape React's error boundaries,
 * such as errors in event handlers, async code, or third-party scripts.
 */

import { reportError } from './errorReporting'

/**
 * Set up global error handlers
 * Call this once at app startup, before React mounts
 */
export function setupGlobalErrorHandlers(): void {
  // Handle uncaught synchronous errors
  window.onerror = (
    message: string | Event,
    source?: string,
    lineno?: number,
    colno?: number,
    error?: Error,
  ): boolean => {
    const errorMessage =
      typeof message === 'string' ? message : 'Unknown error'

    console.error('[Global Error]', {
      message: errorMessage,
      source,
      line: lineno,
      column: colno,
      stack: error?.stack,
    })

    if (error) {
      reportError(error, {
        userAction: 'Global uncaught error',
        extra: { source, lineno, colno },
      })
    } else {
      // Create synthetic error for non-Error throws
      const syntheticError = new Error(errorMessage)
      syntheticError.name = 'UncaughtError'
      reportError(syntheticError, {
        userAction: 'Global uncaught error (no Error object)',
        extra: { source, lineno, colno },
      })
    }

    // Return false to allow default browser error handling
    return false
  }

  // Handle unhandled promise rejections
  window.onunhandledrejection = (event: PromiseRejectionEvent): void => {
    const reason = event.reason

    console.error('[Unhandled Promise Rejection]', {
      reason,
      promise: event.promise,
    })

    if (reason instanceof Error) {
      reportError(reason, {
        userAction: 'Unhandled promise rejection',
      })
    } else {
      // Create synthetic error for non-Error rejections
      const syntheticError = new Error(
        typeof reason === 'string' ? reason : 'Promise rejected',
      )
      syntheticError.name = 'UnhandledRejection'
      reportError(syntheticError, {
        userAction: 'Unhandled promise rejection (non-Error)',
        extra: { reason },
      })
    }
  }

  console.log('[GlobalErrorHandlers] Installed window.onerror and onunhandledrejection')
}
