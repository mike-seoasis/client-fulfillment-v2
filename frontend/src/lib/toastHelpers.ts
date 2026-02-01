/**
 * Toast helper functions
 *
 * Utilities for working with toasts outside of React components.
 * Use these for integrating toasts with API clients and error handling.
 */

import type { ToastOptions } from '@/components/ui/toast-provider'

type ToastFn = (options: ToastOptions) => string

/**
 * Helper to show API error toasts with full context
 *
 * @example
 * try {
 *   await api.post('/projects', data)
 * } catch (err) {
 *   showApiErrorToast(toast, err, 'Creating project')
 * }
 */
export function showApiErrorToast(
  toastFn: ToastFn,
  error: Error & { status?: number; endpoint?: string; method?: string; responseBody?: unknown },
  userAction: string
): string {
  // Log the full API error context
  console.error('[API Error Toast]', {
    message: error.message,
    endpoint: error.endpoint,
    method: error.method,
    status: error.status,
    responseBody: error.responseBody,
    userAction,
  })

  // Determine user-friendly message based on status
  let description = error.message
  if (error.status === 401) {
    description = 'Please sign in to continue.'
  } else if (error.status === 403) {
    description = 'You don\'t have permission to perform this action.'
  } else if (error.status === 404) {
    description = 'The requested resource was not found.'
  } else if (error.status && error.status >= 500) {
    description = 'Something went wrong on our end. Please try again later.'
  }

  return toastFn({
    title: 'Something went wrong',
    description,
    variant: 'error',
    duration: 7000, // Longer duration for errors
    userAction,
  })
}
