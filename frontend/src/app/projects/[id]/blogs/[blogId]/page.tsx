'use client';

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useCluster } from '@/hooks/useClusters';
import {
  useBlogCampaign,
  useUpdateBlogPost,
  useBulkApproveBlogPosts,
  useDeleteBlogCampaign,
} from '@/hooks/useBlogs';
import { Button, Toast } from '@/components/ui';
import type { BlogPost } from '@/lib/api';

// Blog workflow steps
const BLOG_STEPS = [
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'links', label: 'Links' },
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

// --- Step indicator ---

function StepIndicator({ currentStep }: { currentStep: string }) {
  const currentIndex = BLOG_STEPS.findIndex((s) => s.key === currentStep);

  return (
    <div className="mb-8">
      <p className="text-sm text-warm-gray-600 mb-3">
        Step {currentIndex + 1} of {BLOG_STEPS.length}: {BLOG_STEPS[currentIndex].label}
      </p>
      <div className="flex items-center gap-1">
        {BLOG_STEPS.map((step, index) => (
          <div key={step.key} className="flex items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                index <= currentIndex ? 'bg-palm-500' : 'bg-cream-300'
              }`}
            />
            {index < BLOG_STEPS.length - 1 && (
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
        {BLOG_STEPS.map((step, index) => (
          <div
            key={step.key}
            className={`text-xs ${
              index === 0 ? 'text-left' : index === BLOG_STEPS.length - 1 ? 'text-right' : 'text-center'
            } ${
              index <= currentIndex ? 'text-palm-700' : 'text-warm-gray-400'
            }`}
            style={{ width: index === BLOG_STEPS.length - 1 ? 'auto' : '60px' }}
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

// --- Blog post row ---

function BlogPostRow({
  post,
  projectId,
  blogId,
  sourcePageKeyword,
  onShowToast,
}: {
  post: BlogPost;
  projectId: string;
  blogId: string;
  sourcePageKeyword: string | null;
  onShowToast: (message: string, variant: 'success' | 'error') => void;
}) {
  const updatePost = useUpdateBlogPost();

  const handleToggleApproval = useCallback(() => {
    updatePost.mutate(
      {
        projectId,
        blogId,
        postId: post.id,
        data: { is_approved: !post.is_approved },
      },
      {
        onError: (err) => {
          onShowToast(err.message || 'Failed to update approval', 'error');
        },
      }
    );
  }, [updatePost, projectId, blogId, post.id, post.is_approved, onShowToast]);

  const handleKeywordSave = useCallback(
    (newKeyword: string) => {
      updatePost.mutate(
        {
          projectId,
          blogId,
          postId: post.id,
          data: { primary_keyword: newKeyword },
        },
        {
          onError: (err) => {
            onShowToast(err.message || 'Failed to update keyword', 'error');
          },
        }
      );
    },
    [updatePost, projectId, blogId, post.id, onShowToast]
  );

  const handleSlugSave = useCallback(
    (newSlug: string) => {
      updatePost.mutate(
        {
          projectId,
          blogId,
          postId: post.id,
          data: { url_slug: newSlug },
        },
        {
          onError: (err) => {
            onShowToast(err.message || 'Failed to update URL slug', 'error');
          },
        }
      );
    },
    [updatePost, projectId, blogId, post.id, onShowToast]
  );

  const formatVolume = (vol: number | null) => {
    if (vol == null) return '—';
    return vol.toLocaleString();
  };

  return (
    <div className="px-4 py-3 flex items-center gap-3 hover:bg-cream-50">
      {/* Approve checkbox */}
      <ApproveToggle isApproved={post.is_approved} onToggle={handleToggleApproval} />

      {/* Keyword (editable) */}
      <div className="flex-1 min-w-0">
        <InlineEditableCell
          value={post.primary_keyword}
          onSave={handleKeywordSave}
          className="text-sm font-medium text-warm-gray-900 max-w-[300px] truncate"
        />
        {/* URL slug (editable) */}
        <div className="flex items-center gap-1 mt-0.5">
          <span className="text-xs text-warm-gray-400 flex-shrink-0">/</span>
          <InlineEditableCell
            value={post.url_slug}
            onSave={handleSlugSave}
            className="text-xs text-warm-gray-500 font-mono max-w-[300px] truncate"
          />
        </div>
      </div>

      {/* Source Page */}
      <div className="w-36 flex-shrink-0">
        {sourcePageKeyword ? (
          <p className="text-sm text-warm-gray-600 truncate" title={sourcePageKeyword}>
            {sourcePageKeyword}
          </p>
        ) : (
          <p className="text-sm text-warm-gray-400">—</p>
        )}
      </div>

      {/* Volume */}
      <div className="text-right w-16 flex-shrink-0">
        <p className="text-sm text-warm-gray-900 font-medium">{formatVolume(post.search_volume)}</p>
        <p className="text-xs text-warm-gray-400">Vol</p>
      </div>
    </div>
  );
}

// --- Main page component ---

export default function BlogKeywordsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const blogId = params.blogId as string;

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
  const { data: campaign, isLoading: isCampaignLoading, error: campaignError } = useBlogCampaign(projectId, blogId);
  const { data: cluster } = useCluster(projectId, campaign?.cluster_id ?? '', {
    enabled: !!campaign?.cluster_id,
  });
  const bulkApprove = useBulkApproveBlogPosts();
  const deleteCampaignMutation = useDeleteBlogCampaign();

  const isLoading = isProjectLoading || isCampaignLoading;

  // Build lookup from cluster page ID to keyword for the "Source Page" column
  const sourcePageLookup = useMemo(() => {
    if (!cluster?.pages) return new Map<string, string>();
    const map = new Map<string, string>();
    for (const page of cluster.pages) {
      map.set(page.id, page.keyword);
    }
    return map;
  }, [cluster?.pages]);

  // Sort posts by search_volume descending (nulls last)
  const sortedPosts = useMemo(
    () =>
      campaign?.posts
        ? [...campaign.posts].sort((a, b) => {
            return (b.search_volume ?? -1) - (a.search_volume ?? -1);
          })
        : [],
    [campaign?.posts]
  );

  const approvedCount = sortedPosts.filter((p) => p.is_approved).length;
  const totalPosts = sortedPosts.length;
  const hasApprovedPosts = approvedCount > 0;

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

  const handleShowToast = useCallback((message: string, variant: 'success' | 'error') => {
    setToastMessage(message);
    setToastVariant(variant);
    setShowToast(true);
  }, []);

  const handleDeleteCampaign = useCallback(() => {
    if (!isDeleteConfirming) {
      setIsDeleteConfirming(true);
      return;
    }
    deleteCampaignMutation.mutate(
      { projectId, blogId },
      {
        onSuccess: () => {
          router.push(`/projects/${projectId}`);
        },
        onError: (err) => {
          setIsDeleteConfirming(false);
          handleShowToast(err.message || 'Failed to delete campaign', 'error');
        },
      }
    );
  }, [isDeleteConfirming, deleteCampaignMutation, projectId, blogId, router, handleShowToast]);

  const handleDeleteBlur = useCallback((e: React.FocusEvent) => {
    if (!deleteButtonRef.current?.contains(e.relatedTarget as Node)) {
      setIsDeleteConfirming(false);
    }
  }, []);

  // Approve all unapproved posts
  const handleApproveAll = useCallback(() => {
    if (!campaign) return;
    const unapproved = sortedPosts.filter((p) => !p.is_approved);
    if (unapproved.length === 0) return;

    bulkApprove.mutate(
      { projectId, blogId },
      {
        onSuccess: (data) => {
          handleShowToast(`${data.approved_count} topics approved`, 'success');
        },
        onError: (err) => {
          handleShowToast(err.message || 'Failed to approve topics', 'error');
        },
      }
    );
  }, [campaign, sortedPosts, bulkApprove, projectId, blogId, handleShowToast]);

  // Generate Content — navigate to content step
  const handleGenerateContent = useCallback(() => {
    router.push(`/projects/${projectId}/blogs/${blogId}/content`);
  }, [projectId, blogId, router]);

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

  // Campaign not found
  if (campaignError || !campaign) {
    return (
      <div>
        <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
          <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
            <BackArrowIcon className="w-4 h-4 mr-1" />
            {project.name}
          </Link>
        </nav>
        <NotFoundState message="The blog campaign you're looking for doesn't exist or has been deleted." />
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
        <span className="text-warm-gray-900">{campaign.name}</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="keywords" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Main content card */}
      <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm">
        {/* Header */}
        <div className="flex items-start justify-between mb-1">
          <div>
            <h2 className="text-lg font-semibold text-warm-gray-900">
              {campaign.name}
            </h2>
            <p className="text-sm text-warm-gray-500 mt-0.5">
              Blog topics discovered from cluster analysis
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={handleApproveAll}
            disabled={approvedCount === totalPosts || bulkApprove.isPending}
          >
            {bulkApprove.isPending ? 'Approving...' : 'Approve All'}
          </Button>
        </div>

        {/* Summary stats */}
        <div className="flex gap-4 text-sm mb-4 mt-3">
          <span className="text-warm-gray-600">
            <span className="font-medium text-warm-gray-900">{totalPosts}</span> topics
          </span>
          <span className="text-warm-gray-600">
            <span className="font-medium text-palm-600">{approvedCount}</span> approved
          </span>
          <span className="text-warm-gray-600">
            <span className="font-medium text-lagoon-600">{totalPosts - approvedCount}</span> pending
          </span>
        </div>

        {/* Column headers */}
        <div className="border border-cream-500 rounded-sm overflow-hidden">
          <div className="px-4 py-2 bg-cream-50 border-b border-cream-300 flex items-center gap-3 text-xs font-medium text-warm-gray-500 uppercase tracking-wide">
            <div className="w-6 flex-shrink-0" />
            <div className="flex-1 min-w-0">Topic Keyword</div>
            <div className="w-36 flex-shrink-0">Source Page</div>
            <div className="text-right w-16 flex-shrink-0">Volume</div>
          </div>

          {/* Post rows */}
          <div className="divide-y divide-cream-300">
            {sortedPosts.map((post) => (
              <BlogPostRow
                key={post.id}
                post={post}
                projectId={projectId}
                blogId={blogId}
                sourcePageKeyword={post.source_page_id ? (sourcePageLookup.get(post.source_page_id) ?? null) : null}
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
            <Button
              ref={deleteButtonRef}
              variant="danger"
              onClick={handleDeleteCampaign}
              onBlur={handleDeleteBlur}
              disabled={deleteCampaignMutation.isPending}
            >
              {deleteCampaignMutation.isPending
                ? 'Deleting...'
                : isDeleteConfirming
                ? 'Confirm Delete'
                : 'Delete Campaign'}
            </Button>
          </div>

          <div className="relative">
            <Button
              onClick={handleGenerateContent}
              disabled={!hasApprovedPosts}
              onMouseEnter={() => !hasApprovedPosts && setShowGenerateTooltip(true)}
              onMouseLeave={() => setShowGenerateTooltip(false)}
            >
              Generate Content &rarr;
            </Button>
            {showGenerateTooltip && !hasApprovedPosts && (
              <div
                className="absolute z-50 px-3 py-2 text-sm bg-warm-gray-800 text-white rounded-sm shadow-lg whitespace-nowrap"
                style={{
                  bottom: 'calc(100% + 8px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                }}
              >
                Approve at least one topic to continue
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
