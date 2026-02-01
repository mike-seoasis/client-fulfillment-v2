/**
 * KeywordResearchPanel - Keyword research with approval workflow
 *
 * Features:
 * - Statistics overview showing total pages and keyword research progress
 * - Keyword research configuration form with LLM options
 * - Approval workflow for reviewing suggested keywords
 * - Real-time progress during research
 * - Cache statistics display
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
  Search,
  Play,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  TrendingUp,
  Check,
  X,
  Sparkles,
  Database,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { useProjectSubscription } from '@/lib/hooks/useWebSocket'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { FormField, Select } from '@/components/ui/form-field'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Volume stats from API */
interface VolumeStats {
  total_keywords: number
  cache_hits: number
  cache_misses: number
  api_lookups: number
  api_errors: number
  cache_hit_rate: number
}

/** Keyword research stats from API */
interface KeywordResearchStats {
  project_id: string
  total_pages: number
  pages_with_keywords: number
  pages_without_keywords: number
  total_primary_keywords: number
  total_secondary_keywords: number
  cache_stats: VolumeStats | null
}

/** Keyword with volume data */
interface KeywordWithVolume {
  keyword: string
  volume: number | null
  cpc: number | null
  competition: number | null
}

/** Pending approval item */
interface PendingApproval {
  page_id: string
  page_url: string
  page_title: string
  primary_keyword: string | null
  primary_volume: number | null
  secondary_keywords: KeywordWithVolume[]
  all_suggestions: KeywordWithVolume[]
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

/** Form state for keyword research options */
interface KeywordResearchFormState {
  country: string
  dataSource: string
  autoApprove: boolean
}

// ============================================================================
// Constants
// ============================================================================

/** Default form values */
const DEFAULT_FORM_STATE: KeywordResearchFormState = {
  country: 'us',
  dataSource: 'gkp',
  autoApprove: false,
}

/** Country options */
const COUNTRY_OPTIONS = [
  { value: 'us', label: 'United States' },
  { value: 'uk', label: 'United Kingdom' },
  { value: 'ca', label: 'Canada' },
  { value: 'au', label: 'Australia' },
]

/** Data source options */
const DATA_SOURCE_OPTIONS = [
  { value: 'gkp', label: 'Google Keyword Planner' },
  { value: 'cli', label: 'Clickstream Data' },
]

/** Status colors */
const statusColors = {
  pending: { bg: 'bg-gold-50', text: 'text-gold-700', border: 'border-gold-200' },
  approved: { bg: 'bg-success-50', text: 'text-success-700', border: 'border-success-200' },
  rejected: { bg: 'bg-error-50', text: 'text-error-700', border: 'border-error-200' },
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Progress bar component
 */
function ProgressBar({
  current,
  total,
  label,
}: {
  current: number
  total: number
  label: string
}) {
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-warmgray-600">{label}</span>
        <span className="text-warmgray-500 font-medium">{percentage}%</span>
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
 * Stats card component
 */
function StatsCard({
  label,
  value,
  icon: Icon,
  variant = 'default',
}: {
  label: string
  value: number | string
  icon: React.ElementType
  variant?: 'default' | 'success' | 'warning'
}) {
  const variantStyles = {
    default: 'bg-cream-50 border-cream-200',
    success: 'bg-success-50 border-success-200',
    warning: 'bg-gold-50 border-gold-200',
  }

  const iconStyles = {
    default: 'text-warmgray-500',
    success: 'text-success-600',
    warning: 'text-gold-600',
  }

  return (
    <div className={cn('p-4 rounded-xl border', variantStyles[variant])}>
      <div className="flex items-center gap-3">
        <Icon className={cn('w-5 h-5', iconStyles[variant])} />
        <div>
          <p className="text-2xl font-semibold text-warmgray-900">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          <p className="text-sm text-warmgray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}

/**
 * Keyword badge component
 */
function KeywordBadge({
  keyword,
  volume,
  isPrimary = false,
}: {
  keyword: string
  volume: number | null
  isPrimary?: boolean
}) {
  return (
    <div
      className={cn(
        'flex items-center justify-between px-3 py-2 rounded-lg border',
        isPrimary
          ? 'bg-primary-100 border-primary-200'
          : 'bg-cream-50 border-cream-200'
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        {isPrimary && <Sparkles className="w-3.5 h-3.5 text-primary-600 shrink-0" />}
        <span
          className={cn(
            'text-sm font-medium truncate',
            isPrimary ? 'text-primary-700' : 'text-warmgray-700'
          )}
        >
          {keyword}
        </span>
      </div>
      {volume !== null && (
        <span
          className={cn(
            'text-xs font-medium ml-2 shrink-0',
            isPrimary ? 'text-primary-600' : 'text-warmgray-500'
          )}
        >
          {volume.toLocaleString()} /mo
        </span>
      )}
    </div>
  )
}

/**
 * Checkbox toggle component
 */
function Checkbox({
  label,
  checked,
  onChange,
  disabled,
  helperText,
}: {
  label: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
  helperText?: string
}) {
  return (
    <label
      className={cn(
        'flex items-start gap-3 cursor-pointer',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="mt-1 w-4 h-4 rounded border-warmgray-300 text-primary-600 focus:ring-primary-500 focus:ring-offset-0"
      />
      <div>
        <span className="text-sm font-medium text-warmgray-700">{label}</span>
        {helperText && (
          <p className="text-xs text-warmgray-500 mt-0.5">{helperText}</p>
        )}
      </div>
    </label>
  )
}

/**
 * Approval card component for reviewing keyword suggestions
 */
function ApprovalCard({
  approval,
  onApprove,
  onReject,
  onModify,
  isProcessing,
}: {
  approval: PendingApproval
  onApprove: (pageId: string) => void
  onReject: (pageId: string) => void
  onModify: (pageId: string) => void
  isProcessing: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="border border-cream-200 rounded-xl bg-white overflow-hidden">
      <button
        type="button"
        className="w-full p-4 flex items-center justify-between hover:bg-cream-50/50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={cn(
              'w-2 h-2 rounded-full shrink-0',
              approval.status === 'pending' && 'bg-gold-500',
              approval.status === 'approved' && 'bg-success-500',
              approval.status === 'rejected' && 'bg-error-500'
            )}
          />
          <div className="text-left min-w-0">
            <p className="text-sm font-medium text-warmgray-900 truncate">
              {approval.page_title || approval.page_url}
            </p>
            {approval.primary_keyword && (
              <p className="text-xs text-warmgray-500 mt-0.5">
                Primary: <span className="font-medium">{approval.primary_keyword}</span>
                {approval.primary_volume !== null && (
                  <span className="text-warmgray-400">
                    {' '}({approval.primary_volume.toLocaleString()} /mo)
                  </span>
                )}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={cn(
              'text-xs px-2 py-0.5 rounded-full font-medium capitalize',
              statusColors[approval.status].bg,
              statusColors[approval.status].text
            )}
          >
            {approval.status}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-warmgray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-warmgray-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-cream-100 pt-4 space-y-4">
          {/* Primary Keyword */}
          {approval.primary_keyword && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                Primary Keyword
              </h4>
              <KeywordBadge
                keyword={approval.primary_keyword}
                volume={approval.primary_volume}
                isPrimary
              />
            </div>
          )}

          {/* Secondary Keywords */}
          {approval.secondary_keywords.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                Secondary Keywords ({approval.secondary_keywords.length})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {approval.secondary_keywords.map((kw) => (
                  <KeywordBadge key={kw.keyword} keyword={kw.keyword} volume={kw.volume} />
                ))}
              </div>
            </div>
          )}

          {/* All Suggestions (collapsed by default) */}
          {approval.all_suggestions.length > 0 && (
            <details className="group">
              <summary className="text-xs font-medium text-warmgray-500 cursor-pointer hover:text-warmgray-700">
                View all suggestions ({approval.all_suggestions.length})
              </summary>
              <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                {approval.all_suggestions.slice(0, 12).map((kw) => (
                  <div
                    key={kw.keyword}
                    className="text-xs px-2 py-1 bg-cream-50 rounded text-warmgray-600 truncate"
                    title={`${kw.keyword} - ${kw.volume?.toLocaleString() || '?'} /mo`}
                  >
                    {kw.keyword}
                  </div>
                ))}
                {approval.all_suggestions.length > 12 && (
                  <div className="text-xs px-2 py-1 text-warmgray-400">
                    +{approval.all_suggestions.length - 12} more
                  </div>
                )}
              </div>
            </details>
          )}

          {/* Action Buttons */}
          {approval.status === 'pending' && (
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onModify(approval.page_id)}
                disabled={isProcessing}
              >
                Modify
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onReject(approval.page_id)}
                disabled={isProcessing}
                className="text-error-600 border-error-200 hover:bg-error-50"
              >
                <X className="w-4 h-4" />
                Reject
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => onApprove(approval.page_id)}
                disabled={isProcessing}
              >
                {isProcessing ? (
                  <ButtonSpinner />
                ) : (
                  <>
                    <Check className="w-4 h-4" />
                    Approve
                  </>
                )}
              </Button>
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

export interface KeywordResearchPanelProps {
  /** Project ID to manage keyword research for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * KeywordResearchPanel provides keyword research controls with approval workflow
 *
 * @example
 * <KeywordResearchPanel projectId="abc-123" />
 */
export function KeywordResearchPanel({ projectId, className }: KeywordResearchPanelProps) {
  const queryClient = useQueryClient()

  // Form state
  const [formState, setFormState] = useState<KeywordResearchFormState>(DEFAULT_FORM_STATE)
  const [showConfig, setShowConfig] = useState(true)
  const [showApprovals, setShowApprovals] = useState(true)
  const [isResearching, setIsResearching] = useState(false)
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([])
  const [processingPageId, setProcessingPageId] = useState<string | null>(null)

  // Fetch keyword research stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useApiQuery<KeywordResearchStats>({
    queryKey: ['keyword-research-stats', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/keyword_research/stats`,
    requestOptions: {
      userAction: 'Load keyword research stats',
      component: 'KeywordResearchPanel',
    },
  })


  // Approve keyword mutation
  const approveKeywordMutation = useToastMutation<void, Error, string>({
    mutationFn: async (pageId) => {
      // In a real implementation, this would call an API to save the approved keywords
      // For now, we just update local state
      setProcessingPageId(pageId)
      await new Promise((resolve) => setTimeout(resolve, 500)) // Simulate API call
      setProcessingPageId(null)
    },
    userAction: 'Approve keywords',
    successMessage: 'Keywords approved',
    onSuccess: (_, pageId) => {
      addBreadcrumb('Keywords approved', 'keyword_research', { page_id: pageId })
      setPendingApprovals((prev) =>
        prev.map((a) => (a.page_id === pageId ? { ...a, status: 'approved' as const } : a))
      )
      refetchStats()
    },
  })

  // Reject keyword mutation
  const rejectKeywordMutation = useToastMutation<void, Error, string>({
    mutationFn: async (pageId) => {
      setProcessingPageId(pageId)
      await new Promise((resolve) => setTimeout(resolve, 500))
      setProcessingPageId(null)
    },
    userAction: 'Reject keywords',
    successMessage: 'Keywords rejected',
    onSuccess: (_, pageId) => {
      addBreadcrumb('Keywords rejected', 'keyword_research', { page_id: pageId })
      setPendingApprovals((prev) =>
        prev.map((a) => (a.page_id === pageId ? { ...a, status: 'rejected' as const } : a))
      )
    },
  })

  // Handle WebSocket updates for real-time progress
  const handleWebSocketUpdate = useCallback(
    (data: Record<string, unknown>, event: string) => {
      console.debug('[KeywordResearchPanel] WebSocket update:', { event, data })
      addBreadcrumb('WebSocket keyword research update', 'websocket', { event })
      queryClient.invalidateQueries({ queryKey: ['keyword-research-stats', projectId] })
    },
    [projectId, queryClient]
  )

  // Subscribe to WebSocket updates
  useProjectSubscription(projectId, {
    onUpdate: handleWebSocketUpdate,
    enabled: isResearching,
  })

  // Poll for stats while researching
  useEffect(() => {
    if (!isResearching) return

    const interval = setInterval(() => {
      refetchStats()
    }, 3000)

    return () => clearInterval(interval)
  }, [isResearching, refetchStats])

  // Form handlers
  const handleCountryChange = useCallback((value: string) => {
    setFormState((prev) => ({ ...prev, country: value }))
  }, [])

  const handleDataSourceChange = useCallback((value: string) => {
    setFormState((prev) => ({ ...prev, dataSource: value }))
  }, [])

  const handleAutoApproveChange = useCallback((checked: boolean) => {
    setFormState((prev) => ({ ...prev, autoApprove: checked }))
  }, [])

  // Approval handlers
  const handleApprove = useCallback(
    (pageId: string) => {
      approveKeywordMutation.mutate(pageId)
    },
    [approveKeywordMutation]
  )

  const handleReject = useCallback(
    (pageId: string) => {
      rejectKeywordMutation.mutate(pageId)
    },
    [rejectKeywordMutation]
  )

  const handleModify = useCallback((pageId: string) => {
    // In a real implementation, this would open a modal to modify keywords
    console.debug('[KeywordResearchPanel] Modify keywords for page:', pageId)
    addBreadcrumb('Modify keywords clicked', 'user_action', { page_id: pageId })
  }, [])

  // Calculate pending approval counts
  const approvalCounts = useMemo(() => {
    const pending = pendingApprovals.filter((a) => a.status === 'pending').length
    const approved = pendingApprovals.filter((a) => a.status === 'approved').length
    const rejected = pendingApprovals.filter((a) => a.status === 'rejected').length
    return { pending, approved, rejected, total: pendingApprovals.length }
  }, [pendingApprovals])

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Search className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Keyword Research</h3>
              <p className="text-sm text-warmgray-500">Page keyword optimization</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchStats()}
            disabled={isLoadingStats}
          >
            <RefreshCw
              className={cn('w-4 h-4', isLoadingStats && 'animate-spin')}
            />
            Refresh
          </Button>
        </div>

        {isLoadingStats ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" label="Loading stats..." showLabel />
          </div>
        ) : stats ? (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <StatsCard
                label="Total Pages"
                value={stats.total_pages}
                icon={FileText}
                variant="default"
              />
              <StatsCard
                label="With Keywords"
                value={stats.pages_with_keywords}
                icon={CheckCircle2}
                variant="success"
              />
              <StatsCard
                label="Need Research"
                value={stats.pages_without_keywords}
                icon={AlertCircle}
                variant="warning"
              />
            </div>

            {/* Progress Bar */}
            <ProgressBar
              current={stats.pages_with_keywords}
              total={stats.total_pages}
              label="Research Progress"
            />

            {/* Cache Stats */}
            {stats.cache_stats && (
              <div className="flex items-center gap-4 p-3 bg-cream-50 rounded-lg">
                <Database className="w-4 h-4 text-warmgray-500" />
                <div className="text-sm">
                  <span className="text-warmgray-600">Cache Hit Rate: </span>
                  <span className="font-medium text-warmgray-900">
                    {(stats.cache_stats.cache_hit_rate * 100).toFixed(1)}%
                  </span>
                  <span className="text-warmgray-400 ml-2">
                    ({stats.cache_stats.cache_hits.toLocaleString()} hits / {stats.cache_stats.total_keywords.toLocaleString()} total)
                  </span>
                </div>
              </div>
            )}

            {stats.total_pages === 0 && (
              <div className="text-center py-6">
                <FileText className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
                <p className="text-warmgray-500">No pages to research</p>
                <p className="text-sm text-warmgray-400 mt-1">
                  Run a crawl first to discover pages.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Active Research Progress */}
      {isResearching && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">
                Research In Progress
              </h3>
              <p className="text-sm text-warmgray-500">
                Generating and analyzing keywords...
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <ProgressBar
              current={stats?.pages_with_keywords || 0}
              total={stats?.total_pages || 0}
              label="Progress"
            />
            <p className="text-sm text-warmgray-600">
              Results will appear in the approval queue below.
            </p>
          </div>
        </div>
      )}

      {/* Approval Queue */}
      {pendingApprovals.length > 0 && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowApprovals(!showApprovals)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gold-100 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-gold-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">
                  Approval Queue
                </h3>
                <p className="text-sm text-warmgray-500">
                  {approvalCounts.pending} pending, {approvalCounts.approved} approved
                </p>
              </div>
            </div>
            {showApprovals ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showApprovals && (
            <div className="mt-4 space-y-3">
              {pendingApprovals.map((approval) => (
                <ApprovalCard
                  key={approval.page_id}
                  approval={approval}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onModify={handleModify}
                  isProcessing={processingPageId === approval.page_id}
                />
              ))}

              {approvalCounts.pending > 0 && (
                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      pendingApprovals
                        .filter((a) => a.status === 'pending')
                        .forEach((a) => handleReject(a.page_id))
                    }}
                  >
                    Reject All
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => {
                      pendingApprovals
                        .filter((a) => a.status === 'pending')
                        .forEach((a) => handleApprove(a.page_id))
                    }}
                  >
                    Approve All ({approvalCounts.pending})
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Configuration Form */}
      {stats && stats.total_pages > 0 && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowConfig(!showConfig)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <Search className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">
                  Research Options
                </h3>
                <p className="text-sm text-warmgray-500">
                  Configure and run keyword research
                </p>
              </div>
            </div>
            {showConfig ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showConfig && (
            <div className="mt-6 space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Country" helperText="Region for volume data">
                  <Select
                    value={formState.country}
                    onChange={(e) => handleCountryChange(e.target.value)}
                    disabled={isResearching}
                  >
                    {COUNTRY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>
                </FormField>

                <FormField label="Data Source" helperText="Volume data provider">
                  <Select
                    value={formState.dataSource}
                    onChange={(e) => handleDataSourceChange(e.target.value)}
                    disabled={isResearching}
                  >
                    {DATA_SOURCE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
              </div>

              <Checkbox
                label="Auto-approve suggestions"
                checked={formState.autoApprove}
                onChange={handleAutoApproveChange}
                disabled={isResearching}
                helperText="Skip approval queue and apply keywords directly"
              />

              <div className="flex items-center justify-between pt-2">
                <p className="text-sm text-warmgray-500">
                  {stats.pages_without_keywords > 0
                    ? `${stats.pages_without_keywords} pages need research`
                    : 'All pages have keywords'}
                </p>
                <Button
                  type="button"
                  disabled={isResearching || stats.pages_without_keywords === 0}
                  onClick={() => {
                    addBreadcrumb('Starting keyword research', 'user_action', {
                      country: formState.country,
                      dataSource: formState.dataSource,
                      autoApprove: formState.autoApprove,
                    })
                    setIsResearching(true)
                    // In a real implementation, this would trigger batch research
                    // For now, we simulate with a timeout
                    setTimeout(() => {
                      setIsResearching(false)
                    }, 3000)
                  }}
                >
                  {isResearching ? (
                    <ButtonSpinner />
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Start Research
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
