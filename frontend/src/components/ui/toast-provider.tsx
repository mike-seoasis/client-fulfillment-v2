/* eslint-disable react-refresh/only-export-components */
/**
 * Toast context provider for global toast notifications
 *
 * Provides a React context for managing toast notifications throughout the app.
 * Includes hooks for showing toasts programmatically and integrates with
 * the error reporting service for logging.
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Error toasts are logged to console with full context
 * - API errors include endpoint, status, and response body
 * - User action context is tracked with each toast
 * - Breadcrumbs are added for debugging toast-triggering actions
 */

import {
  createContext,
  useContext,
  useCallback,
  useState,
  useMemo,
  type ReactNode,
} from 'react'
import { Toast, ToastContainer } from './toast'
import { addBreadcrumb } from '@/lib/errorReporting'

/** Toast variant types */
export type ToastVariant = 'success' | 'error' | 'warning' | 'info'

/** Options for creating a toast */
export interface ToastOptions {
  /** Toast title */
  title: string
  /** Optional description */
  description?: string
  /** Toast variant (success, error, warning, info) */
  variant?: ToastVariant
  /** Auto-dismiss duration in milliseconds (0 = never dismiss, default: 5000) */
  duration?: number
  /** User action that triggered the toast (for logging) */
  userAction?: string
}

/** Toast state with unique ID */
interface ToastState extends ToastOptions {
  id: string
}

/** Toast context value */
interface ToastContextValue {
  /** Show a toast notification */
  toast: (options: ToastOptions) => string
  /** Show a success toast */
  success: (title: string, description?: string) => string
  /** Show an error toast */
  error: (title: string, description?: string) => string
  /** Show a warning toast */
  warning: (title: string, description?: string) => string
  /** Show an info toast */
  info: (title: string, description?: string) => string
  /** Dismiss a specific toast by ID */
  dismiss: (id: string) => void
  /** Dismiss all toasts */
  dismissAll: () => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let toastIdCounter = 0

/** Generate a unique toast ID */
function generateToastId(): string {
  return `toast-${++toastIdCounter}-${Date.now()}`
}

/** Toast position options */
export type ToastPosition = 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center'

export interface ToastProviderProps {
  /** Position of toasts on screen */
  position?: ToastPosition
  /** Maximum number of toasts to show at once (default: 5) */
  maxToasts?: number
  /** Default duration for toasts in milliseconds (default: 5000) */
  defaultDuration?: number
  /** Children components */
  children: ReactNode
}

/**
 * ToastProvider wraps the app to provide toast functionality
 *
 * @example
 * <ToastProvider position="top-right">
 *   <App />
 * </ToastProvider>
 */
export function ToastProvider({
  position = 'top-right',
  maxToasts = 5,
  defaultDuration = 5000,
  children,
}: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastState[]>([])

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const dismissAll = useCallback(() => {
    setToasts([])
  }, [])

  const toast = useCallback(
    (options: ToastOptions): string => {
      const id = generateToastId()
      const newToast: ToastState = {
        id,
        variant: options.variant || 'info',
        duration: options.duration ?? defaultDuration,
        ...options,
      }

      // Add breadcrumb for debugging
      addBreadcrumb(
        `Toast shown: ${options.title}`,
        'ui.toast',
        {
          variant: newToast.variant,
          userAction: options.userAction,
          description: options.description,
        }
      )

      // Log error toasts to console
      if (newToast.variant === 'error') {
        console.error('[Toast Error]', {
          title: newToast.title,
          description: newToast.description,
          userAction: options.userAction,
        })
      }

      setToasts((prev) => {
        // Remove oldest toasts if we exceed maxToasts
        const updated = [...prev, newToast]
        if (updated.length > maxToasts) {
          return updated.slice(-maxToasts)
        }
        return updated
      })

      return id
    },
    [defaultDuration, maxToasts]
  )

  const success = useCallback(
    (title: string, description?: string): string => {
      return toast({ title, description, variant: 'success' })
    },
    [toast]
  )

  const error = useCallback(
    (title: string, description?: string): string => {
      return toast({ title, description, variant: 'error' })
    },
    [toast]
  )

  const warning = useCallback(
    (title: string, description?: string): string => {
      return toast({ title, description, variant: 'warning' })
    },
    [toast]
  )

  const info = useCallback(
    (title: string, description?: string): string => {
      return toast({ title, description, variant: 'info' })
    },
    [toast]
  )

  const value = useMemo(
    () => ({
      toast,
      success,
      error,
      warning,
      info,
      dismiss,
      dismissAll,
    }),
    [toast, success, error, warning, info, dismiss, dismissAll]
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer position={position}>
        {toasts.map((t) => (
          <Toast
            key={t.id}
            id={t.id}
            variant={t.variant}
            title={t.title}
            description={t.description}
            duration={t.duration}
            onDismiss={dismiss}
          />
        ))}
      </ToastContainer>
    </ToastContext.Provider>
  )
}

/**
 * Hook to access toast functions
 *
 * @example
 * function MyComponent() {
 *   const { success, error } = useToast()
 *
 *   const handleSave = async () => {
 *     try {
 *       await saveData()
 *       success('Changes saved', 'Your project has been updated.')
 *     } catch (err) {
 *       error('Failed to save', err.message)
 *     }
 *   }
 * }
 */
export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)

  if (!context) {
    throw new Error('useToast must be used within a ToastProvider')
  }

  return context
}

// Re-export helper function from lib for convenience
export { showApiErrorToast } from '@/lib/toastHelpers'
