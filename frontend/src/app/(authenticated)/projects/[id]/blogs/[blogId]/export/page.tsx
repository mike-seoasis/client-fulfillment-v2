'use client';

import { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useBlogCampaign,
  useBlogExport,
  useDownloadBlogPostHtml,
} from '@/hooks/useBlogs';
import { Button, Toast } from '@/components/ui';
import type { BlogExportItem } from '@/lib/api';

// Blog workflow steps (shared with other blog pages)
const BLOG_STEPS = [
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

function CopyIcon({ className }: { className?: string }) {
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
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
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
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
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
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

// --- Step indicator (same as other blog pages) ---

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
            <div key={i} className="h-32 bg-cream-300 rounded w-full" />
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

// --- Export post card ---

function ExportPostCard({
  post,
  projectId,
  blogId,
  onCopied,
}: {
  post: BlogExportItem;
  projectId: string;
  blogId: string;
  onCopied: (keyword: string) => void;
}) {
  const [copyState, setCopyState] = useState(false);
  const downloadMutation = useDownloadBlogPostHtml();

  const wordCount = post.word_count;
  const truncatedMeta = post.meta_description
    ? post.meta_description.length > 120
      ? post.meta_description.slice(0, 120) + '...'
      : post.meta_description
    : null;

  const handleCopyHtml = useCallback(async () => {
    if (!post.html_content) return;
    try {
      await navigator.clipboard.writeText(post.html_content);
      setCopyState(true);
      onCopied(post.primary_keyword);
      setTimeout(() => setCopyState(false), 2000);
    } catch {
      // Clipboard API unavailable
    }
  }, [post.html_content, post.primary_keyword, onCopied]);

  const handleDownload = useCallback(() => {
    downloadMutation.mutate({ projectId, blogId, postId: post.post_id });
  }, [downloadMutation, projectId, blogId, post.post_id]);

  return (
    <div className="bg-white rounded-sm border border-cream-500 p-5 shadow-sm">
      {/* Header: keyword + slug + word count */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <FileIcon className="w-4 h-4 text-palm-500 flex-shrink-0" />
            <h3 className="text-sm font-semibold text-warm-gray-900 truncate">
              {post.primary_keyword}
            </h3>
          </div>
          <p className="text-xs text-warm-gray-500 font-mono truncate">
            /{post.url_slug}
          </p>
        </div>
        <span className="text-xs text-warm-gray-500 flex-shrink-0 ml-3">
          {wordCount.toLocaleString()} words
        </span>
      </div>

      {/* Title & Meta */}
      {post.title && (
        <div className="mb-2">
          <p className="text-xs text-warm-gray-500 mb-0.5">Title</p>
          <p className="text-sm text-warm-gray-800 select-all">{post.title}</p>
        </div>
      )}
      {truncatedMeta && (
        <div className="mb-3">
          <p className="text-xs text-warm-gray-500 mb-0.5">Meta Description</p>
          <p className="text-sm text-warm-gray-700 select-all">{truncatedMeta}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-3 border-t border-cream-300">
        <button
          type="button"
          onClick={handleCopyHtml}
          disabled={!post.html_content}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm transition-colors bg-palm-50 text-palm-700 hover:bg-palm-100 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {copyState ? (
            <>
              <CheckIcon className="w-3.5 h-3.5" />
              Copied!
            </>
          ) : (
            <>
              <CopyIcon className="w-3.5 h-3.5" />
              Copy HTML
            </>
          )}
        </button>
        <button
          type="button"
          onClick={handleDownload}
          disabled={!post.html_content || downloadMutation.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm transition-colors bg-sand-200 text-warm-gray-700 hover:bg-sand-300 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <DownloadIcon className="w-3.5 h-3.5" />
          Download .html
        </button>
      </div>
    </div>
  );
}

// --- Unapproved post row (grayed out) ---

function UnapprovedPostRow({ keyword, slug }: { keyword: string; slug: string }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-cream-100 rounded-sm opacity-60">
      <FileIcon className="w-4 h-4 text-warm-gray-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-warm-gray-500 truncate">{keyword}</p>
        <p className="text-xs text-warm-gray-400 font-mono truncate">/{slug}</p>
      </div>
      <span className="text-xs text-warm-gray-400">Not approved</span>
    </div>
  );
}

// --- Main export page ---

export default function BlogExportPage() {
  const params = useParams();
  const projectId = params.id as string;
  const blogId = params.blogId as string;

  const { data: project, isLoading: projectLoading } = useProject(projectId);
  const { data: campaign, isLoading: campaignLoading } = useBlogCampaign(projectId, blogId);
  const { data: exportItems, isLoading: exportLoading } = useBlogExport(projectId, blogId);

  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Separate approved export items from unapproved posts
  const { approvedPosts, unapprovedPosts, totalPostCount } = useMemo(() => {
    const approved = exportItems ?? [];
    const allPosts = campaign?.posts ?? [];
    const exportedIds = new Set(approved.map((p) => p.post_id));
    const unapproved = allPosts.filter((p) => !exportedIds.has(p.id));
    return {
      approvedPosts: approved,
      unapprovedPosts: unapproved,
      totalPostCount: allPosts.length,
    };
  }, [exportItems, campaign?.posts]);

  // Toast for per-post copy
  const handlePostCopied = useCallback((keyword: string) => {
    setToastMessage(`Copied HTML for "${keyword}"`);
  }, []);

  // Copy All HTML with separators
  const handleCopyAllHtml = useCallback(async () => {
    if (!approvedPosts.length) return;
    const combined = approvedPosts
      .map((post) => `<!-- POST: ${post.primary_keyword} -->\n${post.html_content ?? ''}`)
      .join('\n\n');
    try {
      await navigator.clipboard.writeText(combined);
      setToastMessage(`Copied all ${approvedPosts.length} posts to clipboard`);
    } catch {
      // Clipboard API unavailable
    }
  }, [approvedPosts]);

  // Loading state
  if (projectLoading || campaignLoading || exportLoading) {
    return <LoadingSkeleton />;
  }

  // Not found states
  if (!project) {
    return <NotFoundState message="Project not found." />;
  }
  if (!campaign) {
    return <NotFoundState message="Blog campaign not found." />;
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
        <span className="text-warm-gray-900">Export</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="export" />

      {/* Divider */}
      <hr className="border-cream-500 mb-6" />

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-warm-gray-900 mb-1">
          Export Blog Posts
        </h1>
        <p className="text-sm text-warm-gray-600">
          Copy HTML to paste into Shopify, or download as files
        </p>
      </div>

      {/* Ready count */}
      <div className="mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-palm-50 rounded-sm">
          <CheckIcon className="w-4 h-4 text-palm-600" />
          <span className="text-sm font-medium text-palm-700">
            Ready to export: {approvedPosts.length} of {totalPostCount} posts approved
          </span>
        </div>
      </div>

      {/* Approved post cards */}
      {approvedPosts.length > 0 ? (
        <div className="space-y-3 mb-6">
          {approvedPosts.map((post) => (
            <ExportPostCard
              key={post.post_id}
              post={post}
              projectId={projectId}
              blogId={blogId}
              onCopied={handlePostCopied}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-sm border border-cream-500 p-8 text-center mb-6">
          <p className="text-warm-gray-600 mb-2">No approved posts ready for export.</p>
          <p className="text-sm text-warm-gray-500">
            Approve blog post content on the{' '}
            <Link
              href={`/projects/${projectId}/blogs/${blogId}/content`}
              className="text-lagoon-600 hover:text-lagoon-700 underline"
            >
              Content
            </Link>{' '}
            step before exporting.
          </p>
        </div>
      )}

      {/* Unapproved posts (grayed out) */}
      {unapprovedPosts.length > 0 && (
        <div className="mb-6">
          <p className="text-xs text-warm-gray-500 uppercase tracking-wide mb-2">
            Unapproved ({unapprovedPosts.length})
          </p>
          <div className="space-y-1.5">
            {unapprovedPosts.map((post) => (
              <UnapprovedPostRow
                key={post.id}
                keyword={post.primary_keyword}
                slug={post.url_slug}
              />
            ))}
          </div>
        </div>
      )}

      {/* Bottom bar */}
      <div className="flex justify-between items-center mt-8 pt-6 border-t border-cream-300">
        <Link href={`/projects/${projectId}/blogs/${blogId}/links/map`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back
          </Button>
        </Link>
        {approvedPosts.length > 0 && (
          <button
            type="button"
            onClick={handleCopyAllHtml}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-sm bg-palm-500 text-white hover:bg-palm-600 transition-colors"
          >
            <CopyIcon className="w-4 h-4" />
            Copy All HTML
          </button>
        )}
      </div>

      {/* Toast */}
      {toastMessage && (
        <Toast
          message={toastMessage}
          variant="success"
          onClose={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
