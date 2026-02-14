'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useProject } from '@/hooks/use-projects';
import { Button, Toast } from '@/components/ui';
import { apiClient, ApiError } from '@/lib/api';
import { LabelEditDropdown } from '@/components/onboarding/LabelEditDropdown';

// Step indicator data - shared across onboarding pages
const ONBOARDING_STEPS = [
  { key: 'upload', label: 'Upload' },
  { key: 'crawl', label: 'Crawl' },
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'links', label: 'Links' },
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

// Types matching backend TaxonomyResponse
interface TaxonomyLabel {
  name: string;
  description: string;
  examples: string[];
}

interface TaxonomyResponse {
  labels: TaxonomyLabel[];
  generated_at: string;
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

function RetryIcon({ className }: { className?: string }) {
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
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function TagIcon({ className }: { className?: string }) {
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
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
      <line x1="7" y1="7" x2="7.01" y2="7" />
    </svg>
  );
}

function PencilIcon({ className }: { className?: string }) {
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
      <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
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

function CrawlProgressIndicator({
  status,
  completed,
  total,
  crawling,
}: {
  status: 'crawling' | 'labeling' | 'complete';
  completed: number;
  total: number;
  crawling: number;
}) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="mb-6">
      {/* Status indicator with spinner */}
      <div className="flex items-center gap-2 mb-3">
        {status === 'crawling' ? (
          <>
            <SpinnerIcon className="w-5 h-5 text-lagoon-500 animate-spin" />
            <span className="text-warm-gray-700">
              Crawling pages...{' '}
              <span className="font-medium text-lagoon-600">
                {completed}/{total} complete
              </span>
              {crawling > 0 && (
                <span className="text-warm-gray-500"> ({crawling} in progress)</span>
              )}
            </span>
          </>
        ) : status === 'labeling' ? (
          <>
            <SpinnerIcon className="w-5 h-5 text-palm-500 animate-spin" />
            <span className="text-warm-gray-700">
              Assigning labels...{' '}
              <span className="font-medium text-palm-600">
                {completed}/{total} pages crawled
              </span>
            </span>
          </>
        ) : (
          <>
            <CheckIcon className="w-5 h-5 text-palm-500" />
            <span className="text-warm-gray-700">
              <span className="font-medium text-palm-600">
                {completed}/{total} pages crawled
              </span>
            </span>
          </>
        )}
      </div>

      {/* Progress bar */}
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

interface PageListItemProps {
  page: PageSummary;
  onRetry?: (pageId: string) => Promise<void>;
  isRetrying?: boolean;
  onEditLabels?: (pageId: string) => void;
  isEditingLabels?: boolean;
  taxonomyLabels?: TaxonomyLabel[];
  onCloseEditLabels?: () => void;
  onSaveLabels?: (labels: string[]) => Promise<void>;
  isSavingLabels?: boolean;
}

function PageListItem({
  page,
  onRetry,
  isRetrying,
  onEditLabels,
  isEditingLabels,
  taxonomyLabels,
  onCloseEditLabels,
  onSaveLabels,
  isSavingLabels,
}: PageListItemProps) {
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

  // Check if page has labels
  const hasLabels = page.labels && page.labels.length > 0;

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
            <div className="flex items-center gap-2">
              <PageStatusText status={page.status} />
              {page.status === 'failed' && onRetry && (
                <button
                  onClick={() => onRetry(page.id)}
                  disabled={isRetrying}
                  className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-coral-700 bg-coral-50 hover:bg-coral-100 rounded-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  title="Retry crawl"
                >
                  {isRetrying ? (
                    <SpinnerIcon className="w-3 h-3 animate-spin" />
                  ) : (
                    <RetryIcon className="w-3 h-3" />
                  )}
                  {isRetrying ? 'Retrying...' : 'Retry'}
                </button>
              )}
            </div>
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
          {/* Label tags display */}
          {page.status === 'completed' && hasLabels && (
            <div className="mt-2 relative">
              <div className="flex items-center gap-2 flex-wrap">
                <div className="flex flex-wrap gap-1.5">
                  {page.labels.map((label) => (
                    <span
                      key={label}
                      className="inline-flex items-center px-2 py-0.5 text-xs bg-palm-100 text-palm-700 rounded-sm"
                    >
                      {label}
                    </span>
                  ))}
                </div>
                {onEditLabels && (
                  <button
                    onClick={() => onEditLabels(page.id)}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs text-warm-gray-500 hover:text-palm-600 hover:bg-palm-50 rounded-sm transition-colors"
                    title="Edit labels"
                  >
                    <PencilIcon className="w-3 h-3" />
                    Edit
                  </button>
                )}
              </div>
              {/* Label edit dropdown */}
              {isEditingLabels && taxonomyLabels && onCloseEditLabels && onSaveLabels && (
                <LabelEditDropdown
                  taxonomyLabels={taxonomyLabels}
                  selectedLabels={page.labels}
                  onLabelsChange={() => {}} // Local state managed inside dropdown
                  onClose={onCloseEditLabels}
                  onSave={onSaveLabels}
                  isSaving={isSavingLabels}
                />
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

interface TaxonomyStatusProps {
  status: 'crawling' | 'labeling' | 'complete';
  taxonomy: TaxonomyResponse | null;
  isLoading: boolean;
  onRegenerateLabels?: () => Promise<void>;
  isRegenerating?: boolean;
}

function TaxonomyStatus({ status, taxonomy, isLoading, onRegenerateLabels, isRegenerating }: TaxonomyStatusProps) {
  // Only show taxonomy section when crawling is done
  if (status === 'crawling') {
    return null;
  }

  // Show spinner when generating taxonomy
  if (status === 'labeling' || isLoading || isRegenerating) {
    return (
      <div className="mt-6 p-4 bg-sand-50 rounded-sm border border-sand-200">
        <div className="flex items-center gap-3">
          <SpinnerIcon className="w-5 h-5 text-palm-500 animate-spin" />
          <span className="text-warm-gray-700">
            {isRegenerating ? 'Regenerating labels...' : 'Generating label taxonomy...'}
          </span>
        </div>
      </div>
    );
  }

  // Show taxonomy labels when complete
  if (status === 'complete' && taxonomy) {
    return (
      <div className="mt-6 p-4 bg-palm-50 rounded-sm border border-palm-200">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TagIcon className="w-5 h-5 text-palm-600" />
            <span className="font-medium text-warm-gray-900">
              {taxonomy.labels.length} labels generated
            </span>
          </div>
          {onRegenerateLabels && (
            <button
              onClick={onRegenerateLabels}
              disabled={isRegenerating}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-palm-700 bg-palm-100 hover:bg-palm-200 rounded-sm transition-colors disabled:opacity-50"
              title="Regenerate taxonomy and reassign labels"
            >
              <RetryIcon className="w-3.5 h-3.5" />
              Regenerate Labels
            </button>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {taxonomy.labels.map((label) => (
            <span
              key={label.name}
              className="inline-flex items-center px-2.5 py-1 text-sm bg-palm-100 text-palm-700 rounded-sm"
              title={label.description}
            >
              {label.name}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return null;
}

/**
 * Get user-friendly error message from an error object.
 */
function getErrorMessage(err: unknown): string {
  // Network error (no internet, server unreachable)
  if (err instanceof TypeError && err.message === 'Failed to fetch') {
    return 'Unable to connect to the server. Please check your internet connection and try again.';
  }

  // API error with message from backend
  if (err instanceof ApiError) {
    if (err.status === 400) {
      return err.message || 'Invalid request. Please try again.';
    }
    if (err.status === 404) {
      return 'Page not found. It may have been deleted.';
    }
    if (err.status === 429) {
      return 'Too many requests. Please wait a moment and try again.';
    }
    if (err.status >= 500) {
      return 'Server error. Please try again later.';
    }
    return err.message || 'An error occurred. Please try again.';
  }

  // Generic error
  if (err instanceof Error) {
    return err.message;
  }

  return 'An unexpected error occurred. Please try again.';
}

export default function CrawlProgressPage() {
  const params = useParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();
  const [retryingPageId, setRetryingPageId] = useState<string | null>(null);
  const [editingPageId, setEditingPageId] = useState<string | null>(null);
  const [savingLabels, setSavingLabels] = useState(false);
  const [regeneratingLabels, setRegeneratingLabels] = useState(false);
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);

  // Poll crawl status every 2 seconds while crawling
  const { data: crawlStatus, isLoading: isCrawlStatusLoading, error: crawlStatusError } = useQuery({
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
    // Don't fail immediately on network errors during polling
    retry: 3,
    retryDelay: 1000,
  });

  // Fetch taxonomy when status is 'labeling' or 'complete'
  const { data: taxonomy, isLoading: isTaxonomyLoading } = useQuery({
    queryKey: ['taxonomy', projectId],
    queryFn: () => apiClient.get<TaxonomyResponse>(`/projects/${projectId}/taxonomy`),
    enabled: !!projectId && (crawlStatus?.status === 'labeling' || crawlStatus?.status === 'complete'),
    // Retry to handle timing where taxonomy isn't ready yet during labeling
    retry: (failureCount, error) => {
      // Stop retrying after 3 attempts or if not a 404
      if (failureCount >= 3) return false;
      // Keep retrying 404s during labeling phase (taxonomy not generated yet)
      return (error as Error)?.message?.includes('404') ?? false;
    },
    retryDelay: 2000,
  });

  const isLoading = isProjectLoading || isCrawlStatusLoading;

  // Handle retry for a failed page
  const handleRetryPage = async (pageId: string) => {
    setRetryingPageId(pageId);
    try {
      await apiClient.post(`/projects/${projectId}/pages/${pageId}/retry`);
      // Invalidate query to refresh the page list immediately
      await queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
      // Show success toast
      setToastMessage('Retry started');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      // Show user-friendly error toast
      const message = getErrorMessage(error);
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    } finally {
      setRetryingPageId(null);
    }
  };

  // Handle edit labels button click
  const handleEditLabels = (pageId: string) => {
    setEditingPageId(pageId);
  };

  // Handle closing the label edit dropdown
  const handleCloseEditLabels = () => {
    setEditingPageId(null);
  };

  // Handle saving labels for a page
  const handleSaveLabels = async (pageId: string, labels: string[]) => {
    setSavingLabels(true);
    try {
      await apiClient.put(`/projects/${projectId}/pages/${pageId}/labels`, { labels });
      // Refresh the page list to show updated labels
      await queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
      setEditingPageId(null);
      // Show success toast
      setToastMessage('Labels saved');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      // Get user-friendly error message
      const message = getErrorMessage(error);
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
      throw error;
    } finally {
      setSavingLabels(false);
    }
  };

  // Handle regenerating taxonomy and labels
  const handleRegenerateLabels = async () => {
    setRegeneratingLabels(true);
    try {
      await apiClient.post(`/projects/${projectId}/taxonomy/regenerate`);
      // Show success toast
      setToastMessage('Regenerating labels...');
      setToastVariant('success');
      setShowToast(true);
      // Invalidate queries to start polling for new status
      await queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
      await queryClient.invalidateQueries({ queryKey: ['taxonomy', projectId] });
    } catch (error) {
      const message = getErrorMessage(error);
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    } finally {
      setRegeneratingLabels(false);
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

  const progress = crawlStatus?.progress ?? { total: 0, completed: 0, failed: 0, pending: 0 };
  const pages = crawlStatus?.pages ?? [];
  const overallStatus = crawlStatus?.status ?? 'crawling';
  const isComplete = overallStatus === 'complete';
  const inProgressCount = progress.total - progress.completed - progress.failed - progress.pending;

  // Check if there's a network error during polling
  const hasNetworkError = crawlStatusError && !crawlStatus;

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

      {/* Network error banner */}
      {hasNetworkError && (
        <div className="mb-6 p-3 bg-coral-50 border border-coral-200 rounded-sm flex items-start gap-2">
          <svg
            className="w-5 h-5 text-coral-500 flex-shrink-0 mt-0.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <p className="text-sm text-coral-700">
            Unable to load crawl status. Please check your internet connection.
          </p>
        </div>
      )}

      {/* Page content */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-warm-gray-900 mb-4">
          {isComplete
            ? `Crawled ${progress.total} pages`
            : `Crawling ${progress.total} pages...`}
        </h2>

        {/* Progress indicator with spinner */}
        <CrawlProgressIndicator
          status={overallStatus}
          completed={progress.completed}
          total={progress.total}
          crawling={inProgressCount}
        />

        {/* Failed pages warning */}
        {progress.failed > 0 && (
          <div className="flex items-center gap-2 text-sm mb-4 p-2 bg-coral-50 rounded-sm border border-coral-200">
            <svg
              className="w-4 h-4 text-coral-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <span className="text-coral-700">
              {progress.failed} {progress.failed === 1 ? 'page' : 'pages'} failed to crawl
            </span>
          </div>
        )}

        {/* Pages list */}
        <div className="border border-cream-300 rounded-sm overflow-hidden">
          <div className="max-h-80 overflow-y-auto px-4">
            {pages.map((page) => (
              <PageListItem
                key={page.id}
                page={page}
                onRetry={handleRetryPage}
                isRetrying={retryingPageId === page.id}
                onEditLabels={handleEditLabels}
                isEditingLabels={editingPageId === page.id}
                taxonomyLabels={taxonomy?.labels}
                onCloseEditLabels={handleCloseEditLabels}
                onSaveLabels={(labels) => handleSaveLabels(page.id, labels)}
                isSavingLabels={savingLabels}
              />
            ))}
            {pages.length === 0 && (
              <div className="py-8 text-center text-warm-gray-500">
                No pages to display
              </div>
            )}
          </div>
        </div>

        {/* Taxonomy status */}
        <TaxonomyStatus
          status={overallStatus}
          taxonomy={taxonomy ?? null}
          isLoading={isTaxonomyLoading}
          onRegenerateLabels={handleRegenerateLabels}
          isRegenerating={regeneratingLabels}
        />

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

      {/* Toast notifications */}
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
