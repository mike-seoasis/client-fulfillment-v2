'use client';

import { useEffect, useState } from 'react';
import { useBrandConfigGeneration } from '@/hooks/useBrandConfigGeneration';
import { Button } from '@/components/ui';

/**
 * All 13 generation steps:
 * - 3 research phase steps
 * - 9 brand section generation steps
 * - 1 ai_prompt_snippet (summary)
 */
export const GENERATION_STEPS = [
  // Research phase
  'perplexity_research',
  'crawling',
  'processing_docs',
  // Synthesis phase (8 sections)
  'brand_foundation',
  'target_audience',
  'voice_dimensions',
  'voice_characteristics',
  'writing_style',
  'vocabulary',
  'trust_elements',
  'competitor_context',
  // Summary
  'ai_prompt_snippet',
] as const;

export type GenerationStep = (typeof GENERATION_STEPS)[number];

/** Human-readable display names for each step */
export const STEP_DISPLAY_NAMES: Record<GenerationStep, string> = {
  // Research phase
  perplexity_research: 'Researching brand online',
  crawling: 'Crawling website',
  processing_docs: 'Processing uploaded documents',
  // Synthesis phase
  brand_foundation: 'Extracting brand foundation',
  target_audience: 'Building target audience personas',
  voice_dimensions: 'Analyzing voice dimensions (4 scales)',
  voice_characteristics: 'Defining voice characteristics',
  writing_style: 'Setting writing style rules',
  vocabulary: 'Building vocabulary guide',
  trust_elements: 'Compiling trust elements',
  competitor_context: 'Analyzing competitor context',
  ai_prompt_snippet: 'Generating AI prompt snippet',
};

interface GenerationProgressProps {
  /** Project ID to track generation for */
  projectId: string;
  /** Project name to display on completion */
  projectName?: string;
  /** Called when generation completes successfully */
  onComplete?: () => void;
  /** Called when user wants to go back (on failure) */
  onBack?: () => void;
  /** Called when user clicks "Go to Project" */
  onGoToProject?: () => void;
  /** Called when user wants to retry generation (on failure) */
  onRetry?: () => Promise<void>;
}

/**
 * GenerationProgress component for Step 2 of project creation wizard.
 *
 * Features:
 * - Animated progress indicator with percentage
 * - List of all 13 generation steps with status icons
 * - Current step highlighting
 * - Polls status endpoint every 2 seconds
 * - Stops polling when complete or failed
 * - Shows error message on failure
 */
export function GenerationProgress({
  projectId,
  projectName,
  onComplete,
  onBack,
  onGoToProject,
  onRetry,
}: GenerationProgressProps) {
  const generation = useBrandConfigGeneration(projectId);
  const [isRetrying, setIsRetrying] = useState(false);

  // Call onComplete when generation finishes successfully
  useEffect(() => {
    if (generation.isComplete && onComplete) {
      onComplete();
    }
  }, [generation.isComplete, onComplete]);

  // Determine which step index we're on based on stepsCompleted
  // The backend tracks synthesis steps (indices 3-12 in our 13-step list)
  // Research phase (steps 0-2) happens before synthesis starts
  const getStepStatus = (stepIndex: number) => {
    const stepsCompleted = generation.stepsCompleted;
    const isGenerating = generation.isGenerating;
    const currentStep = generation.currentStep;

    // Research phase (steps 0-2): These complete before synthesis starts
    if (stepIndex < 3) {
      // If synthesis has started (stepsCompleted >= 0 and isGenerating with a current step)
      // then research phase is complete
      if (currentStep && GENERATION_STEPS.indexOf(currentStep as GenerationStep) >= 3) {
        return 'complete';
      }
      // If we're generating but no synthesis step yet, research is in progress
      if (isGenerating && (!currentStep || currentStep === 'perplexity_research')) {
        if (stepIndex === 0) return 'current';
        return 'pending';
      }
      if (isGenerating && currentStep === 'crawling') {
        if (stepIndex === 0) return 'complete';
        if (stepIndex === 1) return 'current';
        return 'pending';
      }
      if (isGenerating && currentStep === 'processing_docs') {
        if (stepIndex <= 1) return 'complete';
        if (stepIndex === 2) return 'current';
        return 'pending';
      }
      // If stepsCompleted > 0, research is done
      if (stepsCompleted > 0) {
        return 'complete';
      }
      // Default: first research step is current if generating
      if (isGenerating && stepIndex === 0) {
        return 'current';
      }
      return 'pending';
    }

    // Synthesis phase (steps 3-12): Map stepsCompleted to step status
    // Backend stepsCompleted counts synthesis steps (0-9)
    // Our synthesis steps are at indices 3-12
    const synthesisIndex = stepIndex - 3; // 0-9

    if (synthesisIndex < stepsCompleted) {
      return 'complete';
    }

    if (synthesisIndex === stepsCompleted && isGenerating) {
      return 'current';
    }

    return 'pending';
  };

  // Calculate overall progress (all 13 steps)
  const calculateProgress = () => {
    if (generation.isComplete) return 100;
    if (!generation.isGenerating) return 0;

    // Research phase: steps 0-2 (we estimate as 1 step combined for simplicity)
    // Synthesis phase: steps 3-12 (10 steps)
    // Total: 13 steps
    const synthesisProgress = generation.stepsCompleted;
    const currentStep = generation.currentStep;

    // If still in research phase
    if (currentStep === 'perplexity_research') {
      return Math.round((0.5 / 13) * 100); // ~4%
    }
    if (currentStep === 'crawling') {
      return Math.round((1 / 13) * 100); // ~8%
    }
    if (currentStep === 'processing_docs') {
      return Math.round((2 / 13) * 100); // ~15%
    }

    // Synthesis phase: 3 research steps + synthesis steps completed
    const totalCompleted = 3 + synthesisProgress;
    return Math.round((totalCompleted / 13) * 100);
  };

  const progress = calculateProgress();

  // Get current step label for display
  const getCurrentStepLabel = () => {
    if (generation.isComplete) return 'Complete!';
    if (generation.isFailed) return 'Failed';

    const currentStep = generation.currentStep as GenerationStep | null;
    if (currentStep && STEP_DISPLAY_NAMES[currentStep]) {
      return STEP_DISPLAY_NAMES[currentStep] + '...';
    }

    // Default labels for research phase
    if (generation.isGenerating && generation.stepsCompleted === 0) {
      return 'Gathering research data...';
    }

    return 'Starting...';
  };

  return (
    <div className="space-y-6">
      {/* Generation header */}
      {generation.isComplete ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-palm-100 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-palm-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
            Project Created!
          </h2>
          <p className="text-warm-gray-600">
            {projectName ? (
              <>
                &ldquo;{projectName}&rdquo; is ready. Brand configuration has been
                generated successfully.
              </>
            ) : (
              'Brand configuration has been generated successfully.'
            )}
          </p>
        </div>
      ) : generation.isFailed ? (
        <div className="text-center py-4">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-coral-100 flex items-center justify-center">
            <svg
              className="w-8 h-8 text-coral-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
            Generation Failed
          </h2>
          <p className="text-coral-600">{generation.error}</p>
        </div>
      ) : (
        <div className="text-center py-4">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-palm-100 flex items-center justify-center animate-pulse">
            <svg
              className="w-8 h-8 text-palm-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
            Generating Brand Configuration...
          </h2>
        </div>
      )}

      {/* Progress bar */}
      {!generation.isComplete && !generation.isFailed && (
        <div className="space-y-2">
          <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-palm-500 transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex justify-between text-sm text-warm-gray-500">
            <span>{getCurrentStepLabel()}</span>
            <span>{progress}%</span>
          </div>
        </div>
      )}

      {/* Generation steps checklist */}
      <div className="space-y-2 max-h-80 overflow-y-auto">
        {GENERATION_STEPS.map((step, index) => {
          const status = getStepStatus(index);
          const isComplete = status === 'complete';
          const isCurrent = status === 'current';

          return (
            <div
              key={step}
              className={`flex items-center gap-3 p-2 rounded-sm ${
                isCurrent ? 'bg-palm-50' : ''
              }`}
            >
              {/* Status icon */}
              <div className="flex-shrink-0 w-5 h-5">
                {isComplete ? (
                  <svg
                    className="w-5 h-5 text-palm-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : isCurrent ? (
                  <svg
                    className="w-5 h-5 text-palm-500 animate-spin"
                    fill="none"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                ) : (
                  <div className="w-5 h-5 rounded-full border-2 border-warm-gray-300" />
                )}
              </div>

              {/* Step name */}
              <span
                className={`text-sm ${
                  isComplete
                    ? 'text-warm-gray-600'
                    : isCurrent
                    ? 'text-palm-700 font-medium'
                    : 'text-warm-gray-400'
                }`}
              >
                {STEP_DISPLAY_NAMES[step]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
        {generation.isComplete ? (
          <Button onClick={onGoToProject}>
            Go to Project
            <svg
              className="w-4 h-4 ml-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </Button>
        ) : generation.isFailed ? (
          <>
            <Button variant="ghost" onClick={onBack}>
              Back
            </Button>
            {onRetry && (
              <Button
                variant="secondary"
                onClick={async () => {
                  setIsRetrying(true);
                  try {
                    await onRetry();
                  } finally {
                    setIsRetrying(false);
                  }
                }}
                disabled={isRetrying}
              >
                {isRetrying ? 'Retrying...' : 'Retry'}
              </Button>
            )}
            <Button onClick={onGoToProject}>
              Go to Project Anyway
            </Button>
          </>
        ) : (
          <Button variant="ghost" disabled>
            Please wait...
          </Button>
        )}
      </div>
    </div>
  );
}
