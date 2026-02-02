/**
 * WizardContainer component - layout wrapper for brand wizard
 *
 * Provides the overall layout structure for the brand wizard including:
 * - Header with title and close button
 * - Progress indicator
 * - Step content area
 * - Navigation footer
 *
 * Features:
 * - Responsive layout
 * - Auto-save indicator
 * - Error display
 * - Loading states
 */

import { cn } from '@/lib/utils'
import { WizardProgress, type WizardProgressProps } from './WizardProgress'
import { WizardNavigation, type WizardNavigationProps } from './WizardNavigation'
import { X, Save, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { ReactNode } from 'react'

export interface WizardContainerProps {
  /** Wizard title */
  title?: string
  /** Progress indicator props */
  progress: WizardProgressProps
  /** Navigation props */
  navigation: WizardNavigationProps
  /** Step content to render */
  children: ReactNode
  /** Whether auto-save is in progress */
  isSaving?: boolean
  /** Last save timestamp */
  lastSavedAt?: string | null
  /** Error message to display */
  error?: string | null
  /** Callback when close/cancel is clicked */
  onClose?: () => void
  /** Optional additional CSS classes */
  className?: string
}

/**
 * WizardContainer provides the layout structure for the brand wizard
 *
 * @example
 * <WizardContainer
 *   title="Configure Brand"
 *   progress={{ currentStep: 2, completedSteps: [1], canNavigate: true }}
 *   navigation={{ currentStep: 2, onPrevious: handlePrev, onNext: handleNext }}
 *   onClose={() => navigate('/projects')}
 * >
 *   <StepContent />
 * </WizardContainer>
 */
export function WizardContainer({
  title = 'Brand Configuration Wizard',
  progress,
  navigation,
  children,
  isSaving = false,
  lastSavedAt,
  error,
  onClose,
  className,
}: WizardContainerProps) {
  return (
    <div className={cn('min-h-screen bg-cream-50', className)}>
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white border-b border-cream-200 shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Title and save status */}
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-semibold text-warmgray-900">
                {title}
              </h1>

              {/* Save indicator */}
              {(isSaving || lastSavedAt) && (
                <span className="flex items-center gap-1.5 text-sm text-warmgray-500">
                  {isSaving ? (
                    <>
                      <Save className="w-4 h-4 animate-pulse" />
                      Saving...
                    </>
                  ) : lastSavedAt ? (
                    <>
                      <Save className="w-4 h-4" />
                      Saved
                    </>
                  ) : null}
                </span>
              )}
            </div>

            {/* Close button */}
            {onClose && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={onClose}
                aria-label="Close wizard"
              >
                <X className="w-5 h-5" />
              </Button>
            )}
          </div>

          {/* Progress indicator */}
          <div className="mt-6">
            <WizardProgress {...progress} />
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* Error banner */}
        {error && (
          <div className="mb-6 p-4 bg-error-50 border border-error-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-error-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-medium text-error-800">
                Something went wrong
              </p>
              <p className="mt-1 text-sm text-error-700">
                {error}
              </p>
            </div>
          </div>
        )}

        {/* Step content */}
        <div className="bg-white rounded-xl border border-cream-200 shadow-sm">
          <div className="p-6 md:p-8">
            {children}
          </div>

          {/* Navigation footer */}
          <div className="px-6 md:px-8 pb-6 md:pb-8">
            <WizardNavigation {...navigation} />
          </div>
        </div>
      </main>
    </div>
  )
}

/**
 * WizardStepHeader - header for individual wizard steps
 */
export interface WizardStepHeaderProps {
  /** Step title */
  title: string
  /** Step description */
  description?: string
  /** Optional badge/indicator */
  badge?: ReactNode
  /** Optional additional CSS classes */
  className?: string
}

export function WizardStepHeader({
  title,
  description,
  badge,
  className,
}: WizardStepHeaderProps) {
  return (
    <div className={cn('mb-8', className)}>
      <div className="flex items-center gap-3">
        <h2 className="text-2xl font-semibold text-warmgray-900">
          {title}
        </h2>
        {badge}
      </div>
      {description && (
        <p className="mt-2 text-warmgray-600">
          {description}
        </p>
      )}
    </div>
  )
}
