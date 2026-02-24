/**
 * PhaseProgress component for visualizing project phase status
 *
 * Displays a horizontal progress bar with status indicators for each phase.
 * Used to show project progress in cards, detail views, and dashboards.
 *
 * Features:
 * - Color-coded phase indicators (pending, in_progress, completed, blocked, skipped)
 * - Animated pulse for active phases
 * - Accessible with aria labels and tooltips
 * - Optional labels showing current phase and completion percentage
 */

import { cn } from '@/lib/utils'
import {
  type PhaseStatus,
  type PhaseStatusEntry,
  PHASE_ORDER,
  phaseLabels,
  getCompletionPercentage,
  getCurrentPhase,
} from '@/lib/phaseUtils'

export interface PhaseProgressProps {
  /** Phase status data keyed by phase name */
  phaseStatus: Record<string, PhaseStatusEntry>
  /** Whether to show labels (current phase and percentage) */
  showLabels?: boolean
  /** Size variant for the indicators */
  size?: 'sm' | 'md' | 'lg'
  /** Optional additional CSS classes */
  className?: string
}

/** Phase status indicator colors */
const phaseColors: Record<PhaseStatus, string> = {
  pending: 'bg-cream-300',
  in_progress: 'bg-primary-400',
  completed: 'bg-success-500',
  blocked: 'bg-error-400',
  skipped: 'bg-warmgray-300',
}

/** Height classes for different sizes */
const sizeClasses: Record<'sm' | 'md' | 'lg', string> = {
  sm: 'h-1.5',
  md: 'h-2',
  lg: 'h-3',
}

/**
 * Get human-readable status text
 */
function formatStatus(status: PhaseStatus): string {
  return status.replace('_', ' ')
}

/**
 * PhaseProgress component displays project phase progression
 *
 * @example
 * // Basic usage
 * <PhaseProgress phaseStatus={project.phase_status} />
 *
 * @example
 * // With labels and larger size
 * <PhaseProgress
 *   phaseStatus={project.phase_status}
 *   showLabels
 *   size="lg"
 * />
 */
export function PhaseProgress({
  phaseStatus,
  showLabels = false,
  size = 'md',
  className,
}: PhaseProgressProps) {
  const completionPercentage = getCompletionPercentage(phaseStatus)
  const currentPhase = getCurrentPhase(phaseStatus)

  return (
    <div className={cn('w-full', className)}>
      {/* Optional labels */}
      {showLabels && (
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-warmgray-600 font-medium">
            {currentPhase ? phaseLabels[currentPhase] : 'Complete'}
          </span>
          <span className="text-warmgray-500">
            {completionPercentage}% complete
          </span>
        </div>
      )}

      {/* Phase indicators */}
      <div
        className="flex gap-1.5"
        role="progressbar"
        aria-valuenow={completionPercentage}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Project progress: ${completionPercentage}% complete${currentPhase ? `, currently in ${phaseLabels[currentPhase]}` : ''}`}
      >
        {PHASE_ORDER.map((phase) => {
          const phaseData = phaseStatus[phase]
          const status: PhaseStatus = phaseData?.status || 'pending'

          return (
            <div
              key={phase}
              className={cn(
                'flex-1 rounded-full transition-all duration-300',
                sizeClasses[size],
                phaseColors[status],
                status === 'in_progress' && 'animate-pulse-soft'
              )}
              title={`${phaseLabels[phase]}: ${formatStatus(status)}`}
              aria-label={`${phaseLabels[phase]}: ${formatStatus(status)}`}
            />
          )
        })}
      </div>
    </div>
  )
}

/**
 * Loading skeleton for PhaseProgress
 * Use while data is being fetched
 */
export function PhaseProgressSkeleton({
  showLabels = false,
  size = 'md',
  className,
}: Omit<PhaseProgressProps, 'phaseStatus'>) {
  return (
    <div className={cn('w-full', className)}>
      {/* Labels skeleton */}
      {showLabels && (
        <div className="flex items-center justify-between mb-2">
          <div className="h-4 bg-cream-200 rounded w-24 animate-pulse-soft" />
          <div className="h-4 bg-cream-200 rounded w-16 animate-pulse-soft" />
        </div>
      )}

      {/* Phase indicators skeleton */}
      <div className="flex gap-1.5">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className={cn(
              'flex-1 bg-cream-200 rounded-full animate-pulse-soft',
              sizeClasses[size]
            )}
          />
        ))}
      </div>
    </div>
  )
}
