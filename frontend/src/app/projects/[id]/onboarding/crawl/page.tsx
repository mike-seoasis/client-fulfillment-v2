'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useProject } from '@/hooks/use-projects';
import { Button } from '@/components/ui';
import { apiClient } from '@/lib/api';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'export', label: 'Export' },
] as const;

// Types matching backend CrawlStatusResponse
interface PageSummary {
  id: string;
  url: string;
  status: 'pending' | 'crawling' | 'completed' | 'failed';
  title: string | null;
  word_count: number | null;
  headings: { h1?: string[]; h2?: string[]; h3?: string[] } | null;
  product_count: number | null;
  labels: string[];
  crawl_error: string | null;
}

interface ProgressCounts {
  total: number;
  completed: number;
  failed: number;
  pending: number;
}

interface CrawlStatusResponse {
  project_id: string;
  status: 'crawling' | 'labeling' | 'complete';
  progress: ProgressCounts;
  pages: PageSummary[];
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

function ProgressBar({ completed, total }: { completed: number; total: number }) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="mb-6">
      <div className="flex justify-between text-sm text-warm-gray-600 mb-2">
        <span>Progress</span>
        <span>{completed} of {total}</span>
      </div>
      <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-palm-500 rounded-full transition-all duration-500"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

function PageStatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <CheckIcon className="w-5 h-5 text-palm-500" />;
    case 'crawling':
      return <SpinnerIcon className="w-5 h-5 text-lagoon-500 animate-spin" />;
    case 'failed':
      return (
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
      );
    default: // pending
      return (
        <div className="w-5 h-5 rounded-full border-2 border-warm-gray-300" />
      );
  }
}

function PageStatusText({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <span className="text-palm-600">Crawled</span>;
    case 'crawling':
      return <span className="text-lagoon-600">Crawling...</span>;
    case 'failed':
      return <span className="text-coral-600">Failed</span>;
    default:
      return <span className="text-warm-gray-500">Pending</span>;
  }
}

function PageListItem({ page }: { page: PageSummary }) {
  // Extract path from URL for display
  const displayUrl = (() => {
    try {
      const url = new URL(page.url);
      return url.pathname + url.search;
    } catch {
      return page.url;
    }
  })();

  // Calculate heading counts
  const h2Count = page.headings?.h2?.length ?? 0;

  return (
    <div className="py-3 border-b border-cream-200 last:border-b-0">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          <PageStatusIcon status={page.status} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <span className="text-warm-gray-900 font-mono text-sm truncate">
              {displayUrl}
            </span>
            <PageStatusText status={page.status} />
          </div>
          {page.status === 'completed' && page.title && (
            <div className="mt-1 text-sm text-warm-gray-600 truncate">
              {page.title}
            </div>
          )}
          {page.status === 'completed' && (
            <div className="mt-1 text-xs text-warm-gray-500 flex gap-3 flex-wrap">
              {page.word_count !== null && (
                <span>{page.word_count.toLocaleString()} words</span>
              )}
              {h2Count > 0 && (
                <span>H2s: {h2Count}</span>
              )}
              {page.product_count !== null && (
                <span>{page.product_count} products</span>
              )}
            </div>
          )}
          {page.status === 'failed' && page.crawl_error && (
            <div className="mt-1 text-sm text-coral-600">
              {page.crawl_error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CrawlProgressPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);

  // Poll crawl status every 2 seconds while crawling
  const { data: crawlStatus, isLoading: isCrawlStatusLoading } = useQuery({
    queryKey: ['crawl-status', projectId],
    queryFn: () => apiClient.get<CrawlStatusResponse>(`/projects/${projectId}/crawl-status`),
    enabled: !!projectId,
    refetchInterval: (data) => {
      // Stop polling when status is complete
      if (data.state.data?.status === 'complete') {
        return false;
      }
      return 2000; // Poll every 2 seconds while crawling/labeling
    },
  });

  const isLoading = isProjectLoading || isCrawlStatusLoading;

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

  const progress = crawlStatus?.progress ?? { total: 0, completed: 0, failed: 0, pending: 0 };
  const pages = crawlStatus?.pages ?? [];
  const overallStatus = crawlStatus?.status ?? 'crawling';
  const isComplete = overallStatus === 'complete';
  const inProgressCount = progress.total - progress.completed - progress.failed - progress.pending;

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
      <StepIndicator currentStep="crawl" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">
          {isComplete
            ? `Crawled ${progress.total} pages`
            : `Crawling ${progress.total} pages...`}
        </h2>

        {/* Progress bar */}
        <ProgressBar completed={progress.completed} total={progress.total} />

        {/* Status summary */}
        {(progress.failed > 0 || inProgressCount > 0) && (
          <div className="flex gap-4 text-sm mb-4">
            {inProgressCount > 0 && (
              <span className="text-lagoon-600">
                {inProgressCount} crawling
              </span>
            )}
            {progress.failed > 0 && (
              <span className="text-coral-600">
                {progress.failed} failed
              </span>
            )}
          </div>
        )}

        {/* Pages list */}
        <div className="border border-cream-300 rounded-sm overflow-hidden">
          <div className="max-h-80 overflow-y-auto px-4">
            {pages.map((page) => (
              <PageListItem key={page.id} page={page} />
            ))}
            {pages.length === 0 && (
              <div className="py-8 text-center text-warm-gray-500">
                No pages to display
              </div>
            )}
          </div>
        </div>

        <hr className="border-cream-300 my-6" />

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Link href={`/projects/${projectId}/onboarding/upload`}>
            <Button variant="secondary">Back</Button>
          </Link>
          {isComplete ? (
            <Link href={`/projects/${projectId}/onboarding/keywords`}>
              <Button>Continue to Keywords</Button>
            </Link>
          ) : (
            <Button disabled>
              Crawling...
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
