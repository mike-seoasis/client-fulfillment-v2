'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useCluster,
  useUpdateClusterPage,
  useBulkApproveCluster,
  useDeleteCluster,
} from '@/hooks/useClusters';
import { Button, Toast } from '@/components/ui';
import type { ClusterPage } from '@/lib/api';

// Cluster workflow steps
const CLUSTER_STEPS = [
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'review', label: 'Review' },
  { key: 'export', label: 'Export' },
] as const;

// --- Icon components ---

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

// --- Step indicator ---

function StepIndicator({ currentStep }: { currentStep: string }) {
  const currentIndex = CLUSTER_STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {CLUSTER_STEPS.length}: {CLUSTER_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {CLUSTER_STEPS.map((step, index) => (
          <div key={step.key} className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                index <= currentIndex ? 'bg-palm-500' : 'bg-cream-300'
              }`}
            />
            {index < CLUSTER_STEPS.length - 1 && (
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
        {CLUSTER_STEPS.map((step, index) => (
          <div
            key={step.key}
            className={`text-xs ${
              index === 0 ? 'text-left' : index === CLUSTER_STEPS.length - 1 ? 'text-right' : 'text-center'
            } ${
              index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
            }`}
            style={{ width: index === CLUSTER_STEPS.length - 1 ? 'auto' : '60px' }}
          >
            {step.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Skeleton ---

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="mb-8">
        <div className="h-4 bg-cream-300 rounded w-32 mb-3" />
        <div className="flex items-center gap-1">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center">
              <div className="w-3 h-3 rounded-full bg-cream-300" />
              {i < 3 && <div className="w-12 h-0.5 bg-cream-300" />}
            </div>
          ))}
        </div>
      </div>
      <div className="bg-white rounded-sm border border-cream-500 p-6">
        <div className="h-6 bg-cream-300 rounded w-48 mb-4" />
        <div className="h-4 bg-cream-300 rounded w-full mb-6" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-cream-300 rounded w-full" />
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Not Found ---

function NotFoundState({ message }: { message: string }) {
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
        Not Found
      </h1>
      <p className="text-warm-gray-600 mb-6">{message}</p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

// --- Inline editable cell ---

function InlineEditableCell({
  value,
  onSave,
  className,
}: {
  value: string;
  onSave: (newValue: string) => void;
  className?: string;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleStartEdit = () => {
    setEditValue(value);
    setIsEditing(true);
    // Focus after render
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== value) {
      onSave(trimmed);
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSave();
    } else if (e.key === 'Escape') {
      setIsEditing(false);
    }
  };

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        type="text"
        value={editValue}
        onChange={(e) => setEditValue(e.target.value)}
        onBlur={handleSave}
        onKeyDown={handleKeyDown}
        className={`px-2 py-1 border border-palm-400 rounded-sm text-sm bg-white focus:outline-none focus:ring-1 focus:ring-palm-400 ${className ?? ''}`}
      />
    );
  }

  return (
    <button
      type="button"
      onClick={handleStartEdit}
      className={`text-left cursor-pointer hover:bg-cream-100 px-2 py-1 rounded-sm transition-colors ${className ?? ''}`}
      title="Click to edit"
    >
      {value}
    </button>
  );
}

// --- Role badge ---

function RoleBadge({ role }: { role: string }) {
  const isParent = role === 'parent';
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm ${
        isParent
          ? 'bg-palm-50 text-palm-700 border border-palm-200'
          : 'bg-cream-100 text-warm-gray-600 border border-cream-300'
      }`}
    >
      {isParent ? 'Parent' : 'Child'}
    </span>
  );
}

// --- Approve toggle ---

function ApproveToggle({
  isApproved,
  onToggle,
}: {
  isApproved: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`w-6 h-6 rounded-sm border-2 flex items-center justify-center transition-colors ${
        isApproved
          ? 'bg-palm-500 border-palm-500 text-white'
          : 'border-warm-gray-300 hover:border-palm-400'
      }`}
      title={isApproved ? 'Click to reject' : 'Click to approve'}
    >
      {isApproved && <CheckIcon className="w-4 h-4" />}
    </button>
  );
}

// --- Cluster page row ---

function ClusterPageRow({
  page,
  projectId,
  clusterId,
  isParentRow,
  onShowToast,
}: {
  page: ClusterPage;
  projectId: string;
  clusterId: string;
  isParentRow: boolean;
  onShowToast: (message: string, variant: 'success' | 'error') => void;
}) {
  const updatePage = useUpdateClusterPage();

  const handleToggleApproval = useCallback(() => {
    updatePage.mutate(
      {
        projectId,
        clusterId,
        pageId: page.id,
        data: { is_approved: !page.is_approved },
      },
      {
        onError: (err) => {
          onShowToast(err.message || 'Failed to update approval', 'error');
        },
      }
    );
  }, [updatePage, projectId, clusterId, page.id, page.is_approved, onShowToast]);

  const handleKeywordSave = useCallback(
    (newKeyword: string) => {
      updatePage.mutate(
        {
          projectId,
          clusterId,
          pageId: page.id,
          data: { keyword: newKeyword },
        },
        {
          onError: (err) => {
            onShowToast(err.message || 'Failed to update keyword', 'error');
          },
        }
      );
    },
    [updatePage, projectId, clusterId, page.id, onShowToast]
  );

  const handleSlugSave = useCallback(
    (newSlug: string) => {
      updatePage.mutate(
        {
          projectId,
          clusterId,
          pageId: page.id,
          data: { url_slug: newSlug },
        },
        {
          onError: (err) => {
            onShowToast(err.message || 'Failed to update URL slug', 'error');
          },
        }
      );
    },
    [updatePage, projectId, clusterId, page.id, onShowToast]
  );

  const handleMakeParent = useCallback(() => {
    updatePage.mutate(
      {
        projectId,
        clusterId,
        pageId: page.id,
        data: { role: 'parent' },
      },
      {
        onSuccess: () => {
          onShowToast(`"${page.keyword}" is now the parent page`, 'success');
        },
        onError: (err) => {
          onShowToast(err.message || 'Failed to reassign parent', 'error');
        },
      }
    );
  }, [updatePage, projectId, clusterId, page.id, page.keyword, onShowToast]);

  const formatVolume = (vol: number | null) => {
    if (vol == null) return '—';
    return vol.toLocaleString();
  };

  const formatCPC = (cpc: number | null) => {
    if (cpc == null) return '—';
    return `$${cpc.toFixed(2)}`;
  };

  const formatScore = (score: number | null) => {
    if (score == null) return '—';
    return score.toFixed(1);
  };

  return (
    <div
      className={`px-4 py-3 flex items-center gap-3 ${
        isParentRow
          ? 'bg-palm-50/40 border-l-2 border-l-palm-500'
          : 'hover:bg-cream-50'
      }`}
    >
      {/* Approve checkbox */}
      <ApproveToggle isApproved={page.is_approved} onToggle={handleToggleApproval} />

      {/* Keyword (editable) */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <InlineEditableCell
            value={page.keyword}
            onSave={handleKeywordSave}
            className="text-sm font-medium text-warm-gray-900 max-w-[250px] truncate"
          />
          <RoleBadge role={page.role} />
          {page.expansion_strategy && (
            <span className="inline-flex items-center px-1.5 py-0.5 text-xs text-lagoon-700 bg-lagoon-50 border border-lagoon-200 rounded-sm">
              {page.expansion_strategy}
            </span>
          )}
        </div>
        {/* URL slug (editable) */}
        <div className="flex items-center gap-1 mt-0.5">
          <span className="text-xs text-warm-gray-400 flex-shrink-0">/</span>
          <InlineEditableCell
            value={page.url_slug}
            onSave={handleSlugSave}
            className="text-xs text-warm-gray-500 font-mono max-w-[250px] truncate"
          />
        </div>
      </div>

      {/* Volume */}
      <div className="text-right w-16 flex-shrink-0">
        <p className="text-sm text-warm-gray-900 font-medium">{formatVolume(page.search_volume)}</p>
        <p className="text-xs text-warm-gray-400">Vol</p>
      </div>

      {/* CPC */}
      <div className="text-right w-14 flex-shrink-0">
        <p className="text-sm text-warm-gray-900">{formatCPC(page.cpc)}</p>
        <p className="text-xs text-warm-gray-400">CPC</p>
      </div>

      {/* Competition */}
      <div className="text-right w-16 flex-shrink-0">
        <p className="text-sm text-warm-gray-900">{page.competition_level ?? '—'}</p>
        <p className="text-xs text-warm-gray-400">Comp</p>
      </div>

      {/* Composite Score */}
      <div className="text-right w-14 flex-shrink-0">
        <p className="text-sm text-warm-gray-900 font-medium">{formatScore(page.composite_score)}</p>
        <p className="text-xs text-warm-gray-400">Score</p>
      </div>

      {/* Make Parent action (only on child rows) */}
      <div className="w-20 flex-shrink-0 text-right">
        {page.role !== 'parent' && (
          <button
            type="button"
            onClick={handleMakeParent}
            className="text-xs text-lagoon-600 hover:text-lagoon-800 hover:underline"
          >
            Make Parent
          </button>
        )}
      </div>
    </div>
  );
}

// --- Main page component ---

export default function ClusterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const clusterId = params.clusterId as string;

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  // Tooltip state for Generate Content button
  const [showGenerateTooltip, setShowGenerateTooltip] = useState(false);

  // Delete confirmation state
  const [isDeleteConfirming, setIsDeleteConfirming] = useState(false);
  const deleteConfirmTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const deleteButtonRef = useRef<HTMLButtonElement>(null);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: cluster, isLoading: isClusterLoading, error: clusterError } = useCluster(projectId, clusterId);
  const updatePage = useUpdateClusterPage();
  const bulkApprove = useBulkApproveCluster();
  const deleteClusterMutation = useDeleteCluster();

  const isLoading = isProjectLoading || isClusterLoading;

  // Sort pages: parent first, then by composite_score descending
  const sortedPages = useMemo(
    () =>
      cluster?.pages
        ? [...cluster.pages].sort((a, b) => {
            if (a.role === 'parent' && b.role !== 'parent') return -1;
            if (a.role !== 'parent' && b.role === 'parent') return 1;
            return (b.composite_score ?? 0) - (a.composite_score ?? 0);
          })
        : [],
    [cluster?.pages]
  );

  const approvedCount = sortedPages.filter((p) => p.is_approved).length;
  const totalPages = sortedPages.length;
  const hasApprovedPages = approvedCount > 0;

  // Check if volume data was unavailable
  const volumeUnavailable =
    cluster?.generation_metadata &&
    (cluster.generation_metadata as Record<string, unknown>).volume_unavailable === true;

  // Reset delete confirmation after 3 seconds
  useEffect(() => {
    if (isDeleteConfirming) {
      deleteConfirmTimeoutRef.current = setTimeout(() => {
        setIsDeleteConfirming(false);
      }, 3000);
    }
    return () => {
      if (deleteConfirmTimeoutRef.current) {
        clearTimeout(deleteConfirmTimeoutRef.current);
      }
    };
  }, [isDeleteConfirming]);

  // Whether cluster can be deleted (only before approved)
  const canDelete = cluster
    ? !['approved', 'content_generating', 'complete'].includes(cluster.status)
    : false;

  const handleShowToast = useCallback((message: string, variant: 'success' | 'error') => {
    setToastMessage(message);
    setToastVariant(variant);
    setShowToast(true);
  }, []);

  const handleDeleteCluster = useCallback(() => {
    if (!isDeleteConfirming) {
      setIsDeleteConfirming(true);
      return;
    }
    deleteClusterMutation.mutate(
      { projectId, clusterId },
      {
        onSuccess: () => {
          router.push(`/projects/${projectId}`);
        },
        onError: (err) => {
          setIsDeleteConfirming(false);
          handleShowToast(err.message || 'Failed to delete cluster', 'error');
        },
      }
    );
  }, [isDeleteConfirming, deleteClusterMutation, projectId, clusterId, router, handleShowToast]);

  const handleDeleteBlur = useCallback((e: React.FocusEvent) => {
    if (!deleteButtonRef.current?.contains(e.relatedTarget as Node)) {
      setIsDeleteConfirming(false);
    }
  }, []);

  // Approve all suggestions
  const handleApproveAll = useCallback(() => {
    if (!cluster) return;
    const unapproved = sortedPages.filter((p) => !p.is_approved);
    if (unapproved.length === 0) return;

    // Optimistically approve each page
    for (const page of unapproved) {
      updatePage.mutate({
        projectId,
        clusterId,
        pageId: page.id,
        data: { is_approved: true },
      });
    }
    handleShowToast(`${unapproved.length} suggestions approved`, 'success');
  }, [cluster, sortedPages, updatePage, projectId, clusterId, handleShowToast]);

  // Generate Content (bulk approve then navigate)
  const handleGenerateContent = useCallback(() => {
    bulkApprove.mutate(
      { projectId, clusterId },
      {
        onSuccess: () => {
          router.push(`/projects/${projectId}/onboarding/content`);
        },
        onError: (err) => {
          handleShowToast(err.message || 'Failed to approve cluster', 'error');
        },
      }
    );
  }, [bulkApprove, projectId, clusterId, router, handleShowToast]);

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

  // Project not found
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
        <NotFoundState message="The project you're looking for doesn't exist or has been deleted." />
      </div>
    );
  }

  // Cluster not found
  if (clusterError || !cluster) {
    return (
      <div>
        <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
          <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
            <BackArrowIcon className="w-4 h-4 mr-1" />
            {project.name}
          </Link>
        </nav>
        <NotFoundState message="The cluster you're looking for doesn't exist or has been deleted." />
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
        <span className="text-warm-gray-900">{cluster.name}</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="keywords" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Volume unavailable warning */}
      {volumeUnavailable && (
        <div className="mb-4 p-3 bg-coral-50 border border-coral-200 rounded-sm flex items-start gap-2">
          <svg
            className="w-5 h-5 text-coral-500 flex-shrink-0 mt-0.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <p className="text-sm text-coral-700">
            Search volume data was unavailable during generation. Volume, CPC, and competition values may be missing.
          </p>
        </div>
      )}

      {/* Main content card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div>
            <h2 className="text-lg font-semibold text-warm-gray-900">
              {cluster.name}
            </h2>
            <p className="text-sm text-warm-gray-500 mt-0.5">
              Seed keyword: <span className="font-medium text-warm-gray-700">{cluster.seed_keyword}</span>
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={handleApproveAll}
            disabled={approvedCount === totalPages}
          >
            Approve All
          </Button>
        </div>

        {/* Summary stats */}
        <div className="flex gap-4 text-sm mb-4 mt-3">
          <span className="text-warm-gray-600">
            <span className="font-medium text-warm-gray-900">{totalPages}</span> suggestions
          </span>
          <span className="text-warm-gray-600">
            <span className="font-medium text-palm-600">{approvedCount}</span> approved
          </span>
          <span className="text-warm-gray-600">
            <span className="font-medium text-lagoon-600">{totalPages - approvedCount}</span> pending
          </span>
        </div>

        {/* Suggestions list */}
        <div className="border border-cream-500 rounded-sm overflow-hidden">
          <div className="divide-y divide-cream-300">
            {sortedPages.map((page) => (
              <ClusterPageRow
                key={page.id}
                page={page}
                projectId={projectId}
                clusterId={clusterId}
                isParentRow={page.role === 'parent'}
                onShowToast={handleShowToast}
              />
            ))}
          </div>
        </div>

        <hr className="border-cream-500 my-6" />

        {/* Actions */}
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}`}>
              <Button variant="secondary">
                <BackArrowIcon className="w-4 h-4 mr-1.5" />
                Back to Project
              </Button>
            </Link>
            {canDelete && (
              <Button
                ref={deleteButtonRef}
                variant="danger"
                onClick={handleDeleteCluster}
                onBlur={handleDeleteBlur}
                disabled={deleteClusterMutation.isPending}
              >
                {deleteClusterMutation.isPending
                  ? 'Deleting...'
                  : isDeleteConfirming
                  ? 'Confirm Delete'
                  : 'Delete Cluster'}
              </Button>
            )}
          </div>

          <div className="relative">
            <Button
              onClick={handleGenerateContent}
              disabled={!hasApprovedPages || bulkApprove.isPending}
              onMouseEnter={() => !hasApprovedPages && setShowGenerateTooltip(true)}
              onMouseLeave={() => setShowGenerateTooltip(false)}
            >
              {bulkApprove.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Approving...
                </>
              ) : (
                'Generate Content'
              )}
            </Button>
            {showGenerateTooltip && !hasApprovedPages && (
              <div
                className="absolute z-50 px-3 py-2 text-sm bg-warm-gray-800 text-white rounded-sm shadow-lg whitespace-nowrap"
                style={{
                  bottom: 'calc(100% + 8px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                }}
              >
                Approve at least one suggestion to continue
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
