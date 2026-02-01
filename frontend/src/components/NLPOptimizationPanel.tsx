/**
 * NLPOptimizationPanel - Content optimization with NLP score breakdown
 *
 * Features:
 * - Multi-factor content quality scoring with visual breakdown
 * - Real-time score analysis (word count, semantic, readability, keywords, entities)
 * - Term recommendations from competitor analysis
 * - Score thresholds with visual indicators
 * - Collapsible detail sections
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Log analysis start/complete at debug level
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useCallback, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  BookOpen,
  Target,
  Sparkles,
  FileText,
  Loader2,
  Lightbulb,
  AlertTriangle,
} from 'lucide-react'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

// ============================================================================
// Types
// ============================================================================

/** Individual score component */
interface ScoreComponent {
  score: number
  [key: string]: unknown
}

/** Word count score details */
interface WordCountScoreDetail extends ScoreComponent {
  word_count: number
  sentence_count: number
  paragraph_count: number
  avg_words_per_sentence: number
}

/** Semantic score details */
interface SemanticScoreDetail extends ScoreComponent {
  top_terms: Array<{ term: string; score: number }>
  term_diversity: number
  content_depth: number
}

/** Readability score details */
interface ReadabilityScoreDetail extends ScoreComponent {
  flesch_reading_ease: number
  flesch_kincaid_grade: number
  avg_syllables_per_word: number
}

/** Keyword density score details */
interface KeywordDensityScoreDetail extends ScoreComponent {
  primary_keyword: string
  primary_density: number
  secondary_keywords: Array<{ keyword: string; density: number }>
  total_keyword_occurrences: number
}

/** Entity coverage score details */
interface EntityCoverageScoreDetail extends ScoreComponent {
  entities: Record<string, string[]>
  entity_count: number
  entity_types_covered: number
  coverage_ratio: number
}

/** Full content score result from API */
interface ContentScoreResult {
  success: boolean
  overall_score: number
  word_count_score: WordCountScoreDetail | null
  semantic_score: SemanticScoreDetail | null
  readability_score: ReadabilityScoreDetail | null
  keyword_density_score: KeywordDensityScoreDetail | null
  entity_coverage_score: EntityCoverageScoreDetail | null
  passed: boolean
  error: string | null
  duration_ms: number
}

/** Recommended term from competitor analysis */
interface RecommendedTerm {
  term: string
  score: number
  priority: 'high' | 'medium' | 'low'
  doc_frequency: number
  is_missing: boolean
  category: string | null
}

/** Term recommendations response */
interface TermRecommendationsResponse {
  success: boolean
  request_id: string
  recommendations: RecommendedTerm[]
  recommendation_count: number
  user_term_count: number
  competitor_term_count: number
  document_count: number
  high_priority_count: number
  medium_priority_count: number
  low_priority_count: number
  error: string | null
  duration_ms: number
}

// ============================================================================
// Constants
// ============================================================================

/** Score thresholds for visual indicators */
const SCORE_THRESHOLDS = {
  excellent: 0.8,
  good: 0.6,
  fair: 0.4,
}

/** Priority colors */
const priorityColors = {
  high: {
    bg: 'bg-error-50',
    text: 'text-error-700',
    border: 'border-error-200',
    badge: 'bg-error-100 text-error-700',
  },
  medium: {
    bg: 'bg-warning-50',
    text: 'text-warning-700',
    border: 'border-warning-200',
    badge: 'bg-warning-100 text-warning-700',
  },
  low: {
    bg: 'bg-cream-50',
    text: 'text-warmgray-700',
    border: 'border-cream-200',
    badge: 'bg-cream-100 text-warmgray-600',
  },
}

/** Scoring component metadata */
const SCORE_COMPONENTS = {
  word_count: {
    label: 'Word Count',
    icon: FileText,
    description: 'Content length and structure metrics',
    weight: 0.15,
  },
  semantic: {
    label: 'Semantic Depth',
    icon: Sparkles,
    description: 'Topic coverage and term diversity',
    weight: 0.25,
  },
  readability: {
    label: 'Readability',
    icon: BookOpen,
    description: 'Flesch-Kincaid reading ease',
    weight: 0.20,
  },
  keyword_density: {
    label: 'Keywords',
    icon: Target,
    description: 'Primary and secondary keyword usage',
    weight: 0.25,
  },
  entity_coverage: {
    label: 'Entities',
    icon: TrendingUp,
    description: 'Named entity diversity',
    weight: 0.15,
  },
} as const

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Get score color based on value
 */
function getScoreColor(score: number): {
  text: string
  bg: string
  border: string
  ring: string
} {
  if (score >= SCORE_THRESHOLDS.excellent) {
    return {
      text: 'text-success-700',
      bg: 'bg-success-50',
      border: 'border-success-200',
      ring: 'ring-success-500',
    }
  }
  if (score >= SCORE_THRESHOLDS.good) {
    return {
      text: 'text-primary-700',
      bg: 'bg-primary-50',
      border: 'border-primary-200',
      ring: 'ring-primary-500',
    }
  }
  if (score >= SCORE_THRESHOLDS.fair) {
    return {
      text: 'text-warning-700',
      bg: 'bg-warning-50',
      border: 'border-warning-200',
      ring: 'ring-warning-500',
    }
  }
  return {
    text: 'text-error-700',
    bg: 'bg-error-50',
    border: 'border-error-200',
    ring: 'ring-error-500',
  }
}

/**
 * Get score label
 */
function getScoreLabel(score: number): string {
  if (score >= SCORE_THRESHOLDS.excellent) return 'Excellent'
  if (score >= SCORE_THRESHOLDS.good) return 'Good'
  if (score >= SCORE_THRESHOLDS.fair) return 'Fair'
  return 'Needs Work'
}

/**
 * Format percentage
 */
function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Circular score gauge component
 */
function ScoreGauge({
  score,
  size = 'md',
  showLabel = true,
}: {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}) {
  const colors = getScoreColor(score)
  const circumference = 2 * Math.PI * 45
  const strokeDashoffset = circumference - score * circumference

  const sizeClasses = {
    sm: 'w-16 h-16',
    md: 'w-24 h-24',
    lg: 'w-32 h-32',
  }

  const textSizes = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-3xl',
  }

  return (
    <div className={cn('relative', sizeClasses[size])}>
      <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
        {/* Background circle */}
        <circle
          className="stroke-cream-200"
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="8"
        />
        {/* Progress circle */}
        <circle
          className={cn('transition-all duration-500', colors.text.replace('text-', 'stroke-'))}
          cx="50"
          cy="50"
          r="45"
          fill="none"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn('font-bold', textSizes[size], colors.text)}>
          {Math.round(score * 100)}
        </span>
        {showLabel && (
          <span className="text-xs text-warmgray-500">
            {getScoreLabel(score)}
          </span>
        )}
      </div>
    </div>
  )
}

/**
 * Score bar component for individual metrics
 */
function ScoreBar({
  label,
  score,
  weight,
  icon: Icon,
  isExpanded,
  onToggle,
  children,
}: {
  label: string
  score: number
  weight: number
  icon: React.ElementType
  isExpanded: boolean
  onToggle: () => void
  children?: React.ReactNode
}) {
  const colors = getScoreColor(score)
  const percentage = Math.round(score * 100)

  return (
    <div className={cn('border rounded-xl overflow-hidden', colors.border)}>
      <button
        type="button"
        className={cn(
          'w-full p-4 flex items-center gap-4 transition-colors',
          colors.bg,
          'hover:opacity-90'
        )}
        onClick={onToggle}
        aria-expanded={isExpanded}
      >
        <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon className={cn('w-4 h-4', colors.text)} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-medium text-warmgray-900">{label}</span>
            <div className="flex items-center gap-2">
              <span className={cn('text-sm font-semibold', colors.text)}>
                {percentage}%
              </span>
              <span className="text-xs text-warmgray-400">
                (×{weight})
              </span>
            </div>
          </div>

          <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                colors.bg.replace('bg-', 'bg-').replace('-50', '-500')
              )}
              style={{ width: `${percentage}%` }}
            />
          </div>
        </div>

        {children && (
          isExpanded ? (
            <ChevronUp className="w-4 h-4 text-warmgray-400 shrink-0" />
          ) : (
            <ChevronDown className="w-4 h-4 text-warmgray-400 shrink-0" />
          )
        )}
      </button>

      {isExpanded && children && (
        <div className="px-4 pb-4 pt-2 border-t border-cream-100 bg-white">
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Term recommendation badge
 */
function TermBadge({ term }: { term: RecommendedTerm }) {
  const colors = priorityColors[term.priority]

  return (
    <div
      className={cn(
        'flex items-center justify-between px-3 py-2 rounded-lg border',
        colors.bg,
        colors.border
      )}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className={cn('text-sm font-medium truncate', colors.text)}>
          {term.term}
        </span>
        <span className={cn('text-xs px-1.5 py-0.5 rounded-full shrink-0', colors.badge)}>
          {term.priority}
        </span>
      </div>
      <span className="text-xs text-warmgray-500 ml-2 shrink-0">
        {Math.round(term.score * 100)}%
      </span>
    </div>
  )
}

/**
 * Detail metric row
 */
function DetailMetric({
  label,
  value,
  unit,
  optimal,
}: {
  label: string
  value: string | number
  unit?: string
  optimal?: string
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-warmgray-600">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-warmgray-900">
          {typeof value === 'number' ? value.toLocaleString() : value}
          {unit && <span className="text-warmgray-400"> {unit}</span>}
        </span>
        {optimal && (
          <span className="text-xs text-warmgray-400">({optimal})</span>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export interface NLPOptimizationPanelProps {
  /** Project ID */
  projectId: string
  /** Page ID for content being analyzed */
  pageId?: string
  /** Content to analyze (if not fetched from API) */
  content?: string
  /** Primary keyword for the content */
  primaryKeyword?: string
  /** Secondary keywords */
  secondaryKeywords?: string[]
  /** Competitor documents for term recommendations */
  competitorDocuments?: string[]
  /** Optional CSS classes */
  className?: string
}

/**
 * NLPOptimizationPanel displays comprehensive NLP content scoring with breakdown
 *
 * @example
 * <NLPOptimizationPanel
 *   projectId="proj-123"
 *   pageId="page-456"
 *   content="Your content here..."
 *   primaryKeyword="main keyword"
 * />
 */
export function NLPOptimizationPanel({
  projectId,
  pageId,
  content = '',
  primaryKeyword = '',
  secondaryKeywords = [],
  competitorDocuments = [],
  className,
}: NLPOptimizationPanelProps) {
  // Expanded state for score details
  const [expandedScores, setExpandedScores] = useState<Set<string>>(new Set())
  const [showRecommendations, setShowRecommendations] = useState(true)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [scoreResult, setScoreResult] = useState<ContentScoreResult | null>(null)

  // Analyze content mutation
  const analyzeContentMutation = useToastMutation<ContentScoreResult, Error, void>({
    mutationFn: async () => {
      addBreadcrumb('Starting content analysis', 'nlp_optimization', {
        projectId,
        pageId,
        contentLength: content.length,
      })

      setIsAnalyzing(true)
      try {
        // Call the content scoring API
        const response = await api.post<ContentScoreResult>(
          '/api/v1/content/score',
          {
            content,
            primary_keyword: primaryKeyword,
            secondary_keywords: secondaryKeywords,
            project_id: projectId,
            page_id: pageId,
          }
        )
        return response
      } finally {
        setIsAnalyzing(false)
      }
    },
    userAction: 'Analyze content',
    successMessage: 'Content analyzed successfully',
    onSuccess: (data) => {
      setScoreResult(data)
      addBreadcrumb('Content analysis complete', 'nlp_optimization', {
        overallScore: data.overall_score,
        passed: data.passed,
      })
    },
  })

  // Fetch term recommendations (uses POST, so we use useQuery with api.post)
  const {
    data: recommendations,
    isLoading: isLoadingRecommendations,
    refetch: refetchRecommendations,
  } = useQuery<TermRecommendationsResponse>({
    queryKey: ['term-recommendations', projectId, pageId, content.slice(0, 100)],
    queryFn: async () => {
      addBreadcrumb('Fetching term recommendations', 'nlp_optimization', {
        projectId,
        pageId,
      })
      return api.post<TermRecommendationsResponse>(
        '/api/v1/nlp/recommend-terms',
        {
          user_content: content,
          competitor_documents: competitorDocuments,
          top_n: 20,
          include_bigrams: true,
          only_missing: true,
          project_id: projectId,
          page_id: pageId,
        },
        {
          userAction: 'Fetch term recommendations',
          component: 'NLPOptimizationPanel',
        }
      )
    },
    enabled: content.length > 0 && competitorDocuments.length > 0,
  })

  // Toggle score detail expansion
  const toggleScoreExpansion = useCallback((key: string) => {
    setExpandedScores((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

  // Handle analyze click
  const handleAnalyze = useCallback(() => {
    if (content.length === 0) return
    analyzeContentMutation.mutate()
  }, [content.length, analyzeContentMutation])

  // Memoize priority counts
  const priorityCounts = useMemo(() => {
    if (!recommendations?.recommendations) return { high: 0, medium: 0, low: 0 }
    return {
      high: recommendations.high_priority_count,
      medium: recommendations.medium_priority_count,
      low: recommendations.low_priority_count,
    }
  }, [recommendations])

  // Check if we can analyze
  const canAnalyze = content.length > 0

  return (
    <div className={cn('space-y-6', className)}>
      {/* Header Card */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">NLP Optimization</h3>
              <p className="text-sm text-warmgray-500">Content quality analysis</p>
            </div>
          </div>

          <Button
            variant="default"
            size="sm"
            onClick={handleAnalyze}
            disabled={!canAnalyze || isAnalyzing}
          >
            {isAnalyzing ? (
              <ButtonSpinner />
            ) : (
              <>
                <RefreshCw className={cn('w-4 h-4', isAnalyzing && 'animate-spin')} />
                Analyze
              </>
            )}
          </Button>
        </div>

        {/* No content message */}
        {!canAnalyze && (
          <div className="text-center py-8 border border-dashed border-cream-200 rounded-xl">
            <FileText className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
            <p className="text-warmgray-500">No content to analyze</p>
            <p className="text-sm text-warmgray-400 mt-1">
              Add content to see NLP optimization scores
            </p>
          </div>
        )}

        {/* Loading state */}
        {isAnalyzing && (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" label="Analyzing content..." showLabel />
          </div>
        )}

        {/* Score Overview */}
        {scoreResult && !isAnalyzing && (
          <div className="space-y-6">
            {/* Overall Score */}
            <div className="flex items-center gap-6 p-4 bg-cream-50 rounded-xl">
              <ScoreGauge score={scoreResult.overall_score} size="lg" />

              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  {scoreResult.passed ? (
                    <CheckCircle2 className="w-5 h-5 text-success-600" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-warning-600" />
                  )}
                  <span className="font-medium text-warmgray-900">
                    {scoreResult.passed ? 'Content meets quality threshold' : 'Content needs improvement'}
                  </span>
                </div>

                <p className="text-sm text-warmgray-600 mb-3">
                  Overall score based on 5 quality dimensions weighted by importance.
                </p>

                <div className="flex items-center gap-4 text-xs text-warmgray-500">
                  <span>Analysis time: {scoreResult.duration_ms.toFixed(0)}ms</span>
                  <span>•</span>
                  <span>Pass threshold: 60%</span>
                </div>
              </div>
            </div>

            {/* Error message */}
            {scoreResult.error && (
              <div className="flex items-center gap-3 p-4 bg-error-50 border border-error-200 rounded-xl">
                <AlertCircle className="w-5 h-5 text-error-600 shrink-0" />
                <p className="text-sm text-error-700">{scoreResult.error}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Score Breakdown */}
      {scoreResult && !isAnalyzing && (
        <div className="card">
          <h4 className="font-semibold text-warmgray-900 mb-4">Score Breakdown</h4>

          <div className="space-y-3">
            {/* Word Count Score */}
            {scoreResult.word_count_score && (
              <ScoreBar
                label={SCORE_COMPONENTS.word_count.label}
                score={scoreResult.word_count_score.score}
                weight={SCORE_COMPONENTS.word_count.weight}
                icon={SCORE_COMPONENTS.word_count.icon}
                isExpanded={expandedScores.has('word_count')}
                onToggle={() => toggleScoreExpansion('word_count')}
              >
                <div className="space-y-1 text-sm">
                  <DetailMetric
                    label="Word count"
                    value={scoreResult.word_count_score.word_count}
                    optimal="300-2000"
                  />
                  <DetailMetric
                    label="Sentences"
                    value={scoreResult.word_count_score.sentence_count}
                  />
                  <DetailMetric
                    label="Paragraphs"
                    value={scoreResult.word_count_score.paragraph_count}
                  />
                  <DetailMetric
                    label="Avg words/sentence"
                    value={scoreResult.word_count_score.avg_words_per_sentence.toFixed(1)}
                    optimal="15-25"
                  />
                </div>
              </ScoreBar>
            )}

            {/* Semantic Score */}
            {scoreResult.semantic_score && (
              <ScoreBar
                label={SCORE_COMPONENTS.semantic.label}
                score={scoreResult.semantic_score.score}
                weight={SCORE_COMPONENTS.semantic.weight}
                icon={SCORE_COMPONENTS.semantic.icon}
                isExpanded={expandedScores.has('semantic')}
                onToggle={() => toggleScoreExpansion('semantic')}
              >
                <div className="space-y-3">
                  <div className="space-y-1">
                    <DetailMetric
                      label="Term diversity"
                      value={formatPercent(scoreResult.semantic_score.term_diversity)}
                    />
                    <DetailMetric
                      label="Content depth"
                      value={formatPercent(scoreResult.semantic_score.content_depth)}
                    />
                  </div>

                  {scoreResult.semantic_score.top_terms.length > 0 && (
                    <div>
                      <p className="text-xs text-warmgray-500 mb-2">Top terms:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {scoreResult.semantic_score.top_terms.slice(0, 8).map((t) => (
                          <span
                            key={t.term}
                            className="text-xs px-2 py-1 bg-cream-100 text-warmgray-600 rounded-md"
                          >
                            {t.term}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </ScoreBar>
            )}

            {/* Readability Score */}
            {scoreResult.readability_score && (
              <ScoreBar
                label={SCORE_COMPONENTS.readability.label}
                score={scoreResult.readability_score.score}
                weight={SCORE_COMPONENTS.readability.weight}
                icon={SCORE_COMPONENTS.readability.icon}
                isExpanded={expandedScores.has('readability')}
                onToggle={() => toggleScoreExpansion('readability')}
              >
                <div className="space-y-1">
                  <DetailMetric
                    label="Flesch Reading Ease"
                    value={scoreResult.readability_score.flesch_reading_ease.toFixed(1)}
                    optimal="30-70"
                  />
                  <DetailMetric
                    label="Grade Level"
                    value={scoreResult.readability_score.flesch_kincaid_grade.toFixed(1)}
                  />
                  <DetailMetric
                    label="Avg syllables/word"
                    value={scoreResult.readability_score.avg_syllables_per_word.toFixed(2)}
                  />
                </div>
              </ScoreBar>
            )}

            {/* Keyword Density Score */}
            {scoreResult.keyword_density_score && (
              <ScoreBar
                label={SCORE_COMPONENTS.keyword_density.label}
                score={scoreResult.keyword_density_score.score}
                weight={SCORE_COMPONENTS.keyword_density.weight}
                icon={SCORE_COMPONENTS.keyword_density.icon}
                isExpanded={expandedScores.has('keyword_density')}
                onToggle={() => toggleScoreExpansion('keyword_density')}
              >
                <div className="space-y-3">
                  {scoreResult.keyword_density_score.primary_keyword && (
                    <div className="p-3 bg-primary-50 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Target className="w-4 h-4 text-primary-600" />
                          <span className="text-sm font-medium text-primary-700">
                            {scoreResult.keyword_density_score.primary_keyword}
                          </span>
                        </div>
                        <span className="text-sm text-primary-600">
                          {scoreResult.keyword_density_score.primary_density.toFixed(2)}%
                        </span>
                      </div>
                      <p className="text-xs text-warmgray-500 mt-1">
                        Optimal: 0.5% - 2.5%
                      </p>
                    </div>
                  )}

                  {scoreResult.keyword_density_score.secondary_keywords.length > 0 && (
                    <div>
                      <p className="text-xs text-warmgray-500 mb-2">Secondary keywords:</p>
                      <div className="space-y-1">
                        {scoreResult.keyword_density_score.secondary_keywords.map((kw) => (
                          <div
                            key={kw.keyword}
                            className="flex items-center justify-between text-sm"
                          >
                            <span className="text-warmgray-600">{kw.keyword}</span>
                            <span className="text-warmgray-500">
                              {kw.density.toFixed(2)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <DetailMetric
                    label="Total occurrences"
                    value={scoreResult.keyword_density_score.total_keyword_occurrences}
                  />
                </div>
              </ScoreBar>
            )}

            {/* Entity Coverage Score */}
            {scoreResult.entity_coverage_score && (
              <ScoreBar
                label={SCORE_COMPONENTS.entity_coverage.label}
                score={scoreResult.entity_coverage_score.score}
                weight={SCORE_COMPONENTS.entity_coverage.weight}
                icon={SCORE_COMPONENTS.entity_coverage.icon}
                isExpanded={expandedScores.has('entity_coverage')}
                onToggle={() => toggleScoreExpansion('entity_coverage')}
              >
                <div className="space-y-3">
                  <div className="space-y-1">
                    <DetailMetric
                      label="Entity types found"
                      value={scoreResult.entity_coverage_score.entity_types_covered}
                    />
                    <DetailMetric
                      label="Total entities"
                      value={scoreResult.entity_coverage_score.entity_count}
                    />
                    <DetailMetric
                      label="Coverage ratio"
                      value={formatPercent(scoreResult.entity_coverage_score.coverage_ratio)}
                    />
                  </div>

                  {Object.keys(scoreResult.entity_coverage_score.entities).length > 0 && (
                    <div>
                      <p className="text-xs text-warmgray-500 mb-2">Detected entities:</p>
                      <div className="space-y-2">
                        {Object.entries(scoreResult.entity_coverage_score.entities).map(
                          ([type, entities]) => (
                            <div key={type}>
                              <p className="text-xs font-medium text-warmgray-600 capitalize mb-1">
                                {type.replace('_', ' ')}
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {entities.slice(0, 5).map((e, i) => (
                                  <span
                                    key={`${e}-${i}`}
                                    className="text-xs px-2 py-0.5 bg-cream-100 text-warmgray-600 rounded"
                                  >
                                    {e}
                                  </span>
                                ))}
                                {entities.length > 5 && (
                                  <span className="text-xs text-warmgray-400">
                                    +{entities.length - 5} more
                                  </span>
                                )}
                              </div>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </ScoreBar>
            )}
          </div>
        </div>
      )}

      {/* Term Recommendations */}
      {competitorDocuments.length > 0 && content.length > 0 && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowRecommendations(!showRecommendations)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gold-100 flex items-center justify-center">
                <Lightbulb className="w-5 h-5 text-gold-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Term Recommendations</h3>
                <p className="text-sm text-warmgray-500">
                  {recommendations?.recommendation_count || 0} terms from competitor analysis
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {isLoadingRecommendations && (
                <Loader2 className="w-4 h-4 text-warmgray-400 animate-spin" />
              )}
              {showRecommendations ? (
                <ChevronUp className="w-5 h-5 text-warmgray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-warmgray-400" />
              )}
            </div>
          </button>

          {showRecommendations && (
            <div className="mt-4 space-y-4">
              {isLoadingRecommendations ? (
                <div className="flex items-center justify-center py-8">
                  <LoadingSpinner size="md" label="Loading recommendations..." showLabel />
                </div>
              ) : recommendations?.recommendations ? (
                <>
                  {/* Priority summary */}
                  <div className="flex items-center gap-4 p-3 bg-cream-50 rounded-lg text-sm">
                    <span className="text-error-600 font-medium">
                      {priorityCounts.high} high
                    </span>
                    <span className="text-warning-600 font-medium">
                      {priorityCounts.medium} medium
                    </span>
                    <span className="text-warmgray-500">
                      {priorityCounts.low} low
                    </span>
                  </div>

                  {/* High priority terms */}
                  {priorityCounts.high > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                        High Priority
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {recommendations.recommendations
                          .filter((t) => t.priority === 'high')
                          .map((term) => (
                            <TermBadge key={term.term} term={term} />
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Medium priority terms */}
                  {priorityCounts.medium > 0 && (
                    <div className="space-y-2">
                      <h4 className="text-xs font-medium text-warmgray-500 uppercase tracking-wide">
                        Medium Priority
                      </h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {recommendations.recommendations
                          .filter((t) => t.priority === 'medium')
                          .map((term) => (
                            <TermBadge key={term.term} term={term} />
                          ))}
                      </div>
                    </div>
                  )}

                  {/* Low priority (collapsed by default) */}
                  {priorityCounts.low > 0 && (
                    <details className="group">
                      <summary className="text-xs font-medium text-warmgray-500 cursor-pointer hover:text-warmgray-700">
                        Show {priorityCounts.low} low priority terms
                      </summary>
                      <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                        {recommendations.recommendations
                          .filter((t) => t.priority === 'low')
                          .map((term) => (
                            <span
                              key={term.term}
                              className="text-xs px-2 py-1 bg-cream-50 rounded text-warmgray-600 truncate"
                            >
                              {term.term}
                            </span>
                          ))}
                      </div>
                    </details>
                  )}

                  {/* Refresh button */}
                  <div className="flex justify-end pt-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => refetchRecommendations()}
                      disabled={isLoadingRecommendations}
                    >
                      <RefreshCw
                        className={cn('w-4 h-4', isLoadingRecommendations && 'animate-spin')}
                      />
                      Refresh
                    </Button>
                  </div>
                </>
              ) : (
                <div className="text-center py-6">
                  <Lightbulb className="w-10 h-10 text-warmgray-300 mx-auto mb-2" />
                  <p className="text-warmgray-500 text-sm">
                    No recommendations available
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
