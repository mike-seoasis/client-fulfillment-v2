'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject, useDeleteProject } from '@/hooks/use-projects';
import { useStartBrandConfigGeneration, useBrandConfigGeneration } from '@/hooks/useBrandConfigGeneration';
import { useCrawlStatus, getOnboardingStep } from '@/hooks/use-crawl-status';
import { Button, Toast } from '@/components/ui';

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      {/* Back link skeleton */}
      <div className="h-4 bg-cream-300 rounded w-24 mb-6" />

      {/* Header skeleton */}
      <div className="mb-8">
        <div className="h-8 bg-cream-300 rounded w-48 mb-2" />
        <div className="h-4 bg-cream-300 rounded w-64" />
      </div>

      {/* Sections skeleton */}
      <div className="space-y-6">
        <div className="bg-white rounded-sm border border-cream-500 p-6">
          <div className="h-6 bg-cream-300 rounded w-40 mb-4" />
          <div className="h-4 bg-cream-300 rounded w-full mb-2" />
          <div className="h-10 bg-cream-300 rounded w-32" />
        </div>
        <div className="bg-white rounded-sm border border-cream-500 p-6">
          <div className="h-6 bg-cream-300 rounded w-32 mb-4" />
          <div className="h-4 bg-cream-300 rounded w-3/4" />
        </div>
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

function ClipboardIcon({ className }: { className?: string }) {
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
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
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
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
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
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
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
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function CheckCircleIcon({ className }: { className?: string }) {
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
      <polyline points="9 12 12 15 16 10" />
    </svg>
  );
}

function CircleIcon({ className }: { className?: string }) {
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
    </svg>
  );
}

// Onboarding steps definition
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'export', label: 'Export' },
] as const;

type OnboardingStepKey = typeof ONBOARDING_STEPS[number]['key'];

interface OnboardingStepIndicatorProps {
  currentStep: OnboardingStepKey;
  hasStarted: boolean;
}

function OnboardingStepIndicator({ currentStep, hasStarted }: OnboardingStepIndicatorProps) {
  if (!hasStarted) {
    return null;
  }

  const currentIndex = ONBOARDING_STEPS.findIndex(s => s.key === currentStep);

  return (
    <div className="flex items-center gap-1.5">
      {ONBOARDING_STEPS.map((step, index) => {
        const isComplete = index < currentIndex;
        const isCurrent = index === currentIndex;

        return (
          <div
            key={step.key}
            className="flex items-center gap-1"
            title={step.label}
          >
            {isComplete ? (
              <CheckCircleIcon className="w-4 h-4 text-palm-500" />
            ) : isCurrent ? (
              <div className="w-4 h-4 rounded-full border-2 border-palm-500 bg-palm-50" />
            ) : (
              <CircleIcon className="w-4 h-4 text-cream-400" />
            )}
            {index < ONBOARDING_STEPS.length - 1 && (
              <div
                className={`w-3 h-0.5 ${
                  isComplete ? 'bg-palm-500' : 'bg-cream-300'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function BrandConfigStatusBadge({
  status,
  progress
}: {
  status: 'pending' | 'generating' | 'complete' | 'failed';
  progress?: number;
}) {
  switch (status) {
    case 'complete':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-1 rounded-sm border border-palm-200">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          Brand Ready
        </span>
      );
    case 'generating':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-lagoon-50 text-lagoon-700 px-2 py-1 rounded-sm border border-lagoon-200">
          <SpinnerIcon className="w-3 h-3" />
          Generating{progress !== undefined ? ` ${progress}%` : '...'}
        </span>
      );
    case 'failed':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-coral-50 text-coral-700 px-2 py-1 rounded-sm border border-coral-200">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          Generation Failed
        </span>
      );
    case 'pending':
    default:
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-cream-100 text-warm-gray-600 px-2 py-1 rounded-sm border border-cream-300">
          <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          No Brand Config
        </span>
      );
  }
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const { data: project, isLoading, error } = useProject(projectId);
  const deleteProject = useDeleteProject();
  const generation = useBrandConfigGeneration(projectId);
  const startGeneration = useStartBrandConfigGeneration();

  // Fetch crawl status for onboarding progress
  const { data: crawlStatus } = useCrawlStatus(projectId, {
    enabled: !!projectId && !isLoading && !error,
  });
  const onboardingProgress = getOnboardingStep(crawlStatus);

  // Two-step delete confirmation
  const [isConfirming, setIsConfirming] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const confirmTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const deleteButtonRef = useRef<HTMLButtonElement>(null);

  // Reset confirmation state after 3 seconds
  useEffect(() => {
    if (isConfirming) {
      confirmTimeoutRef.current = setTimeout(() => {
        setIsConfirming(false);
      }, 3000);
    }
    return () => {
      if (confirmTimeoutRef.current) {
        clearTimeout(confirmTimeoutRef.current);
      }
    };
  }, [isConfirming]);

  // Handle blur to reset confirmation
  const handleBlur = useCallback((e: React.FocusEvent) => {
    // Only reset if focus is moving outside the button
    if (!deleteButtonRef.current?.contains(e.relatedTarget as Node)) {
      setIsConfirming(false);
    }
  }, []);

  const handleDeleteClick = async () => {
    if (!isConfirming) {
      // First click: show confirmation state
      setIsConfirming(true);
      return;
    }

    // Second click: execute deletion
    try {
      await deleteProject.mutateAsync(projectId);
      setToastMessage('Project deleted');
      setShowToast(true);
      // Delay redirect slightly to show toast
      setTimeout(() => {
        router.push('/');
      }, 500);
    } catch {
      // Error is already handled by optimistic update rollback
      setIsConfirming(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <svg
            className="w-4 h-4 mr-1"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          All Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  // 404 state
  if (error || !project) {
    return (
      <div>
        <Link
          href="/"
          className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
        >
          <svg
            className="w-4 h-4 mr-1"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  return (
    <div>
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm"
      >
        <svg
          className="w-4 h-4 mr-1"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        All Projects
      </Link>

      {/* Project header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-semibold text-warm-gray-900">
              {project.name}
            </h1>
            <BrandConfigStatusBadge
              status={generation.isGenerating ? 'generating' : project.brand_config_status}
              progress={generation.isGenerating ? generation.progress : undefined}
            />
          </div>
          <div className="flex items-center gap-3 text-sm">
            <a
              href={project.site_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-warm-gray-500 hover:text-palm-600"
            >
              {project.site_url}
            </a>
            {project.uploaded_files_count > 0 && (
              <span className="inline-flex items-center gap-1 text-warm-gray-500">
                <FileIcon className="w-3.5 h-3.5" />
                {project.uploaded_files_count} {project.uploaded_files_count === 1 ? 'file' : 'files'}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Brand config action button */}
          {project.has_brand_config ? (
            <Link href={`/projects/${projectId}/brand-config`}>
              <Button variant="secondary">Brand Details</Button>
            </Link>
          ) : generation.isGenerating ? (
            <Button variant="secondary" disabled>
              <SpinnerIcon className="w-4 h-4 mr-2" />
              Generating...
            </Button>
          ) : (
            <Button
              variant="secondary"
              onClick={async () => {
                try {
                  await startGeneration.mutateAsync(projectId);
                } catch {
                  setToastMessage('Failed to start brand generation');
                  setShowToast(true);
                }
              }}
              disabled={startGeneration.isPending}
            >
              {startGeneration.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-2" />
                  Starting...
                </>
              ) : (
                'Generate Brand'
              )}
            </Button>
          )}
          <Button
            ref={deleteButtonRef}
            variant="danger"
            onClick={handleDeleteClick}
            onBlur={handleBlur}
            disabled={deleteProject.isPending}
          >
            {deleteProject.isPending
              ? 'Deleting...'
              : isConfirming
              ? 'Confirm Delete'
              : 'Delete Project'}
          </Button>
        </div>
      </div>

      {/* Toast notification */}
      {showToast && (
        <Toast
          message={toastMessage || 'Project deleted'}
          variant={toastMessage?.includes('Failed') ? 'error' : 'success'}
          onClose={() => {
            setShowToast(false);
            setToastMessage('');
          }}
        />
      )}

      {/* Divider */}
      <hr className="border-cream-500 mb-8" />

      {/* Sections */}
      <div className="space-y-6">
        {/* Onboarding section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <ClipboardIcon className="w-5 h-5 text-palm-500" />
              <h2 className="text-lg font-semibold text-warm-gray-900">
                Onboarding
              </h2>
              <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
                Existing Pages
              </span>
            </div>
            <OnboardingStepIndicator
              currentStep={onboardingProgress.currentStep}
              hasStarted={onboardingProgress.hasStarted}
            />
          </div>

          {/* Quick stats when pages exist */}
          {crawlStatus && crawlStatus.progress.total > 0 && (
            <div className="mb-4">
              {/* Quick stats row */}
              <div className="flex items-center gap-4 text-sm mb-3">
                {/* Page count */}
                <span className="text-warm-gray-600">
                  <span className="font-medium text-warm-gray-900">{crawlStatus.progress.total}</span>{' '}
                  {crawlStatus.progress.total === 1 ? 'page' : 'pages'}
                </span>

                {/* Failed count (warning style) */}
                {crawlStatus.progress.failed > 0 && (
                  <span className="text-coral-600">
                    <span className="font-medium">{crawlStatus.progress.failed}</span>{' '}
                    failed
                  </span>
                )}

                {/* Label status */}
                {(() => {
                  const pagesWithLabels = crawlStatus.pages.filter(
                    (p) => p.labels && p.labels.length > 0
                  ).length;
                  const allPagesLabeled = pagesWithLabels === crawlStatus.progress.total;

                  if (crawlStatus.status === 'complete' && allPagesLabeled) {
                    return (
                      <span className="text-palm-600">
                        Labels assigned
                      </span>
                    );
                  } else if (crawlStatus.status === 'labeling') {
                    return (
                      <span className="text-warm-gray-500">
                        Labels pending
                      </span>
                    );
                  } else if (crawlStatus.status === 'complete' && !allPagesLabeled) {
                    return (
                      <span className="text-warm-gray-500">
                        Labels pending
                      </span>
                    );
                  }
                  return null;
                })()}
              </div>

              {/* Progress bar */}
              <div className="flex items-center justify-between text-sm text-warm-gray-600 mb-1.5">
                <span>
                  {crawlStatus.status === 'complete'
                    ? 'Crawl complete'
                    : crawlStatus.status === 'labeling'
                    ? 'Labeling pages...'
                    : 'Crawling pages...'}
                </span>
                <span className="font-medium">
                  {crawlStatus.progress.completed} of {crawlStatus.progress.total} pages complete
                </span>
              </div>
              <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-palm-500 transition-all duration-500 ease-out rounded-full"
                  style={{
                    width: `${Math.round(
                      (crawlStatus.progress.completed / crawlStatus.progress.total) * 100
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}

          {/* Description when no pages */}
          {(!crawlStatus || crawlStatus.progress.total === 0) && (
            <p className="text-warm-gray-600 text-sm mb-4">
              Optimize existing collection pages with new copy
            </p>
          )}

          {/* Action button */}
          <Link
            href={
              onboardingProgress.currentStep === 'upload'
                ? `/projects/${projectId}/onboarding/upload`
                : onboardingProgress.currentStep === 'crawl'
                ? `/projects/${projectId}/onboarding/crawl`
                : `/projects/${projectId}/onboarding/keywords`
            }
          >
            <Button>
              {onboardingProgress.hasStarted ? 'Continue Onboarding' : 'Start Onboarding'}
            </Button>
          </Link>
        </div>

        {/* New Content section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <PlusIcon className="w-5 h-5 text-palm-500" />
            <h2 className="text-lg font-semibold text-warm-gray-900">
              New Content
            </h2>
            <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
              Keyword Clusters
            </span>
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            Build new collection pages from keyword clusters
          </p>
          <Button disabled>+ New Cluster</Button>
        </div>
      </div>
    </div>
  );
}
