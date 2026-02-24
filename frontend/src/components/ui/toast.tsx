/**
 * Toast notification component for user feedback
 *
 * A warm, sophisticated toast that matches the design system.
 * Displays success, error, warning, and info notifications.
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Toast errors are logged through the error reporting service
 * - API errors can be displayed as toasts with full context
 * - User actions that trigger toasts are tracked via breadcrumbs
 */

import { useEffect, useState } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { X, CheckCircle, XCircle, AlertTriangle, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

const toastVariants = cva(
  'relative flex items-start gap-3 w-full max-w-sm rounded-xl p-4 shadow-soft-lg border transition-all duration-300 ease-smooth',
  {
    variants: {
      variant: {
        success: 'bg-success-50 border-success-200 text-success-800',
        error: 'bg-error-50 border-error-200 text-error-800',
        warning: 'bg-warning-50 border-warning-200 text-warning-800',
        info: 'bg-cream-100 border-cream-300 text-warmgray-800',
      },
    },
    defaultVariants: {
      variant: 'info',
    },
  }
)

const iconVariants: Record<string, { icon: typeof CheckCircle; className: string }> = {
  success: { icon: CheckCircle, className: 'text-success-500' },
  error: { icon: XCircle, className: 'text-error-500' },
  warning: { icon: AlertTriangle, className: 'text-warning-500' },
  info: { icon: Info, className: 'text-primary-500' },
}

export interface ToastProps extends VariantProps<typeof toastVariants> {
  /** Unique identifier for the toast */
  id: string
  /** Toast title */
  title: string
  /** Optional description */
  description?: string
  /** Auto-dismiss duration in milliseconds (0 = never dismiss) */
  duration?: number
  /** Callback when toast is dismissed */
  onDismiss?: (id: string) => void
  /** Additional CSS classes */
  className?: string
}

/**
 * Toast displays a notification message with optional auto-dismiss
 *
 * @example
 * <Toast
 *   id="1"
 *   variant="success"
 *   title="Changes saved"
 *   description="Your project has been updated."
 *   onDismiss={handleDismiss}
 * />
 */
export function Toast({
  id,
  variant = 'info',
  title,
  description,
  duration = 5000,
  onDismiss,
  className,
}: ToastProps) {
  const [isExiting, setIsExiting] = useState(false)

  const variantKey = variant || 'info'
  const { icon: Icon, className: iconClassName } = iconVariants[variantKey]

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(() => {
      onDismiss?.(id)
    }, 200)
  }

  useEffect(() => {
    if (duration === 0) return

    const timer = setTimeout(() => {
      handleDismiss()
    }, duration)

    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration, id])

  return (
    <div
      role="alert"
      aria-live="assertive"
      aria-atomic="true"
      className={cn(
        toastVariants({ variant }),
        isExiting ? 'opacity-0 translate-x-2' : 'opacity-100 translate-x-0 animate-slide-in',
        className
      )}
    >
      <Icon className={cn('w-5 h-5 mt-0.5 shrink-0', iconClassName)} aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{title}</p>
        {description && (
          <p className="mt-1 text-sm opacity-80">{description}</p>
        )}
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        className={cn(
          'shrink-0 p-1 rounded-md transition-colors',
          'hover:bg-black/5 focus:outline-none focus:ring-2 focus:ring-offset-1',
          variant === 'success' && 'focus:ring-success-400',
          variant === 'error' && 'focus:ring-error-400',
          variant === 'warning' && 'focus:ring-warning-400',
          variant === 'info' && 'focus:ring-primary-400'
        )}
        aria-label="Dismiss notification"
      >
        <X className="w-4 h-4" aria-hidden="true" />
      </button>
    </div>
  )
}

export interface ToastContainerProps {
  /** Position of the toast container */
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left' | 'top-center' | 'bottom-center'
  /** Additional CSS classes */
  className?: string
  /** Toast elements to render */
  children?: React.ReactNode
}

const positionClasses: Record<string, string> = {
  'top-right': 'top-4 right-4',
  'top-left': 'top-4 left-4',
  'bottom-right': 'bottom-4 right-4',
  'bottom-left': 'bottom-4 left-4',
  'top-center': 'top-4 left-1/2 -translate-x-1/2',
  'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
}

/**
 * ToastContainer positions toasts on the screen
 *
 * @example
 * <ToastContainer position="top-right">
 *   {toasts.map(toast => <Toast key={toast.id} {...toast} />)}
 * </ToastContainer>
 */
export function ToastContainer({
  position = 'top-right',
  className,
  children,
}: ToastContainerProps) {
  return (
    <div
      className={cn(
        'fixed z-50 flex flex-col gap-3 pointer-events-none',
        positionClasses[position],
        className
      )}
      aria-label="Notifications"
    >
      <div className="flex flex-col gap-3 pointer-events-auto">
        {children}
      </div>
    </div>
  )
}
