/**
 * Step 1: Brand Setup
 *
 * First step of the brand wizard - collects basic brand info and triggers research.
 *
 * Features:
 * - Brand name input
 * - Domain input with validation
 * - Research button to trigger Perplexity research
 * - Research status indicator
 * - Research results preview
 */

import { cn } from '@/lib/utils'
import { WizardStepHeader } from '../WizardContainer'
import { Button } from '@/components/ui/button'
import { Search, Loader2, CheckCircle2, AlertCircle, ExternalLink } from 'lucide-react'
import type { WizardFormData, ResearchData } from '../types'

export interface Step1BrandSetupProps {
  /** Current form data */
  formData: WizardFormData
  /** Callback when form data changes */
  onChange: (data: Partial<WizardFormData>) => void
  /** Research data from Perplexity */
  researchData?: ResearchData | null
  /** Research citations */
  researchCitations?: string[]
  /** When research was cached */
  researchCachedAt?: string | null
  /** Whether research is in progress */
  isResearching?: boolean
  /** Callback to trigger research */
  onResearch?: () => void
  /** Research error message */
  researchError?: string | null
  /** Whether the step is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}

/**
 * Step1BrandSetup - first wizard step for brand name and domain
 */
export function Step1BrandSetup({
  formData,
  onChange,
  researchData,
  researchCitations = [],
  researchCachedAt,
  isResearching = false,
  onResearch,
  researchError,
  disabled = false,
  className,
}: Step1BrandSetupProps) {
  const hasResearchData = !!researchData
  const canResearch = formData.domain && formData.domain.trim().length > 0

  return (
    <div className={cn('space-y-8', className)}>
      <WizardStepHeader
        title="Brand Setup"
        description="Let's start by identifying your brand. Enter your brand name and website domain, then we'll research your brand to help pre-fill the wizard."
      />

      {/* Brand name and domain inputs */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Brand Name */}
        <div>
          <label
            htmlFor="brand-name"
            className="block text-sm font-medium text-warmgray-700 mb-2"
          >
            Brand Name
          </label>
          <input
            id="brand-name"
            type="text"
            value={formData.brand_name || ''}
            onChange={(e) => onChange({ brand_name: e.target.value })}
            placeholder="e.g., Acme Corp"
            disabled={disabled}
            className={cn(
              'w-full px-4 py-3 text-base border border-cream-200 rounded-lg',
              'focus:border-primary-400 focus:ring-2 focus:ring-primary-100',
              'placeholder:text-warmgray-400',
              disabled && 'bg-cream-50 cursor-not-allowed'
            )}
          />
          <p className="mt-1.5 text-sm text-warmgray-500">
            Your company or brand name as it appears publicly
          </p>
        </div>

        {/* Domain */}
        <div>
          <label
            htmlFor="domain"
            className="block text-sm font-medium text-warmgray-700 mb-2"
          >
            Website Domain
          </label>
          <input
            id="domain"
            type="text"
            value={formData.domain || ''}
            onChange={(e) => onChange({ domain: e.target.value })}
            placeholder="e.g., acmecorp.com"
            disabled={disabled}
            className={cn(
              'w-full px-4 py-3 text-base border border-cream-200 rounded-lg',
              'focus:border-primary-400 focus:ring-2 focus:ring-primary-100',
              'placeholder:text-warmgray-400',
              disabled && 'bg-cream-50 cursor-not-allowed'
            )}
          />
          <p className="mt-1.5 text-sm text-warmgray-500">
            Your main website domain (without https://)
          </p>
        </div>
      </div>

      {/* Research Section */}
      <div className="p-6 bg-cream-50 rounded-xl border border-cream-200">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <h3 className="font-medium text-warmgray-900">
              Brand Research
            </h3>
            <p className="mt-1 text-sm text-warmgray-600">
              We'll analyze your website and online presence to gather information about your brand, helping pre-fill the wizard with relevant details.
            </p>
          </div>

          <Button
            type="button"
            onClick={onResearch}
            disabled={disabled || isResearching || !canResearch}
            className="shrink-0"
          >
            {isResearching ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Researching...
              </>
            ) : hasResearchData ? (
              <>
                <Search className="w-4 h-4 mr-2" />
                Re-research
              </>
            ) : (
              <>
                <Search className="w-4 h-4 mr-2" />
                Research Brand
              </>
            )}
          </Button>
        </div>

        {/* Research error */}
        {researchError && (
          <div className="mt-4 p-4 bg-error-50 border border-error-200 rounded-lg flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-error-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-error-800">
                Research failed
              </p>
              <p className="mt-1 text-sm text-error-700">
                {researchError}
              </p>
            </div>
          </div>
        )}

        {/* Research success indicator */}
        {hasResearchData && !researchError && (
          <div className="mt-4 p-4 bg-success-50 border border-success-200 rounded-lg">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-success-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm font-medium text-success-800">
                  Research complete
                </p>
                <p className="mt-1 text-sm text-success-700">
                  We found information about your brand that will help pre-fill the following steps.
                  {researchCachedAt && (
                    <span className="text-success-600">
                      {' '}(Cached {new Date(researchCachedAt).toLocaleDateString()})
                    </span>
                  )}
                </p>

                {/* Citations */}
                {researchCitations.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-success-700 mb-2">
                      Sources:
                    </p>
                    <ul className="space-y-1">
                      {researchCitations.slice(0, 5).map((citation, index) => (
                        <li key={index} className="text-xs text-success-600">
                          <a
                            href={citation}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 hover:underline"
                          >
                            <ExternalLink className="w-3 h-3" />
                            <span className="truncate max-w-[300px]">
                              {citation.replace(/^https?:\/\//, '').split('/')[0]}
                            </span>
                          </a>
                        </li>
                      ))}
                      {researchCitations.length > 5 && (
                        <li className="text-xs text-success-600">
                          +{researchCitations.length - 5} more sources
                        </li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Help text */}
      <div className="text-sm text-warmgray-500 bg-warmgray-50 rounded-lg p-4">
        <p className="font-medium text-warmgray-700 mb-2">What happens next?</p>
        <ul className="space-y-1 list-disc list-inside">
          <li>We'll use AI to research your brand online</li>
          <li>The research helps pre-fill brand details in the next steps</li>
          <li>You can review and edit all information before generating</li>
          <li>Your final brand configuration will guide all AI-generated content</li>
        </ul>
      </div>
    </div>
  )
}
