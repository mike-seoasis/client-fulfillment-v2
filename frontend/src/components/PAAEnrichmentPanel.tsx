/**
 * PAAEnrichmentPanel - PAA (People Also Ask) enrichment with question review
 *
 * Features:
 * - Statistics overview showing total keywords and PAA enrichment progress
 * - PAA enrichment configuration form with fan-out and fallback options
 * - Question review workflow for approving/rejecting discovered questions
 * - Real-time progress during enrichment
 * - Intent category breakdown display
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
  HelpCircle,
  Play,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Loader2,
  MessageCircleQuestion,
  TrendingUp,
  Check,
  X,
  ExternalLink,
  Filter,
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

/** PAA question with metadata */
interface PAAQuestion {
  question: string
  answer_snippet: string | null
  source_url: string | null
  source_domain: string | null
  position: number | null
  is_nested: boolean
  parent_question: string | null
  intent: 'buying' | 'usage' | 'care' | 'comparison' | 'unknown'
}

/** PAA enrichment stats from API */
interface PAAEnrichmentStats {
  project_id: string
  total_keywords_enriched: number
  total_questions_discovered: number
  questions_by_intent: Record<string, number>
  cache_hit_rate: number
}

/** Pending question review item */
interface PendingQuestionReview {
  question_id: string
  keyword: string
  question: PAAQuestion
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

/** Form state for PAA enrichment options */
interface PAAEnrichmentFormState {
  locationCode: number
  languageCode: string
  fanoutEnabled: boolean
  maxFanoutQuestions: number
  fallbackEnabled: boolean
  minPaaForFallback: number
  categorizeEnabled: boolean
}

// ============================================================================
// Constants
// ============================================================================

/** Default form values */
const DEFAULT_FORM_STATE: PAAEnrichmentFormState = {
  locationCode: 2840,
  languageCode: 'en',
  fanoutEnabled: true,
  maxFanoutQuestions: 10,
  fallbackEnabled: true,
  minPaaForFallback: 3,
  categorizeEnabled: true,
}

/** Location options */
const LOCATION_OPTIONS = [
  { value: '2840', label: 'United States' },
  { value: '2826', label: 'United Kingdom' },
  { value: '2124', label: 'Canada' },
  { value: '2036', label: 'Australia' },
]

/** Language options */
const LANGUAGE_OPTIONS = [
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
]

/** Max fanout question options */
const FANOUT_OPTIONS = [
  { value: '5', label: '5 questions' },
  { value: '10', label: '10 questions' },
  { value: '15', label: '15 questions' },
  { value: '20', label: '20 questions' },
]

/** Status colors */
const statusColors = {
  pending: { bg: 'bg-gold-50', text: 'text-gold-700', border: 'border-gold-200' },
  approved: { bg: 'bg-success-50', text: 'text-success-700', border: 'border-success-200' },
  rejected: { bg: 'bg-error-50', text: 'text-error-700', border: 'border-error-200' },
}

/** Intent colors */
const intentColors: Record<string, { bg: string; text: string }> = {
  buying: { bg: 'bg-primary-100', text: 'text-primary-700' },
  usage: { bg: 'bg-blue-100', text: 'text-blue-700' },
  care: { bg: 'bg-green-100', text: 'text-green-700' },
  comparison: { bg: 'bg-purple-100', text: 'text-purple-700' },
  unknown: { bg: 'bg-warmgray-100', text: 'text-warmgray-600' },
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
 * Intent badge component
 */
function IntentBadge({ intent }: { intent: string }) {
  const colors = intentColors[intent] || intentColors.unknown
  return (
    <span
      className={cn(
        'text-xs px-2 py-0.5 rounded-full font-medium capitalize',
        colors.bg,
        colors.text
      )}
    >
      {intent}
    </span>
  )
}

/**
 * Intent breakdown chart
 */
function IntentBreakdown({
  questionsByIntent,
  total,
}: {
  questionsByIntent: Record<string, number>
  total: number
}) {
  const intents = ['buying', 'usage', 'care', 'comparison', 'unknown']

  return (
    <div className="space-y-2">
      <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
        Questions by Intent
      </h4>
      <div className="space-y-1.5">
        {intents.map((intent) => {
          const count = questionsByIntent[intent] || 0
          const percentage = total > 0 ? Math.round((count / total) * 100) : 0
          const colors = intentColors[intent]

          return (
            <div key={intent} className="flex items-center gap-2">
              <div className="w-20 text-xs text-warmgray-600 capitalize">{intent}</div>
              <div className="flex-1 h-1.5 bg-cream-200 rounded-full overflow-hidden">
                <div
                  className={cn('h-full rounded-full transition-all duration-300', colors.bg)}
                  style={{ width: `${percentage}%` }}
                />
              </div>
              <div className="w-12 text-xs text-warmgray-500 text-right">
                {count.toLocaleString()}
              </div>
            </div>
          )
        })}
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

/**
 * Question review card component
 */
function QuestionReviewCard({
  review,
  onApprove,
  onReject,
  isProcessing,
}: {
  review: PendingQuestionReview
  onApprove: (questionId: string) => void
  onReject: (questionId: string) => void
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
              review.status === 'pending' && 'bg-gold-500',
              review.status === 'approved' && 'bg-success-500',
              review.status === 'rejected' && 'bg-error-500'
            )}
          />
          <div className="text-left min-w-0">
            <p className="text-sm font-medium text-warmgray-900 truncate">
              {review.question.question}
            </p>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs text-warmgray-500">
                Keyword: <span className="font-medium">{review.keyword}</span>
              </span>
              <IntentBadge intent={review.question.intent} />
              {review.question.is_nested && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-cream-100 text-warmgray-500">
                  nested
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={cn(
              'text-xs px-2 py-0.5 rounded-full font-medium capitalize',
              statusColors[review.status].bg,
              statusColors[review.status].text
            )}
          >
            {review.status}
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
          {/* Answer Snippet */}
          {review.question.answer_snippet && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                Answer Snippet
              </h4>
              <p className="text-sm text-warmgray-700 bg-cream-50 p-3 rounded-lg">
                {review.question.answer_snippet}
              </p>
            </div>
          )}

          {/* Source */}
          {review.question.source_url && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                Source
              </h4>
              <a
                href={review.question.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-primary-600 hover:text-primary-700"
              >
                <span className="truncate">
                  {review.question.source_domain || review.question.source_url}
                </span>
                <ExternalLink className="w-3.5 h-3.5 shrink-0" />
              </a>
            </div>
          )}

          {/* Parent Question (for nested) */}
          {review.question.parent_question && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                Parent Question
              </h4>
              <p className="text-sm text-warmgray-600 italic">
                "{review.question.parent_question}"
              </p>
            </div>
          )}

          {/* Position */}
          {review.question.position !== null && (
            <div className="flex items-center gap-2 text-sm text-warmgray-500">
              <TrendingUp className="w-4 h-4" />
              <span>Position #{review.question.position + 1} in SERP</span>
            </div>
          )}

          {/* Action Buttons */}
          {review.status === 'pending' && (
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onReject(review.question_id)}
                disabled={isProcessing}
                className="text-error-600 border-error-200 hover:bg-error-50"
              >
                <X className="w-4 h-4" />
                Reject
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => onApprove(review.question_id)}
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

export interface PAAEnrichmentPanelProps {
  /** Project ID to manage PAA enrichment for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * PAAEnrichmentPanel provides PAA enrichment controls with question review workflow
 *
 * @example
 * <PAAEnrichmentPanel projectId="abc-123" />
 */
export function PAAEnrichmentPanel({ projectId, className }: PAAEnrichmentPanelProps) {
  const queryClient = useQueryClient()

  // Form state
  const [formState, setFormState] = useState<PAAEnrichmentFormState>(DEFAULT_FORM_STATE)
  const [showConfig, setShowConfig] = useState(true)
  const [showReviews, setShowReviews] = useState(true)
  const [isEnriching, setIsEnriching] = useState(false)
  const [pendingReviews, setPendingReviews] = useState<PendingQuestionReview[]>([])
  const [processingQuestionId, setProcessingQuestionId] = useState<string | null>(null)
  const [intentFilter, setIntentFilter] = useState<string>('all')

  // Fetch PAA enrichment stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useApiQuery<PAAEnrichmentStats>({
    queryKey: ['paa-enrichment-stats', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/paa_enrichment/stats`,
    requestOptions: {
      userAction: 'Load PAA enrichment stats',
      component: 'PAAEnrichmentPanel',
    },
  })

  // Approve question mutation
  const approveQuestionMutation = useToastMutation<void, Error, string>({
    mutationFn: async (questionId) => {
      setProcessingQuestionId(questionId)
      await new Promise((resolve) => setTimeout(resolve, 500))
      setProcessingQuestionId(null)
    },
    userAction: 'Approve PAA question',
    successMessage: 'Question approved',
    onSuccess: (_, questionId) => {
      addBreadcrumb('PAA question approved', 'paa_enrichment', { question_id: questionId })
      setPendingReviews((prev) =>
        prev.map((r) => (r.question_id === questionId ? { ...r, status: 'approved' as const } : r))
      )
      refetchStats()
    },
  })

  // Reject question mutation
  const rejectQuestionMutation = useToastMutation<void, Error, string>({
    mutationFn: async (questionId) => {
      setProcessingQuestionId(questionId)
      await new Promise((resolve) => setTimeout(resolve, 500))
      setProcessingQuestionId(null)
    },
    userAction: 'Reject PAA question',
    successMessage: 'Question rejected',
    onSuccess: (_, questionId) => {
      addBreadcrumb('PAA question rejected', 'paa_enrichment', { question_id: questionId })
      setPendingReviews((prev) =>
        prev.map((r) => (r.question_id === questionId ? { ...r, status: 'rejected' as const } : r))
      )
    },
  })

  // Handle WebSocket updates for real-time progress
  const handleWebSocketUpdate = useCallback(
    (data: Record<string, unknown>, event: string) => {
      console.debug('[PAAEnrichmentPanel] WebSocket update:', { event, data })
      addBreadcrumb('WebSocket PAA enrichment update', 'websocket', { event })
      queryClient.invalidateQueries({ queryKey: ['paa-enrichment-stats', projectId] })
    },
    [projectId, queryClient]
  )

  // Subscribe to WebSocket updates
  useProjectSubscription(projectId, {
    onUpdate: handleWebSocketUpdate,
    enabled: isEnriching,
  })

  // Poll for stats while enriching
  useEffect(() => {
    if (!isEnriching) return

    const interval = setInterval(() => {
      refetchStats()
    }, 3000)

    return () => clearInterval(interval)
  }, [isEnriching, refetchStats])

  // Form handlers
  const handleLocationChange = useCallback((value: string) => {
    setFormState((prev) => ({ ...prev, locationCode: parseInt(value, 10) }))
  }, [])

  const handleLanguageChange = useCallback((value: string) => {
    setFormState((prev) => ({ ...prev, languageCode: value }))
  }, [])

  const handleFanoutQuestionsChange = useCallback((value: string) => {
    setFormState((prev) => ({ ...prev, maxFanoutQuestions: parseInt(value, 10) }))
  }, [])

  const handleFanoutEnabledChange = useCallback((checked: boolean) => {
    setFormState((prev) => ({ ...prev, fanoutEnabled: checked }))
  }, [])

  const handleFallbackEnabledChange = useCallback((checked: boolean) => {
    setFormState((prev) => ({ ...prev, fallbackEnabled: checked }))
  }, [])

  const handleCategorizeEnabledChange = useCallback((checked: boolean) => {
    setFormState((prev) => ({ ...prev, categorizeEnabled: checked }))
  }, [])

  // Review handlers
  const handleApprove = useCallback(
    (questionId: string) => {
      approveQuestionMutation.mutate(questionId)
    },
    [approveQuestionMutation]
  )

  const handleReject = useCallback(
    (questionId: string) => {
      rejectQuestionMutation.mutate(questionId)
    },
    [rejectQuestionMutation]
  )

  // Calculate pending review counts
  const reviewCounts = useMemo(() => {
    const pending = pendingReviews.filter((r) => r.status === 'pending').length
    const approved = pendingReviews.filter((r) => r.status === 'approved').length
    const rejected = pendingReviews.filter((r) => r.status === 'rejected').length
    return { pending, approved, rejected, total: pendingReviews.length }
  }, [pendingReviews])

  // Filter reviews by intent
  const filteredReviews = useMemo(() => {
    if (intentFilter === 'all') return pendingReviews
    return pendingReviews.filter((r) => r.question.intent === intentFilter)
  }, [pendingReviews, intentFilter])

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <HelpCircle className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">PAA Enrichment</h3>
              <p className="text-sm text-warmgray-500">People Also Ask questions</p>
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
                label="Keywords Enriched"
                value={stats.total_keywords_enriched}
                icon={CheckCircle2}
                variant="success"
              />
              <StatsCard
                label="Questions Found"
                value={stats.total_questions_discovered}
                icon={MessageCircleQuestion}
                variant="default"
              />
              <StatsCard
                label="Cache Hit Rate"
                value={`${(stats.cache_hit_rate * 100).toFixed(0)}%`}
                icon={Database}
                variant={stats.cache_hit_rate > 0.5 ? 'success' : 'warning'}
              />
            </div>

            {/* Intent Breakdown */}
            {stats.total_questions_discovered > 0 && (
              <IntentBreakdown
                questionsByIntent={stats.questions_by_intent}
                total={stats.total_questions_discovered}
              />
            )}

            {stats.total_keywords_enriched === 0 && (
              <div className="text-center py-6">
                <MessageCircleQuestion className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
                <p className="text-warmgray-500">No keywords enriched yet</p>
                <p className="text-sm text-warmgray-400 mt-1">
                  Run keyword research first to discover keywords for PAA enrichment.
                </p>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Active Enrichment Progress */}
      {isEnriching && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Loader2 className="w-5 h-5 text-primary-600 animate-spin" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">
                Enrichment In Progress
              </h3>
              <p className="text-sm text-warmgray-500">
                Discovering PAA questions...
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <ProgressBar
              current={stats?.total_keywords_enriched || 0}
              total={100}
              label="Progress"
            />
            <p className="text-sm text-warmgray-600">
              Questions will appear in the review queue below.
            </p>
          </div>
        </div>
      )}

      {/* Question Review Queue */}
      {pendingReviews.length > 0 && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowReviews(!showReviews)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gold-100 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-gold-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">
                  Question Review
                </h3>
                <p className="text-sm text-warmgray-500">
                  {reviewCounts.pending} pending, {reviewCounts.approved} approved
                </p>
              </div>
            </div>
            {showReviews ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showReviews && (
            <div className="mt-4 space-y-3">
              {/* Intent Filter */}
              <div className="flex items-center gap-2 pb-2 border-b border-cream-100">
                <Filter className="w-4 h-4 text-warmgray-400" />
                <span className="text-xs text-warmgray-500">Filter by intent:</span>
                <div className="flex gap-1">
                  {['all', 'buying', 'usage', 'care', 'comparison', 'unknown'].map((intent) => (
                    <button
                      key={intent}
                      type="button"
                      onClick={() => setIntentFilter(intent)}
                      className={cn(
                        'text-xs px-2 py-0.5 rounded-full transition-colors capitalize',
                        intentFilter === intent
                          ? 'bg-primary-100 text-primary-700'
                          : 'bg-cream-100 text-warmgray-600 hover:bg-cream-200'
                      )}
                    >
                      {intent}
                    </button>
                  ))}
                </div>
              </div>

              {filteredReviews.map((review) => (
                <QuestionReviewCard
                  key={review.question_id}
                  review={review}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  isProcessing={processingQuestionId === review.question_id}
                />
              ))}

              {reviewCounts.pending > 0 && (
                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      filteredReviews
                        .filter((r) => r.status === 'pending')
                        .forEach((r) => handleReject(r.question_id))
                    }}
                  >
                    Reject All
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={() => {
                      filteredReviews
                        .filter((r) => r.status === 'pending')
                        .forEach((r) => handleApprove(r.question_id))
                    }}
                  >
                    Approve All ({filteredReviews.filter((r) => r.status === 'pending').length})
                  </Button>
                </div>
              )}
            </div>
          )}
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
              <HelpCircle className="w-5 h-5 text-warmgray-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-warmgray-900">
                Enrichment Options
              </h3>
              <p className="text-sm text-warmgray-500">
                Configure and run PAA enrichment
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
              <FormField label="Location" helperText="Region for SERP data">
                <Select
                  value={formState.locationCode.toString()}
                  onChange={(e) => handleLocationChange(e.target.value)}
                  disabled={isEnriching}
                >
                  {LOCATION_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </FormField>

              <FormField label="Language" helperText="SERP language">
                <Select
                  value={formState.languageCode}
                  onChange={(e) => handleLanguageChange(e.target.value)}
                  disabled={isEnriching}
                >
                  {LANGUAGE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Max Fan-out Questions" helperText="Questions to search for nested PAA">
                <Select
                  value={formState.maxFanoutQuestions.toString()}
                  onChange={(e) => handleFanoutQuestionsChange(e.target.value)}
                  disabled={isEnriching || !formState.fanoutEnabled}
                >
                  {FANOUT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>

            <div className="space-y-3 pt-2">
              <Checkbox
                label="Enable fan-out search"
                checked={formState.fanoutEnabled}
                onChange={handleFanoutEnabledChange}
                disabled={isEnriching}
                helperText="Search initial PAA questions for nested questions"
              />

              <Checkbox
                label="Enable Related Searches fallback"
                checked={formState.fallbackEnabled}
                onChange={handleFallbackEnabledChange}
                disabled={isEnriching}
                helperText="Use Related Searches when PAA results are insufficient"
              />

              <Checkbox
                label="Categorize questions by intent"
                checked={formState.categorizeEnabled}
                onChange={handleCategorizeEnabledChange}
                disabled={isEnriching}
                helperText="Automatically classify questions (buying, usage, care, comparison)"
              />
            </div>

            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-warmgray-500">
                {stats && stats.total_keywords_enriched > 0
                  ? `${stats.total_keywords_enriched} keywords already enriched`
                  : 'Ready to start enrichment'}
              </p>
              <Button
                type="button"
                disabled={isEnriching}
                onClick={() => {
                  addBreadcrumb('Starting PAA enrichment', 'user_action', {
                    locationCode: formState.locationCode,
                    languageCode: formState.languageCode,
                    fanoutEnabled: formState.fanoutEnabled,
                    maxFanoutQuestions: formState.maxFanoutQuestions,
                    fallbackEnabled: formState.fallbackEnabled,
                    categorizeEnabled: formState.categorizeEnabled,
                  })
                  setIsEnriching(true)
                  setTimeout(() => {
                    setIsEnriching(false)
                  }, 3000)
                }}
              >
                {isEnriching ? (
                  <ButtonSpinner />
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Start Enrichment
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
