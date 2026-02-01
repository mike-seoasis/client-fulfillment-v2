/**
 * ProjectDetailPage - Detailed view of a single project with phase status overview
 *
 * Features:
 * - Project header with name, status, and actions
 * - Phase status overview with detailed progress for each phase
 * - Real-time updates via WebSocket connection
 * - Error handling with ErrorBoundary integration
 * - Loading states with skeletons
 * - Breadcrumb navigation back to projects list
 *
 * RAILWAY DEPLOYMENT:
 * - WebSocket connection with heartbeat for keepalive
 * - Automatic reconnection with exponential backoff
 * - Fallback to polling when WebSocket unavailable
 */

import { useCallback, useMemo } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Clock, Calendar, AlertCircle, CheckCircle2, Circle, SkipForward, Loader2, Wifi, WifiOff } from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useProjectSubscription } from '@/lib/hooks/useWebSocket'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { PhaseProgress } from '@/components/PhaseProgress'
import { cn } from '@/lib/utils'
import {
  type PhaseStatus,
  type PhaseStatusEntry,
  PHASE_ORDER,
  type PhaseName,
  phaseLabels,
  getCompletionPercentage,
  getCurrentPhase,
} from '@/lib/phaseUtils'

/** Valid project statuses */
type ProjectStatus = 'active' | 'completed' | 'on_hold' | 'cancelled' | 'archived'

/** Project data structure matching backend schema */
interface ProjectDetail {
  id: string
  name: string
  client_id: string
  status: ProjectStatus
  phase_status: Record<string, PhaseStatusEntry>
  created_at: string
  updated_at: string
}

/** Status badge colors */
const statusColors: Record<ProjectStatus, string> = {
  active: 'bg-success-100 text-success-800 border-success-200',
  completed: 'bg-primary-100 text-primary-800 border-primary-200',
  on_hold: 'bg-warning-100 text-warning-800 border-warning-200',
  cancelled: 'bg-error-100 text-error-800 border-error-200',
  archived: 'bg-cream-200 text-warmgray-600 border-cream-300',
}

/** Human-readable status labels */
const statusLabels: Record<ProjectStatus, string> = {
  active: 'Active',
  completed: 'Completed',
  on_hold: 'On Hold',
  cancelled: 'Cancelled',
  archived: 'Archived',
}

/** Phase status icon mapping */
const phaseStatusIcons: Record<PhaseStatus, React.ElementType> = {
  pending: Circle,
  in_progress: Loader2,
  completed: CheckCircle2,
  blocked: AlertCircle,
  skipped: SkipForward,
}

/** Phase status colors for cards */
const phaseStatusColors: Record<PhaseStatus, { bg: string; border: string; text: string; icon: string }> = {
  pending: {
    bg: 'bg-cream-50',
    border: 'border-cream-200',
    text: 'text-warmgray-500',
    icon: 'text-warmgray-400',
  },
  in_progress: {
    bg: 'bg-primary-50',
    border: 'border-primary-200',
    text: 'text-primary-700',
    icon: 'text-primary-500',
  },
  completed: {
    bg: 'bg-success-50',
    border: 'border-success-200',
    text: 'text-success-700',
    icon: 'text-success-500',
  },
  blocked: {
    bg: 'bg-error-50',
    border: 'border-error-200',
    text: 'text-error-700',
    icon: 'text-error-500',
  },
  skipped: {
    bg: 'bg-warmgray-50',
    border: 'border-warmgray-200',
    text: 'text-warmgray-600',
    icon: 'text-warmgray-400',
  },
}

/** Human-readable phase status labels */
const phaseStatusLabels: Record<PhaseStatus, string> = {
  pending: 'Not Started',
  in_progress: 'In Progress',
  completed: 'Completed',
  blocked: 'Blocked',
  skipped: 'Skipped',
}

/**
 * Format a date string for display
 */
function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—'
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
 * Format a date with time for display
 */
function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Phase status card component
 */
function PhaseCard({
  phase,
  phaseData,
  isCurrentPhase,
}: {
  phase: PhaseName
  phaseData: PhaseStatusEntry | undefined
  isCurrentPhase: boolean
}) {
  const status: PhaseStatus = phaseData?.status || 'pending'
  const colors = phaseStatusColors[status]
  const Icon = phaseStatusIcons[status]

  return (
    <div
      className={cn(
        'rounded-xl border-2 p-5 transition-all duration-200',
        colors.bg,
        colors.border,
        isCurrentPhase && 'ring-2 ring-primary-400 ring-offset-2 ring-offset-cream-50'
      )}
    >
      {/* Phase header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-warmgray-900">
            {phaseLabels[phase]}
          </h3>
          <div className={cn('flex items-center gap-1.5 mt-1', colors.text)}>
            <Icon
              className={cn(
                'w-4 h-4 shrink-0',
                colors.icon,
                status === 'in_progress' && 'animate-spin'
              )}
            />
            <span className="text-sm font-medium">{phaseStatusLabels[status]}</span>
          </div>
        </div>
        {isCurrentPhase && (
          <span className="shrink-0 px-2 py-0.5 text-xs font-medium bg-primary-500 text-white rounded-full">
            Current
          </span>
        )}
      </div>

      {/* Phase timestamps */}
      <div className="space-y-2 text-sm">
        {phaseData?.started_at && (
          <div className="flex items-center gap-2 text-warmgray-600">
            <Clock className="w-3.5 h-3.5 text-warmgray-400" />
            <span>Started: {formatDateTime(phaseData.started_at)}</span>
          </div>
        )}
        {phaseData?.completed_at && (
          <div className="flex items-center gap-2 text-warmgray-600">
            <Calendar className="w-3.5 h-3.5 text-warmgray-400" />
            <span>Completed: {formatDateTime(phaseData.completed_at)}</span>
          </div>
        )}
        {phaseData?.blocked_reason && (
          <div className="mt-3 p-3 bg-error-100/50 rounded-lg border border-error-200">
            <p className="text-sm text-error-700">
              <span className="font-medium">Blocked:</span> {phaseData.blocked_reason}
            </p>
          </div>
        )}
        {!phaseData?.started_at && !phaseData?.completed_at && !phaseData?.blocked_reason && (
          <p className="text-warmgray-400 text-sm">Waiting to start</p>
        )}
      </div>
    </div>
  )
}

/**
 * Loading skeleton for the detail page
 */
function ProjectDetailSkeleton() {
  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb skeleton */}
        <div className="h-5 bg-cream-200 rounded w-32 mb-6 animate-pulse-soft" />

        {/* Header skeleton */}
        <div className="mb-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-3">
              <div className="h-8 bg-cream-200 rounded-lg w-64 animate-pulse-soft" />
              <div className="h-5 bg-cream-200 rounded w-40 animate-pulse-soft" />
            </div>
            <div className="h-8 w-20 bg-cream-200 rounded-lg animate-pulse-soft" />
          </div>
        </div>

        {/* Progress skeleton */}
        <div className="card mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="h-6 bg-cream-200 rounded w-32 animate-pulse-soft" />
            <div className="h-5 bg-cream-200 rounded w-24 animate-pulse-soft" />
          </div>
          <div className="flex gap-1.5">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-3 flex-1 bg-cream-200 rounded-full animate-pulse-soft" />
            ))}
          </div>
        </div>

        {/* Phase cards skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="rounded-xl border-2 border-cream-200 p-5 bg-white">
              <div className="space-y-3">
                <div className="h-5 bg-cream-200 rounded w-24 animate-pulse-soft" />
                <div className="h-4 bg-cream-200 rounded w-20 animate-pulse-soft" />
                <div className="h-4 bg-cream-200 rounded w-32 animate-pulse-soft" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/**
 * Error state component
 */
function ErrorState({
  error,
  onRetry,
  onGoBack,
}: {
  error: Error & { status?: number }
  onRetry: () => void
  onGoBack: () => void
}) {
  const isNotFound = error.status === 404

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
          <div
            className={cn(
              'w-16 h-16 rounded-2xl flex items-center justify-center mb-6',
              isNotFound ? 'bg-warning-100' : 'bg-error-100'
            )}
          >
            <AlertCircle
              className={cn('w-8 h-8', isNotFound ? 'text-warning-500' : 'text-error-500')}
            />
          </div>
          <h2 className="text-xl font-semibold text-warmgray-900 mb-2">
            {isNotFound ? 'Project not found' : 'Failed to load project'}
          </h2>
          <p className="text-warmgray-500 mb-6 max-w-sm">
            {isNotFound
              ? "The project you're looking for doesn't exist or has been deleted."
              : "We couldn't load this project. Please check your connection and try again."}
          </p>
          <div className="flex gap-3">
            <Button variant="outline" onClick={onGoBack}>
              <ArrowLeft className="w-4 h-4" />
              Back to projects
            </Button>
            {!isNotFound && <Button onClick={onRetry}>Try again</Button>}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * ProjectDetailPage displays detailed information about a single project
 */
export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Fetch project details
  const {
    data: project,
    isLoading,
    isError,
    error,
    refetch,
  } = useApiQuery<ProjectDetail>({
    queryKey: ['project', projectId],
    endpoint: `/api/projects/${projectId}`,
    requestOptions: {
      userAction: 'Load project details',
      component: 'ProjectDetailPage',
    },
    enabled: !!projectId,
  })

  // Handle real-time updates via WebSocket
  const handleUpdate = useCallback((data: Record<string, unknown>, event: string) => {
    console.info('[ProjectDetailPage] Real-time update received:', {
      projectId,
      event,
      dataKeys: Object.keys(data),
    })
    addBreadcrumb('Project update received', 'websocket', { projectId, event })

    // Invalidate and refetch project data
    queryClient.invalidateQueries({ queryKey: ['project', projectId] })
  }, [projectId, queryClient])

  const handleProgress = useCallback((progress: Record<string, unknown>) => {
    console.debug('[ProjectDetailPage] Progress update received:', {
      projectId,
      progress,
    })
    addBreadcrumb('Progress update received', 'websocket', { projectId })
  }, [projectId])

  // Subscribe to real-time updates for this project
  const { isConnected, state: wsState } = useProjectSubscription(projectId, {
    onUpdate: handleUpdate,
    onProgress: handleProgress,
    enabled: !!projectId && !isLoading,
  })

  // Calculate phase progress
  const { completionPercentage, currentPhase } = useMemo(() => {
    if (!project) return { completionPercentage: 0, currentPhase: null }
    return {
      completionPercentage: getCompletionPercentage(project.phase_status),
      currentPhase: getCurrentPhase(project.phase_status),
    }
  }, [project])

  // Handle navigation
  const handleGoBack = () => {
    addBreadcrumb('Navigate back to projects list', 'navigation')
    navigate('/projects')
  }

  const handleRetry = () => {
    addBreadcrumb('Retry loading project', 'user-action', { projectId })
    refetch()
  }

  // Log errors
  if (isError && error) {
    console.error('[ProjectDetailPage] Failed to load project:', {
      error: error.message,
      endpoint: `/api/projects/${projectId}`,
      status: error.status,
      projectId,
    })
  }

  // Loading state
  if (isLoading) {
    return <ProjectDetailSkeleton />
  }

  // Error state
  if (isError) {
    return <ErrorState error={error} onRetry={handleRetry} onGoBack={handleGoBack} />
  }

  // No data (shouldn't happen but handle gracefully)
  if (!project) {
    return <ErrorState error={new Error('No data')} onRetry={handleRetry} onGoBack={handleGoBack} />
  }

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb navigation */}
        <nav className="mb-6">
          <Link
            to="/projects"
            className="inline-flex items-center gap-1.5 text-sm text-warmgray-500 hover:text-warmgray-700 transition-colors"
            onClick={() => addBreadcrumb('Click breadcrumb to projects', 'navigation')}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to projects
          </Link>
        </nav>

        {/* Project header */}
        <header className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-display font-semibold text-warmgray-900 mb-1">
                {project.name}
              </h1>
              <p className="text-warmgray-500">
                Client: {project.client_id}
              </p>
            </div>
            <span
              className={cn(
                'badge shrink-0 border',
                statusColors[project.status]
              )}
            >
              {statusLabels[project.status]}
            </span>
          </div>

          {/* Timestamps and connection status */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mt-4 text-sm text-warmgray-500">
            <div className="flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-warmgray-400" />
              <span>Created: {formatDate(project.created_at)}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-warmgray-400" />
              <span>Updated: {formatDate(project.updated_at)}</span>
            </div>
            {/* Real-time connection indicator */}
            <div
              className={cn(
                'flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
                isConnected
                  ? 'bg-success-100 text-success-700'
                  : wsState === 'reconnecting' || wsState === 'connecting'
                    ? 'bg-warning-100 text-warning-700'
                    : wsState === 'fallback_polling'
                      ? 'bg-primary-100 text-primary-700'
                      : 'bg-warmgray-100 text-warmgray-600'
              )}
              title={
                isConnected
                  ? 'Real-time updates active'
                  : wsState === 'reconnecting'
                    ? 'Reconnecting...'
                    : wsState === 'connecting'
                      ? 'Connecting...'
                      : wsState === 'fallback_polling'
                        ? 'Using polling for updates'
                        : 'Updates paused'
              }
            >
              {isConnected ? (
                <Wifi className="w-3 h-3" />
              ) : wsState === 'reconnecting' || wsState === 'connecting' ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <WifiOff className="w-3 h-3" />
              )}
              <span>
                {isConnected
                  ? 'Live'
                  : wsState === 'reconnecting'
                    ? 'Reconnecting'
                    : wsState === 'connecting'
                      ? 'Connecting'
                      : wsState === 'fallback_polling'
                        ? 'Polling'
                        : 'Offline'}
              </span>
            </div>
          </div>
        </header>

        {/* Progress overview card */}
        <section className="card mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-warmgray-900">
              Overall Progress
            </h2>
            <span className="text-warmgray-600 font-medium">
              {completionPercentage}% complete
            </span>
          </div>
          <PhaseProgress phaseStatus={project.phase_status} size="lg" />
          {currentPhase && (
            <p className="mt-3 text-sm text-warmgray-500">
              Currently in <span className="font-medium text-warmgray-700">{phaseLabels[currentPhase]}</span> phase
            </p>
          )}
        </section>

        {/* Phase details grid */}
        <section>
          <h2 className="text-lg font-semibold text-warmgray-900 mb-4">
            Phase Status
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PHASE_ORDER.map((phase) => (
              <PhaseCard
                key={phase}
                phase={phase}
                phaseData={project.phase_status[phase]}
                isCurrentPhase={phase === currentPhase}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
