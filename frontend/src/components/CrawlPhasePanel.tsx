/**
 * CrawlPhasePanel - Configuration form and progress display for crawl phase
 *
 * Features:
 * - Crawl configuration form (start URL, include/exclude patterns, limits)
 * - Real-time progress display during crawl execution
 * - Crawl history list with status indicators
 * - Stop/cancel running crawls
 * - Error handling with user-friendly messages
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Log form validation errors at debug level
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Play,
  Square,
  RefreshCw,
  Globe,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { useProjectSubscription } from '@/lib/hooks/useWebSocket'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { FormField, Input, Textarea } from '@/components/ui/form-field'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Crawl request body */
interface CrawlStartRequest {
  start_url: string
  include_patterns: string[]
  exclude_patterns: string[]
  max_pages: number
  max_depth: number
}

/** Crawl history record from API */
interface CrawlHistory {
  id: string
  project_id: string
  schedule_id: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
  trigger_type: 'manual' | 'scheduled' | 'webhook'
  started_at: string | null
  completed_at: string | null
  pages_crawled: number
  pages_failed: number
  stats: Record<string, unknown>
  error_log: Array<Record<string, unknown>>
  error_message: string | null
  created_at: string
  updated_at: string
}

/** Crawl history list response */
interface CrawlHistoryListResponse {
  items: CrawlHistory[]
  total: number
  limit: number
  offset: number
}

/** Crawl progress response */
interface CrawlProgress {
  crawl_id: string
  project_id: string
  status: string
  pages_crawled: number
  pages_failed: number
  pages_skipped: number
  urls_discovered: number
  current_depth: number
  started_at: string | null
  completed_at: string | null
  error_count: number
}

/** Form state */
interface CrawlFormState {
  startUrl: string
  includePatterns: string
  excludePatterns: string
  maxPages: number
  maxDepth: number
}

/** Form errors */
interface CrawlFormErrors {
  startUrl?: string
  includePatterns?: string
  excludePatterns?: string
  maxPages?: string
  maxDepth?: string
}

// ============================================================================
// Constants
// ============================================================================

/** Default form values */
const DEFAULT_FORM_STATE: CrawlFormState = {
  startUrl: '',
  includePatterns: '',
  excludePatterns: '/admin/*\n/api/*\n*.pdf\n*.zip',
  maxPages: 100,
  maxDepth: 3,
}

/** Status badge styling */
const statusConfig: Record<CrawlHistory['status'], { bg: string; text: string; icon: React.ElementType }> = {
  pending: { bg: 'bg-warmgray-100', text: 'text-warmgray-600', icon: Clock },
  running: { bg: 'bg-primary-100', text: 'text-primary-700', icon: Loader2 },
  completed: { bg: 'bg-success-100', text: 'text-success-700', icon: CheckCircle2 },
  failed: { bg: 'bg-error-100', text: 'text-error-700', icon: XCircle },
  cancelled: { bg: 'bg-warmgray-100', text: 'text-warmgray-600', icon: Square },
  interrupted: { bg: 'bg-warning-100', text: 'text-warning-700', icon: AlertCircle },
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Parse multiline pattern input into array
 */
function parsePatterns(input: string): string[] {
  return input
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

/**
 * Validate the crawl form
 */
function validateForm(state: CrawlFormState): CrawlFormErrors {
  const errors: CrawlFormErrors = {}

  // Validate start URL
  if (!state.startUrl.trim()) {
    errors.startUrl = 'Start URL is required'
  } else if (!state.startUrl.match(/^https?:\/\/.+/)) {
    errors.startUrl = 'URL must start with http:// or https://'
  }

  // Validate max pages
  if (state.maxPages < 1 || state.maxPages > 10000) {
    errors.maxPages = 'Max pages must be between 1 and 10,000'
  }

  // Validate max depth
  if (state.maxDepth < 1 || state.maxDepth > 10) {
    errors.maxDepth = 'Max depth must be between 1 and 10'
  }

  return errors
}

/**
 * Format a date string for display
 */
function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '—'
  try {
    const date = new Date(dateString)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Format duration between two dates
 */
function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return '—'
  const start = new Date(startedAt)
  const end = completedAt ? new Date(completedAt) : new Date()
  const seconds = Math.floor((end.getTime() - start.getTime()) / 1000)

  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  return `${hours}h ${remainingMinutes}m`
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: CrawlHistory['status'] }) {
  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
        config.bg,
        config.text
      )}
    >
      <Icon
        className={cn('w-3.5 h-3.5', status === 'running' && 'animate-spin')}
      />
      <span className="capitalize">{status}</span>
    </span>
  )
}

/**
 * Progress bar component
 */
function ProgressBar({
  current,
  max,
  label,
}: {
  current: number
  max: number
  label: string
}) {
  const percentage = max > 0 ? Math.min(100, Math.round((current / max) * 100)) : 0

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-warmgray-600">{label}</span>
        <span className="text-warmgray-500 font-medium">
          {current.toLocaleString()} / {max.toLocaleString()}
        </span>
      </div>
      <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-primary-500 rounded-full transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}

/**
 * Crawl history item component
 */
function CrawlHistoryItem({
  crawl,
}: {
  crawl: CrawlHistory
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="border border-cream-200 rounded-xl bg-white overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between p-4 text-left hover:bg-cream-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-4 min-w-0 flex-1">
          <StatusBadge status={crawl.status} />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-warmgray-900 truncate">
              {formatDateTime(crawl.started_at || crawl.created_at)}
            </p>
            <p className="text-xs text-warmgray-500">
              {crawl.pages_crawled} pages crawled
              {crawl.pages_failed > 0 && (
                <span className="text-error-500"> • {crawl.pages_failed} failed</span>
              )}
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-warmgray-400 shrink-0" />
        ) : (
          <ChevronDown className="w-5 h-5 text-warmgray-400 shrink-0" />
        )}
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-cream-100 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-warmgray-500">Trigger:</span>{' '}
              <span className="text-warmgray-700 capitalize">{crawl.trigger_type}</span>
            </div>
            <div>
              <span className="text-warmgray-500">Duration:</span>{' '}
              <span className="text-warmgray-700">
                {formatDuration(crawl.started_at, crawl.completed_at)}
              </span>
            </div>
            {crawl.completed_at && (
              <div className="col-span-2">
                <span className="text-warmgray-500">Completed:</span>{' '}
                <span className="text-warmgray-700">{formatDateTime(crawl.completed_at)}</span>
              </div>
            )}
          </div>

          {crawl.error_message && (
            <div className="p-3 bg-error-50 rounded-lg border border-error-200">
              <p className="text-sm text-error-700">
                <span className="font-medium">Error:</span> {crawl.error_message}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export interface CrawlPhasePanelProps {
  /** Project ID to manage crawls for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * CrawlPhasePanel provides crawl configuration and progress tracking
 *
 * @example
 * <CrawlPhasePanel projectId="abc-123" />
 */
export function CrawlPhasePanel({ projectId, className }: CrawlPhasePanelProps) {
  const queryClient = useQueryClient()

  // Form state
  const [formState, setFormState] = useState<CrawlFormState>(DEFAULT_FORM_STATE)
  const [formErrors, setFormErrors] = useState<CrawlFormErrors>({})
  const [showConfig, setShowConfig] = useState(true)

  // Track active crawl for progress polling
  const [activeCrawlId, setActiveCrawlId] = useState<string | null>(null)

  // Fetch crawl history
  const {
    data: historyData,
    isLoading: isLoadingHistory,
    refetch: refetchHistory,
  } = useApiQuery<CrawlHistoryListResponse>({
    queryKey: ['crawl-history', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/crawl`,
    requestOptions: {
      userAction: 'Load crawl history',
      component: 'CrawlPhasePanel',
    },
  })

  // Fetch active crawl progress (when there's a running crawl)
  const { data: progressData } = useApiQuery<CrawlProgress>({
    queryKey: ['crawl-progress', projectId, activeCrawlId],
    endpoint: `/api/v1/projects/${projectId}/phases/crawl/${activeCrawlId}/progress`,
    requestOptions: {
      userAction: 'Get crawl progress',
      component: 'CrawlPhasePanel',
    },
    enabled: !!activeCrawlId,
    refetchInterval: activeCrawlId ? 2000 : false, // Poll every 2s when crawl is active
  })

  // Start crawl mutation
  const startCrawlMutation = useToastMutation<CrawlHistory, Error, CrawlStartRequest>({
    mutationFn: async (data) => {
      const response = await fetch(
        `/api/v1/projects/${projectId}/phases/crawl`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const error = new Error(errorData.error || 'Failed to start crawl')
        console.error('[CrawlPhasePanel] Start crawl failed:', {
          endpoint: `/api/v1/projects/${projectId}/phases/crawl`,
          status: response.status,
          responseBody: errorData,
          userAction: 'Start crawl',
        })
        throw error
      }
      return response.json()
    },
    userAction: 'Start crawl',
    successMessage: 'Crawl started',
    successDescription: 'The crawl is now running in the background.',
    onSuccess: (data) => {
      addBreadcrumb('Crawl started', 'crawl', { crawlId: data.id })
      setActiveCrawlId(data.id)
      setShowConfig(false)
      queryClient.invalidateQueries({ queryKey: ['crawl-history', projectId] })
    },
  })

  // Stop crawl mutation
  const stopCrawlMutation = useToastMutation<{ status: string; message: string }, Error, string>({
    mutationFn: async (crawlId) => {
      const response = await fetch(
        `/api/v1/projects/${projectId}/phases/crawl/${crawlId}/stop`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const error = new Error(errorData.error || 'Failed to stop crawl')
        console.error('[CrawlPhasePanel] Stop crawl failed:', {
          endpoint: `/api/v1/projects/${projectId}/phases/crawl/${crawlId}/stop`,
          status: response.status,
          responseBody: errorData,
          userAction: 'Stop crawl',
        })
        throw error
      }
      return response.json()
    },
    userAction: 'Stop crawl',
    successMessage: 'Crawl stopped',
    successDescription: 'The crawl has been cancelled.',
    onSuccess: () => {
      addBreadcrumb('Crawl stopped', 'crawl', { crawlId: activeCrawlId })
      setActiveCrawlId(null)
      queryClient.invalidateQueries({ queryKey: ['crawl-history', projectId] })
    },
  })

  // Find running crawl from history
  const runningCrawl = useMemo(() => {
    return historyData?.items.find((c) => c.status === 'running' || c.status === 'pending')
  }, [historyData])

  // Set active crawl ID when we find a running crawl
  useEffect(() => {
    if (runningCrawl && !activeCrawlId) {
      setActiveCrawlId(runningCrawl.id)
      setShowConfig(false)
    } else if (!runningCrawl && activeCrawlId) {
      // Crawl completed, clear active crawl
      setActiveCrawlId(null)
      refetchHistory()
    }
  }, [runningCrawl, activeCrawlId, refetchHistory])

  // Handle WebSocket updates for real-time progress
  const handleWebSocketUpdate = useCallback(
    (data: Record<string, unknown>, event: string) => {
      console.debug('[CrawlPhasePanel] WebSocket update:', { event, data })
      addBreadcrumb('WebSocket crawl update', 'websocket', { event })
      queryClient.invalidateQueries({ queryKey: ['crawl-history', projectId] })
      queryClient.invalidateQueries({ queryKey: ['crawl-progress', projectId] })
    },
    [projectId, queryClient]
  )

  // Subscribe to WebSocket updates
  useProjectSubscription(projectId, {
    onUpdate: handleWebSocketUpdate,
    enabled: !!activeCrawlId,
  })

  // Form handlers
  const handleInputChange = useCallback(
    (field: keyof CrawlFormState, value: string | number) => {
      setFormState((prev) => ({ ...prev, [field]: value }))
      setFormErrors((prev) => ({ ...prev, [field]: undefined }))
    },
    []
  )

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()

      const errors = validateForm(formState)
      if (Object.keys(errors).length > 0) {
        setFormErrors(errors)
        console.debug('[CrawlPhasePanel] Form validation failed:', errors)
        addBreadcrumb('Crawl form validation failed', 'validation', { errors })
        return
      }

      addBreadcrumb('Starting crawl', 'user_action', {
        startUrl: formState.startUrl,
        maxPages: formState.maxPages,
        maxDepth: formState.maxDepth,
      })

      startCrawlMutation.mutate({
        start_url: formState.startUrl.trim(),
        include_patterns: parsePatterns(formState.includePatterns),
        exclude_patterns: parsePatterns(formState.excludePatterns),
        max_pages: formState.maxPages,
        max_depth: formState.maxDepth,
      })
    },
    [formState, startCrawlMutation]
  )

  const handleStopCrawl = useCallback(() => {
    if (activeCrawlId) {
      addBreadcrumb('Stopping crawl', 'user_action', { crawlId: activeCrawlId })
      stopCrawlMutation.mutate(activeCrawlId)
    }
  }, [activeCrawlId, stopCrawlMutation])

  const isSubmitting = startCrawlMutation.isPending
  const isStopping = stopCrawlMutation.isPending

  return (
    <div className={cn('space-y-6', className)}>
      {/* Active Crawl Progress */}
      {activeCrawlId && progressData && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
              </div>
              <div>
                <h3 className="font-semibold text-warmgray-900">Crawl In Progress</h3>
                <p className="text-sm text-warmgray-500">
                  Started {formatDateTime(progressData.started_at)}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStopCrawl}
              disabled={isStopping}
              className="text-error-600 hover:text-error-700 hover:bg-error-50"
            >
              {isStopping ? (
                <ButtonSpinner />
              ) : (
                <>
                  <Square className="w-4 h-4" />
                  Stop Crawl
                </>
              )}
            </Button>
          </div>

          <div className="space-y-4">
            <ProgressBar
              current={progressData.pages_crawled}
              max={100} // We don't have max_pages in progress response
              label="Pages Crawled"
            />

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
              <div className="text-center p-3 bg-white rounded-lg border border-cream-200">
                <p className="text-2xl font-semibold text-warmgray-900">
                  {progressData.pages_crawled}
                </p>
                <p className="text-xs text-warmgray-500">Crawled</p>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border border-cream-200">
                <p className="text-2xl font-semibold text-warmgray-900">
                  {progressData.urls_discovered}
                </p>
                <p className="text-xs text-warmgray-500">Discovered</p>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border border-cream-200">
                <p className="text-2xl font-semibold text-warmgray-900">
                  {progressData.current_depth}
                </p>
                <p className="text-xs text-warmgray-500">Depth</p>
              </div>
              <div className="text-center p-3 bg-white rounded-lg border border-cream-200">
                <p className={cn(
                  'text-2xl font-semibold',
                  progressData.pages_failed > 0 ? 'text-error-600' : 'text-warmgray-900'
                )}>
                  {progressData.pages_failed}
                </p>
                <p className="text-xs text-warmgray-500">Failed</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configuration Form */}
      <div className="card">
        <button
          type="button"
          className="w-full flex items-center justify-between"
          onClick={() => setShowConfig(!showConfig)}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
              <Globe className="w-5 h-5 text-warmgray-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-warmgray-900">Crawl Configuration</h3>
              <p className="text-sm text-warmgray-500">Configure and start a new crawl</p>
            </div>
          </div>
          {showConfig ? (
            <ChevronUp className="w-5 h-5 text-warmgray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-warmgray-400" />
          )}
        </button>

        {showConfig && (
          <form onSubmit={handleSubmit} className="mt-6 space-y-5">
            <FormField
              label="Start URL"
              required
              error={formErrors.startUrl}
              helperText="The URL to begin crawling from"
            >
              <Input
                type="url"
                placeholder="https://example.com"
                value={formState.startUrl}
                onChange={(e) => handleInputChange('startUrl', e.target.value)}
                disabled={isSubmitting || !!activeCrawlId}
              />
            </FormField>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField
                label="Max Pages"
                error={formErrors.maxPages}
                helperText="Maximum pages to crawl (1-10,000)"
              >
                <Input
                  type="number"
                  min={1}
                  max={10000}
                  value={formState.maxPages}
                  onChange={(e) => handleInputChange('maxPages', parseInt(e.target.value, 10) || 100)}
                  disabled={isSubmitting || !!activeCrawlId}
                />
              </FormField>

              <FormField
                label="Max Depth"
                error={formErrors.maxDepth}
                helperText="Maximum crawl depth (1-10)"
              >
                <Input
                  type="number"
                  min={1}
                  max={10}
                  value={formState.maxDepth}
                  onChange={(e) => handleInputChange('maxDepth', parseInt(e.target.value, 10) || 3)}
                  disabled={isSubmitting || !!activeCrawlId}
                />
              </FormField>
            </div>

            <FormField
              label="Include Patterns"
              optional
              error={formErrors.includePatterns}
              helperText="Glob patterns for URLs to include, one per line (e.g., /products/*)"
            >
              <Textarea
                placeholder="/products/*&#10;/services/*"
                rows={3}
                value={formState.includePatterns}
                onChange={(e) => handleInputChange('includePatterns', e.target.value)}
                disabled={isSubmitting || !!activeCrawlId}
              />
            </FormField>

            <FormField
              label="Exclude Patterns"
              optional
              error={formErrors.excludePatterns}
              helperText="Glob patterns for URLs to exclude, one per line (e.g., /admin/*)"
            >
              <Textarea
                placeholder="/admin/*&#10;/api/*&#10;*.pdf"
                rows={3}
                value={formState.excludePatterns}
                onChange={(e) => handleInputChange('excludePatterns', e.target.value)}
                disabled={isSubmitting || !!activeCrawlId}
              />
            </FormField>

            <div className="flex justify-end pt-2">
              <Button
                type="submit"
                disabled={isSubmitting || !!activeCrawlId}
              >
                {isSubmitting ? (
                  <ButtonSpinner />
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Start Crawl
                  </>
                )}
              </Button>
            </div>
          </form>
        )}
      </div>

      {/* Crawl History */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-warmgray-900">Crawl History</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchHistory()}
            disabled={isLoadingHistory}
          >
            <RefreshCw className={cn('w-4 h-4', isLoadingHistory && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {isLoadingHistory ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" label="Loading crawl history..." showLabel />
          </div>
        ) : historyData?.items.length === 0 ? (
          <div className="text-center py-8">
            <Globe className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
            <p className="text-warmgray-500">No crawls yet</p>
            <p className="text-sm text-warmgray-400 mt-1">
              Configure and start a crawl above to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {historyData?.items.slice(0, 10).map((crawl) => (
              <CrawlHistoryItem key={crawl.id} crawl={crawl} />
            ))}
            {historyData && historyData.total > 10 && (
              <p className="text-center text-sm text-warmgray-500 pt-2">
                Showing 10 of {historyData.total} crawls
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
