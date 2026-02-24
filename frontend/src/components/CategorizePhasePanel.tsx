/**
 * CategorizePhasePanel - Page category breakdown and categorization controls
 *
 * Features:
 * - Statistics overview showing total, categorized, and uncategorized pages
 * - Category breakdown with visual distribution
 * - Bulk categorization controls with LLM options
 * - Manual category update for individual pages
 * - Real-time progress during categorization
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
  Tags,
  Play,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { useProjectSubscription } from '@/lib/hooks/useWebSocket'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { FormField, Input } from '@/components/ui/form-field'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Categorization stats from API */
interface CategorizeStats {
  project_id: string
  total_pages: number
  categorized_pages: number
  uncategorized_pages: number
  category_counts: Record<string, number>
  valid_categories: string[]
}

/** Categorize all request */
interface CategorizeAllRequest {
  force_llm: boolean
  skip_llm: boolean
  update_pages: boolean
  include_categorized: boolean
  batch_size: number
}

/** Categorize all response */
interface CategorizeAllResponse {
  total: number
  categorized: number
  failed: number
  skipped: number
  category_counts: Record<string, number>
  tier_counts: Record<string, number>
  duration_ms: number
}

/** Form state for categorization options */
interface CategorizeFormState {
  forceLlm: boolean
  skipLlm: boolean
  includeCategorized: boolean
  batchSize: number
}

// ============================================================================
// Constants
// ============================================================================

/** Default form values */
const DEFAULT_FORM_STATE: CategorizeFormState = {
  forceLlm: false,
  skipLlm: false,
  includeCategorized: false,
  batchSize: 10,
}

/** Category colors for visual distinction */
const categoryColors: Record<string, { bg: string; text: string; border: string }> = {
  homepage: { bg: 'bg-primary-100', text: 'text-primary-700', border: 'border-primary-200' },
  product: { bg: 'bg-success-100', text: 'text-success-700', border: 'border-success-200' },
  collection: { bg: 'bg-coral-100', text: 'text-coral-700', border: 'border-coral-200' },
  blog: { bg: 'bg-gold-100', text: 'text-gold-700', border: 'border-gold-200' },
  policy: { bg: 'bg-warmgray-100', text: 'text-warmgray-600', border: 'border-warmgray-200' },
  about: { bg: 'bg-primary-50', text: 'text-primary-600', border: 'border-primary-100' },
  contact: { bg: 'bg-success-50', text: 'text-success-600', border: 'border-success-100' },
  faq: { bg: 'bg-gold-50', text: 'text-gold-600', border: 'border-gold-100' },
  account: { bg: 'bg-coral-50', text: 'text-coral-600', border: 'border-coral-100' },
  cart: { bg: 'bg-error-100', text: 'text-error-700', border: 'border-error-200' },
  search: { bg: 'bg-cream-200', text: 'text-warmgray-700', border: 'border-cream-300' },
  other: { bg: 'bg-warmgray-50', text: 'text-warmgray-500', border: 'border-warmgray-100' },
}

/** Get color config for a category */
function getCategoryColor(category: string) {
  return categoryColors[category] || categoryColors.other
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Category badge component
 */
function CategoryBadge({ category, count }: { category: string; count: number }) {
  const colors = getCategoryColor(category)

  return (
    <div
      className={cn(
        'flex items-center justify-between px-3 py-2 rounded-lg border',
        colors.bg,
        colors.border
      )}
    >
      <span className={cn('text-sm font-medium capitalize', colors.text)}>
        {category}
      </span>
      <span className={cn('text-sm font-semibold', colors.text)}>
        {count.toLocaleString()}
      </span>
    </div>
  )
}

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
  value: number
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
            {value.toLocaleString()}
          </p>
          <p className="text-sm text-warmgray-500">{label}</p>
        </div>
      </div>
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
    <label className={cn('flex items-start gap-3 cursor-pointer', disabled && 'opacity-50 cursor-not-allowed')}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className="mt-1 w-4 h-4 rounded border-warmgray-300 text-primary-600 focus:ring-primary-500 focus:ring-offset-0"
      />
      <div>
        <span className="text-sm font-medium text-warmgray-700">{label}</span>
        {helperText && <p className="text-xs text-warmgray-500 mt-0.5">{helperText}</p>}
      </div>
    </label>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export interface CategorizePhaseaPanelProps {
  /** Project ID to manage categorization for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * CategorizePhasePanel provides page category breakdown and categorization controls
 *
 * @example
 * <CategorizePhasePanel projectId="abc-123" />
 */
export function CategorizePhasePanel({ projectId, className }: CategorizePhaseaPanelProps) {
  const queryClient = useQueryClient()

  // Form state
  const [formState, setFormState] = useState<CategorizeFormState>(DEFAULT_FORM_STATE)
  const [showConfig, setShowConfig] = useState(true)
  const [isCategorizingAll, setIsCategorizingAll] = useState(false)

  // Fetch categorization stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useApiQuery<CategorizeStats>({
    queryKey: ['categorize-stats', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/categorize/stats`,
    requestOptions: {
      userAction: 'Load categorization stats',
      component: 'CategorizePhasePanel',
    },
  })

  // Categorize all mutation
  const categorizeAllMutation = useToastMutation<CategorizeAllResponse, Error, CategorizeAllRequest>({
    mutationFn: async (data) => {
      const response = await fetch(
        `/api/v1/projects/${projectId}/phases/categorize/all`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        const error = new Error(errorData.error || 'Failed to start categorization')
        console.error('[CategorizePhasePanel] Start categorization failed:', {
          endpoint: `/api/v1/projects/${projectId}/phases/categorize/all`,
          status: response.status,
          responseBody: errorData,
          userAction: 'Start categorization',
        })
        throw error
      }
      return response.json()
    },
    userAction: 'Categorize all pages',
    successMessage: 'Categorization started',
    successDescription: (data) =>
      `Processing ${data.total} pages in the background.`,
    onSuccess: (data) => {
      addBreadcrumb('Categorization started', 'categorize', {
        total: data.total,
        skipped: data.skipped,
      })
      setIsCategorizingAll(true)
      setShowConfig(false)
      // Start polling for completion
      setTimeout(() => {
        refetchStats()
        setIsCategorizingAll(false)
      }, 5000)
    },
  })

  // Handle WebSocket updates for real-time progress
  const handleWebSocketUpdate = useCallback(
    (data: Record<string, unknown>, event: string) => {
      console.debug('[CategorizePhasePanel] WebSocket update:', { event, data })
      addBreadcrumb('WebSocket categorize update', 'websocket', { event })
      queryClient.invalidateQueries({ queryKey: ['categorize-stats', projectId] })
    },
    [projectId, queryClient]
  )

  // Subscribe to WebSocket updates
  useProjectSubscription(projectId, {
    onUpdate: handleWebSocketUpdate,
    enabled: isCategorizingAll,
  })

  // Poll for stats while categorizing
  useEffect(() => {
    if (!isCategorizingAll) return

    const interval = setInterval(() => {
      refetchStats()
    }, 3000)

    return () => clearInterval(interval)
  }, [isCategorizingAll, refetchStats])

  // Form handlers
  const handleCheckboxChange = useCallback(
    (field: keyof CategorizeFormState, value: boolean) => {
      setFormState((prev) => ({ ...prev, [field]: value }))
    },
    []
  )

  const handleBatchSizeChange = useCallback((value: string) => {
    const num = parseInt(value, 10)
    if (!isNaN(num) && num >= 1 && num <= 50) {
      setFormState((prev) => ({ ...prev, batchSize: num }))
    }
  }, [])

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()

      addBreadcrumb('Starting categorization', 'user_action', {
        forceLlm: formState.forceLlm,
        skipLlm: formState.skipLlm,
        includeCategorized: formState.includeCategorized,
        batchSize: formState.batchSize,
      })

      categorizeAllMutation.mutate({
        force_llm: formState.forceLlm,
        skip_llm: formState.skipLlm,
        update_pages: true,
        include_categorized: formState.includeCategorized,
        batch_size: formState.batchSize,
      })
    },
    [formState, categorizeAllMutation]
  )

  const isSubmitting = categorizeAllMutation.isPending

  // Calculate sorted categories for display
  const sortedCategories = useMemo(() => {
    if (!stats?.category_counts) return []
    return Object.entries(stats.category_counts)
      .sort((a, b) => b[1] - a[1])
      .map(([category, count]) => ({ category, count }))
  }, [stats])

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Tags className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Categorization Overview</h3>
              <p className="text-sm text-warmgray-500">
                Page category distribution
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchStats()}
            disabled={isLoadingStats}
          >
            <RefreshCw className={cn('w-4 h-4', isLoadingStats && 'animate-spin')} />
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
                label="Categorized"
                value={stats.categorized_pages}
                icon={CheckCircle2}
                variant="success"
              />
              <StatsCard
                label="Uncategorized"
                value={stats.uncategorized_pages}
                icon={AlertCircle}
                variant="warning"
              />
            </div>

            {/* Progress Bar */}
            <ProgressBar
              current={stats.categorized_pages}
              total={stats.total_pages}
              label="Categorization Progress"
            />

            {/* Category Breakdown */}
            {sortedCategories.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-warmgray-700">
                  Category Breakdown
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {sortedCategories.map(({ category, count }) => (
                    <CategoryBadge key={category} category={category} count={count} />
                  ))}
                </div>
              </div>
            )}

            {stats.total_pages === 0 && (
              <div className="text-center py-6">
                <FileText className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
                <p className="text-warmgray-500">No pages to categorize</p>
                <p className="text-sm text-warmgray-400 mt-1">
                  Run a crawl first to discover pages.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Active Categorization Progress */}
      {isCategorizingAll && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Categorization In Progress</h3>
              <p className="text-sm text-warmgray-500">
                Processing pages in the background...
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <ProgressBar
              current={stats?.categorized_pages || 0}
              total={stats?.total_pages || 0}
              label="Progress"
            />
            <p className="text-sm text-warmgray-600">
              Stats will update automatically as pages are categorized.
            </p>
          </div>
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
                <Tags className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Categorization Options</h3>
                <p className="text-sm text-warmgray-500">Configure and run categorization</p>
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
              <div className="space-y-4">
                <Checkbox
                  label="Include already categorized pages"
                  checked={formState.includeCategorized}
                  onChange={(v) => handleCheckboxChange('includeCategorized', v)}
                  disabled={isSubmitting || isCategorizingAll}
                  helperText="Re-process pages that already have a category"
                />

                <Checkbox
                  label="Force LLM categorization"
                  checked={formState.forceLlm}
                  onChange={(v) => handleCheckboxChange('forceLlm', v)}
                  disabled={isSubmitting || isCategorizingAll || formState.skipLlm}
                  helperText="Use LLM for all pages (slower, more accurate)"
                />

                <Checkbox
                  label="Skip LLM fallback"
                  checked={formState.skipLlm}
                  onChange={(v) => handleCheckboxChange('skipLlm', v)}
                  disabled={isSubmitting || isCategorizingAll || formState.forceLlm}
                  helperText="Only use pattern matching (faster, may be less accurate)"
                />
              </div>

              <FormField
                label="Batch Size"
                helperText="Pages per LLM batch (1-50)"
              >
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={formState.batchSize}
                  onChange={(e) => handleBatchSizeChange(e.target.value)}
                  disabled={isSubmitting || isCategorizingAll || formState.skipLlm}
                  className="w-24"
                />
              </FormField>

              <div className="flex items-center justify-between pt-2">
                <p className="text-sm text-warmgray-500">
                  {stats.uncategorized_pages > 0
                    ? `${stats.uncategorized_pages} pages to categorize`
                    : 'All pages categorized'}
                </p>
                <Button
                  type="submit"
                  disabled={isSubmitting || isCategorizingAll || (stats.uncategorized_pages === 0 && !formState.includeCategorized)}
                >
                  {isSubmitting ? (
                    <ButtonSpinner />
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Start Categorization
                    </>
                  )}
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
