'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useCluster } from '@/hooks/useClusters';
import { useLinkMap, usePlanLinks } from '@/hooks/useLinks';
import { Button, Toast } from '@/components/ui';
import type { LinkMapPage } from '@/lib/api';

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

// --- Loading / Error states ---

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
      <p className="text-warm-gray-600 mb-6">The project or cluster you&apos;re looking for doesn&apos;t exist.</p>
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

// --- Helpers ---

function shortTitle(title: string): string {
  const cleaned = title.split(/\s*[–—|]\s*/)[0].trim();
  return cleaned || title;
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.pathname === '/' ? u.hostname : u.pathname;
  } catch {
    return url;
  }
}

// --- Page card with outbound links ---

function PageCard({ page, isParent }: { page: LinkMapPage; isParent: boolean }) {
  return (
    <div className={`px-4 py-3 ${isParent ? 'bg-palm-50/30' : ''}`}>
      {/* Page header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {isParent && (
            <span className="text-palm-500 text-xs shrink-0" title="Parent page">&#9733;</span>
          )}
          <span className="text-sm font-medium text-warm-gray-900 truncate">
            {shortTitle(page.title)}
          </span>
          <span className="text-xs text-warm-gray-400 truncate hidden sm:inline">
            {shortUrl(page.url)}
          </span>
          {isParent && (
            <span className="inline-flex items-center px-1.5 py-0 text-[10px] font-medium rounded-sm bg-palm-100 text-palm-700 border border-palm-200">
              parent
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-warm-gray-500 shrink-0 ml-3">
          <span title="Outbound">{page.outbound_count} out</span>
          <span title="Inbound">{page.inbound_count} in</span>
        </div>
      </div>

      {/* Outbound links */}
      {page.outbound_links.length > 0 ? (
        <div className="ml-4 space-y-1">
          {page.outbound_links.map((link, idx) => (
            <div key={idx} className="flex items-baseline gap-2 text-sm">
              <span className="text-warm-gray-400 shrink-0">&rarr;</span>
              <span className="font-medium text-lagoon-700">
                &ldquo;{link.anchor_text}&rdquo;
              </span>
              <span className="text-warm-gray-400 shrink-0">&rarr;</span>
              <span className="text-warm-gray-600 truncate" title={link.target_url}>
                {shortTitle(link.target_title) || shortUrl(link.target_url)}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="ml-4 text-xs text-warm-gray-400 italic">No outbound links</div>
      )}
    </div>
  );
}

// --- Main page component ---

export default function ClusterLinkMapPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const clusterId = params.clusterId as string;

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');
  const [showReplanConfirm, setShowReplanConfirm] = useState(false);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: cluster, isLoading: isClusterLoading } = useCluster(projectId, clusterId);
  const { data: linkMap, isLoading: isMapLoading } = useLinkMap(projectId, 'cluster', clusterId);
  const planLinksMutation = usePlanLinks();

  const isLoading = isProjectLoading || isClusterLoading || isMapLoading;

  // Split pages into parent + children
  const { parentPage, childPages } = useMemo(() => {
    if (!linkMap?.pages) return { parentPage: null, childPages: [] };
    const parent = linkMap.pages.find((p) => p.role === 'parent') ?? null;
    const children = linkMap.pages.filter((p) => p.role !== 'parent');
    return { parentPage: parent, childPages: children };
  }, [linkMap?.pages]);

  const handleReplan = async () => {
    try {
      await planLinksMutation.mutateAsync({ projectId, scope: 'cluster', clusterId });
      setShowReplanConfirm(false);
      setToastMessage('Link re-planning started. You will be redirected when complete.');
      setToastVariant('success');
      setShowToast(true);
      router.push(`/projects/${projectId}/clusters/${clusterId}/links`);
    } catch (error) {
      setShowReplanConfirm(false);
      const message = error instanceof Error ? error.message : 'Failed to start re-planning';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    }
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

  if (projectError || !project || !cluster) {
    return (
      <div>
        <Link href="/" className="inline-flex items-center text-warm-gray-600 hover:text-warm-gray-900 mb-6 text-sm">
          <BackArrowIcon className="w-4 h-4 mr-1" />All Projects
        </Link>
        <NotFoundState />
      </div>
    );
  }

  const hasLinks = linkMap && linkMap.total_links > 0;

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
        <span className="text-warm-gray-900">Link Map</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
            Link Map &mdash; {cluster.name}
          </h1>
          {hasLinks && linkMap && (
            <p className="text-sm text-warm-gray-600">
              {linkMap.total_links} links across {linkMap.total_pages} pages &middot; {linkMap.avg_links_per_page.toFixed(1)} avg per page
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
            Run link planning to generate the internal linking structure for this cluster.
          </p>
          <Link href={`/projects/${projectId}/clusters/${clusterId}/links`}>
            <Button>Plan Links</Button>
          </Link>
        </div>
      )}

      {/* Link map grouped by parent / children */}
      {hasLinks && linkMap && (
        <div className="space-y-6">
          {/* Parent section */}
          {parentPage && (
            <div className="rounded-sm border border-palm-200 overflow-hidden">
              <div className="px-4 py-2.5 bg-palm-50 border-b border-palm-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-sm border bg-palm-100 text-palm-700 border-palm-300">
                    Parent Page
                  </span>
                </div>
                <span className="text-xs text-warm-gray-500">
                  {parentPage.outbound_count} outbound links
                </span>
              </div>
              <div className="bg-white">
                <PageCard page={parentPage} isParent />
              </div>
            </div>
          )}

          {/* Children section */}
          {childPages.length > 0 && (
            <div className="rounded-sm border border-cream-400 overflow-hidden">
              <div className="px-4 py-2.5 bg-cream-50 border-b border-cream-400 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-sm border bg-cream-200 text-warm-gray-700 border-cream-400">
                    Child Pages
                  </span>
                  <span className="text-xs text-warm-gray-500">
                    {childPages.length} {childPages.length === 1 ? 'page' : 'pages'}
                  </span>
                </div>
                <span className="text-xs text-warm-gray-500">
                  {childPages.reduce((sum, p) => sum + p.outbound_count, 0)} outbound links
                </span>
              </div>
              <div className="divide-y divide-cream-200 bg-white">
                {childPages.map((page) => (
                  <PageCard key={page.page_id} page={page} isParent={false} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Back button */}
      <div className="flex justify-start mt-6">
        <Link href={`/projects/${projectId}/clusters/${clusterId}`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Cluster
          </Button>
        </Link>
      </div>

      {/* Re-plan confirmation dialog */}
      {showReplanConfirm && (
        <ConfirmDialog
          title="Re-plan Links"
          message="This will replace all current links. Previous plan will be saved as a snapshot."
          confirmLabel="Re-plan Links"
          onConfirm={handleReplan}
          onCancel={() => setShowReplanConfirm(false)}
          isPending={planLinksMutation.isPending}
        />
      )}

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
