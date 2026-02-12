'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useCluster } from '@/hooks/useClusters';
import { useContentGeneration } from '@/hooks/useContentGeneration';
import { usePlanLinks, usePlanStatus } from '@/hooks/useLinks';
import { useQueryClient } from '@tanstack/react-query';
import { Button, Toast } from '@/components/ui';

// 4-step link planning pipeline
const LINK_PLAN_STEPS = [
  { key: 1, label: 'Building link graph' },
  { key: 2, label: 'Selecting targets & anchor text' },
  { key: 3, label: 'Injecting links into content' },
  { key: 4, label: 'Validating link rules' },
] as const;

const CLUSTER_RULES = [
  'First link on every child page \u2192 parent collection',
  'No cross-silo links',
  '3\u20135 links per page',
  'Anchor text diversified (partial match, exact, natural)',
  'Parent collection links to sub-collections only',
  'Sub-collections link to parent + siblings',
];

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

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-64 mb-2" />
        <div className="h-4 bg-cream-300 rounded w-96 mb-6" />
        <div className="h-24 bg-cream-300 rounded w-full mb-6" />
        <div className="h-10 bg-cream-300 rounded w-48 mx-auto" />
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
        Not Found
      </h1>
      <p className="text-warm-gray-600 mb-6">
        The project or cluster you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

/** Step icon: check for complete, spinner for active, circle for pending */
function StepIcon({ step, currentStep }: { step: number; currentStep: number | null }) {
  if (currentStep !== null && step < currentStep) {
    return <CheckIcon className="w-5 h-5 text-palm-500" />;
  }
  if (currentStep !== null && step === currentStep) {
    return <SpinnerIcon className="w-5 h-5 text-lagoon-500 animate-spin" />;
  }
  return <CircleIcon className="w-5 h-5 text-warm-gray-300" />;
}

export default function ClusterLinksPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const clusterId = params.clusterId as string;

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: cluster, isLoading: isClusterLoading } = useCluster(projectId, clusterId);
  const contentGen = useContentGeneration(projectId);
  const queryClient = useQueryClient();
  const planLinksMutation = usePlanLinks();
  const planStatus = usePlanStatus(projectId, 'cluster', clusterId, true);

  const isLoading = isProjectLoading || isClusterLoading || contentGen.isLoading;
  const isPlanning = planStatus.data?.status === 'planning';
  const isComplete = planStatus.data?.status === 'complete';
  const isFailed = planStatus.data?.status === 'failed';

  // Filter content generation pages to those belonging to this cluster
  const clusterCrawledPageIds = useMemo(() => {
    if (!cluster?.pages) return new Set<string>();
    return new Set(
      cluster.pages
        .map((p) => p.crawled_page_id)
        .filter((id): id is string => id != null)
    );
  }, [cluster?.pages]);

  const clusterPages = useMemo(
    () => contentGen.pages.filter((p) => clusterCrawledPageIds.has(p.page_id)),
    [contentGen.pages, clusterCrawledPageIds]
  );

  // Derive prerequisites from cluster-filtered pages
  const pagesTotal = clusterPages.length;
  const allKeywordsApproved = pagesTotal > 0 && clusterPages.every((p) => p.is_approved);
  const pagesCompleted = clusterPages.filter((p) => p.status === 'complete').length;
  const allContentGenerated = pagesTotal > 0 && pagesCompleted === pagesTotal;
  const allPrerequisitesMet = allKeywordsApproved && allContentGenerated;

  // Auto-redirect to link map on completion
  useEffect(() => {
    if (isComplete) {
      queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'links', 'map'],
      });
      const timer = setTimeout(() => {
        router.push(`/projects/${projectId}/clusters/${clusterId}/links/map`);
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [isComplete, projectId, clusterId, router, queryClient]);

  const handlePlanLinks = async () => {
    try {
      await planLinksMutation.mutateAsync({
        projectId,
        scope: 'cluster',
        clusterId,
      });
      setToastMessage('Link planning started');
      setToastVariant('success');
      setShowToast(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start link planning';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    }
  };

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

  if (projectError || !project || !cluster) {
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
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <Link href={`/projects/${projectId}/clusters/${clusterId}`} className="hover:text-warm-gray-900">
          {cluster.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Internal Links</span>
      </nav>

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
          Internal Links &mdash; {cluster.name}
        </h1>
        <p className="text-sm text-warm-gray-600">
          Plan and inject internal links across all pages in this silo.
        </p>
      </div>

      {/* Prerequisites card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm mb-6">
        <h2 className="text-sm font-semibold text-warm-gray-900 mb-4">Prerequisites</h2>
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            {allKeywordsApproved ? (
              <CheckIcon className="w-5 h-5 text-palm-500 shrink-0" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-coral-400 shrink-0" />
            )}
            <span className={`text-sm ${allKeywordsApproved ? 'text-warm-gray-900' : 'text-warm-gray-500'}`}>
              All pages have approved keywords
            </span>
          </div>
          <div className="flex items-center gap-3">
            {allContentGenerated ? (
              <CheckIcon className="w-5 h-5 text-palm-500 shrink-0" />
            ) : (
              <XCircleIcon className="w-5 h-5 text-coral-400 shrink-0" />
            )}
            <span className={`text-sm ${allContentGenerated ? 'text-warm-gray-900' : 'text-warm-gray-500'}`}>
              All content generated ({pagesCompleted}/{pagesTotal} complete)
            </span>
          </div>
        </div>
      </div>

      {/* Plan button OR progress indicator */}
      {!isPlanning && !isComplete && (
        <div className="flex justify-center mb-6">
          <Button
            onClick={handlePlanLinks}
            disabled={!allPrerequisitesMet || planLinksMutation.isPending}
          >
            {planLinksMutation.isPending ? (
              <>
                <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                Starting...
              </>
            ) : (
              'Plan & Inject Links'
            )}
          </Button>
        </div>
      )}

      {/* Planning progress */}
      {isPlanning && planStatus.data && (
        <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm mb-6">
          <h2 className="text-sm font-semibold text-warm-gray-900 mb-4">Planning & Injecting Links...</h2>

          {/* Progress bar */}
          {planStatus.data.total_pages > 0 && (
            <div className="mb-4">
              <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-palm-500 rounded-full transition-all duration-500"
                  style={{
                    width: `${Math.round(((planStatus.data.current_step ?? 1) - 1) / 4 * 100 + (planStatus.data.pages_processed / Math.max(planStatus.data.total_pages, 1)) * 25)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-warm-gray-500 mt-1 text-right">
                Step {planStatus.data.current_step} of 4
              </p>
            </div>
          )}

          {/* Step list */}
          <div className="space-y-3">
            {LINK_PLAN_STEPS.map((step) => (
              <div key={step.key} className="flex items-center gap-3">
                <StepIcon step={step.key} currentStep={planStatus.data?.current_step ?? null} />
                <span className={`text-sm ${
                  planStatus.data?.current_step !== null && step.key < (planStatus.data?.current_step ?? 0)
                    ? 'text-warm-gray-900'
                    : planStatus.data?.current_step === step.key
                    ? 'text-lagoon-700 font-medium'
                    : 'text-warm-gray-400'
                }`}>
                  {step.label}
                </span>
                {/* Page progress for steps 2-3 */}
                {(step.key === 2 || step.key === 3) && planStatus.data?.current_step === step.key && planStatus.data.total_pages > 0 && (
                  <span className="text-xs text-warm-gray-500 ml-auto">
                    ({planStatus.data.pages_processed}/{planStatus.data.total_pages} pages)
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Completion message */}
      {isComplete && (
        <div className="bg-white rounded-sm border border-palm-200 p-6 shadow-sm mb-6 text-center">
          <CheckIcon className="w-8 h-8 text-palm-500 mx-auto mb-2" />
          <p className="text-sm font-medium text-palm-700">
            Link planning complete! {planStatus.data?.total_links} links created.
          </p>
          <p className="text-xs text-warm-gray-500 mt-1">Redirecting to link map...</p>
        </div>
      )}

      {/* Failure message */}
      {isFailed && (
        <div className="bg-coral-50 rounded-sm border border-coral-200 p-6 shadow-sm mb-6">
          <p className="text-sm text-coral-700">
            Link planning failed: {planStatus.data?.error ?? 'Unknown error'}
          </p>
          <div className="flex justify-center mt-4">
            <Button onClick={handlePlanLinks} disabled={planLinksMutation.isPending}>
              Retry
            </Button>
          </div>
        </div>
      )}

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Link rules */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-warm-gray-900 mb-3">
          Link Rules (applied automatically):
        </h2>
        <ul className="space-y-2">
          {CLUSTER_RULES.map((rule) => (
            <li key={rule} className="flex items-start gap-2 text-sm text-warm-gray-700">
              <span className="text-warm-gray-400 mt-0.5">&bull;</span>
              {rule}
            </li>
          ))}
        </ul>
      </div>

      {/* Back button */}
      <div className="flex justify-start mt-6">
        <Link href={`/projects/${projectId}`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Project
          </Button>
        </Link>
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
