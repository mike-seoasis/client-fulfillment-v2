/**
 * LabelPhasePanel - Label visualization and generation controls
 *
 * Features:
 * - Statistics overview showing total, labeled, and unlabeled pages
 * - Label distribution visualization with counts
 * - Top labels display
 * - Bulk labeling controls with LLM options
 * - Real-time progress during labeling
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
  Tag,
  Play,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  Hash,
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

/** Label stats from API */
interface LabelStats {
  project_id: string
  total_pages: number
  labeled_pages: number
  unlabeled_pages: number
  label_counts: Record<string, number>
  top_labels: string[]
}

/** Label all request */
interface LabelAllRequest {
  force_llm: boolean
  skip_llm: boolean
  update_pages: boolean
  include_labeled: boolean
  batch_size: number
}

/** Label all response */
interface LabelAllResponse {
  total: number
  labeled: number
  failed: number
  skipped: number
  tier_counts: Record<string, number>
  duration_ms: number
}

/** Form state for labeling options */
interface LabelFormState {
  forceLlm: boolean
  skipLlm: boolean
  includeLabeled: boolean
  batchSize: number
}

// ============================================================================
// Constants
// ============================================================================

/** Default form values */
const DEFAULT_FORM_STATE: LabelFormState = {
  forceLlm: false,
  skipLlm: false,
  includeLabeled: false,
  batchSize: 10,
}

/** Label colors for visual distinction - warm palette following design system */
const labelColors: Array<{ bg: string; text: string; border: string }> = [
  { bg: 'bg-primary-100', text: 'text-primary-700', border: 'border-primary-200' },
  { bg: 'bg-success-100', text: 'text-success-700', border: 'border-success-200' },
  { bg: 'bg-coral-100', text: 'text-coral-700', border: 'border-coral-200' },
  { bg: 'bg-gold-100', text: 'text-gold-700', border: 'border-gold-200' },
  { bg: 'bg-warmgray-100', text: 'text-warmgray-600', border: 'border-warmgray-200' },
  { bg: 'bg-primary-50', text: 'text-primary-600', border: 'border-primary-100' },
  { bg: 'bg-success-50', text: 'text-success-600', border: 'border-success-100' },
  { bg: 'bg-gold-50', text: 'text-gold-600', border: 'border-gold-100' },
  { bg: 'bg-coral-50', text: 'text-coral-600', border: 'border-coral-100' },
  { bg: 'bg-cream-200', text: 'text-warmgray-700', border: 'border-cream-300' },
]

/**
 * Get color config for a label based on its index
 * Uses consistent hashing to ensure same label always gets same color
 */
function getLabelColor(label: string, allLabels: string[]) {
  const index = allLabels.indexOf(label)
  const colorIndex = index >= 0 ? index % labelColors.length : 0
  return labelColors[colorIndex]
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Label badge component with count
 */
function LabelBadge({
  label,
  count,
  allLabels,
}: {
  label: string
  count: number
  allLabels: string[]
}) {
  const colors = getLabelColor(label, allLabels)

  return (
    <div
      className={cn(
        'flex items-center justify-between px-3 py-2 rounded-lg border',
        colors.bg,
        colors.border
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <Tag className={cn('w-3.5 h-3.5 shrink-0', colors.text)} />
        <span className={cn('text-sm font-medium truncate', colors.text)}>
          {label}
        </span>
      </div>
      <span className={cn('text-sm font-semibold ml-2 shrink-0', colors.text)}>
        {count.toLocaleString()}
      </span>
    </div>
  )
}

/**
 * Top label chip component
 */
function TopLabelChip({ label, allLabels }: { label: string; allLabels: string[] }) {
  const colors = getLabelColor(label, allLabels)

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border',
        colors.bg,
        colors.text,
        colors.border
      )}
    >
      <Hash className="w-3 h-3" />
      {label}
    </span>
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

// ============================================================================
// Main Component
// ============================================================================

export interface LabelPhasePanelProps {
  /** Project ID to manage labeling for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * LabelPhasePanel provides label visualization and generation controls
 *
 * @example
 * <LabelPhasePanel projectId="abc-123" />
 */
export function LabelPhasePanel({ projectId, className }: LabelPhasePanelProps) {
  const queryClient = useQueryClient()

  // Form state
  const [formState, setFormState] = useState<LabelFormState>(DEFAULT_FORM_STATE)
  const [showConfig, setShowConfig] = useState(true)
  const [isLabelingAll, setIsLabelingAll] = useState(false)

  // Fetch label stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useApiQuery<LabelStats>({
    queryKey: ['label-stats', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/label/stats`,
    requestOptions: {
      userAction: 'Load label stats',
      component: 'LabelPhasePanel',
    },
  })

  // Label all mutation
  const labelAllMutation = useToastMutation<LabelAllResponse, Error, LabelAllRequest>(
    {
      mutationFn: async (data) => {
        const response = await fetch(
          `/api/v1/projects/${projectId}/phases/label/all`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          }
        )
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}))
          const error = new Error(errorData.error || 'Failed to start labeling')
          console.error('[LabelPhasePanel] Start labeling failed:', {
            endpoint: `/api/v1/projects/${projectId}/phases/label/all`,
            status: response.status,
            responseBody: errorData,
            userAction: 'Start labeling',
          })
          throw error
        }
        return response.json()
      },
      userAction: 'Label all pages',
      successMessage: 'Labeling started',
      successDescription: (data) =>
        `Processing ${data.total} pages in the background.`,
      onSuccess: (data) => {
        addBreadcrumb('Labeling started', 'label', {
          total: data.total,
          skipped: data.skipped,
        })
        setIsLabelingAll(true)
        setShowConfig(false)
        // Start polling for completion
        setTimeout(() => {
          refetchStats()
          setIsLabelingAll(false)
        }, 5000)
      },
    }
  )

  // Handle WebSocket updates for real-time progress
  const handleWebSocketUpdate = useCallback(
    (data: Record<string, unknown>, event: string) => {
      console.debug('[LabelPhasePanel] WebSocket update:', { event, data })
      addBreadcrumb('WebSocket label update', 'websocket', { event })
      queryClient.invalidateQueries({ queryKey: ['label-stats', projectId] })
    },
    [projectId, queryClient]
  )

  // Subscribe to WebSocket updates
  useProjectSubscription(projectId, {
    onUpdate: handleWebSocketUpdate,
    enabled: isLabelingAll,
  })

  // Poll for stats while labeling
  useEffect(() => {
    if (!isLabelingAll) return

    const interval = setInterval(() => {
      refetchStats()
    }, 3000)

    return () => clearInterval(interval)
  }, [isLabelingAll, refetchStats])

  // Form handlers
  const handleCheckboxChange = useCallback(
    (field: keyof LabelFormState, value: boolean) => {
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

      addBreadcrumb('Starting labeling', 'user_action', {
        forceLlm: formState.forceLlm,
        skipLlm: formState.skipLlm,
        includeLabeled: formState.includeLabeled,
        batchSize: formState.batchSize,
      })

      labelAllMutation.mutate({
        force_llm: formState.forceLlm,
        skip_llm: formState.skipLlm,
        update_pages: true,
        include_labeled: formState.includeLabeled,
        batch_size: formState.batchSize,
      })
    },
    [formState, labelAllMutation]
  )

  const isSubmitting = labelAllMutation.isPending

  // Calculate sorted labels for display
  const sortedLabels = useMemo(() => {
    if (!stats?.label_counts) return []
    return Object.entries(stats.label_counts)
      .sort((a, b) => b[1] - a[1])
      .map(([label, count]) => ({ label, count }))
  }, [stats])

  // Get all label names for consistent coloring
  const allLabelNames = useMemo(() => {
    return sortedLabels.map((l) => l.label)
  }, [sortedLabels])

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Tag className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Label Overview</h3>
              <p className="text-sm text-warmgray-500">Page label distribution</p>
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
                label="Labeled"
                value={stats.labeled_pages}
                icon={CheckCircle2}
                variant="success"
              />
              <StatsCard
                label="Unlabeled"
                value={stats.unlabeled_pages}
                icon={AlertCircle}
                variant="warning"
              />
            </div>

            {/* Progress Bar */}
            <ProgressBar
              current={stats.labeled_pages}
              total={stats.total_pages}
              label="Labeling Progress"
            />

            {/* Top Labels */}
            {stats.top_labels && stats.top_labels.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-warmgray-700">
                  Top Labels
                </h4>
                <div className="flex flex-wrap gap-2">
                  {stats.top_labels.map((label) => (
                    <TopLabelChip
                      key={label}
                      label={label}
                      allLabels={allLabelNames}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Label Distribution */}
            {sortedLabels.length > 0 && (
              <div className="space-y-3">
                <h4 className="text-sm font-medium text-warmgray-700">
                  Label Distribution
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {sortedLabels.slice(0, 12).map(({ label, count }) => (
                    <LabelBadge
                      key={label}
                      label={label}
                      count={count}
                      allLabels={allLabelNames}
                    />
                  ))}
                </div>
                {sortedLabels.length > 12 && (
                  <p className="text-sm text-warmgray-500 text-center pt-2">
                    +{sortedLabels.length - 12} more labels
                  </p>
                )}
              </div>
            )}

            {stats.total_pages === 0 && (
              <div className="text-center py-6">
                <FileText className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
                <p className="text-warmgray-500">No pages to label</p>
                <p className="text-sm text-warmgray-400 mt-1">
                  Run a crawl first to discover pages.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Active Labeling Progress */}
      {isLabelingAll && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">
                Labeling In Progress
              </h3>
              <p className="text-sm text-warmgray-500">
                Processing pages in the background...
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <ProgressBar
              current={stats?.labeled_pages || 0}
              total={stats?.total_pages || 0}
              label="Progress"
            />
            <p className="text-sm text-warmgray-600">
              Stats will update automatically as pages are labeled.
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
                <Tag className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">
                  Labeling Options
                </h3>
                <p className="text-sm text-warmgray-500">
                  Configure and run labeling
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
            <form onSubmit={handleSubmit} className="mt-6 space-y-5">
              <div className="space-y-4">
                <Checkbox
                  label="Include already labeled pages"
                  checked={formState.includeLabeled}
                  onChange={(v) => handleCheckboxChange('includeLabeled', v)}
                  disabled={isSubmitting || isLabelingAll}
                  helperText="Re-process pages that already have labels"
                />

                <Checkbox
                  label="Force LLM labeling"
                  checked={formState.forceLlm}
                  onChange={(v) => handleCheckboxChange('forceLlm', v)}
                  disabled={isSubmitting || isLabelingAll || formState.skipLlm}
                  helperText="Use LLM for all pages (slower, more accurate)"
                />

                <Checkbox
                  label="Skip LLM fallback"
                  checked={formState.skipLlm}
                  onChange={(v) => handleCheckboxChange('skipLlm', v)}
                  disabled={isSubmitting || isLabelingAll || formState.forceLlm}
                  helperText="Only use pattern matching (faster, may be less accurate)"
                />
              </div>

              <FormField label="Batch Size" helperText="Pages per batch (1-50)">
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={formState.batchSize}
                  onChange={(e) => handleBatchSizeChange(e.target.value)}
                  disabled={isSubmitting || isLabelingAll || formState.skipLlm}
                  className="w-24"
                />
              </FormField>

              <div className="flex items-center justify-between pt-2">
                <p className="text-sm text-warmgray-500">
                  {stats.unlabeled_pages > 0
                    ? `${stats.unlabeled_pages} pages to label`
                    : 'All pages labeled'}
                </p>
                <Button
                  type="submit"
                  disabled={
                    isSubmitting ||
                    isLabelingAll ||
                    (stats.unlabeled_pages === 0 && !formState.includeLabeled)
                  }
                >
                  {isSubmitting ? (
                    <ButtonSpinner />
                  ) : (
                    <>
                      <Play className="w-4 h-4" />
                      Start Labeling
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
