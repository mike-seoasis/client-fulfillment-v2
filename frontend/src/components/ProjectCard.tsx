/**
 * ProjectCard component for displaying project information in a list
 *
 * Displays project details including name, client, status, phase progress,
 * and timestamps in a warm, sophisticated card layout.
 */

import { cn } from '@/lib/utils'
import { addBreadcrumb } from '@/lib/errorReporting'

/** Valid project statuses matching backend schema */
type ProjectStatus = 'active' | 'completed' | 'on_hold' | 'cancelled' | 'archived'

/** Valid phase statuses matching backend schema */
type PhaseStatus = 'pending' | 'in_progress' | 'completed' | 'blocked' | 'skipped'

/** Valid phase names in order */
const PHASE_ORDER = ['discovery', 'requirements', 'implementation', 'review', 'launch'] as const
type PhaseName = (typeof PHASE_ORDER)[number]

/** Phase status entry from API */
interface PhaseStatusEntry {
  status: PhaseStatus
  started_at?: string | null
  completed_at?: string | null
  blocked_reason?: string | null
}

/** Project data structure matching backend ProjectResponse schema */
export interface Project {
  id: string
  name: string
  client_id: string
  status: ProjectStatus
  phase_status: Record<string, PhaseStatusEntry>
  created_at: string
  updated_at: string
}

export interface ProjectCardProps {
  /** Project data to display */
  project: Project
  /** Optional click handler for card interaction */
  onClick?: (project: Project) => void
  /** Optional additional CSS classes */
  className?: string
}

/** Status badge color configuration */
const statusColors: Record<ProjectStatus, string> = {
  active: 'bg-success-100 text-success-800',
  completed: 'bg-primary-100 text-primary-800',
  on_hold: 'bg-warning-100 text-warning-800',
  cancelled: 'bg-error-100 text-error-800',
  archived: 'bg-cream-200 text-warmgray-600',
}

/** Phase status indicator colors */
const phaseColors: Record<PhaseStatus, string> = {
  pending: 'bg-cream-300',
  in_progress: 'bg-primary-400',
  completed: 'bg-success-500',
  blocked: 'bg-error-400',
  skipped: 'bg-warmgray-300',
}

/** Human-readable status labels */
const statusLabels: Record<ProjectStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  on_hold: 'On Hold',
  cancelled: 'Cancelled',
  archived: 'Archived',
}

/** Human-readable phase labels */
const phaseLabels: Record<PhaseName, string> = {
  discovery: 'Discovery',
  requirements: 'Requirements',
  implementation: 'Implementation',
  review: 'Review',
  launch: 'Launch',
}

/**
 * Format a date string for display
 */
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateString
  }
}

/**
 * Calculate completion percentage from phase status
 */
function getCompletionPercentage(phaseStatus: Record<string, PhaseStatusEntry>): number {
  const completedPhases = PHASE_ORDER.filter(
    (phase) => phaseStatus[phase]?.status === 'completed' || phaseStatus[phase]?.status === 'skipped'
  ).length
  return Math.round((completedPhases / PHASE_ORDER.length) * 100)
}

/**
 * Get the current active phase (first non-completed/skipped phase)
 */
function getCurrentPhase(phaseStatus: Record<string, PhaseStatusEntry>): PhaseName | null {
  for (const phase of PHASE_ORDER) {
    const status = phaseStatus[phase]?.status
    if (status === 'in_progress' || status === 'blocked') {
      return phase
    }
    if (status !== 'completed' && status !== 'skipped') {
      return phase
    }
  }
  return null
}

/**
 * ProjectCard component displays a project summary in a card format
 *
 * Features:
 * - Project name and client ID
 * - Status badge with color coding
 * - Phase progress visualization
 * - Creation and update timestamps
 * - Hover effects for interactivity
 */
export function ProjectCard({ project, onClick, className }: ProjectCardProps) {
  const completionPercentage = getCompletionPercentage(project.phase_status)
  const currentPhase = getCurrentPhase(project.phase_status)

  const handleClick = () => {
    if (onClick) {
      // Add breadcrumb for debugging
      addBreadcrumb(`Clicked project: ${project.name}`, 'user-action', {
        projectId: project.id,
        projectStatus: project.status,
      })
      onClick(project)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (onClick && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault()
      handleClick()
    }
  }

  return (
    <div
      className={cn(
        'card-hover cursor-pointer group',
        'focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2 focus-visible:ring-offset-cream-50',
        className
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={onClick ? `View project: ${project.name}` : undefined}
    >
      {/* Header: Name and Status */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-warmgray-900 truncate group-hover:text-primary-700 transition-colors duration-200">
            {project.name}
          </h3>
          <p className="text-sm text-warmgray-500 truncate mt-0.5">
            Client: {project.client_id}
          </p>
        </div>
        <span
          className={cn(
            'badge shrink-0',
            statusColors[project.status]
          )}
        >
          {statusLabels[project.status]}
        </span>
      </div>

      {/* Phase Progress */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-2">
          <span className="text-warmgray-600 font-medium">
            {currentPhase ? `${phaseLabels[currentPhase]}` : 'Complete'}
          </span>
          <span className="text-warmgray-500">
            {completionPercentage}% complete
          </span>
        </div>

        {/* Phase indicators */}
        <div className="flex gap-1.5">
          {PHASE_ORDER.map((phase) => {
            const phaseData = project.phase_status[phase]
            const status: PhaseStatus = phaseData?.status || 'pending'

            return (
              <div
                key={phase}
                className={cn(
                  'h-2 flex-1 rounded-full transition-all duration-300',
                  phaseColors[status],
                  status === 'in_progress' && 'animate-pulse-soft'
                )}
                title={`${phaseLabels[phase]}: ${status.replace('_', ' ')}`}
                aria-label={`${phaseLabels[phase]}: ${status.replace('_', ' ')}`}
              />
            )
          })}
        </div>
      </div>

      {/* Footer: Timestamps */}
      <div className="flex items-center justify-between text-xs text-warmgray-400 pt-3 border-t border-cream-200">
        <span>Created {formatDate(project.created_at)}</span>
        <span>Updated {formatDate(project.updated_at)}</span>
      </div>
    </div>
  )
}

/**
 * Loading skeleton for ProjectCard
 * Use while data is being fetched
 */
export function ProjectCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('card', className)}>
      {/* Header skeleton */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex-1 space-y-2">
          <div className="h-5 bg-cream-200 rounded-lg w-3/4 animate-pulse-soft" />
          <div className="h-4 bg-cream-200 rounded-lg w-1/2 animate-pulse-soft" />
        </div>
        <div className="h-6 w-16 bg-cream-200 rounded-lg animate-pulse-soft" />
      </div>

      {/* Progress skeleton */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="h-4 bg-cream-200 rounded w-24 animate-pulse-soft" />
          <div className="h-4 bg-cream-200 rounded w-16 animate-pulse-soft" />
        </div>
        <div className="flex gap-1.5">
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="h-2 flex-1 bg-cream-200 rounded-full animate-pulse-soft"
            />
          ))}
        </div>
      </div>

      {/* Footer skeleton */}
      <div className="flex items-center justify-between pt-3 border-t border-cream-200">
        <div className="h-3 bg-cream-200 rounded w-28 animate-pulse-soft" />
        <div className="h-3 bg-cream-200 rounded w-28 animate-pulse-soft" />
      </div>
    </div>
  )
}
