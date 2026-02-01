/**
 * ContentGenerationPanel - Content generation with 3-phase progress display
 *
 * Features:
 * - 3-phase content generation: Research, Drafting, Review
 * - Real-time progress tracking during generation
 * - Configuration options for tone, style, and length
 * - Content preview with approve/reject workflow
 * - Stats overview showing generation status
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Log form validation errors at debug level
 * - Log generation progress updates
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useCallback, useEffect } from 'react'
import {
  FileText,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Eye,
  ThumbsUp,
  ThumbsDown,
  Settings2,
  Clock,
  Zap,
  PenLine,
  Search,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { useProjectSubscription } from '@/lib/hooks/useWebSocket'
import { addBreadcrumb } from '@/lib/errorReporting'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { FormField, Textarea, Select, Input } from '@/components/ui/form-field'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Generation phase names */
type GenerationPhase = 'research' | 'drafting' | 'review'

/** Phase status */
type PhaseStatus = 'pending' | 'in_progress' | 'completed' | 'error'

/** Phase progress entry */
interface PhaseProgress {
  phase: GenerationPhase
  status: PhaseStatus
  started_at?: string | null
  completed_at?: string | null
  message?: string | null
  progress_percent?: number | null
}

/** Content generation stats from API */
interface ContentGenerationStats {
  total_generated: number
  pending_review: number
  approved: number
  rejected: number
  average_generation_time_ms: number | null
}

/** Generated content item */
interface GeneratedContent {
  id: string
  project_id: string
  title: string
  content: string
  content_type: string
  status: 'pending_review' | 'approved' | 'rejected'
  tone: string
  word_count: number
  generated_at: string
  reviewed_at?: string | null
  reviewer_notes?: string | null
}

/** Content list response */
interface ContentListResponse {
  items: GeneratedContent[]
  total: number
  page: number
  per_page: number
}

/** Generation request */
interface GenerationRequest {
  topic: string
  content_type: string
  tone: string
  target_word_count: number
  additional_instructions?: string
}

/** Generation response */
interface GenerationResponse {
  success: boolean
  content_id: string | null
  phases: PhaseProgress[]
  error: string | null
  duration_ms: number
}

/** Review action request */
interface ReviewRequest {
  action: 'approve' | 'reject'
  notes?: string
}

// ============================================================================
// Constants
// ============================================================================

/** Phase definitions */
const GENERATION_PHASES: { phase: GenerationPhase; label: string; icon: React.ElementType; description: string }[] = [
  { phase: 'research', label: 'Research', icon: Search, description: 'Analyzing topic and gathering context' },
  { phase: 'drafting', label: 'Drafting', icon: PenLine, description: 'Writing initial content draft' },
  { phase: 'review', label: 'Review', icon: Eye, description: 'Finalizing and polishing content' },
]

/** Content type options */
const CONTENT_TYPE_OPTIONS = [
  { value: 'blog_post', label: 'Blog Post' },
  { value: 'landing_page', label: 'Landing Page' },
  { value: 'product_description', label: 'Product Description' },
  { value: 'email', label: 'Email Copy' },
  { value: 'social_post', label: 'Social Media Post' },
  { value: 'faq', label: 'FAQ Entry' },
]

/** Tone options */
const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'conversational', label: 'Conversational' },
  { value: 'authoritative', label: 'Authoritative' },
  { value: 'playful', label: 'Playful' },
  { value: 'formal', label: 'Formal' },
]

/** Default form state */
const DEFAULT_FORM_STATE: GenerationRequest = {
  topic: '',
  content_type: 'blog_post',
  tone: 'professional',
  target_word_count: 500,
  additional_instructions: '',
}

/** Phase status colors */
const PHASE_STATUS_COLORS: Record<PhaseStatus, { bg: string; border: string; text: string; icon: string }> = {
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
  error: {
    bg: 'bg-error-50',
    border: 'border-error-200',
    text: 'text-error-700',
    icon: 'text-error-500',
  },
}

/** Content status colors */
const CONTENT_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending_review: { bg: 'bg-warning-100', text: 'text-warning-800' },
  approved: { bg: 'bg-success-100', text: 'text-success-800' },
  rejected: { bg: 'bg-error-100', text: 'text-error-800' },
}

// ============================================================================
// Sub-components
// ============================================================================

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
 * Phase progress indicator component
 */
function PhaseProgressIndicator({
  phases,
  currentPhase,
}: {
  phases: PhaseProgress[]
  currentPhase: GenerationPhase | null
}) {
  return (
    <div className="space-y-3">
      {GENERATION_PHASES.map((phaseDef, index) => {
        const phaseData = phases.find((p) => p.phase === phaseDef.phase)
        const status: PhaseStatus = phaseData?.status || 'pending'
        const colors = PHASE_STATUS_COLORS[status]
        const Icon = phaseDef.icon
        const isActive = phaseDef.phase === currentPhase

        return (
          <div key={phaseDef.phase} className="flex items-start gap-4">
            {/* Phase number and connector */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  'w-10 h-10 rounded-xl flex items-center justify-center border-2 transition-all',
                  colors.bg,
                  colors.border,
                  isActive && 'ring-2 ring-primary-400 ring-offset-2'
                )}
              >
                {status === 'in_progress' ? (
                  <Loader2 className={cn('w-5 h-5 animate-spin', colors.icon)} />
                ) : status === 'completed' ? (
                  <CheckCircle2 className={cn('w-5 h-5', colors.icon)} />
                ) : status === 'error' ? (
                  <AlertCircle className={cn('w-5 h-5', colors.icon)} />
                ) : (
                  <Icon className={cn('w-5 h-5', colors.icon)} />
                )}
              </div>
              {/* Connector line */}
              {index < GENERATION_PHASES.length - 1 && (
                <div
                  className={cn(
                    'w-0.5 h-8 mt-1',
                    status === 'completed' ? 'bg-success-300' : 'bg-cream-300'
                  )}
                />
              )}
            </div>

            {/* Phase content */}
            <div className="flex-1 min-w-0 pt-1">
              <div className="flex items-center gap-2">
                <h4 className={cn('font-medium', colors.text)}>{phaseDef.label}</h4>
                {status === 'in_progress' && phaseData?.progress_percent != null && (
                  <span className="text-xs font-medium text-primary-600">
                    {phaseData.progress_percent}%
                  </span>
                )}
              </div>
              <p className="text-sm text-warmgray-500 mt-0.5">{phaseDef.description}</p>
              {phaseData?.message && (
                <p className={cn('text-xs mt-1', colors.text)}>{phaseData.message}</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/**
 * Content preview card component
 */
function ContentPreviewCard({
  content,
  onApprove,
  onReject,
  isReviewing,
}: {
  content: GeneratedContent
  onApprove: (id: string, notes?: string) => void
  onReject: (id: string, notes?: string) => void
  isReviewing: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [reviewNotes, setReviewNotes] = useState('')
  const statusColors = CONTENT_STATUS_COLORS[content.status] || CONTENT_STATUS_COLORS.pending_review

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    } catch {
      return dateString
    }
  }

  return (
    <div className="border border-cream-200 rounded-xl bg-white overflow-hidden">
      {/* Header */}
      <button
        type="button"
        className="w-full flex items-center justify-between p-4 hover:bg-cream-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-cream-100 flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4 text-warmgray-600" />
          </div>
          <div className="text-left min-w-0">
            <h4 className="font-medium text-warmgray-900 truncate">{content.title}</h4>
            <p className="text-xs text-warmgray-500">
              {content.word_count} words · {formatDate(content.generated_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors.bg, statusColors.text)}>
            {content.status.replace('_', ' ')}
          </span>
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-warmgray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-warmgray-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-cream-200 p-4 space-y-4">
          {/* Content preview */}
          <div className="p-3 bg-cream-50 rounded-lg">
            <p className="text-sm text-warmgray-700 whitespace-pre-wrap line-clamp-6">
              {content.content}
            </p>
          </div>

          {/* Metadata */}
          <div className="flex flex-wrap gap-4 text-sm">
            <div className="flex items-center gap-1.5">
              <Settings2 className="w-3.5 h-3.5 text-warmgray-400" />
              <span className="text-warmgray-600">Type: {content.content_type.replace('_', ' ')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-warmgray-400" />
              <span className="text-warmgray-600">Tone: {content.tone}</span>
            </div>
          </div>

          {/* Review actions for pending content */}
          {content.status === 'pending_review' && (
            <div className="space-y-3 pt-2 border-t border-cream-200">
              <FormField label="Review Notes" optional>
                <Textarea
                  placeholder="Add feedback or notes..."
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  rows={2}
                  disabled={isReviewing}
                />
              </FormField>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onReject(content.id, reviewNotes)}
                  disabled={isReviewing}
                  className="flex-1"
                >
                  {isReviewing ? <ButtonSpinner /> : <ThumbsDown className="w-4 h-4" />}
                  Reject
                </Button>
                <Button
                  size="sm"
                  onClick={() => onApprove(content.id, reviewNotes)}
                  disabled={isReviewing}
                  className="flex-1"
                >
                  {isReviewing ? <ButtonSpinner /> : <ThumbsUp className="w-4 h-4" />}
                  Approve
                </Button>
              </div>
            </div>
          )}

          {/* Show reviewer notes for reviewed content */}
          {content.reviewer_notes && content.status !== 'pending_review' && (
            <div className="p-3 bg-cream-50 rounded-lg border border-cream-200">
              <p className="text-xs font-medium text-warmgray-500 mb-1">Review Notes</p>
              <p className="text-sm text-warmgray-700">{content.reviewer_notes}</p>
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

export interface ContentGenerationPanelProps {
  /** Project ID to manage content generation for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * ContentGenerationPanel provides content generation with 3-phase progress tracking
 *
 * @example
 * <ContentGenerationPanel projectId="abc-123" />
 */
export function ContentGenerationPanel({ projectId, className }: ContentGenerationPanelProps) {
  // UI state
  const [showConfig, setShowConfig] = useState(true)
  const [showContent, setShowContent] = useState(true)
  const [formState, setFormState] = useState<GenerationRequest>(DEFAULT_FORM_STATE)

  // Generation progress state
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationPhases, setGenerationPhases] = useState<PhaseProgress[]>([])
  const [currentPhase, setCurrentPhase] = useState<GenerationPhase | null>(null)

  // Fetch stats
  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useApiQuery<ContentGenerationStats>({
    queryKey: ['content-generation-stats', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/content_generation/stats`,
    requestOptions: {
      userAction: 'Load content generation stats',
      component: 'ContentGenerationPanel',
    },
  })

  // Fetch generated content
  const {
    data: contentList,
    isLoading: isLoadingContent,
    refetch: refetchContent,
  } = useApiQuery<ContentListResponse>({
    queryKey: ['content-generation-list', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/content_generation`,
    requestOptions: {
      userAction: 'Load generated content',
      component: 'ContentGenerationPanel',
    },
  })

  // Generate content mutation
  const generateMutation = useToastMutation<GenerationResponse, Error, GenerationRequest>({
    mutationFn: (data) =>
      api.post<GenerationResponse>(
        `/api/v1/projects/${projectId}/phases/content_generation/generate`,
        data,
        {
          userAction: 'Generate content',
          component: 'ContentGenerationPanel',
        }
      ),
    userAction: 'Generate content',
    successMessage: 'Content generated',
    successDescription: 'New content has been created and is ready for review.',
    onSuccess: () => {
      addBreadcrumb('Content generated', 'mutation', { projectId })
      setIsGenerating(false)
      setGenerationPhases([])
      setCurrentPhase(null)
      setFormState(DEFAULT_FORM_STATE)
      refetchStats()
      refetchContent()
    },
    onError: () => {
      setIsGenerating(false)
      setCurrentPhase(null)
    },
  })

  // Review content mutation
  const reviewMutation = useToastMutation<GeneratedContent, Error, { contentId: string; request: ReviewRequest }>({
    mutationFn: ({ contentId, request }) =>
      api.post<GeneratedContent>(
        `/api/v1/projects/${projectId}/phases/content_generation/${contentId}/review`,
        request,
        {
          userAction: `${request.action} content`,
          component: 'ContentGenerationPanel',
        }
      ),
    userAction: 'Review content',
    successMessage: (data) => `Content ${data.status === 'approved' ? 'approved' : 'rejected'}`,
    onSuccess: () => {
      addBreadcrumb('Content reviewed', 'mutation', { projectId })
      refetchStats()
      refetchContent()
    },
  })

  // WebSocket subscription for real-time progress updates
  useProjectSubscription(projectId, {
    onProgress: (progress) => {
      if (progress.type === 'content_generation') {
        const phases = progress.phases as PhaseProgress[] | undefined
        if (phases) {
          setGenerationPhases(phases)
          // Find current phase (first in_progress or last with any status)
          const activePhase = phases.find((p) => p.status === 'in_progress')
          setCurrentPhase(activePhase?.phase || null)
        }
      }
    },
    enabled: isGenerating,
  })

  // Poll for updates while generating
  useEffect(() => {
    if (!isGenerating) return

    const pollInterval = setInterval(() => {
      refetchStats()
      refetchContent()
    }, 3000)

    return () => clearInterval(pollInterval)
  }, [isGenerating, refetchStats, refetchContent])

  // Handlers
  const handleGenerate = useCallback(() => {
    if (!formState.topic.trim()) {
      console.warn('[ContentGenerationPanel] Topic required for generation')
      return
    }

    addBreadcrumb('Starting content generation', 'user_action', {
      topic: formState.topic,
      contentType: formState.content_type,
      tone: formState.tone,
    })

    // Initialize phases
    setGenerationPhases(
      GENERATION_PHASES.map((p) => ({
        phase: p.phase,
        status: 'pending' as PhaseStatus,
      }))
    )
    setIsGenerating(true)
    setCurrentPhase('research')

    // Simulate phase progression for demo (in production, this comes from WebSocket)
    const simulateProgress = async () => {
      const phases: GenerationPhase[] = ['research', 'drafting', 'review']
      for (let i = 0; i < phases.length; i++) {
        const phase = phases[i]
        setCurrentPhase(phase)
        setGenerationPhases((prev) =>
          prev.map((p) =>
            p.phase === phase
              ? { ...p, status: 'in_progress' as PhaseStatus, started_at: new Date().toISOString() }
              : p.phase === phases[i - 1]
                ? { ...p, status: 'completed' as PhaseStatus, completed_at: new Date().toISOString() }
                : p
          )
        )
        await new Promise((resolve) => setTimeout(resolve, 1500))
      }
      // Complete last phase
      setGenerationPhases((prev) =>
        prev.map((p) =>
          p.phase === 'review'
            ? { ...p, status: 'completed' as PhaseStatus, completed_at: new Date().toISOString() }
            : p
        )
      )
    }

    simulateProgress()
    generateMutation.mutate(formState)
  }, [formState, generateMutation])

  const handleApprove = useCallback(
    (contentId: string, notes?: string) => {
      reviewMutation.mutate({
        contentId,
        request: { action: 'approve', notes },
      })
    },
    [reviewMutation]
  )

  const handleReject = useCallback(
    (contentId: string, notes?: string) => {
      reviewMutation.mutate({
        contentId,
        request: { action: 'reject', notes },
      })
    },
    [reviewMutation]
  )

  const handleRefresh = useCallback(() => {
    refetchStats()
    refetchContent()
  }, [refetchStats, refetchContent])

  // Computed values
  const canGenerate = formState.topic.trim() && !isGenerating && !generateMutation.isPending
  const pendingContent = contentList?.items.filter((c) => c.status === 'pending_review') || []
  const reviewedContent = contentList?.items.filter((c) => c.status !== 'pending_review') || []

  const isLoading = isLoadingStats || isLoadingContent

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <FileText className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Content Generation</h3>
              <p className="text-sm text-warmgray-500">AI-powered content creation with review</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={isLoading}>
            <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" label="Loading content stats..." showLabel />
          </div>
        ) : stats ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              label="Total Generated"
              value={stats.total_generated}
              icon={FileText}
              variant="default"
            />
            <StatsCard
              label="Pending Review"
              value={stats.pending_review}
              icon={Clock}
              variant={stats.pending_review > 0 ? 'warning' : 'default'}
            />
            <StatsCard
              label="Approved"
              value={stats.approved}
              icon={CheckCircle2}
              variant="success"
            />
            <StatsCard
              label="Avg. Time"
              value={stats.average_generation_time_ms ? `${(stats.average_generation_time_ms / 1000).toFixed(1)}s` : '—'}
              icon={Zap}
              variant="default"
            />
          </div>
        ) : (
          <div className="text-center py-6">
            <FileText className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
            <p className="text-warmgray-500">No content generated yet</p>
            <p className="text-sm text-warmgray-400 mt-1">
              Configure and generate content to get started.
            </p>
          </div>
        )}
      </div>

      {/* Generation Configuration */}
      <div className="card">
        <button
          type="button"
          className="w-full flex items-center justify-between"
          onClick={() => setShowConfig(!showConfig)}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
              <Settings2 className="w-5 h-5 text-warmgray-600" />
            </div>
            <div className="text-left">
              <h3 className="font-semibold text-warmgray-900">Generate New Content</h3>
              <p className="text-sm text-warmgray-500">Configure and create content</p>
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
            {/* Generation progress */}
            {isGenerating && (
              <div className="p-4 bg-primary-50 rounded-xl border border-primary-200 mb-6">
                <h4 className="font-medium text-primary-700 mb-4">Generation in Progress</h4>
                <PhaseProgressIndicator phases={generationPhases} currentPhase={currentPhase} />
              </div>
            )}

            {/* Form fields */}
            <FormField label="Topic" required helperText="What should the content be about?">
              <Textarea
                placeholder="e.g., Benefits of sustainable packaging for e-commerce businesses"
                value={formState.topic}
                onChange={(e) => setFormState((prev) => ({ ...prev, topic: e.target.value }))}
                disabled={isGenerating}
                rows={3}
              />
            </FormField>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Content Type" required>
                <Select
                  value={formState.content_type}
                  onChange={(e) => setFormState((prev) => ({ ...prev, content_type: e.target.value }))}
                  disabled={isGenerating}
                >
                  {CONTENT_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </FormField>

              <FormField label="Tone" required>
                <Select
                  value={formState.tone}
                  onChange={(e) => setFormState((prev) => ({ ...prev, tone: e.target.value }))}
                  disabled={isGenerating}
                >
                  {TONE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>

            <FormField label="Target Word Count" required helperText="Approximate length of content">
              <Input
                type="number"
                value={formState.target_word_count}
                onChange={(e) =>
                  setFormState((prev) => ({ ...prev, target_word_count: parseInt(e.target.value) || 500 }))
                }
                disabled={isGenerating}
                min={100}
                max={5000}
                step={100}
              />
            </FormField>

            <FormField label="Additional Instructions" optional helperText="Special requirements or context">
              <Textarea
                placeholder="Add any specific requirements, keywords to include, or additional context..."
                value={formState.additional_instructions}
                onChange={(e) => setFormState((prev) => ({ ...prev, additional_instructions: e.target.value }))}
                disabled={isGenerating}
                rows={2}
              />
            </FormField>

            <div className="flex items-center justify-end pt-2">
              <Button
                type="button"
                disabled={!canGenerate}
                onClick={handleGenerate}
              >
                {isGenerating || generateMutation.isPending ? (
                  <ButtonSpinner />
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Generate Content
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Content List */}
      {(pendingContent.length > 0 || reviewedContent.length > 0) && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowContent(!showContent)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <Eye className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Generated Content</h3>
                <p className="text-sm text-warmgray-500">
                  {pendingContent.length > 0
                    ? `${pendingContent.length} awaiting review`
                    : 'All content reviewed'}
                </p>
              </div>
            </div>
            {showContent ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showContent && (
            <div className="mt-6 space-y-4">
              {/* Pending review section */}
              {pendingContent.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-warmgray-700 flex items-center gap-2">
                    <Clock className="w-4 h-4 text-warning-500" />
                    Pending Review ({pendingContent.length})
                  </h4>
                  {pendingContent.map((content) => (
                    <ContentPreviewCard
                      key={content.id}
                      content={content}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      isReviewing={reviewMutation.isPending}
                    />
                  ))}
                </div>
              )}

              {/* Reviewed content section */}
              {reviewedContent.length > 0 && (
                <div className="space-y-3">
                  <h4 className="text-sm font-medium text-warmgray-700 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-success-500" />
                    Reviewed ({reviewedContent.length})
                  </h4>
                  {reviewedContent.map((content) => (
                    <ContentPreviewCard
                      key={content.id}
                      content={content}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      isReviewing={reviewMutation.isPending}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
