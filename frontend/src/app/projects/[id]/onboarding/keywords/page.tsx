'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { Button } from '@/components/ui';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'export', label: 'Export' },
] as const;

function BackArrowIcon({ className }: { className?: string }) {
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

function StepIndicator({ currentStep }: { currentStep: string }) {
  const currentIndex = ONBOARDING_STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {ONBOARDING_STEPS.length}: {ONBOARDING_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {ONBOARDING_STEPS.map((step, index) => (
          <div key={step.key} className="flex items-center">
            {/* Step circle */}
            <div
              className={`w-3 h-3 rounded-full ${
                index < currentIndex
                  ? 'bg-palm-500'
                  : index === currentIndex
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            />
            {/* Connector line */}
            {index < ONBOARDING_STEPS.length - 1 && (
              <div
                className={`w-12 h-0.5 ${
                  index < currentIndex ? 'bg-palm-500' : 'bg-cream-300'
                }`}
              />
            )}
          </div>
        ))}
      </div>
      <div className="flex mt-1">
        {ONBOARDING_STEPS.map((step, index) => (
          <div
            key={step.key}
            className={`text-xs ${
              index === 0 ? 'text-left' : index === ONBOARDING_STEPS.length - 1 ? 'text-right' : 'text-center'
            } ${
              index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
            }`}
            style={{ width: index === ONBOARDING_STEPS.length - 1 ? 'auto' : '60px' }}
          >
            {step.label}
          </div>
        ))}
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Breadcrumb skeleton */}
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />

      {/* Step indicator skeleton */}
      <div className="mb-8">
        <div className="h-4 bg-cream-300 rounded w-32 mb-3" />
        <div className="flex items-center gap-1">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center">
              <div className="w-3 h-3 rounded-full bg-cream-300" />
              {i < 4 && <div className="w-12 h-0.5 bg-cream-300" />}
            </div>
          ))}
        </div>
      </div>

      {/* Content skeleton */}
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-48 mb-4" />
        <div className="h-4 bg-cream-300 rounded w-full" />
      </div>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <svg
          className="w-8 h-8 text-coral-500"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">
        Project Not Found
      </h1>
      <p className="text-warm-gray-600 mb-6">
        The project you&apos;re looking for doesn&apos;t exist or has been deleted.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

function ComingSoonIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export default function KeywordsPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading, error: projectError } = useProject(projectId);

  // Loading state
  if (isLoading) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // 404 state
  if (projectError || !project) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <BackArrowIcon className="w-4 h-4 mr-1" />
          All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  return (
    <div>
      {/* Breadcrumb navigation */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">›</span>
        <span className="text-warm-gray-900">Onboarding</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="keywords" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Coming Soon content */}
      <div className="bg-white rounded-sm border border-cream-500 p-8 shadow-sm">
        <div className="text-center max-w-md mx-auto">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-palm-50 mb-4">
            <ComingSoonIcon className="w-8 h-8 text-palm-500" />
          </div>
          <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
            Keywords Coming Soon
          </h2>
          <p className="text-warm-gray-600 mb-6">
            The keyword analysis feature is currently under development.
            This step will help you identify and optimize keywords for your crawled pages.
          </p>
          <div className="flex justify-center gap-3">
            <Link href={`/projects/${projectId}/onboarding/crawl`}>
              <Button variant="secondary">Back to Crawl</Button>
            </Link>
            <Link href={`/projects/${projectId}`}>
              <Button>Go to Project</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
