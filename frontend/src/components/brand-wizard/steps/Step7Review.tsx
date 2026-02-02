/**
 * Step 7: Review & Generate
 *
 * Final review of all wizard data and generate button.
 *
 * Features:
 * - Summary of all configured sections
 * - Quick reference preview
 * - Generate button to create V3 config
 * - Validation warnings
 */

import { cn } from '@/lib/utils'
import { useMemo } from 'react'
import { WizardStepHeader } from '../WizardContainer'
import { Button } from '@/components/ui/button'
import {
  Building2,
  Users,
  MessageSquare,
  PenTool,
  Award,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Loader2,
  ChevronRight,
} from 'lucide-react'
import type { WizardFormData } from '../types'

export interface Step7ReviewProps {
  /** Current form data */
  formData: WizardFormData
  /** Callback to navigate to a specific step */
  onNavigateToStep?: (step: number) => void
  /** Whether generation is in progress */
  isGenerating?: boolean
  /** Callback to trigger generation */
  onGenerate?: () => void
  /** Generation error message */
  generateError?: string | null
  /** Whether the step is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}

interface SectionStatus {
  name: string
  icon: React.ElementType
  step: number
  isComplete: boolean
  summary: string
  warnings: string[]
}

/**
 * Step7Review - final review step before generation
 */
export function Step7Review({
  formData,
  onNavigateToStep,
  isGenerating = false,
  onGenerate,
  generateError,
  disabled = false,
  className,
}: Step7ReviewProps) {
  // Analyze completion status of each section
  const sections = useMemo<SectionStatus[]>(() => {
    const foundation = formData.foundation || {}
    const personas = formData.personas || []
    const voice = formData.voice_dimensions
    const characteristics = formData.voice_characteristics
    const rules = formData.writing_rules
    const vocabulary = formData.vocabulary
    const proof = formData.proof_elements
    const examples = formData.examples_bank

    return [
      {
        name: 'Brand Setup',
        icon: Building2,
        step: 1,
        isComplete: !!(formData.brand_name && formData.domain),
        summary: formData.brand_name
          ? `${formData.brand_name} (${formData.domain || 'no domain'})`
          : 'Not configured',
        warnings: [
          ...(!formData.brand_name ? ['Missing brand name'] : []),
          ...(!formData.domain ? ['Missing domain'] : []),
        ],
      },
      {
        name: 'Foundation',
        icon: Building2,
        step: 2,
        isComplete: !!(
          foundation.company_overview?.name ||
          foundation.positioning?.tagline ||
          foundation.mission_values?.mission_statement
        ),
        summary: foundation.positioning?.tagline
          ? `"${foundation.positioning.tagline.substring(0, 50)}..."`
          : foundation.company_overview?.name || 'Not configured',
        warnings: [
          ...(!foundation.positioning?.one_sentence ? ['Missing one-sentence description'] : []),
          ...(!foundation.differentiators?.primary_usp ? ['Missing primary USP'] : []),
        ],
      },
      {
        name: 'Audience',
        icon: Users,
        step: 3,
        isComplete: personas.length > 0,
        summary: personas.length > 0
          ? `${personas.length} persona${personas.length > 1 ? 's' : ''} defined`
          : 'No personas defined',
        warnings: [
          ...(personas.length === 0 ? ['No customer personas defined'] : []),
          ...(!personas.some((p) => p.is_primary) && personas.length > 0 ? ['No primary persona selected'] : []),
        ],
      },
      {
        name: 'Voice',
        icon: MessageSquare,
        step: 4,
        isComplete: !!(voice || characteristics?.we_are?.length),
        summary: voice
          ? `Formality: ${voice.formality}/10, Humor: ${voice.humor}/10`
          : 'Not configured',
        warnings: [
          ...(!characteristics?.we_are?.length ? ['No "We are" characteristics'] : []),
          ...(!characteristics?.we_are_not?.length ? ['No "We are NOT" characteristics'] : []),
        ],
      },
      {
        name: 'Writing Rules',
        icon: PenTool,
        step: 5,
        isComplete: !!(rules || vocabulary?.power_words?.length),
        summary: vocabulary?.power_words?.length
          ? `${vocabulary.power_words.length} power words, ${vocabulary.banned_words?.length || 0} banned`
          : rules
            ? 'Basic rules configured'
            : 'Not configured',
        warnings: [
          ...(!vocabulary?.power_words?.length ? ['No power words defined'] : []),
        ],
      },
      {
        name: 'Proof & Examples',
        icon: Award,
        step: 6,
        isComplete: !!(
          proof?.statistics?.length ||
          proof?.customer_quotes?.length ||
          examples?.headlines?.length
        ),
        summary: proof?.statistics?.length
          ? `${proof.statistics.length} stats, ${proof.customer_quotes?.length || 0} quotes`
          : examples?.headlines?.length
            ? `${examples.headlines.length} example headlines`
            : 'Not configured',
        warnings: [],
      },
    ]
  }, [formData])

  const completedCount = sections.filter((s) => s.isComplete).length
  const totalWarnings = sections.reduce((acc, s) => acc + s.warnings.length, 0)
  const canGenerate = completedCount >= 3 && formData.brand_name // At least brand name + 2 other sections

  return (
    <div className={cn('space-y-8', className)}>
      <WizardStepHeader
        title="Review & Generate"
        description="Review your brand configuration before generating. You can click any section to make changes."
      />

      {/* Overall status */}
      <div className={cn(
        'p-5 rounded-xl border',
        completedCount >= 5
          ? 'bg-success-50 border-success-200'
          : completedCount >= 3
            ? 'bg-warning-50 border-warning-200'
            : 'bg-error-50 border-error-200'
      )}>
        <div className="flex items-center gap-3">
          {completedCount >= 5 ? (
            <CheckCircle2 className="w-6 h-6 text-success-600" />
          ) : (
            <AlertTriangle className="w-6 h-6 text-warning-600" />
          )}
          <div>
            <p className={cn(
              'font-medium',
              completedCount >= 5 ? 'text-success-800' : 'text-warning-800'
            )}>
              {completedCount}/{sections.length} sections configured
            </p>
            <p className={cn(
              'text-sm',
              completedCount >= 5 ? 'text-success-700' : 'text-warning-700'
            )}>
              {completedCount >= 5
                ? 'Your brand configuration is ready to generate!'
                : totalWarnings > 0
                  ? `${totalWarnings} warning${totalWarnings > 1 ? 's' : ''} - consider completing more sections for better results`
                  : 'Complete more sections for better results'}
            </p>
          </div>
        </div>
      </div>

      {/* Section summaries */}
      <div className="space-y-3">
        {sections.map((section) => (
          <button
            key={section.step}
            type="button"
            onClick={() => onNavigateToStep?.(section.step)}
            disabled={disabled}
            className={cn(
              'w-full text-left p-4 rounded-lg border transition-colors',
              'hover:border-primary-300 hover:bg-primary-50/50',
              section.isComplete
                ? 'bg-white border-cream-200'
                : 'bg-cream-50 border-cream-300'
            )}
          >
            <div className="flex items-start gap-4">
              {/* Icon */}
              <div className={cn(
                'p-2 rounded-lg',
                section.isComplete ? 'bg-success-100' : 'bg-cream-200'
              )}>
                <section.icon className={cn(
                  'w-5 h-5',
                  section.isComplete ? 'text-success-600' : 'text-warmgray-400'
                )} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="font-medium text-warmgray-900">
                    {section.name}
                  </h4>
                  {section.isComplete && (
                    <CheckCircle2 className="w-4 h-4 text-success-500" />
                  )}
                </div>
                <p className="text-sm text-warmgray-600 truncate">
                  {section.summary}
                </p>
                {section.warnings.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {section.warnings.map((warning, i) => (
                      <li key={i} className="text-xs text-warning-600 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        {warning}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Arrow */}
              <ChevronRight className="w-5 h-5 text-warmgray-400" />
            </div>
          </button>
        ))}
      </div>

      {/* Generate button */}
      <div className="pt-6 border-t border-cream-200">
        <div className="flex flex-col items-center text-center">
          <FileText className="w-12 h-12 text-primary-400 mb-4" />
          <h3 className="text-lg font-medium text-warmgray-900 mb-2">
            Ready to generate your brand configuration?
          </h3>
          <p className="text-warmgray-600 mb-6 max-w-md">
            This will create a comprehensive brand guidelines document that AI will use
            to generate all your content.
          </p>

          {generateError && (
            <div className="mb-4 p-4 bg-error-50 border border-error-200 rounded-lg text-left w-full max-w-md">
              <p className="text-sm text-error-800">
                <strong>Generation failed:</strong> {generateError}
              </p>
            </div>
          )}

          <Button
            type="button"
            size="lg"
            onClick={onGenerate}
            disabled={disabled || isGenerating || !canGenerate}
            className="min-w-[200px]"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Sparkles className="w-5 h-5 mr-2" />
                Generate Brand Config
              </>
            )}
          </Button>

          {!canGenerate && !isGenerating && (
            <p className="mt-3 text-sm text-warmgray-500">
              Please complete at least the Brand Setup and 2 other sections
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
