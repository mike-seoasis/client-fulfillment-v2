'use client';

import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useBlogCampaign,
  useBlogContentStatus,
  useTriggerBlogContentGeneration,
  useBulkApproveBlogContent,
  useApproveBlogPostContent,
} from '@/hooks/useBlogs';
import { Button, Toast } from '@/components/ui';
import type { BlogPostGenerationStatusItem, BlogPost } from '@/lib/api';

// Blog workflow steps (same as keywords page)
const BLOG_STEPS = [
  { key: 'keywords', label: 'Keywords' },
  { key: 'content', label: 'Content' },
  { key: 'review', label: 'Review' },
  { key: 'export', label: 'Export' },
] as const;

// Pipeline step definitions for per-post status indicator
const PIPELINE_STEPS = [
  { key: 'brief', label: 'Brief' },
  { key: 'write', label: 'Write' },
  { key: 'links', label: 'Links' },
  { key: 'check', label: 'Check' },
  { key: 'done', label: 'Done' },
] as const;

/** Map backend content_status to step index (0-3 for Brief/Write/Links/Check) */
function getContentStep(status: string): number {
  switch (status) {
    case 'pending':
      return -1;
    case 'generating_brief':
      return 0;
    case 'generating':
      return 0; // backward compat
    case 'writing':
      return 1;
    case 'linking':
      return 2;
    case 'checking':
      return 3;
    case 'complete':
      return 4; // past all steps
    case 'failed':
      return -2;
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
    case 'generating':
      return 'Generating brief...'; // backward compat
    case 'writing':
      return 'Writing content...';
    case 'linking':
      return 'Planning links...';
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

function WarningIcon({ className }: { className?: string }) {
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
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
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

// --- Step indicator (same as keywords page) ---

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

// --- Loading skeleton ---

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
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-20 bg-cream-300 rounded w-full" />
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
        <XCircleIcon className="w-8 h-8 text-coral-500" />
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

// --- Pipeline indicator: Brief → Write → Check → Done ---

function PipelineIndicator({ status }: { status: string }) {
  const contentStep = getContentStep(status);
  const isFailed = status === 'failed';

  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, index) => {
        const isComplete = contentStep > index;
        const isCurrent = contentStep === index;

        let dotClass = 'bg-cream-300';
        let labelClass = 'text-warm-gray-400';

        if (isFailed) {
          if (contentStep > index) {
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

// --- Post row in the generation progress table ---

function PostRow({
  post,
  isGenerating,
}: {
  post: BlogPostGenerationStatusItem;
  isGenerating: boolean;
}) {
  const isFailed = post.content_status === 'failed';
  const isComplete = post.content_status === 'complete';

  return (
    <div className={`px-4 py-3 ${isFailed ? 'bg-coral-50/50' : ''}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-warm-gray-900 truncate">
            {post.primary_keyword}
          </p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className={`text-xs ${
              isFailed ? 'text-coral-600' :
              isComplete ? 'text-palm-600' :
              post.content_status === 'pending' && !isGenerating ? 'text-warm-gray-500' :
              'text-lagoon-600'
            }`}>
              {getStatusLabel(post.content_status)}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <PipelineIndicator status={post.content_status} />
          <div className="flex items-center gap-1">
            {isComplete && (
              <span className="inline-flex items-center gap-1 text-xs text-palm-600 px-2 py-1">
                <CheckIcon className="w-3.5 h-3.5" />
                Done
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Helper: count words in HTML content ---
function countWords(html: string | null): number {
  if (!html) return 0;
  const text = html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  return text ? text.split(' ').length : 0;
}

// --- Review table: Needs Review / Approved tabs ---

function ReviewTable({
  posts,
  projectId,
  blogId,
  onApproveToggle,
  isApproving,
}: {
  posts: BlogPost[];
  projectId: string;
  blogId: string;
  onApproveToggle: (postId: string, value: boolean) => void;
  isApproving: boolean;
}) {
  const [activeTab, setActiveTab] = useState<'review' | 'approved'>('review');

  // Split posts into review (unapproved content) and approved content
  const completedPosts = posts.filter((p) => p.content_status === 'complete');
  const reviewPosts = completedPosts.filter((p) => !p.content_approved);
  const approvedPosts = completedPosts.filter((p) => p.content_approved);

  const visiblePosts = activeTab === 'review' ? reviewPosts : approvedPosts;

  return (
    <div className="border border-cream-500 rounded-sm overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-cream-500 bg-cream-50">
        <button
          type="button"
          onClick={() => setActiveTab('review')}
          className={`flex items-center gap-2 px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'review'
              ? 'border-palm-500 text-palm-700 bg-white'
              : 'border-transparent text-warm-gray-500 hover:text-warm-gray-700'
          }`}
        >
          Needs Review
          {reviewPosts.length > 0 && (
            <span className={`text-xs font-mono px-1.5 py-0.5 rounded-sm ${
              activeTab === 'review' ? 'bg-coral-100 text-coral-700' : 'bg-cream-200 text-warm-gray-500'
            }`}>
              {reviewPosts.length}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('approved')}
          className={`flex items-center gap-2 px-5 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'approved'
              ? 'border-palm-500 text-palm-700 bg-white'
              : 'border-transparent text-warm-gray-500 hover:text-warm-gray-700'
          }`}
        >
          Approved
          {approvedPosts.length > 0 && (
            <span className={`text-xs font-mono px-1.5 py-0.5 rounded-sm ${
              activeTab === 'approved' ? 'bg-palm-100 text-palm-700' : 'bg-cream-200 text-warm-gray-500'
            }`}>
              {approvedPosts.length}
            </span>
          )}
        </button>
      </div>

      {/* Table header */}
      <div className="grid grid-cols-[1fr_80px_100px_120px_80px] gap-4 px-4 py-2.5 bg-cream-100 border-b border-cream-500 text-xs font-medium text-warm-gray-600 uppercase tracking-wide">
        <div>Topic Keyword</div>
        <div className="text-center">Words</div>
        <div className="text-center">QA Status</div>
        <div className="text-center">Approval</div>
        <div className="text-center">Action</div>
      </div>

      {/* Table body */}
      <div className="max-h-[28rem] overflow-y-auto divide-y divide-cream-300">
        {visiblePosts.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-warm-gray-500">
            {activeTab === 'review'
              ? 'All posts have been approved!'
              : 'No posts approved yet.'}
          </div>
        )}
        {visiblePosts.map((post) => {
          const wordCount = countWords(post.content);
          const qaPassed = post.qa_results?.passed as boolean | undefined;
          const qaIssueCount = Array.isArray(post.qa_results?.issues)
            ? (post.qa_results!.issues as unknown[]).length
            : 0;

          return (
            <div
              key={post.id}
              className="grid grid-cols-[1fr_80px_100px_120px_80px] gap-4 px-4 py-3 items-center hover:bg-cream-50 transition-colors"
            >
              {/* Topic Keyword */}
              <p className="text-sm text-warm-gray-900 truncate">
                {post.primary_keyword}
              </p>

              {/* Word Count */}
              <p className="text-sm text-warm-gray-700 text-center font-mono">
                {wordCount > 0 ? wordCount.toLocaleString() : '\u2014'}
              </p>

              {/* QA Status */}
              <div className="flex justify-center">
                {qaPassed === true && (
                  <CheckIcon className="w-4 h-4 text-palm-500" />
                )}
                {qaPassed === false && (
                  <span className="inline-flex items-center gap-1 text-xs text-coral-600">
                    <WarningIcon className="w-4 h-4" />
                    {qaIssueCount}
                  </span>
                )}
                {qaPassed == null && (
                  <span className="text-xs text-warm-gray-400">&mdash;</span>
                )}
              </div>

              {/* Content Approval toggle */}
              <div className="flex justify-center">
                <button
                  type="button"
                  onClick={() => onApproveToggle(post.id, !post.content_approved)}
                  disabled={isApproving}
                  className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-sm transition-colors ${
                    post.content_approved
                      ? 'bg-palm-100 text-palm-700 hover:bg-palm-200'
                      : 'bg-cream-200 text-warm-gray-600 hover:bg-cream-300'
                  }`}
                >
                  {post.content_approved ? (
                    <>
                      <CheckIcon className="w-3 h-3" />
                      Approved
                    </>
                  ) : (
                    'Pending'
                  )}
                </button>
              </div>

              {/* Edit link */}
              <div className="flex justify-center">
                <Link
                  href={`/projects/${projectId}/blogs/${blogId}/content/${post.id}`}
                  className="text-xs font-medium text-lagoon-600 hover:text-lagoon-700 hover:underline"
                >
                  Edit
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// --- Main page component ---

export default function BlogContentPage() {
  const params = useParams();
  const projectId = params.id as string;
  const blogId = params.blogId as string;

  // Toast state
  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  const handleShowToast = useCallback((message: string, variant: 'success' | 'error') => {
    setToastMessage(message);
    setToastVariant(variant);
    setShowToast(true);
  }, []);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: campaign, isLoading: isCampaignLoading, error: campaignError } = useBlogCampaign(projectId, blogId);
  const { data: contentStatus, isLoading: isStatusLoading } = useBlogContentStatus(projectId, blogId);
  const triggerGeneration = useTriggerBlogContentGeneration();
  const bulkApproveContent = useBulkApproveBlogContent();
  const approvePostContent = useApproveBlogPostContent();

  // Auto-trigger link planning after generation completes
  const prevOverallStatusRef = useRef<string | undefined>(undefined);

  const isLoading = isProjectLoading || isCampaignLoading || isStatusLoading;

  // Derive generation state from content status
  const isGenerating = contentStatus?.overall_status === 'generating';
  const postsTotal = contentStatus?.posts_total ?? 0;
  const postsCompleted = contentStatus?.posts_completed ?? 0;
  const postsFailed = contentStatus?.posts_failed ?? 0;
  const progress = postsTotal > 0 ? Math.round((postsCompleted / postsTotal) * 100) : 0;

  // Derive states for UI
  const approvedPosts = useMemo(
    () => campaign?.posts?.filter((p) => p.is_approved) ?? [],
    [campaign?.posts]
  );
  const hasApprovedPosts = approvedPosts.length > 0;

  const allContentDone = postsTotal > 0 && postsCompleted + postsFailed >= postsTotal && !isGenerating;
  const isIdle = !isGenerating && postsCompleted === 0 && postsFailed === 0;
  const isComplete = allContentDone && postsFailed === 0;
  const isFailed = allContentDone && postsFailed > 0;

  // Posts with complete content for the review table
  const completePosts = useMemo(
    () => campaign?.posts?.filter((p) => p.content_status === 'complete') ?? [],
    [campaign?.posts]
  );
  const contentApprovedCount = completePosts.filter((p) => p.content_approved).length;

  // Watch for generation completion to show toast
  useEffect(() => {
    const prev = prevOverallStatusRef.current;
    const curr = contentStatus?.overall_status;
    prevOverallStatusRef.current = curr;

    if (prev === 'generating' && curr === 'complete') {
      handleShowToast('Content generation complete', 'success');
    }
  }, [contentStatus?.overall_status, handleShowToast]);

  // Handle trigger generation
  const handleGenerate = async () => {
    try {
      await triggerGeneration.mutateAsync({ projectId, blogId });
      handleShowToast('Content generation started', 'success');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start content generation';
      handleShowToast(message, 'error');
    }
  };

  // Handle regenerate (force refresh all posts)
  const handleRegenerate = async () => {
    try {
      await triggerGeneration.mutateAsync({ projectId, blogId, forceRefresh: true });
      handleShowToast('Regenerating all content...', 'success');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to start regeneration';
      handleShowToast(message, 'error');
    }
  };

  // Handle content approval toggle
  const handleApproveToggle = useCallback(
    (postId: string, value: boolean) => {
      approvePostContent.mutate(
        { projectId, blogId, postId, value },
        {
          onError: (err) => {
            handleShowToast(err.message || 'Failed to update approval', 'error');
          },
        }
      );
    },
    [approvePostContent, projectId, blogId, handleShowToast]
  );

  // Handle bulk approve
  const handleBulkApprove = async () => {
    try {
      const result = await bulkApproveContent.mutateAsync({ projectId, blogId });
      handleShowToast(`Approved ${result.approved_count} post${result.approved_count === 1 ? '' : 's'}`, 'success');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to bulk approve';
      handleShowToast(message, 'error');
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
        <Link href={`/projects/${projectId}/blogs/${blogId}`} className="hover:text-warm-gray-900">
          {campaign.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Content</span>
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
              ? `Generating content for ${postsTotal} posts...`
              : isComplete
              ? 'Content Generation Complete'
              : isFailed
              ? 'Content Generation Complete'
              : `${approvedPosts.length} Approved Posts`}
          </h2>

          {/* Generate / Retry buttons */}
          {(isIdle || (!isGenerating && !allContentDone)) && hasApprovedPosts && (
            <Button
              onClick={handleGenerate}
              disabled={triggerGeneration.isPending}
            >
              {triggerGeneration.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Starting...
                </>
              ) : (
                'Generate Content'
              )}
            </Button>
          )}
          {isFailed && (
            <Button
              onClick={handleGenerate}
              disabled={triggerGeneration.isPending}
            >
              {triggerGeneration.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Retrying...
                </>
              ) : (
                `Retry ${postsFailed} Failed`
              )}
            </Button>
          )}
          {allContentDone && !isGenerating && (
            <Button
              variant="secondary"
              onClick={handleRegenerate}
              disabled={triggerGeneration.isPending}
            >
              {triggerGeneration.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                  Regenerating...
                </>
              ) : (
                'Regenerate Content'
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
                  {postsCompleted} of {postsTotal} complete
                </span>
              </div>
              <span className="font-medium text-lagoon-600">{progress}%</span>
            </div>
            <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-palm-500 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Completion summary */}
        {allContentDone && !isGenerating && (
          <div className="mb-4 flex items-center gap-4 text-sm">
            {postsCompleted > 0 && (
              <span className="inline-flex items-center gap-1.5 text-palm-700">
                <CheckIcon className="w-4 h-4" />
                {postsCompleted} posts complete
              </span>
            )}
            {postsFailed > 0 && (
              <span className="inline-flex items-center gap-1.5 text-coral-600">
                <XCircleIcon className="w-4 h-4" />
                {postsFailed} posts failed
              </span>
            )}
          </div>
        )}

        {/* Idle state - no approved posts */}
        {isIdle && !hasApprovedPosts && (
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
            <h3 className="text-lg font-medium text-warm-gray-900 mb-1">No Approved Topics</h3>
            <p className="text-warm-gray-600 text-sm">
              Approve topics in the keywords step before generating content.
            </p>
          </div>
        )}

        {/* Posts table - generation progress view */}
        {(isGenerating || (isIdle && hasApprovedPosts) || (!isGenerating && !allContentDone && postsTotal > 0)) && contentStatus?.posts && (
          <div className="border border-cream-500 rounded-sm overflow-hidden">
            <div className="max-h-[28rem] overflow-y-auto divide-y divide-cream-300">
              {contentStatus.posts.map((post) => (
                <PostRow
                  key={post.post_id}
                  post={post}
                  isGenerating={isGenerating}
                />
              ))}
            </div>
          </div>
        )}

        {/* Review table - shown after generation */}
        {allContentDone && !isGenerating && completePosts.length > 0 && (
          <ReviewTable
            posts={completePosts}
            projectId={projectId}
            blogId={blogId}
            onApproveToggle={handleApproveToggle}
            isApproving={approvePostContent.isPending}
          />
        )}

        <hr className="border-cream-500 my-6" />

        {/* Summary + actions for review state */}
        {allContentDone && !isGenerating && completePosts.length > 0 && (
          <div className="flex items-center justify-between mb-6">
            <p className="text-sm text-warm-gray-700">
              Content approved: <span className="font-semibold text-warm-gray-900">{contentApprovedCount} of {completePosts.length}</span>
            </p>
            <div className="flex items-center gap-3">
              {(() => {
                const eligibleCount = completePosts.filter(
                  (p) => (p.qa_results?.passed as boolean | undefined) === true && !p.content_approved
                ).length;
                return (
                  <Button
                    variant="secondary"
                    onClick={handleBulkApprove}
                    disabled={eligibleCount === 0 || bulkApproveContent.isPending}
                  >
                    {bulkApproveContent.isPending ? (
                      <>
                        <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                        Approving...
                      </>
                    ) : (
                      `Approve All Ready${eligibleCount > 0 ? ` (${eligibleCount})` : ''}`
                    )}
                  </Button>
                );
              })()}
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between items-center">
          <Link href={`/projects/${projectId}/blogs/${blogId}`}>
            <Button variant="secondary">
              <BackArrowIcon className="w-4 h-4 mr-1.5" />
              Back to Keywords
            </Button>
          </Link>
          <div className="flex items-center gap-3">
            {allContentDone && !isGenerating && contentApprovedCount > 0 && (
              <Link href={`/projects/${projectId}/blogs/${blogId}/export`}>
                <Button>
                  Continue &rarr;
                </Button>
              </Link>
            )}
            {allContentDone && !isGenerating && contentApprovedCount === 0 && (
              <Button disabled title="Approve at least 1 post to continue">
                Continue &rarr;
              </Button>
            )}
            {isGenerating && (
              <Button disabled>
                Generating...
              </Button>
            )}
          </div>
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
