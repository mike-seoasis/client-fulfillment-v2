'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useKeywordGeneration } from '@/hooks/useKeywordGeneration';
import { usePagesWithKeywordsData } from '@/hooks/usePagesWithKeywords';
import { useApproveAllKeywords } from '@/hooks/useKeywordMutations';
import { Button, Toast } from '@/components/ui';
import { KeywordPageRow } from '@/components/onboarding/KeywordPageRow';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'links', label: 'Links' },
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
        <div className="h-4 bg-cream-300 rounded w-full mb-6" />
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 bg-cream-300 rounded w-full" />
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

function ErrorState({
  message,
  onRetry,
  isRetrying,
}: {
  message: string;
  onRetry: () => void;
  isRetrying?: boolean;
}) {
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
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      </div>
      <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
        Failed to Load Pages
      </h2>
      <p className="text-warm-gray-600 mb-6">
        {message}
      </p>
      <Button onClick={onRetry} disabled={isRetrying}>
        {isRetrying ? (
          <>
            <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
            Retrying...
          </>
        ) : (
          'Retry'
        )}
      </Button>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-12">
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
      <h2 className="text-xl font-semibold text-warm-gray-900 mb-2">
        No Pages Available
      </h2>
      <p className="text-warm-gray-600">
        No crawled pages found. Please complete the crawl step first.
      </p>
    </div>
  );
}

function GenerationProgressIndicator({
  status,
  completed,
  total,
  currentPage,
}: {
  status: 'pending' | 'generating' | 'completed' | 'failed';
  completed: number;
  total: number;
  currentPage?: string | null;
}) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  // Extract path from current page URL for display
  const displayCurrentPage = currentPage
    ? (() => {
        try {
          const url = new URL(currentPage);
          return url.pathname + url.search;
        } catch {
          return currentPage;
        }
      })()
    : null;

  return (
    <div className="mb-6">
      {/* Status indicator with spinner */}
      <div className="flex items-center gap-2 mb-3">
        {status === 'generating' ? (
          <>
            <SpinnerIcon className="w-5 h-5 text-lagoon-500 animate-spin" />
            <span className="text-warm-gray-700">
              Generating keywords...{' '}
              <span className="font-medium text-lagoon-600">
                {completed}/{total} complete
              </span>
            </span>
          </>
        ) : status === 'completed' ? (
          <>
            <CheckIcon className="w-5 h-5 text-palm-500" />
            <span className="text-warm-gray-700">
              <span className="font-medium text-palm-600">
                {completed}/{total} keywords generated
              </span>
            </span>
          </>
        ) : status === 'failed' ? (
          <>
            <svg
              className="w-5 h-5 text-coral-500"
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
            <span className="text-coral-700 font-medium">
              Generation failed
            </span>
          </>
        ) : (
          <>
            <div className="w-5 h-5 rounded-full border-2 border-warm-gray-300" />
            <span className="text-warm-gray-500">
              Ready to generate keywords
            </span>
          </>
        )}
      </div>

      {/* Progress bar - only show when generating */}
      {status === 'generating' && (
        <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-palm-500 rounded-full transition-all duration-500"
            style={{ width: `${percentage}%` }}
          />
        </div>
      )}

      {/* Current page being processed */}
      {status === 'generating' && displayCurrentPage && (
        <p className="mt-2 text-xs text-warm-gray-500 truncate">
          Processing: <span className="font-mono">{displayCurrentPage}</span>
        </p>
      )}
    </div>
  );
}

export default function KeywordsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  // Tooltip state for continue button
  const [showContinueTooltip, setShowContinueTooltip] = useState(false);
  const continueButtonRef = useRef<HTMLButtonElement>(null);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const keywordGen = useKeywordGeneration(projectId);
  const { pages, isLoading: isPagesLoading, isError: isPagesError, error: pagesError, refetch: refetchPages } = usePagesWithKeywordsData(projectId);
  const approveAllMutation = useApproveAllKeywords();
  const [isRetrying, setIsRetrying] = useState(false);

  const isLoading = isProjectLoading || keywordGen.isLoading;

  // Track if we've auto-started to avoid double-firing
  const hasAutoStarted = useRef(false);

  // Calculate counts
  const totalPages = pages.length;
  const pagesWithKeywords = pages.filter(p => p.keywords?.primary_keyword).length;
  const approvedCount = pages.filter(p => p.keywords?.is_approved).length;
  const pendingApprovalCount = pagesWithKeywords - approvedCount;

  // Determine if we should show the generating state or the list
  const showGeneratingState = keywordGen.status === 'generating';
  const showPendingState = keywordGen.status === 'pending' && pagesWithKeywords === 0;

  // Auto-start generation when page loads and no keywords exist yet
  useEffect(() => {
    if (
      !isLoading &&
      !hasAutoStarted.current &&
      keywordGen.status === 'pending' &&
      pagesWithKeywords === 0 &&
      totalPages > 0 &&
      !keywordGen.isStarting
    ) {
      hasAutoStarted.current = true;
      keywordGen.startGeneration();
    }
  }, [isLoading, keywordGen.status, pagesWithKeywords, totalPages, keywordGen.isStarting]);

  // Handle approve all
  const handleApproveAll = async () => {
    try {
      const result = await approveAllMutation.mutateAsync(projectId);
      setToastMessage(`${result.approved_count} keywords approved`);
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to approve keywords';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    }
  };

  // Handle retry for pages fetch
  const handleRetryFetch = async () => {
    setIsRetrying(true);
    try {
      await refetchPages();
    } finally {
      setIsRetrying(false);
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
      <StepIndicator currentStep="keywords" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {/* Header with title and fallback generate button */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-warm-gray-900">
            {showGeneratingState
              ? 'Generating Keywords...'
              : showPendingState
              ? 'Starting Keyword Generation...'
              : `${pagesWithKeywords} Keywords Generated`}
          </h2>

          {/* Fallback generate/regenerate button - shown when not actively generating */}
          {!showGeneratingState && pagesWithKeywords === 0 && totalPages > 0 && (
            <Button
              variant="secondary"
              onClick={() => keywordGen.startGeneration()}
              disabled={keywordGen.isStarting}
            >
              {keywordGen.isStarting ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Starting...
                </>
              ) : (
                'Generate Keywords'
              )}
            </Button>
          )}

          {/* Regenerate button - shown when keywords exist but user might want to regenerate */}
          {!showGeneratingState && pagesWithKeywords > 0 && keywordGen.status !== 'generating' && (
            <Button
              variant="secondary"
              onClick={() => {
                hasAutoStarted.current = false;
                keywordGen.startGeneration();
              }}
              disabled={keywordGen.isStarting}
            >
              {keywordGen.isStarting ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Starting...
                </>
              ) : (
                'Regenerate All'
              )}
            </Button>
          )}
        </div>

        {/* Progress/status indicator */}
        <GenerationProgressIndicator
          status={keywordGen.status}
          completed={keywordGen.completed}
          total={keywordGen.total}
          currentPage={keywordGen.currentPage}
        />

        {/* Error message */}
        {keywordGen.isFailed && keywordGen.error && (
          <div className="mb-4 p-3 bg-coral-50 border border-coral-200 rounded-sm">
            <p className="text-sm text-coral-700">{keywordGen.error}</p>
          </div>
        )}

        {/* Pending/starting state - show loading message */}
        {showPendingState && (
          <div className="text-center py-8">
            <SpinnerIcon className="w-8 h-8 text-lagoon-500 animate-spin mx-auto mb-3" />
            <p className="text-warm-gray-600">
              Preparing to generate keywords for {totalPages} pages...
            </p>
          </div>
        )}

        {/* Generating or completed state - show page list */}
        {!showPendingState && (
          <>
            {/* Summary stats and Approve All button */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex gap-4 text-sm">
                <span className="text-warm-gray-600">
                  <span className="font-medium text-warm-gray-900">{pagesWithKeywords}</span> keywords generated
                </span>
                <span className="text-warm-gray-600">
                  <span className="font-medium text-palm-600">{approvedCount}</span> approved
                </span>
                <span className="text-warm-gray-600">
                  <span className="font-medium text-lagoon-600">{pendingApprovalCount}</span> pending
                </span>
              </div>

              {/* Approval progress display and Approve All button */}
              <div className="flex items-center gap-3">
                {/* Approval progress - shows "Approved: X of Y" with checkmark when complete */}
                <div className="flex items-center gap-2">
                  {approvedCount === pagesWithKeywords && pagesWithKeywords > 0 ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-sm font-medium text-palm-700 bg-palm-50 rounded-sm border border-palm-200">
                      <CheckIcon className="w-4 h-4" />
                      Approved: {approvedCount} of {pagesWithKeywords}
                    </span>
                  ) : pagesWithKeywords > 0 ? (
                    <span className="text-sm text-warm-gray-600">
                      Approved: <span className="font-medium">{approvedCount}</span> of <span className="font-medium">{pagesWithKeywords}</span>
                    </span>
                  ) : null}
                </div>

                {/* Approve All button */}
                <Button
                  variant="secondary"
                  onClick={handleApproveAll}
                  disabled={pendingApprovalCount === 0 || approveAllMutation.isPending}
                >
                  {approveAllMutation.isPending ? (
                    <>
                      <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                      Approving...
                    </>
                  ) : (
                    'Approve All'
                  )}
                </Button>
              </div>
            </div>

            {/* Pages list */}
            <div className="border border-cream-500 rounded-sm overflow-hidden">
              <div className="max-h-80 overflow-y-auto">
                {isPagesLoading ? (
                  /* Skeleton loading rows */
                  <div className="divide-y divide-cream-300">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="px-4 py-3 animate-pulse">
                        <div className="flex items-center gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="h-4 bg-cream-300 rounded w-48 mb-2" />
                            <div className="h-3 bg-cream-200 rounded w-32" />
                          </div>
                          <div className="flex items-center gap-3">
                            <div className="h-6 bg-cream-300 rounded w-20" />
                            <div className="h-6 bg-cream-300 rounded w-16" />
                            <div className="h-8 bg-cream-300 rounded w-20" />
                            <div className="h-6 w-6 bg-cream-300 rounded-full" />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : isPagesError ? (
                  /* Error state with retry */
                  <ErrorState
                    message={pagesError instanceof Error ? pagesError.message : 'Failed to load pages. Please try again.'}
                    onRetry={handleRetryFetch}
                    isRetrying={isRetrying}
                  />
                ) : pages.length === 0 ? (
                  /* Empty state */
                  <EmptyState />
                ) : (
                  pages.map((page) => (
                    <KeywordPageRow
                      key={page.id}
                      page={page}
                      projectId={projectId}
                      onShowToast={(message, variant) => {
                        setToastMessage(message);
                        setToastVariant(variant);
                        setShowToast(true);
                      }}
                    />
                  ))
                )}
              </div>
            </div>
          </>
        )}

        <hr className="border-cream-500 my-6" />

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}/onboarding/crawl`}>
            <Button variant="secondary">Back</Button>
          </Link>
          {(() => {
            // All keywords approved - fully enabled
            const allApproved = pagesWithKeywords > 0 && approvedCount === pagesWithKeywords;
            // Some keywords generated but not all approved
            const someUnapproved = pagesWithKeywords > 0 && approvedCount < pagesWithKeywords;

            if (allApproved) {
              return (
                <Button onClick={() => router.push(`/projects/${projectId}/onboarding/content`)}>
                  Continue to Content
                </Button>
              );
            }

            if (showGeneratingState) {
              return (
                <Button disabled>
                  Generating...
                </Button>
              );
            }

            // Show disabled button with tooltip when some unapproved
            return (
              <div className="relative">
                <Button
                  ref={continueButtonRef}
                  disabled
                  onMouseEnter={() => someUnapproved && setShowContinueTooltip(true)}
                  onMouseLeave={() => setShowContinueTooltip(false)}
                >
                  Continue to Content
                </Button>
                {showContinueTooltip && someUnapproved && (
                  <div
                    className="absolute z-50 px-3 py-2 text-sm bg-warm-gray-800 text-white rounded-sm shadow-lg whitespace-nowrap"
                    style={{
                      bottom: 'calc(100% + 8px)',
                      left: '50%',
                      transform: 'translateX(-50%)',
                    }}
                  >
                    Approve all {pendingApprovalCount} remaining keywords to continue
                    <div
                      className="absolute w-2 h-2 bg-warm-gray-800 rotate-45"
                      style={{
                        bottom: '-4px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                      }}
                    />
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      </div>

      {/* Toast notification */}
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
