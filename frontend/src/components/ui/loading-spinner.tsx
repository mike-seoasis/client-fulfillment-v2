/**
 * LoadingSpinner component for indicating loading states
 *
 * A warm, sophisticated spinner that matches the design system.
 * Use for inline loading indicators or full-screen loading states.
 */

import { cn } from '@/lib/utils'

export interface LoadingSpinnerProps {
  /** Size variant */
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** Optional label for accessibility and visual context */
  label?: string
  /** Whether to show the label visually (always announced to screen readers) */
  showLabel?: boolean
  /** Additional CSS classes */
  className?: string
}

/** Size configurations for the spinner */
const sizeClasses: Record<'sm' | 'md' | 'lg' | 'xl', { spinner: string; label: string }> = {
  sm: { spinner: 'w-4 h-4 border-2', label: 'text-xs' },
  md: { spinner: 'w-6 h-6 border-2', label: 'text-sm' },
  lg: { spinner: 'w-8 h-8 border-[3px]', label: 'text-base' },
  xl: { spinner: 'w-12 h-12 border-4', label: 'text-lg' },
}

/**
 * LoadingSpinner displays an animated loading indicator
 *
 * @example
 * // Basic usage
 * <LoadingSpinner />
 *
 * @example
 * // With visible label
 * <LoadingSpinner size="lg" label="Loading projects..." showLabel />
 *
 * @example
 * // Small inline spinner
 * <LoadingSpinner size="sm" label="Saving" />
 */
export function LoadingSpinner({
  size = 'md',
  label = 'Loading',
  showLabel = false,
  className,
}: LoadingSpinnerProps) {
  const { spinner, label: labelSize } = sizeClasses[size]

  return (
    <div
      className={cn('inline-flex flex-col items-center justify-center gap-2', className)}
      role="status"
      aria-live="polite"
    >
      <div
        className={cn(
          // Base spinner styles
          'rounded-full animate-spin',
          // Warm gold primary color with cream background
          'border-cream-300 border-t-primary-500',
          spinner
        )}
        aria-hidden="true"
      />
      {showLabel ? (
        <span className={cn('text-warmgray-600 font-medium', labelSize)}>
          {label}
        </span>
      ) : (
        <span className="sr-only">{label}</span>
      )}
    </div>
  )
}

/**
 * FullPageSpinner displays a centered loading spinner for page-level loading states
 *
 * @example
 * if (isLoading) {
 *   return <FullPageSpinner label="Loading dashboard..." />
 * }
 */
export function FullPageSpinner({
  label = 'Loading',
  className,
}: Pick<LoadingSpinnerProps, 'label' | 'className'>) {
  return (
    <div
      className={cn(
        'flex items-center justify-center min-h-[200px] w-full',
        className
      )}
    >
      <LoadingSpinner size="lg" label={label} showLabel />
    </div>
  )
}

/**
 * ButtonSpinner for use inside buttons during loading states
 * Designed to replace button content during loading
 *
 * @example
 * <Button disabled={isSubmitting}>
 *   {isSubmitting ? <ButtonSpinner /> : 'Submit'}
 * </Button>
 */
export function ButtonSpinner({ className }: { className?: string }) {
  return (
    <LoadingSpinner
      size="sm"
      label="Processing"
      className={cn('inline-flex', className)}
    />
  )
}
