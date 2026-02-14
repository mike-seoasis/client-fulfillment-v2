'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  useBlogCampaign,
  useBlogLinkMap,
} from '@/hooks/useBlogs';
import { Button } from '@/components/ui';
import type { BlogPost, BlogLinkMapItem } from '@/lib/api';

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
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" className="animate-spin origin-center" />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="15" y1="9" x2="9" y2="15" />
      <line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  );
}

function LinkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
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

// --- Loading / error states ---

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="h-6 bg-cream-300 rounded w-72 mb-2" />
      <div className="h-4 bg-cream-300 rounded w-96 mb-8" />
      <div className="space-y-4">
        <div className="h-32 bg-cream-300 rounded" />
        <div className="h-48 bg-cream-300 rounded" />
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
      <h1 className="text-2xl font-semibold text-warm-gray-900 mb-2">Not Found</h1>
      <p className="text-warm-gray-600 mb-6">The blog campaign you&apos;re looking for doesn&apos;t exist.</p>
      <Link href="/"><Button>Back to Dashboard</Button></Link>
    </div>
  );
}

// --- Confirmation dialog ---

function ConfirmDialog({
  title, message, confirmLabel, onConfirm, onCancel, isPending,
}: {
  title: string; message: string; confirmLabel: string;
  onConfirm: () => void; onCancel: () => void; isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-warm-gray-900/40" onClick={onCancel} />
      <div className="relative bg-white rounded-sm border border-cream-500 shadow-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-warm-gray-900 mb-2">{title}</h3>
        <p className="text-sm text-warm-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel} disabled={isPending}>Cancel</Button>
          <Button variant="danger" onClick={onConfirm} disabled={isPending}>
            {isPending ? (
              <><SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />Re-planning...</>
            ) : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- Aggregated data types ---

interface ClusterTarget {
  targetPageId: string;
  keyword: string;
  url: string | null;
  inboundCount: number;
}

interface BlogPostWithLinks {
  post: BlogPost;
  links: BlogLinkMapItem[];
}

/** Hook to fetch link maps for all eligible posts and aggregate */
function useAggregatedBlogLinkMap(
  projectId: string,
  blogId: string,
  posts: BlogPost[]
) {
  // Fetch link map for each eligible post
  const postResults = posts.map((post) => {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const result = useBlogLinkMap(projectId, blogId, post.id, {
      enabled: !!projectId && !!blogId && !!post.id,
    });
    return { post, result };
  });

  const isLoading = postResults.some((r) => r.result.isLoading);

  // Build aggregated cluster targets and blog post links
  const aggregated = useMemo(() => {
    const clusterTargetMap = new Map<string, ClusterTarget>();
    const blogPostLinks: BlogPostWithLinks[] = [];

    for (const { post, result } of postResults) {
      if (!result.data) continue;

      const links = result.data.links || [];
      blogPostLinks.push({ post, links });

      // Count inbound links per target (cluster pages)
      for (const link of links) {
        const existing = clusterTargetMap.get(link.target_page_id);
        if (existing) {
          existing.inboundCount += 1;
        } else {
          clusterTargetMap.set(link.target_page_id, {
            targetPageId: link.target_page_id,
            keyword: link.target_keyword ?? link.anchor_text,
            url: link.target_url,
            inboundCount: 1,
          });
        }
      }
    }

    const clusterTargets = Array.from(clusterTargetMap.values()).sort(
      (a, b) => b.inboundCount - a.inboundCount
    );

    const totalLinks = blogPostLinks.reduce((sum, bp) => sum + bp.links.length, 0);
    const totalPosts = blogPostLinks.filter((bp) => bp.links.length > 0).length;
    const avgLinksPerPost = totalPosts > 0 ? totalLinks / totalPosts : 0;

    return { clusterTargets, blogPostLinks, totalLinks, totalPosts, avgLinksPerPost };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postResults.map((r) => r.result.data).join(',')]);

  return { ...aggregated, isLoading };
}

// --- Main page component ---

export default function BlogLinkMapPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const blogId = params.blogId as string;

  const [showReplanConfirm, setShowReplanConfirm] = useState(false);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: campaign, isLoading: isCampaignLoading } = useBlogCampaign(projectId, blogId);

  // Eligible posts for link map
  const eligiblePosts = useMemo(() => {
    if (!campaign?.posts) return [];
    return campaign.posts.filter(
      (p) => p.is_approved && p.content_status === 'complete'
    );
  }, [campaign?.posts]);

  const {
    clusterTargets,
    blogPostLinks,
    totalLinks,
    totalPosts,
    avgLinksPerPost,
    isLoading: isMapLoading,
  } = useAggregatedBlogLinkMap(projectId, blogId, eligiblePosts);

  const isLoading = isProjectLoading || isCampaignLoading || isMapLoading;
  const hasLinks = totalLinks > 0;

  const handleReplan = async () => {
    // Re-plan triggers link planning for all eligible posts sequentially
    // Navigate to links planning page which handles the orchestration
    setShowReplanConfirm(false);
    router.push(`/projects/${projectId}/blogs/${blogId}/links`);
  };

  if (isLoading) {
    return (
      <div>
        <Link href="/" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
          <BackArrowIcon className="w-4 h-4 mr-1" />All Projects
        </Link>
        <LoadingSkeleton />
      </div>
    );
  }

  if (projectError || !project || !campaign) {
    return (
      <div>
        <Link href="/" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
          <BackArrowIcon className="w-4 h-4 mr-1" />All Projects
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
        <Link href={`/projects/${projectId}/blogs/${blogId}`} className="hover:text-warm-gray-900">
          {campaign.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900">Link Map</span>
      </nav>

      {/* Step indicator */}
      <StepIndicator currentStep="links" />

      {/* Header with stats */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
            Link Map &mdash; {campaign.name}
          </h1>
          {hasLinks && (
            <p className="text-sm text-warm-gray-600">
              {totalLinks} links across {totalPosts} posts &middot; {avgLinksPerPost.toFixed(1)} avg per post
            </p>
          )}
        </div>
        {hasLinks && (
          <Button variant="secondary" onClick={() => setShowReplanConfirm(true)}>
            Re-plan Links
          </Button>
        )}
      </div>

      {/* Empty state */}
      {!hasLinks && (
        <div className="bg-white rounded-sm border border-cream-500 p-12 shadow-sm text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cream-100 mb-4">
            <LinkIcon className="w-8 h-8 text-warm-gray-400" />
          </div>
          <h2 className="text-lg font-semibold text-warm-gray-900 mb-2">No links planned yet</h2>
          <p className="text-sm text-warm-gray-600 mb-6">
            Run link planning to generate the internal linking structure for these blog posts.
          </p>
          <Link href={`/projects/${projectId}/blogs/${blogId}/links`}>
            <Button>Plan Links</Button>
          </Link>
        </div>
      )}

      {/* Link map content */}
      {hasLinks && (
        <div className="space-y-6">
          {/* Cluster Pages (Targets) section */}
          {clusterTargets.length > 0 && (
            <div className="rounded-sm border border-palm-200 overflow-hidden">
              <div className="px-4 py-2.5 bg-palm-50 border-b border-palm-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-sm border bg-palm-100 text-palm-700 border-palm-300">
                    Cluster Pages
                  </span>
                  <span className="text-xs text-warm-gray-500">
                    Link targets &middot; {clusterTargets.length} {clusterTargets.length === 1 ? 'page' : 'pages'}
                  </span>
                </div>
                <span className="text-xs text-warm-gray-500">
                  {clusterTargets.reduce((sum, t) => sum + t.inboundCount, 0)} inbound links
                </span>
              </div>
              <div className="divide-y divide-cream-200 bg-white">
                {clusterTargets.map((target) => (
                  <div key={target.targetPageId} className="px-4 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-palm-500 text-xs shrink-0">&#9650;</span>
                      <span className="text-sm font-medium text-warm-gray-900 truncate">
                        {target.keyword}
                      </span>
                      {target.url && (
                        <span className="text-xs text-warm-gray-400 truncate hidden sm:inline">
                          {target.url}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-warm-gray-500 shrink-0 ml-3">
                      {target.inboundCount} inbound
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Blog Posts (Outbound Links) section */}
          {blogPostLinks.length > 0 && (
            <div className="rounded-sm border border-cream-400 overflow-hidden">
              <div className="px-4 py-2.5 bg-cream-50 border-b border-cream-400 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-sm border bg-cream-200 text-warm-gray-700 border-cream-400">
                    Blog Posts
                  </span>
                  <span className="text-xs text-warm-gray-500">
                    {blogPostLinks.length} {blogPostLinks.length === 1 ? 'post' : 'posts'}
                  </span>
                </div>
                <span className="text-xs text-warm-gray-500">
                  {totalLinks} outbound links
                </span>
              </div>
              <div className="divide-y divide-cream-200 bg-white">
                {blogPostLinks.map(({ post, links }) => (
                  <div key={post.id} className="px-4 py-3">
                    {/* Post header */}
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-warm-gray-900 truncate">
                        {post.primary_keyword}
                      </span>
                      <span className="text-xs text-warm-gray-500 shrink-0 ml-3">
                        {links.length} {links.length === 1 ? 'link' : 'links'}
                      </span>
                    </div>

                    {/* Outbound links */}
                    {links.length > 0 ? (
                      <div className="ml-4 space-y-1">
                        {links.map((link, idx) => (
                          <div key={idx} className="flex items-baseline gap-2 text-sm">
                            <span className="text-warm-gray-400 shrink-0">&rarr;</span>
                            <span className="font-medium text-lagoon-700">
                              &ldquo;{link.anchor_text}&rdquo;
                            </span>
                            <span className="text-warm-gray-400 shrink-0">&rarr;</span>
                            <span className="text-warm-gray-600 truncate" title={link.target_url ?? undefined}>
                              {link.target_keyword ?? link.target_url ?? 'Unknown target'}
                            </span>
                            <span className="text-xs text-warm-gray-400 shrink-0">
                              ({link.placement_method === 'rule_based' ? 'rule' : 'LLM'})
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="ml-4 text-xs text-warm-gray-400 italic">No outbound links</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Bottom navigation */}
      <div className="flex justify-between mt-6">
        <Link href={`/projects/${projectId}/blogs/${blogId}/content`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Content
          </Button>
        </Link>
        {hasLinks && (
          <Link href={`/projects/${projectId}/blogs/${blogId}/export`}>
            <Button>
              Continue to Export &rarr;
            </Button>
          </Link>
        )}
      </div>

      {/* Re-plan confirmation dialog */}
      {showReplanConfirm && (
        <ConfirmDialog
          title="Re-plan Links"
          message="This will replace all current links across all blog posts. You'll be taken to the link planning page."
          confirmLabel="Re-plan Links"
          onConfirm={handleReplan}
          onCancel={() => setShowReplanConfirm(false)}
          isPending={false}
        />
      )}

    </div>
  );
}
