'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useContentGeneration } from '@/hooks/useContentGeneration';
import { Button, Toast } from '@/components/ui';
import type { PageGenerationStatusItem } from '@/lib/api';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'export', label: 'Export' },
] as const;

// Pipeline step definitions for status indicator
const PIPELINE_STEPS = [
  { key: 'brief', label: 'Brief' },
  { key: 'write', label: 'Write' },
  { key: 'check', label: 'Check' },
  { key: 'done', label: 'Done' },
] as const;

/** Map backend status to which pipeline step is active (0-indexed) */
function getActiveStep(status: string): number {
  switch (status) {
    case 'pending':
      return -1;
    case 'generating_brief':
      return 0;
    case 'writing':
      return 1;
    case 'checking':
      return 2;
    case 'complete':
      return 3;
    case 'failed':
      return -2; // special sentinel for failed
    default:
      return -1;
  }
}

/** Human-readable label for the current status */
function getStatusLabel(status: string): string {
  switch (status) {
    case 'pending':
      return 'Queued';
    case 'generating_brief':
      return 'Generating brief...';
    case 'writing':
      return 'Writing content...';
    case 'checking':
      return 'Running quality checks...';
    case 'complete':
      return 'Complete';
    case 'failed':
      return 'Failed';
    default:
      return status;
  }
}

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

function CheckIcon({ className }: { className?: string }) {
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

function SpinnerIcon({ className }: { className?: string }) {
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

function XCircleIcon({ className }: { className?: string }) {
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
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
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
            <div
              className={`w-3 h-3 rounded-full ${
                index < currentIndex
                  ? 'bg-palm-500'
                  : index === currentIndex
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            />
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
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
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
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-48 mb-4" />
        <div className="h-4 bg-cream-300 rounded w-full mb-6" />
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-cream-300 rounded w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

function NotFoundState() {
  return (
    <div className="text-center py-12">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-coral-50 mb-4">
        <XCircleIcon className="w-8 h-8 text-coral-500" />
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

/** Pipeline step indicator showing Brief → Write → Check → Done */
function PipelineIndicator({ status }: { status: string }) {
  const activeStep = getActiveStep(status);
  const isFailed = status === 'failed';

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, index) => {
        const isComplete = activeStep > index || (activeStep === 3 && index === 3);
        const isCurrent = activeStep === index;

        let dotClass = 'bg-cream-300'; // default: not reached
        let labelClass = 'text-warm-gray-400';

        if (isFailed) {
          // Show completed steps as green, rest as gray
          if (isComplete) {
            dotClass = 'bg-palm-500';
            labelClass = 'text-palm-700';
          }
        } else if (isComplete) {
          dotClass = 'bg-palm-500';
          labelClass = 'text-palm-700';
        } else if (isCurrent) {
          dotClass = 'bg-lagoon-500 animate-pulse';
          labelClass = 'text-lagoon-700 font-medium';
        }

        return (
          <div key={step.key} className="flex items-center">
            <div className="flex flex-col items-center">
              <div className={`w-2.5 h-2.5 rounded-full ${dotClass}`} />
              <span className={`text-[10px] mt-0.5 ${labelClass}`}>{step.label}</span>
            </div>
            {index < PIPELINE_STEPS.length - 1 && (
              <div
                className={`w-8 h-0.5 mb-3 mx-0.5 ${
                  isComplete ? 'bg-palm-400' : 'bg-cream-300'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Single page row in the generation table */
function PageRow({
  page,
  projectId,
  isGenerating,
}: {
  page: PageGenerationStatusItem;
  projectId: string;
  isGenerating: boolean;
}) {
  // Extract path from URL for compact display
  const displayUrl = (() => {
    try {
      const url = new URL(page.url);
      return url.pathname + url.search;
    } catch {
      return page.url;
    }
  })();

  const isFailed = page.status === 'failed';
  const isComplete = page.status === 'complete';

  return (
    <div className={`px-4 py-3 ${isFailed ? 'bg-coral-50/50' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        {/* Left side: URL, keyword, status */}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-warm-gray-900 truncate" title={page.url}>
            {displayUrl}
          </p>
          <p className="text-xs text-warm-gray-500 mt-0.5">
            Keyword: <span className="font-medium text-warm-gray-700">{page.keyword}</span>
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className={`text-xs ${
              isFailed ? 'text-coral-600' :
              isComplete ? 'text-palm-600' :
              page.status === 'pending' && !isGenerating ? 'text-warm-gray-500' :
              'text-lagoon-600'
            }`}>
              {getStatusLabel(page.status)}
            </span>
            {isFailed && page.error && (
              <span className="text-xs text-coral-500 truncate max-w-xs" title={page.error}>
                {page.error}
              </span>
            )}
          </div>
        </div>

        {/* Right side: pipeline indicator + actions */}
        <div className="flex items-center gap-3 shrink-0">
          <PipelineIndicator status={page.status} />
          {isComplete && (
            <Link href={`/projects/${projectId}/onboarding/content/${page.page_id}`}>
              <Button variant="secondary" className="text-xs px-2.5 py-1">
                View
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ContentGenerationPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const contentGen = useContentGeneration(projectId);

  const isLoading = isProjectLoading || contentGen.isLoading;

  // Derive states
  const isIdle = contentGen.overallStatus === 'idle';
  const isGenerating = contentGen.isGenerating;
  const isComplete = contentGen.isComplete;
  const isFailed = contentGen.isFailed;
  const hasPages = contentGen.pagesTotal > 0;

  // Handle trigger generation
  const handleGenerate = async () => {
    try {
      await contentGen.startGenerationAsync();
      setToastMessage('Content generation started');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start content generation';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    }
  };

  // Handle retry (re-triggers the full pipeline, which skips already-complete pages)
  const handleRetry = async () => {
    try {
      await contentGen.startGenerationAsync();
      setToastMessage('Retrying content generation for failed pages');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to retry content generation';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
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

  // Summary counts
  const completedPages = contentGen.pages.filter((p) => p.status === 'complete');
  const failedPages = contentGen.pages.filter((p) => p.status === 'failed');

  return (
    <div>
      {/* Breadcrumb navigation */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Onboarding</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="content" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-warm-gray-900">
            {isGenerating
              ? `Generating content for ${contentGen.pagesTotal} pages...`
              : isComplete
              ? 'Content Generation Complete'
              : isFailed
              ? 'Content Generation Complete'
              : `${contentGen.pagesTotal} Pages with Approved Keywords`}
          </h2>

          {/* Generate / Retry buttons */}
          {isIdle && hasPages && (
            <Button
              onClick={handleGenerate}
              disabled={contentGen.isStarting}
            >
              {contentGen.isStarting ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Starting...
                </>
              ) : (
                'Generate Content'
              )}
            </Button>
          )}
          {isFailed && failedPages.length > 0 && (
            <Button
              onClick={handleRetry}
              disabled={contentGen.isStarting}
            >
              {contentGen.isStarting ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Retrying...
                </>
              ) : (
                `Retry ${failedPages.length} Failed`
              )}
            </Button>
          )}
        </div>

        {/* Progress bar during generation */}
        {isGenerating && (
          <div className="mb-4">
            <div className="flex items-center justify-between text-sm text-warm-gray-600 mb-1.5">
              <div className="flex items-center gap-2">
                <SpinnerIcon className="w-4 h-4 text-lagoon-500 animate-spin" />
                <span>
                  {contentGen.pagesCompleted} of {contentGen.pagesTotal} complete
                </span>
              </div>
              <span className="font-medium text-lagoon-600">{contentGen.progress}%</span>
            </div>
            <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-palm-500 rounded-full transition-all duration-500"
                style={{ width: `${contentGen.progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Completion summary */}
        {(isComplete || isFailed) && !isGenerating && (
          <div className="mb-4 flex items-center gap-4 text-sm">
            {completedPages.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-palm-700">
                <CheckIcon className="w-4 h-4" />
                {completedPages.length} pages complete
              </span>
            )}
            {failedPages.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-coral-600">
                <XCircleIcon className="w-4 h-4" />
                {failedPages.length} pages failed
              </span>
            )}
          </div>
        )}

        {/* Idle state - no pages */}
        {isIdle && !hasPages && (
          <div className="text-center py-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cream-100 mb-4">
              <svg
                className="w-8 h-8 text-warm-gray-400"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <line x1="9" y1="15" x2="15" y2="15" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-warm-gray-900 mb-1">No Approved Keywords</h3>
            <p className="text-warm-gray-600 text-sm">
              Approve keywords in the previous step before generating content.
            </p>
          </div>
        )}

        {/* Pages table - shown when there are pages */}
        {hasPages && (
          <div className="border border-cream-500 rounded-sm overflow-hidden">
            <div className="max-h-[28rem] overflow-y-auto divide-y divide-cream-300">
              {contentGen.pages.map((page) => (
                <PageRow
                  key={page.page_id}
                  page={page}
                  projectId={projectId}
                  isGenerating={isGenerating}
                />
              ))}
            </div>
          </div>
        )}

        {/* Start error */}
        {contentGen.startError && (
          <div className="mt-4 p-3 bg-coral-50 border border-coral-200 rounded-sm">
            <p className="text-sm text-coral-700">{contentGen.startError.message}</p>
          </div>
        )}

        <hr className="border-cream-500 my-6" />

        {/* Navigation */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}/onboarding/keywords`}>
            <Button variant="secondary">Back</Button>
          </Link>
          {isComplete && (
            <Button onClick={() => router.push(`/projects/${projectId}/onboarding/export`)}>
              Continue to Export
            </Button>
          )}
          {isGenerating && (
            <Button disabled>
              Generating...
            </Button>
          )}
        </div>
      </div>

      {/* Toast */}
      {showToast && (
        <Toast
          message={toastMessage}
          variant={toastVariant}
          onClose={() => setShowToast(false)}
        />
      )}
    </div>
  );
}
