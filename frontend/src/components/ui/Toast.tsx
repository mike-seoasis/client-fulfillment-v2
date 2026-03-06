/**
 * Toast notification component for user feedback.
 *
 * Fixed-position toast that auto-dismisses after 4 seconds.
 * Matches the tropical oasis design system (palm/coral/sand palette).
 */

import { useEffect, useState } from 'react'
import { X, CheckCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export type ToastVariant = 'success' | 'error'

export interface ToastProps {
  message: string
  variant?: ToastVariant
  onClose: () => void
  /** Auto-dismiss duration in ms (default 4000, 0 = never) */
  duration?: number
  className?: string
}

const variantStyles: Record<ToastVariant, { bg: string; icon: typeof CheckCircle; iconClass: string; ringClass: string }> = {
  success: {
    bg: 'bg-palm-50 border-palm-200 text-palm-800',
    icon: CheckCircle,
    iconClass: 'text-palm-500',
    ringClass: 'focus:ring-palm-400',
  },
  error: {
    bg: 'bg-coral-50 border-coral-200 text-coral-800',
    icon: XCircle,
    iconClass: 'text-coral-500',
    ringClass: 'focus:ring-coral-400',
  },
}

export function Toast({
  message,
  variant = 'success',
  onClose,
  duration = 4000,
  className,
}: ToastProps) {
  const [isExiting, setIsExiting] = useState(false)

  const { bg, icon: Icon, iconClass, ringClass } = variantStyles[variant]

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(onClose, 200)
  }

  useEffect(() => {
    if (duration === 0) return

    const timer = setTimeout(handleDismiss, duration)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [duration])

  return (
    <div
      className={cn(
        'fixed top-4 right-4 z-50 pointer-events-auto',
        isExiting ? 'opacity-0 translate-x-2' : 'opacity-100 translate-x-0',
        'transition-all duration-200',
      )}
    >
      <div
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        className={cn(
          'flex items-start gap-3 w-full max-w-sm rounded-sm p-4 shadow-lg border',
          bg,
          className,
        )}
      >
        <Icon className={cn('w-5 h-5 mt-0.5 shrink-0', iconClass)} aria-hidden="true" />
        <p className="flex-1 min-w-0 text-sm font-medium">{message}</p>
        <button
          type="button"
          onClick={handleDismiss}
          className={cn(
            'shrink-0 p-1 rounded-sm transition-colors',
            'hover:bg-black/5 focus:outline-none focus:ring-2 focus:ring-offset-1',
            ringClass,
          )}
          aria-label="Dismiss notification"
        >
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
