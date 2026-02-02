/**
 * WizardProgress component for the 7-step brand configuration wizard
 *
 * Displays a horizontal step indicator showing progress through the wizard.
 * Steps are clickable after Step 1 is completed.
 *
 * Features:
 * - Visual step indicators with numbers
 * - Current step highlighting
 * - Completed step checkmarks
 * - Click to navigate (after Step 1)
 * - Accessible with aria labels
 */

import { cn } from '@/lib/utils'
import { Check } from 'lucide-react'

export interface WizardStep {
  number: number
  label: string
}

export const WIZARD_STEPS: WizardStep[] = [
  { number: 1, label: 'Brand Setup' },
  { number: 2, label: 'Foundation' },
  { number: 3, label: 'Audience' },
  { number: 4, label: 'Voice' },
  { number: 5, label: 'Writing Rules' },
  { number: 6, label: 'Proof & Examples' },
  { number: 7, label: 'Review' },
]

export interface WizardProgressProps {
  /** Current step (1-7) */
  currentStep: number
  /** Steps that have been completed */
  completedSteps: number[]
  /** Whether Step 1 has been completed (enables navigation) */
  canNavigate?: boolean
  /** Callback when a step is clicked */
  onStepClick?: (step: number) => void
  /** Optional additional CSS classes */
  className?: string
}

/**
 * WizardProgress component displays the 7-step wizard progression
 *
 * @example
 * <WizardProgress
 *   currentStep={3}
 *   completedSteps={[1, 2]}
 *   canNavigate={true}
 *   onStepClick={(step) => setCurrentStep(step)}
 * />
 */
export function WizardProgress({
  currentStep,
  completedSteps,
  canNavigate = false,
  onStepClick,
  className,
}: WizardProgressProps) {
  const isStepCompleted = (step: number) => completedSteps.includes(step)
  const isStepCurrent = (step: number) => step === currentStep
  const isStepClickable = (step: number) =>
    canNavigate && (step === 1 || completedSteps.includes(1))

  return (
    <nav
      className={cn('w-full', className)}
      aria-label="Wizard progress"
    >
      <ol className="flex items-center justify-between">
        {WIZARD_STEPS.map((step, index) => {
          const completed = isStepCompleted(step.number)
          const current = isStepCurrent(step.number)
          const clickable = isStepClickable(step.number)
          const isLast = index === WIZARD_STEPS.length - 1

          return (
            <li
              key={step.number}
              className={cn(
                'flex items-center',
                !isLast && 'flex-1'
              )}
            >
              {/* Step indicator */}
              <button
                type="button"
                onClick={() => clickable && onStepClick?.(step.number)}
                disabled={!clickable}
                className={cn(
                  'flex flex-col items-center group',
                  clickable && 'cursor-pointer',
                  !clickable && 'cursor-default'
                )}
                aria-current={current ? 'step' : undefined}
                aria-label={`Step ${step.number}: ${step.label}${completed ? ' (completed)' : current ? ' (current)' : ''}`}
              >
                {/* Circle with number/checkmark */}
                <span
                  className={cn(
                    'flex items-center justify-center w-10 h-10 rounded-full border-2 text-sm font-medium transition-all',
                    completed && 'bg-success-500 border-success-500 text-white',
                    current && !completed && 'bg-primary-500 border-primary-500 text-white',
                    !completed && !current && 'bg-cream-100 border-cream-300 text-warmgray-500',
                    clickable && !completed && !current && 'group-hover:border-primary-300 group-hover:bg-primary-50'
                  )}
                >
                  {completed ? (
                    <Check className="w-5 h-5" />
                  ) : (
                    step.number
                  )}
                </span>

                {/* Label */}
                <span
                  className={cn(
                    'mt-2 text-xs font-medium text-center max-w-[80px] leading-tight',
                    current && 'text-primary-700',
                    completed && 'text-success-700',
                    !current && !completed && 'text-warmgray-500',
                    clickable && !completed && !current && 'group-hover:text-primary-600'
                  )}
                >
                  {step.label}
                </span>
              </button>

              {/* Connector line */}
              {!isLast && (
                <div
                  className={cn(
                    'flex-1 h-0.5 mx-3 mt-[-24px]',
                    completed ? 'bg-success-500' : 'bg-cream-200'
                  )}
                  aria-hidden="true"
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

/**
 * Loading skeleton for WizardProgress
 */
export function WizardProgressSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('w-full', className)}>
      <div className="flex items-center justify-between">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="flex flex-col items-center">
            <div className="w-10 h-10 rounded-full bg-cream-200 animate-pulse-soft" />
            <div className="mt-2 h-3 w-16 bg-cream-200 rounded animate-pulse-soft" />
          </div>
        ))}
      </div>
    </div>
  )
}
