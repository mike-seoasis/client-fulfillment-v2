'use client';

import Link from 'next/link';

/** Onboarding step definitions */
export const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'links', label: 'Links' },
  { key: 'export', label: 'Export' },
] as const;

export type OnboardingStepKey = typeof ONBOARDING_STEPS[number]['key'];

/** Map step key to its onboarding route segment. "links" maps to /content (no separate links page). */
function stepUrl(projectId: string, stepKey: OnboardingStepKey, batch?: string | null): string {
  const segment = stepKey === 'links' ? 'content' : stepKey;
  const batchParam = batch ? `?batch=${batch}` : '';
  return `/projects/${projectId}/onboarding/${segment}${batchParam}`;
}

export interface StepIndicatorProps {
  projectId: string;
  currentStep: OnboardingStepKey;
  /** Step keys that are fully completed. Used to determine which steps are clickable. */
  completedStepKeys?: OnboardingStepKey[];
  /** Batch number to preserve in step navigation links. */
  batch?: string | null;
}

export function BackArrowIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

export function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" className="animate-spin origin-center" />
    </svg>
  );
}

/**
 * Shared step indicator for the onboarding flow.
 * Completed and current steps are clickable links; future steps are inert.
 */
export function StepIndicator({ projectId, currentStep, completedStepKeys = [], batch }: StepIndicatorProps) {
  const currentIndex = ONBOARDING_STEPS.findIndex((s) => s.key === currentStep);
  const completedSet = new Set(completedStepKeys);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {ONBOARDING_STEPS.length}: {ONBOARDING_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {ONBOARDING_STEPS.map((step, index) => {
          const isCompleted = completedSet.has(step.key);
          const isCurrent = index === currentIndex;
          const isClickable = isCompleted || isCurrent;

          const circle = (
            <div
              className={`w-3 h-3 rounded-full transition-colors ${
                isCompleted || isCurrent ? 'bg-palm-500' : 'bg-cream-300'
              }`}
            />
          );

          const connector = index < ONBOARDING_STEPS.length - 1 && (
            <div
              className={`w-12 h-0.5 ${
                isCompleted ? 'bg-palm-500' : 'bg-cream-300'
              }`}
            />
          );

          return (
            <div key={step.key} className="flex items-center">
              {isClickable ? (
                <Link
                  href={stepUrl(projectId, step.key, batch)}
                  className="rounded-full hover:ring-2 ring-palm-200 transition-shadow"
                  title={step.label}
                >
                  {circle}
                </Link>
              ) : (
                <div className="cursor-default" title={step.label}>
                  {circle}
                </div>
              )}
              {connector}
            </div>
          );
        })}
      </div>
      <div className="flex mt-1">
        {ONBOARDING_STEPS.map((step, index) => {
          const isCompleted = completedSet.has(step.key);
          const isCurrent = index === currentIndex;
          const isClickable = isCompleted || isCurrent;

          const labelClass = `text-xs ${
            index === 0 ? 'text-left' : index === ONBOARDING_STEPS.length - 1 ? 'text-right' : 'text-center'
          } ${
            index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
          }`;

          const style = { width: index === ONBOARDING_STEPS.length - 1 ? 'auto' : '60px' };

          return isClickable ? (
            <Link
              key={step.key}
              href={stepUrl(projectId, step.key, batch)}
              className={`${labelClass} hover:text-palm-500 transition-colors`}
              style={style}
            >
              {step.label}
            </Link>
          ) : (
            <div key={step.key} className={labelClass} style={style}>
              {step.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}
