'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
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
        <div className="h-32 bg-cream-300 rounded" />
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
      <p className="text-warm-gray-600 mb-6">The project you&apos;re looking for doesn&apos;t exist.</p>
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

// --- Helper: shorten page title ---

function shortTitle(title: string): string {
  // Strip common suffixes like " – Brand Name | Tagline"
  const cleaned = title.split(/\s*[–—|]\s*/)[0].trim();
  return cleaned || title;
}

// --- Helper: shorten URL for display ---

function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.pathname === '/' ? u.hostname : u.pathname;
  } catch {
    return url;
  }
}

// --- Label color palette ---

const LABEL_COLORS = [
  { bg: 'bg-palm-50', border: 'border-palm-200', text: 'text-palm-700', badge: 'bg-palm-100 text-palm-700 border-palm-300' },
  { bg: 'bg-lagoon-50', border: 'border-lagoon-200', text: 'text-lagoon-700', badge: 'bg-lagoon-100 text-lagoon-700 border-lagoon-300' },
  { bg: 'bg-coral-50', border: 'border-coral-200', text: 'text-coral-700', badge: 'bg-coral-100 text-coral-700 border-coral-300' },
  { bg: 'bg-cream-100', border: 'border-cream-400', text: 'text-warm-gray-700', badge: 'bg-cream-200 text-warm-gray-700 border-cream-400' },
  { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', badge: 'bg-amber-100 text-amber-700 border-amber-300' },
  { bg: 'bg-indigo-50', border: 'border-indigo-200', text: 'text-indigo-700', badge: 'bg-indigo-100 text-indigo-700 border-indigo-300' },
];

// --- Build label groups ---

interface LabelGroup {
  label: string;
  pages: LinkMapPage[];
  colorIdx: number;
}

function buildLabelGroups(pages: LinkMapPage[]): LabelGroup[] {
  const groupMap = new Map<string, LinkMapPage[]>();
  for (const page of pages) {
    const primaryLabel = page.labels?.[0] ?? 'unlabeled';
    const existing = groupMap.get(primaryLabel);
    if (existing) {
      existing.push(page);
    } else {
      groupMap.set(primaryLabel, [page]);
    }
  }

  return Array.from(groupMap.entries())
    .map(([label, groupPages], idx) => ({
      label,
      pages: groupPages,
      colorIdx: idx % LABEL_COLORS.length,
    }))
    .sort((a, b) => b.pages.length - a.pages.length);
}

// --- Main page component ---

export default function OnboardingLinkMapPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');
  const [showReplanConfirm, setShowReplanConfirm] = useState(false);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: linkMap, isLoading: isMapLoading } = useLinkMap(projectId, 'onboarding');
  const planLinksMutation = usePlanLinks();

  const isLoading = isProjectLoading || isMapLoading;

  const labelGroups = useMemo(
    () => linkMap?.pages ? buildLabelGroups(linkMap.pages) : [],
    [linkMap?.pages]
  );

  // Build a label color map so we can color-code target references
  const labelColorMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const group of labelGroups) {
      map.set(group.label, group.colorIdx);
    }
    return map;
  }, [labelGroups]);

  // Map page_id → primary label for coloring target links
  const pageToLabel = useMemo(() => {
    const map = new Map<string, string>();
    if (linkMap?.pages) {
      for (const page of linkMap.pages) {
        map.set(page.page_id, page.labels?.[0] ?? 'unlabeled');
      }
    }
    return map;
  }, [linkMap?.pages]);

  // Map URL → page_id for target matching
  const urlToPageId = useMemo(() => {
    const map = new Map<string, string>();
    if (linkMap?.pages) {
      for (const page of linkMap.pages) {
        map.set(page.url, page.page_id);
      }
    }
    return map;
  }, [linkMap?.pages]);

  const handleReplan = async () => {
    try {
      await planLinksMutation.mutateAsync({ projectId, scope: 'onboarding' });
      setShowReplanConfirm(false);
      setToastMessage('Link re-planning started. You will be redirected when complete.');
      setToastVariant('success');
      setShowToast(true);
      router.push(`/projects/${projectId}/links`);
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

  if (projectError || !project) {
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
        <span className="text-warm-gray-900">Link Map</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
            Link Map
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
            Run link planning to generate the internal linking structure.
          </p>
          <Link href={`/projects/${projectId}/links`}>
            <Button>Plan Links</Button>
          </Link>
        </div>
      )}

      {/* Grouped link map */}
      {hasLinks && linkMap && (
        <div className="space-y-6">
          {labelGroups.map((group) => {
            const colors = LABEL_COLORS[group.colorIdx];
            return (
              <div key={group.label} className={`rounded-sm border ${colors.border} overflow-hidden`}>
                {/* Group header */}
                <div className={`px-4 py-2.5 ${colors.bg} border-b ${colors.border} flex items-center justify-between`}>
                  <div className="flex items-center gap-2">
                    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-semibold rounded-sm border ${colors.badge}`}>
                      {group.label}
                    </span>
                    <span className="text-xs text-warm-gray-500">
                      {group.pages.length} {group.pages.length === 1 ? 'page' : 'pages'}
                    </span>
                  </div>
                  <span className="text-xs text-warm-gray-500">
                    {group.pages.reduce((sum, p) => sum + p.outbound_count, 0)} outbound links
                  </span>
                </div>

                {/* Pages in this group */}
                <div className="divide-y divide-cream-200 bg-white">
                  {group.pages.map((page) => (
                    <div key={page.page_id} className="px-4 py-3">
                      {/* Page header row */}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 min-w-0">
                          {page.is_priority && (
                            <span className="text-palm-500 text-xs shrink-0" title="Priority page">&#9733;</span>
                          )}
                          <span className="text-sm font-medium text-warm-gray-900 truncate">
                            {shortTitle(page.title)}
                          </span>
                          <span className="text-xs text-warm-gray-400 truncate hidden sm:inline">
                            {shortUrl(page.url)}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-warm-gray-500 shrink-0 ml-3">
                          <span title="Outbound">{page.outbound_count} out</span>
                          <span title="Inbound">{page.inbound_count} in</span>
                        </div>
                      </div>

                      {/* Outbound links list */}
                      {page.outbound_links.length > 0 ? (
                        <div className="ml-4 space-y-1">
                          {page.outbound_links.map((link, idx) => {
                            const targetPageId = urlToPageId.get(link.target_url);
                            const targetLabel = targetPageId ? pageToLabel.get(targetPageId) : undefined;
                            const targetColorIdx = targetLabel ? labelColorMap.get(targetLabel) : undefined;
                            const targetColors = targetColorIdx !== undefined ? LABEL_COLORS[targetColorIdx] : null;

                            return (
                              <div key={idx} className="flex items-baseline gap-2 text-sm">
                                <span className="text-warm-gray-400 shrink-0">&rarr;</span>
                                <span className="font-medium text-lagoon-700">
                                  &ldquo;{link.anchor_text}&rdquo;
                                </span>
                                <span className="text-warm-gray-400 shrink-0">&rarr;</span>
                                <span className="text-warm-gray-600 truncate" title={link.target_url}>
                                  {shortTitle(link.target_title) || shortUrl(link.target_url)}
                                </span>
                                {targetColors && targetLabel !== group.label && (
                                  <span className={`inline-flex items-center px-1.5 py-0 text-[10px] rounded-sm border ${targetColors.badge} shrink-0`}>
                                    {targetLabel}
                                  </span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="ml-4 text-xs text-warm-gray-400 italic">
                          No outbound links
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Back button */}
      <div className="flex justify-start mt-6">
        <Link href={`/projects/${projectId}`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Project
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
