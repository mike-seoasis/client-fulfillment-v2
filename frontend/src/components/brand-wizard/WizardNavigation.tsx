/**
 * WizardNavigation component for brand wizard step navigation
 *
 * Provides Previous/Next buttons for navigating between wizard steps.
 *
 * Features:
 * - Previous button (disabled on Step 1)
 * - Next/Finish button
 * - Loading state support
 * - Keyboard accessible
 */

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ChevronLeft, ChevronRight, Loader2, Sparkles } from 'lucide-react'

export interface WizardNavigationProps {
  /** Current step (1-7) */
  currentStep: number
  /** Total number of steps */
  totalSteps?: number
  /** Whether the current step can proceed to next */
  canProceed?: boolean
  /** Whether navigation is currently loading */
  isLoading?: boolean
  /** Callback when Previous is clicked */
  onPrevious?: () => void
  /** Callback when Next is clicked */
  onNext?: () => void
  /** Callback when Finish is clicked (on last step) */
  onFinish?: () => void
  /** Custom label for next button */
  nextLabel?: string
  /** Custom label for finish button */
  finishLabel?: string
  /** Optional additional CSS classes */
  className?: string
}

/**
 * WizardNavigation provides step navigation controls
 *
 * @example
 * <WizardNavigation
 *   currentStep={3}
 *   canProceed={isValid}
 *   onPrevious={() => setStep(step - 1)}
 *   onNext={() => setStep(step + 1)}
 * />
 */
export function WizardNavigation({
  currentStep,
  totalSteps = 7,
  canProceed = true,
  isLoading = false,
  onPrevious,
  onNext,
  onFinish,
  nextLabel = 'Next',
  finishLabel = 'Generate Brand Config',
  className,
}: WizardNavigationProps) {
  const isFirstStep = currentStep === 1
  const isLastStep = currentStep === totalSteps

  const handleNext = () => {
    if (isLastStep) {
      onFinish?.()
    } else {
      onNext?.()
    }
  }

  return (
    <div
      className={cn(
        'flex items-center justify-between pt-6 border-t border-cream-200',
        className
      )}
    >
      {/* Previous button */}
      <Button
        type="button"
        variant="outline"
        onClick={onPrevious}
        disabled={isFirstStep || isLoading}
        className={cn(
          'gap-2',
          isFirstStep && 'invisible'
        )}
      >
        <ChevronLeft className="w-4 h-4" />
        Previous
      </Button>

      {/* Step indicator */}
      <span className="text-sm text-warmgray-500">
        Step {currentStep} of {totalSteps}
      </span>

      {/* Next/Finish button */}
      <Button
        type="button"
        onClick={handleNext}
        disabled={!canProceed || isLoading}
        className="gap-2"
      >
        {isLoading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Processing...
          </>
        ) : isLastStep ? (
          <>
            <Sparkles className="w-4 h-4" />
            {finishLabel}
          </>
        ) : (
          <>
            {nextLabel}
            <ChevronRight className="w-4 h-4" />
          </>
        )}
      </Button>
    </div>
  )
}
