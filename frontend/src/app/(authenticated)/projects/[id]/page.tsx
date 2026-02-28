'use client';

import { Suspense, useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useProject, useDeleteProject } from '@/hooks/use-projects';
import { useStartBrandConfigGeneration, useBrandConfigGeneration } from '@/hooks/useBrandConfigGeneration';
import { useCrawlStatus, getOnboardingStep } from '@/hooks/use-crawl-status';
import { useClusters } from '@/hooks/useClusters';
import { useBlogCampaigns } from '@/hooks/useBlogs';
import { useLinkMap, usePlanStatus } from '@/hooks/useLinks';
import { useRedditConfig, useUpsertRedditConfig } from '@/hooks/useReddit';
import { Button, ButtonLink, Toast } from '@/components/ui';
import { PagesTab } from '@/components/PagesTab';
import { useResetOnboarding } from '@/hooks/usePageDeletion';

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
      <ButtonLink href="/">Back to Dashboard</ButtonLink>
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

function ChatBubbleIcon({ className }: { className?: string }) {
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
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
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
  { key: 'links', label: 'Links' },
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

function ClusterStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'complete':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-sm">
          <CheckCircleIcon className="w-3 h-3" />
          Complete
        </span>
      );
    case 'content_generating':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-lagoon-50 text-lagoon-700 px-2 py-0.5 rounded-sm">
          <SpinnerIcon className="w-3 h-3" />
          Generating Content
        </span>
      );
    case 'approved':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-sm">
          <CheckCircleIcon className="w-3 h-3" />
          Approved
        </span>
      );
    case 'suggestions_ready':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-coral-50 text-coral-700 px-2 py-0.5 rounded-sm">
          <CircleIcon className="w-3 h-3" />
          Awaiting Approval
        </span>
      );
    case 'generating':
    default:
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-lagoon-50 text-lagoon-700 px-2 py-0.5 rounded-sm">
          <SpinnerIcon className="w-3 h-3" />
          Generating
        </span>
      );
  }
}

function LinkStatusBadge({
  totalLinks,
  isPlanning,
  href,
}: {
  totalLinks: number | undefined;
  isPlanning: boolean;
  href: string;
}) {
  let label: string;
  let badgeClass: string;
  let icon: React.ReactNode;

  if (isPlanning) {
    label = 'Links: Planning...';
    badgeClass = 'bg-lagoon-50 text-lagoon-700 border-lagoon-200';
    icon = <SpinnerIcon className="w-3 h-3" />;
  } else if (totalLinks && totalLinks > 0) {
    label = `Links: ${totalLinks} planned`;
    badgeClass = 'bg-palm-50 text-palm-700 border-palm-200';
    icon = (
      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    );
  } else {
    label = 'Links: Not planned';
    badgeClass = 'bg-cream-100 text-warm-gray-600 border-cream-300';
    icon = <CircleIcon className="w-3 h-3" />;
  }

  return (
    <Link href={href}>
      <span className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-sm border cursor-pointer hover:opacity-80 transition-opacity ${badgeClass}`}>
        {icon}
        {label}
      </span>
    </Link>
  );
}

function ClusterCard({
  cluster,
  projectId,
}: {
  cluster: { id: string; name: string; seed_keyword: string; page_count: number; approved_count: number; status: string };
  projectId: string;
}) {
  const { data: linkMap } = useLinkMap(projectId, 'cluster', cluster.id);
  const { data: planStatus } = usePlanStatus(projectId, 'cluster', cluster.id, true);
  const isPlanning = planStatus?.status === 'planning';

  return (
    <div className="bg-white rounded-sm border border-sand-500 p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      <h3 className="font-medium text-warm-gray-900 mb-2 truncate">
        {cluster.name || cluster.seed_keyword}
      </h3>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-warm-gray-600">
          {cluster.approved_count} of {cluster.page_count} {cluster.page_count === 1 ? 'page' : 'pages'} approved
        </span>
        <ClusterStatusBadge status={cluster.status} />
      </div>
      <div onClick={(e) => e.preventDefault()}>
        <LinkStatusBadge
          totalLinks={linkMap?.total_links}
          isPlanning={isPlanning}
          href={`/projects/${projectId}/clusters/${cluster.id}/links`}
        />
      </div>
    </div>
  );
}

function BlogCampaignStatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'complete':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-sm">
          <CheckCircleIcon className="w-3 h-3" />
          Complete
        </span>
      );
    case 'review':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-coral-50 text-coral-700 px-2 py-0.5 rounded-sm">
          <CircleIcon className="w-3 h-3" />
          Review
        </span>
      );
    case 'writing':
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-lagoon-50 text-lagoon-700 px-2 py-0.5 rounded-sm">
          <SpinnerIcon className="w-3 h-3" />
          Writing
        </span>
      );
    case 'planning':
    default:
      return (
        <span className="inline-flex items-center gap-1 text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-sm">
          <CircleIcon className="w-3 h-3" />
          Planning
        </span>
      );
  }
}

function BlogCampaignCard({
  campaign,
}: {
  campaign: { id: string; name: string; status: string; cluster_name: string; post_count: number; content_complete_count: number };
}) {
  return (
    <div className="bg-white rounded-sm border border-sand-500 p-4 shadow-sm hover:shadow-md transition-shadow cursor-pointer">
      <h3 className="font-medium text-warm-gray-900 mb-1 truncate">
        {campaign.name}
      </h3>
      <p className="text-xs text-warm-gray-500 mb-2 truncate">
        {campaign.cluster_name}
      </p>
      <div className="flex items-center justify-between">
        <span className="text-sm text-warm-gray-600">
          {campaign.content_complete_count} of {campaign.post_count} {campaign.post_count === 1 ? 'post' : 'posts'} done
        </span>
        <BlogCampaignStatusBadge status={campaign.status} />
      </div>
    </div>
  );
}

export default function ProjectDetailPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <ProjectDetailContent />
    </Suspense>
  );
}

function ProjectDetailContent() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.id as string;

  // Tab state from URL
  const activeTab = searchParams.get('tab') || 'tools';

  const setActiveTab = useCallback((tab: string) => {
    const url = tab === 'tools'
      ? `/projects/${projectId}`
      : `/projects/${projectId}?tab=${tab}`;
    router.replace(url, { scroll: false });
  }, [router, projectId]);

  const { data: project, isLoading, error } = useProject(projectId);
  const deleteProject = useDeleteProject();
  const generation = useBrandConfigGeneration(projectId);
  const startGeneration = useStartBrandConfigGeneration();

  // Fetch crawl status for onboarding progress
  const { data: crawlStatus } = useCrawlStatus(projectId, {
    enabled: !!projectId && !isLoading && !error,
  });
  const onboardingProgress = getOnboardingStep(crawlStatus);

  // Fetch clusters for New Content section
  const { data: clusters } = useClusters(projectId, {
    enabled: !!projectId && !isLoading && !error,
  });

  // Fetch blog campaigns for Blogs section
  const { data: blogCampaigns } = useBlogCampaigns(projectId, {
    enabled: !!projectId && !isLoading && !error,
  });

  // Fetch Reddit config for project
  const { data: redditConfig } = useRedditConfig(projectId, {
    enabled: !!projectId && !isLoading && !error,
  });
  const upsertRedditConfig = useUpsertRedditConfig(projectId);

  // Fetch link status for onboarding scope
  const { data: onboardingLinkMap } = useLinkMap(projectId, 'onboarding');
  const { data: onboardingPlanStatus } = usePlanStatus(projectId, 'onboarding', undefined, true);
  const isOnboardingLinkPlanning = onboardingPlanStatus?.status === 'planning';

  // Onboarding reset
  const resetOnboarding = useResetOnboarding(projectId);
  const [isConfirmingReset, setIsConfirmingReset] = useState(false);
  const resetTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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

  // Onboarding reset: 2-step confirmation
  useEffect(() => {
    if (isConfirmingReset) {
      resetTimeoutRef.current = setTimeout(() => setIsConfirmingReset(false), 3000);
    }
    return () => {
      if (resetTimeoutRef.current) clearTimeout(resetTimeoutRef.current);
    };
  }, [isConfirmingReset]);

  const handleResetOnboarding = async () => {
    if (!isConfirmingReset) {
      setIsConfirmingReset(true);
      return;
    }
    try {
      const result = await resetOnboarding.mutateAsync();
      setIsConfirmingReset(false);
      setToastMessage(`Reset onboarding — removed ${result.deleted_count} pages`);
      setShowToast(true);
    } catch {
      setIsConfirmingReset(false);
      setToastMessage('Failed to reset onboarding');
      setShowToast(true);
    }
  };

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
            <ButtonLink href={`/projects/${projectId}/brand-config`} variant="secondary">Brand Details</ButtonLink>
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

      {/* Tab bar */}
      <div className="flex border-b border-cream-300 mb-8">
        <button
          onClick={() => setActiveTab('tools')}
          className={`px-4 py-2 text-sm transition-colors ${
            activeTab === 'tools'
              ? 'border-b-2 border-palm-500 font-semibold text-warm-gray-900'
              : 'text-warm-gray-400 hover:text-warm-gray-600'
          }`}
        >
          Tools
        </button>
        <button
          onClick={() => setActiveTab('pages')}
          className={`px-4 py-2 text-sm transition-colors ${
            activeTab === 'pages'
              ? 'border-b-2 border-palm-500 font-semibold text-warm-gray-900'
              : 'text-warm-gray-400 hover:text-warm-gray-600'
          }`}
        >
          Pages
        </button>
      </div>

      {/* Tab content */}
      {activeTab === 'pages' ? (
        <PagesTab projectId={projectId} />
      ) : (
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
            <div className="flex items-center gap-2">
              <OnboardingStepIndicator
                currentStep={onboardingProgress.currentStep}
                hasStarted={onboardingProgress.hasStarted}
              />
              <LinkStatusBadge
                totalLinks={onboardingLinkMap?.total_links}
                isPlanning={isOnboardingLinkPlanning}
                href={`/projects/${projectId}/links`}
              />
            </div>
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

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            <ButtonLink
              href={
                onboardingProgress.currentStep === 'upload'
                  ? `/projects/${projectId}/onboarding/upload`
                  : onboardingProgress.currentStep === 'crawl'
                  ? `/projects/${projectId}/onboarding/crawl`
                  : `/projects/${projectId}/onboarding/keywords`
              }
            >
              {onboardingProgress.hasStarted ? 'Continue Onboarding' : 'Start Onboarding'}
            </ButtonLink>
            {onboardingProgress.hasStarted && (
              <Button
                variant="secondary"
                onClick={handleResetOnboarding}
                disabled={resetOnboarding.isPending}
              >
                {resetOnboarding.isPending
                  ? 'Resetting...'
                  : isConfirmingReset
                  ? 'Confirm Reset'
                  : 'Reset Onboarding'}
              </Button>
            )}
          </div>
        </div>

        {/* New Content section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <PlusIcon className="w-5 h-5 text-palm-500" />
              <h2 className="text-lg font-semibold text-warm-gray-900">
                New Content
              </h2>
              <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
                Keyword Clusters
              </span>
            </div>
            {clusters && clusters.length > 0 && (
              <ButtonLink href={`/projects/${projectId}/clusters/new`}>+ New Cluster</ButtonLink>
            )}
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            Build new collection pages from keyword clusters
          </p>

          {/* Cluster cards or empty state */}
          {!clusters || clusters.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-warm-gray-500 text-sm mb-4">No clusters yet</p>
              <ButtonLink href={`/projects/${projectId}/clusters/new`}>+ New Cluster</ButtonLink>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {clusters.map((cluster) => (
                <Link
                  key={cluster.id}
                  href={`/projects/${projectId}/clusters/${cluster.id}`}
                  className="block"
                >
                  <ClusterCard
                    cluster={cluster}
                    projectId={projectId}
                  />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Blogs section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <PencilIcon className="w-5 h-5 text-palm-500" />
              <h2 className="text-lg font-semibold text-warm-gray-900">
                Blogs
              </h2>
              <span className="text-xs bg-cream-100 text-warm-gray-600 px-2 py-0.5 rounded-full">
                Supporting Content
              </span>
            </div>
            {blogCampaigns && blogCampaigns.length > 0 && (
              <ButtonLink href={`/projects/${projectId}/blogs/new`}>+ New Campaign</ButtonLink>
            )}
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            Create blog posts to support your keyword clusters
          </p>

          {/* Blog campaign cards or empty state */}
          {!blogCampaigns || blogCampaigns.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-warm-gray-500 text-sm mb-2">No blog campaigns yet</p>
              <p className="text-warm-gray-400 text-xs mb-4">Blog campaigns create supporting content around your keyword clusters</p>
              <ButtonLink href={`/projects/${projectId}/blogs/new`}>+ New Campaign</ButtonLink>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {blogCampaigns.map((campaign) => (
                <Link
                  key={campaign.id}
                  href={`/projects/${projectId}/blogs/${campaign.id}`}
                  className="block"
                >
                  <BlogCampaignCard campaign={campaign} />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Reddit Marketing section */}
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
          <div className="flex items-center gap-3 mb-3">
            <ChatBubbleIcon className="w-5 h-5 text-palm-500" />
            <h2 className="text-lg font-semibold text-warm-gray-900">
              Reddit Marketing
            </h2>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              redditConfig
                ? 'bg-palm-50 text-palm-700'
                : 'bg-cream-100 text-warm-gray-600'
            }`}>
              {redditConfig ? 'Configured' : 'Not configured'}
            </span>
          </div>
          <p className="text-warm-gray-600 text-sm mb-4">
            {redditConfig
              ? 'Reddit marketing is set up for this project'
              : 'Configure Reddit marketing to promote your content across relevant subreddits'}
          </p>
          {redditConfig ? (
            <ButtonLink href={`/reddit/${projectId}`}>
              View Reddit Project
            </ButtonLink>
          ) : (
            <Button
              onClick={() => {
                upsertRedditConfig.mutate({}, {
                  onSuccess: () => router.push(`/reddit/${projectId}`),
                  onError: () => router.push(`/reddit/${projectId}`),
                });
              }}
              disabled={upsertRedditConfig.isPending}
            >
              {upsertRedditConfig.isPending ? 'Setting up...' : 'Set up Reddit'}
            </Button>
          )}
        </div>
      </div>
      )}
    </div>
  );
}
