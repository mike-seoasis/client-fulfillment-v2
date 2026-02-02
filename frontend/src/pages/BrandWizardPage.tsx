/**
 * BrandWizardPage - 7-step brand configuration wizard
 *
 * Features:
 * - State management with auto-save
 * - Step navigation with completion tracking
 * - Research integration with Perplexity
 * - V3 config generation
 * - Error handling and loading states
 */

import { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useApiQuery, useApiMutation } from '@/lib/hooks/useApiQuery'
import { addBreadcrumb } from '@/lib/errorReporting'
import { useToast } from '@/components/ui/toast-provider'
import {
  WizardContainer,
  WizardProgressSkeleton,
  Step1BrandSetup,
  Step2Foundation,
  Step3Audience,
  Step4Voice,
  Step5WritingRules,
  Step6ProofExamples,
  Step7Review,
  type WizardFormData,
  type WizardState,
  type ResearchData,
} from '@/components/brand-wizard'

/** API response types */
interface WizardStateResponse extends WizardState {}

interface WizardUpdateResponse {
  success: boolean
  project_id: string
  current_step: number
  steps_completed: number[]
  updated_at: string
}

interface ResearchResponse {
  success: boolean
  project_id: string
  domain: string
  raw_research?: string
  citations: string[]
  from_cache: boolean
  cached_at?: string
  error?: string
}

interface GenerateResponse {
  success: boolean
  project_id: string
  brand_config_id?: string
  v3_config?: Record<string, unknown>
  error?: string
}

/** Debounce timer in ms for auto-save */
const AUTO_SAVE_DELAY = 1500

/**
 * BrandWizardPage - main wizard page component
 */
export function BrandWizardPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { addToast } = useToast()

  // Local state
  const [currentStep, setCurrentStep] = useState(1)
  const [formData, setFormData] = useState<WizardFormData>({})
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [researchData, setResearchData] = useState<ResearchData | null>(null)
  const [researchCitations, setResearchCitations] = useState<string[]>([])
  const [researchCachedAt, setResearchCachedAt] = useState<string | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [pendingSave, setPendingSave] = useState(false)

  // Refs for auto-save debouncing
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const latestFormDataRef = useRef<WizardFormData>(formData)
  latestFormDataRef.current = formData

  // Fetch initial wizard state
  const {
    data: wizardState,
    isLoading: isLoadingState,
    error: stateError,
  } = useApiQuery<WizardStateResponse>(
    ['wizard-state', projectId],
    `/api/v1/projects/${projectId}/brand-wizard`,
    {
      enabled: !!projectId,
      staleTime: 0, // Always fetch fresh on mount
    }
  )

  // Update wizard state mutation
  const updateMutation = useApiMutation<WizardUpdateResponse, { current_step: number; form_data: WizardFormData }>(
    `/api/v1/projects/${projectId}/brand-wizard`,
    {
      method: 'PUT',
      onSuccess: (data) => {
        setLastSavedAt(data.updated_at)
        setCompletedSteps(data.steps_completed)
        setPendingSave(false)
        addBreadcrumb('Wizard state saved', 'wizard', { step: data.current_step })
      },
      onError: (error) => {
        setPendingSave(false)
        addToast({
          type: 'error',
          title: 'Failed to save',
          description: error instanceof Error ? error.message : 'Could not save wizard state',
        })
      },
    }
  )

  // Research mutation
  const researchMutation = useApiMutation<ResearchResponse, { domain: string; brand_name?: string; force_refresh?: boolean }>(
    `/api/v1/projects/${projectId}/brand-wizard/research`,
    {
      method: 'POST',
      onSuccess: (data) => {
        if (data.success && data.raw_research) {
          setResearchData({ raw_research: data.raw_research })
          setResearchCitations(data.citations)
          setResearchCachedAt(data.cached_at || null)
          addBreadcrumb('Brand research completed', 'wizard', { from_cache: data.from_cache })
          addToast({
            type: 'success',
            title: 'Research complete',
            description: data.from_cache
              ? 'Loaded cached research data'
              : 'Successfully researched your brand',
          })
        } else if (data.error) {
          addToast({
            type: 'error',
            title: 'Research failed',
            description: data.error,
          })
        }
      },
      onError: (error) => {
        addToast({
          type: 'error',
          title: 'Research failed',
          description: error instanceof Error ? error.message : 'Could not complete brand research',
        })
      },
    }
  )

  // Generate V3 config mutation
  const generateMutation = useApiMutation<GenerateResponse, { brand_name: string; domain?: string; wizard_data: WizardFormData }>(
    `/api/v1/projects/${projectId}/brand-wizard/generate`,
    {
      method: 'POST',
      onSuccess: (data) => {
        if (data.success) {
          addBreadcrumb('V3 config generated', 'wizard', { brand_config_id: data.brand_config_id })
          addToast({
            type: 'success',
            title: 'Brand configuration generated',
            description: 'Your brand guidelines are ready!',
          })
          // Invalidate project query to refresh brand config
          queryClient.invalidateQueries({ queryKey: ['project', projectId] })
          // Navigate back to project detail
          navigate(`/projects/${projectId}`)
        } else if (data.error) {
          addToast({
            type: 'error',
            title: 'Generation failed',
            description: data.error,
          })
        }
      },
      onError: (error) => {
        addToast({
          type: 'error',
          title: 'Generation failed',
          description: error instanceof Error ? error.message : 'Could not generate brand configuration',
        })
      },
    }
  )

  // Initialize state from API response
  useEffect(() => {
    if (wizardState) {
      setCurrentStep(wizardState.current_step)
      setCompletedSteps(wizardState.steps_completed)
      setFormData({
        brand_name: wizardState.brand_name,
        domain: wizardState.domain,
        ...wizardState.form_data,
      })
      setResearchData(wizardState.research_data || null)
      setResearchCitations(wizardState.research_citations || [])
      setResearchCachedAt(wizardState.research_cached_at || null)
      setLastSavedAt(wizardState.updated_at || null)
    }
  }, [wizardState])

  // Auto-save debounced
  const triggerAutoSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    setPendingSave(true)
    saveTimerRef.current = setTimeout(() => {
      updateMutation.mutate({
        current_step: currentStep,
        form_data: latestFormDataRef.current,
      })
    }, AUTO_SAVE_DELAY)
  }, [currentStep, updateMutation])

  // Handle form data changes
  const handleFormChange = useCallback((updates: Partial<WizardFormData>) => {
    setFormData((prev) => ({
      ...prev,
      ...updates,
    }))
    triggerAutoSave()
  }, [triggerAutoSave])

  // Handle step navigation
  const handleStepChange = useCallback((step: number) => {
    // Save current state before changing
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    updateMutation.mutate({
      current_step: step,
      form_data: latestFormDataRef.current,
    })
    setCurrentStep(step)
    addBreadcrumb('Wizard step changed', 'wizard', { from: currentStep, to: step })
  }, [currentStep, updateMutation])

  // Handle research trigger
  const handleResearch = useCallback(() => {
    if (formData.domain) {
      researchMutation.mutate({
        domain: formData.domain,
        brand_name: formData.brand_name,
      })
    }
  }, [formData.domain, formData.brand_name, researchMutation])

  // Handle generate trigger
  const handleGenerate = useCallback(() => {
    if (formData.brand_name) {
      generateMutation.mutate({
        brand_name: formData.brand_name,
        domain: formData.domain,
        wizard_data: formData,
      })
    }
  }, [formData, generateMutation])

  // Handle close/cancel
  const handleClose = useCallback(() => {
    // Save before leaving
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    updateMutation.mutate({
      current_step: currentStep,
      form_data: latestFormDataRef.current,
    })
    navigate(`/projects/${projectId}`)
  }, [currentStep, navigate, projectId, updateMutation])

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [])

  // Determine if navigation is allowed (Step 1 must have brand_name at minimum)
  const canNavigate = useMemo(() => {
    return !!formData.brand_name
  }, [formData.brand_name])

  // Calculate if previous/next are available
  const hasPrevious = currentStep > 1
  const hasNext = currentStep < 7

  // Render loading state
  if (isLoadingState) {
    return (
      <div className="min-h-screen bg-cream-50 flex items-center justify-center">
        <div className="text-center">
          <WizardProgressSkeleton className="mb-8 max-w-3xl mx-auto px-6" />
          <p className="text-warmgray-600">Loading wizard...</p>
        </div>
      </div>
    )
  }

  // Render error state
  if (stateError) {
    return (
      <div className="min-h-screen bg-cream-50 flex items-center justify-center">
        <div className="text-center p-8 bg-white rounded-xl border border-error-200 max-w-md">
          <p className="text-error-800 font-medium mb-2">Failed to load wizard</p>
          <p className="text-warmgray-600 text-sm mb-4">
            {stateError instanceof Error ? stateError.message : 'Unknown error'}
          </p>
          <button
            onClick={() => navigate(`/projects/${projectId}`)}
            className="text-primary-600 hover:text-primary-700 text-sm font-medium"
          >
            Return to project
          </button>
        </div>
      </div>
    )
  }

  // Render current step content
  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <Step1BrandSetup
            formData={formData}
            onChange={handleFormChange}
            researchData={researchData}
            researchCitations={researchCitations}
            researchCachedAt={researchCachedAt}
            isResearching={researchMutation.isPending}
            onResearch={handleResearch}
            researchError={researchMutation.error instanceof Error ? researchMutation.error.message : null}
          />
        )
      case 2:
        return (
          <Step2Foundation
            formData={formData}
            onChange={handleFormChange}
          />
        )
      case 3:
        return (
          <Step3Audience
            formData={formData}
            onChange={handleFormChange}
          />
        )
      case 4:
        return (
          <Step4Voice
            formData={formData}
            onChange={handleFormChange}
          />
        )
      case 5:
        return (
          <Step5WritingRules
            formData={formData}
            onChange={handleFormChange}
          />
        )
      case 6:
        return (
          <Step6ProofExamples
            formData={formData}
            onChange={handleFormChange}
          />
        )
      case 7:
        return (
          <Step7Review
            formData={formData}
            onNavigateToStep={handleStepChange}
            isGenerating={generateMutation.isPending}
            onGenerate={handleGenerate}
            generateError={generateMutation.error instanceof Error ? generateMutation.error.message : null}
          />
        )
      default:
        return null
    }
  }

  return (
    <WizardContainer
      title={formData.brand_name ? `${formData.brand_name} - Brand Wizard` : 'Brand Configuration Wizard'}
      progress={{
        currentStep,
        completedSteps,
        canNavigate,
        onStepClick: handleStepChange,
      }}
      navigation={{
        currentStep,
        totalSteps: 7,
        onPrevious: hasPrevious ? () => handleStepChange(currentStep - 1) : undefined,
        onNext: hasNext ? () => handleStepChange(currentStep + 1) : undefined,
        isPreviousDisabled: !hasPrevious,
        isNextDisabled: !hasNext || (currentStep === 1 && !formData.brand_name),
        nextLabel: currentStep === 6 ? 'Review' : currentStep === 7 ? 'Generate' : 'Next',
      }}
      isSaving={pendingSave || updateMutation.isPending}
      lastSavedAt={lastSavedAt}
      onClose={handleClose}
    >
      {renderStepContent()}
    </WizardContainer>
  )
}
