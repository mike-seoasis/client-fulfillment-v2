'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState, useCallback, useMemo } from 'react';
import { useProject } from '@/hooks/use-projects';
import { useClusters } from '@/hooks/useClusters';
import { useBlogCampaigns, useCreateBlogCampaign } from '@/hooks/useBlogs';
import { Button, Input } from '@/components/ui';
import type { ClusterListItem, BlogCampaignListItem } from '@/lib/api';

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

const PROGRESS_STEPS = [
  'Extracting seeds...',
  'Expanding topics...',
  'Checking volume...',
  'Filtering results...',
] as const;

function ProgressIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex flex-col items-center py-8">
      <div className="mb-6">
        <div className="w-10 h-10 border-3 border-palm-500 border-t-transparent rounded-full animate-spin" />
      </div>
      <div className="space-y-3 w-full max-w-xs">
        {PROGRESS_STEPS.map((label, index) => (
          <div key={label} className="flex items-center gap-3">
            <div
              className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                index < currentStep
                  ? 'bg-palm-500'
                  : index === currentStep
                  ? 'bg-palm-500'
                  : 'bg-cream-300'
              }`}
            >
              {index < currentStep ? (
                <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              ) : index === currentStep ? (
                <div className="w-2 h-2 bg-white rounded-full" />
              ) : null}
            </div>
            <span
              className={`text-sm ${
                index <= currentStep ? 'text-warm-gray-900 font-medium' : 'text-warm-gray-400'
              }`}
            >
              {label}
            </span>
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
      <div className="h-8 bg-cream-300 rounded w-64 mb-6" />
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-5 bg-cream-300 rounded w-32 mb-4" />
        <div className="h-10 bg-cream-300 rounded w-full mb-6" />
        <div className="h-5 bg-cream-300 rounded w-40 mb-4" />
        <div className="h-10 bg-cream-300 rounded w-full" />
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

/** Cluster statuses that have completed content (POP briefs exist). */
const COMPLETED_CONTENT_STATUSES = new Set(['approved', 'content_generating', 'complete']);

interface ClusterOption {
  id: string;
  name: string;
  seed_keyword: string;
  status: string;
  eligible: boolean;
  reason: string | null;
}

function buildClusterOptions(
  clusters: ClusterListItem[],
  campaigns: BlogCampaignListItem[],
): ClusterOption[] {
  const campaignClusterNames = new Set(campaigns.map(c => c.cluster_name));

  return clusters.map((cluster) => {
    const hasCompleted = COMPLETED_CONTENT_STATUSES.has(cluster.status);
    const hasCampaign = campaignClusterNames.has(cluster.name);

    let eligible = true;
    let reason: string | null = null;

    if (hasCampaign) {
      eligible = false;
      reason = 'Already has a blog campaign';
    } else if (!hasCompleted) {
      eligible = false;
      reason = `Content not ready (${cluster.status.replace(/_/g, ' ')})`;
    }

    return {
      id: cluster.id,
      name: cluster.name,
      seed_keyword: cluster.seed_keyword,
      status: cluster.status,
      eligible,
      reason,
    };
  });
}

export default function NewBlogCampaignPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [selectedClusterId, setSelectedClusterId] = useState('');
  const [campaignName, setCampaignName] = useState('');
  const [clusterError, setClusterError] = useState<string | null>(null);
  const [progressStep, setProgressStep] = useState(0);

  const { data: project, isLoading: projectLoading, error: projectError } = useProject(projectId);
  const { data: clusters, isLoading: clustersLoading } = useClusters(projectId);
  const { data: campaigns, isLoading: campaignsLoading } = useBlogCampaigns(projectId);
  const createBlogCampaign = useCreateBlogCampaign();

  const isLoading = projectLoading || clustersLoading || campaignsLoading;

  const clusterOptions = useMemo(
    () => buildClusterOptions(clusters ?? [], campaigns ?? []),
    [clusters, campaigns],
  );

  const eligibleOptions = useMemo(
    () => clusterOptions.filter(o => o.eligible),
    [clusterOptions],
  );

  const ineligibleOptions = useMemo(
    () => clusterOptions.filter(o => !o.eligible),
    [clusterOptions],
  );

  const validate = useCallback((): boolean => {
    if (!selectedClusterId) {
      setClusterError('Please select a cluster');
      return false;
    }
    setClusterError(null);
    return true;
  }, [selectedClusterId]);

  const handleSubmit = useCallback(() => {
    if (!validate()) return;

    setProgressStep(0);

    // Advance progress steps on a timer to show activity during ~10-30s API call
    const timer1 = setTimeout(() => setProgressStep(1), 4000);
    const timer2 = setTimeout(() => setProgressStep(2), 9000);
    const timer3 = setTimeout(() => setProgressStep(3), 15000);

    createBlogCampaign.mutate(
      {
        projectId,
        data: {
          cluster_id: selectedClusterId,
          name: campaignName.trim() || undefined,
        },
      },
      {
        onSuccess: (data) => {
          clearTimeout(timer1);
          clearTimeout(timer2);
          clearTimeout(timer3);
          router.push(`/projects/${projectId}/blogs/${data.id}`);
        },
        onError: () => {
          clearTimeout(timer1);
          clearTimeout(timer2);
          clearTimeout(timer3);
        },
      },
    );
  }, [validate, selectedClusterId, campaignName, projectId, createBlogCampaign, router]);

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
        <span className="text-warm-gray-900">New Blog Campaign</span>
      </nav>

      {/* Page title */}
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-6">
        Create Blog Campaign
      </h1>

      {/* Form card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {createBlogCampaign.isPending ? (
          <ProgressIndicator currentStep={progressStep} />
        ) : createBlogCampaign.isError ? (
          <div>
            <div className="mb-6 p-4 bg-coral-50 border border-coral-200 rounded-sm">
              <p className="text-sm font-medium text-coral-800 mb-1">
                Something went wrong
              </p>
              <p className="text-sm text-coral-700">
                {createBlogCampaign.error?.message || 'An unexpected error occurred. Please try again.'}
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <Link href={`/projects/${projectId}`}>
                <Button variant="secondary">Cancel</Button>
              </Link>
              <Button onClick={handleSubmit}>
                Try Again
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="space-y-5">
              {/* Cluster dropdown */}
              <div>
                <label
                  htmlFor="cluster-select"
                  className="block text-sm font-medium text-warm-gray-700 mb-1.5"
                >
                  Parent Cluster <span className="text-coral-500">*</span>
                </label>
                <select
                  id="cluster-select"
                  value={selectedClusterId}
                  onChange={(e) => {
                    setSelectedClusterId(e.target.value);
                    if (clusterError) setClusterError(null);
                  }}
                  className={`w-full rounded-sm border px-3 py-2 text-sm text-warm-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-palm-400 focus:border-palm-400 ${
                    clusterError
                      ? 'border-coral-400'
                      : 'border-sand-500'
                  }`}
                >
                  <option value="">Select a cluster...</option>
                  {eligibleOptions.length > 0 && (
                    <optgroup label="Available">
                      {eligibleOptions.map((opt) => (
                        <option key={opt.id} value={opt.id}>
                          {opt.name || opt.seed_keyword}
                        </option>
                      ))}
                    </optgroup>
                  )}
                  {ineligibleOptions.length > 0 && (
                    <optgroup label="Unavailable">
                      {ineligibleOptions.map((opt) => (
                        <option key={opt.id} value={opt.id} disabled>
                          {opt.name || opt.seed_keyword} — {opt.reason}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
                {clusterError && (
                  <p className="mt-1.5 text-xs text-coral-500">{clusterError}</p>
                )}
                {eligibleOptions.length === 0 && !clustersLoading && (
                  <p className="mt-1.5 text-xs text-warm-gray-500">
                    No eligible clusters found. Clusters need approved content before creating a blog campaign.
                  </p>
                )}
              </div>

              {/* Campaign name */}
              <div>
                <Input
                  label="Campaign Name (optional)"
                  placeholder="Defaults to cluster name if left blank"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                />
                <p className="mt-1.5 text-xs text-warm-gray-500">
                  Defaults to cluster name if left blank
                </p>
              </div>
            </div>

            <hr className="border-cream-300 my-6" />

            <div className="flex justify-end gap-3">
              <Link href={`/projects/${projectId}`}>
                <Button variant="secondary">Cancel</Button>
              </Link>
              <Button
                onClick={handleSubmit}
                disabled={!selectedClusterId}
              >
                Discover Topics
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
