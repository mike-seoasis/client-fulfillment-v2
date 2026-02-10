'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import { useCluster } from '@/hooks/useClusters';
import { useLinkMap, usePlanLinks } from '@/hooks/useLinks';
import { Button, Toast } from '@/components/ui';
import type { LinkMapPage } from '@/lib/api';

// --- Types for hierarchy data ---

interface HierarchyNode {
  page_id: string;
  keyword: string;
  role: string;
  url: string;
  title: string;
  outbound_count: number;
  inbound_count: number;
  children?: HierarchyNode[];
}

// --- Sort config ---

type SortKey = 'title' | 'role' | 'outbound_count' | 'inbound_count' | 'method' | 'validation_status';
type SortDir = 'asc' | 'desc';

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

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) {
    return (
      <svg className="w-3 h-3 text-warm-gray-300 ml-1 inline-block" viewBox="0 0 12 12" fill="currentColor">
        <path d="M6 2l3 4H3zM6 10l-3-4h6z" />
      </svg>
    );
  }
  return (
    <svg className="w-3 h-3 text-palm-600 ml-1 inline-block" viewBox="0 0 12 12" fill="currentColor">
      {dir === 'asc' ? <path d="M6 2l3 4H3z" /> : <path d="M6 10l-3-4h6z" />}
    </svg>
  );
}

// --- Loading skeleton ---

function LoadingSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-4 bg-cream-300 rounded w-48 mb-6" />
      <div className="h-6 bg-cream-300 rounded w-72 mb-2" />
      <div className="h-4 bg-cream-300 rounded w-96 mb-8" />
      <div className="flex gap-6">
        <div className="w-64 shrink-0 space-y-4">
          <div className="h-48 bg-cream-300 rounded" />
        </div>
        <div className="flex-1">
          <div className="h-64 bg-cream-300 rounded" />
        </div>
      </div>
      <div className="h-48 bg-cream-300 rounded mt-6" />
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
      <p className="text-warm-gray-600 mb-6">
        The project or cluster you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

// --- Stats sidebar ---

function StatsSidebar({
  totalLinks,
  totalPages,
  avgPerPage,
  validationPassRate,
  methodBreakdown,
  anchorDiversity,
}: {
  totalLinks: number;
  totalPages: number;
  avgPerPage: number;
  validationPassRate: number;
  methodBreakdown: Record<string, number>;
  anchorDiversity: Record<string, number>;
}) {
  return (
    <div className="w-64 shrink-0">
      <div className="bg-white rounded-sm border border-cream-500 p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-warm-gray-900 mb-4">Summary</h3>

        <div className="space-y-2 text-sm mb-5">
          <div className="flex justify-between">
            <span className="text-warm-gray-600">Total links</span>
            <span className="font-medium text-warm-gray-900">{totalLinks}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-warm-gray-600">Pages</span>
            <span className="font-medium text-warm-gray-900">{totalPages}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-warm-gray-600">Avg per page</span>
            <span className="font-medium text-warm-gray-900">{avgPerPage.toFixed(1)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-warm-gray-600">Validation</span>
            <span className="font-medium text-warm-gray-900">{Math.round(validationPassRate)}%</span>
          </div>
        </div>

        <hr className="border-cream-400 mb-4" />

        <h4 className="text-xs font-semibold text-warm-gray-700 uppercase tracking-wide mb-3">Link Methods</h4>
        <div className="space-y-1.5 text-sm mb-5">
          {Object.entries(methodBreakdown).map(([method, count]) => (
            <div key={method} className="flex justify-between">
              <span className="text-warm-gray-600 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-palm-400 inline-block" />
                {method}
              </span>
              <span className="font-medium text-warm-gray-900">{count}</span>
            </div>
          ))}
        </div>

        <hr className="border-cream-400 mb-4" />

        <h4 className="text-xs font-semibold text-warm-gray-700 uppercase tracking-wide mb-3">Anchor Diversity</h4>
        <div className="space-y-1.5 text-sm">
          {Object.entries(anchorDiversity).map(([type, pct]) => (
            <div key={type} className="flex justify-between">
              <span className="text-warm-gray-600 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-lagoon-400 inline-block" />
                {type}
              </span>
              <span className="font-medium text-warm-gray-900">{Math.round(pct)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Tree visualization ---

function TreeNode({
  node,
  isParent,
}: {
  node: HierarchyNode;
  isParent: boolean;
}) {
  return (
    <div className="flex flex-col items-center">
      <div
        className={`px-4 py-3 rounded-sm border text-center min-w-[130px] ${
          isParent
            ? 'bg-palm-50 border-palm-300 shadow-sm'
            : 'bg-white border-cream-500'
        }`}
      >
        <div className="text-sm font-medium text-warm-gray-900 truncate max-w-[140px]">
          {isParent && <span className="text-palm-600 mr-1" title="Parent page">&#9733;</span>}
          {node.keyword}
        </div>
        {isParent && (
          <span className="text-[10px] text-palm-600 font-medium">(parent)</span>
        )}
        <div className="flex justify-center gap-2 mt-1 text-xs text-warm-gray-500">
          <span title="Inbound links">&#8593;{node.inbound_count}</span>
          <span title="Outbound links">&#8595;{node.outbound_count}</span>
        </div>
      </div>
    </div>
  );
}

function TreeVisualization({ hierarchy }: { hierarchy: HierarchyNode }) {
  const children = hierarchy.children ?? [];

  // Split children into rows of up to 4 for layout
  const rows: HierarchyNode[][] = [];
  for (let i = 0; i < children.length; i += 4) {
    rows.push(children.slice(i, i + 4));
  }

  return (
    <div className="bg-white rounded-sm border border-cream-500 p-6 shadow-sm flex-1 overflow-x-auto">
      <div className="min-w-fit flex flex-col items-center">
        {/* Parent node */}
        <TreeNode node={hierarchy} isParent />

        {/* Connector from parent down */}
        {children.length > 0 && (
          <div className="w-px h-6 bg-warm-gray-300" />
        )}

        {/* Children rows */}
        {rows.map((row, rowIdx) => (
          <div key={rowIdx}>
            {/* Horizontal connector bar */}
            {row.length > 1 && (
              <div className="flex justify-center mb-0">
                <div
                  className="h-px bg-warm-gray-300"
                  style={{
                    width: `${(row.length - 1) * 170}px`,
                  }}
                />
              </div>
            )}

            {/* Vertical connectors + child nodes */}
            <div className="flex justify-center gap-5">
              {row.map((child) => (
                <div key={child.page_id} className="flex flex-col items-center">
                  <div className="w-px h-4 bg-warm-gray-300" />
                  <TreeNode node={child} isParent={false} />
                </div>
              ))}
            </div>

            {/* Sibling connections indicator */}
            {row.length > 1 && (
              <div className="flex justify-center mt-1 mb-2">
                <div className="flex items-center gap-1 text-xs text-warm-gray-400">
                  {row.slice(0, -1).map((_, i) => (
                    <span key={i} className="mx-8" title="Sibling cross-links">
                      &#9668;&#9658;
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* If there's another row, add a connector */}
            {rowIdx < rows.length - 1 && (
              <div className="flex justify-center">
                <div className="w-px h-4 bg-warm-gray-300" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Validation status icon ---

function ValidationIcon({ status }: { status: string }) {
  if (status === 'verified' || status === 'pass') {
    return <span className="text-palm-600" title="All rules passed">&#10003;</span>;
  }
  if (status.startsWith('failed')) {
    return <span className="text-coral-500" title={`Failed: ${status.replace('failed:', '')}`}>&#10007;</span>;
  }
  return <span className="text-coral-400" title="Warnings">&#9888;</span>;
}

// --- Method summary ---

function formatMethodSummary(methods: Record<string, number>): string {
  const parts: string[] = [];
  for (const [method, count] of Object.entries(methods)) {
    if (method === 'rule_based' || method === 'rule-based') {
      parts.push(`${count} rule`);
    } else if (method === 'llm_fallback' || method === 'llm-fallback') {
      parts.push(`${count} LLM`);
    } else if (method === 'generation') {
      parts.push(`${count} gen`);
    } else {
      parts.push(`${count} ${method}`);
    }
  }
  return parts.join(' + ') || '—';
}

// --- Sortable table header ---

function SortableHeader({
  label,
  sortKey,
  currentSortKey,
  currentSortDir,
  onSort,
  className,
}: {
  label: string;
  sortKey: SortKey;
  currentSortKey: SortKey;
  currentSortDir: SortDir;
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      className={`flex items-center text-xs font-semibold text-warm-gray-600 uppercase tracking-wide hover:text-warm-gray-900 ${className ?? ''}`}
    >
      {label}
      <SortIcon active={currentSortKey === sortKey} dir={currentSortDir} />
    </button>
  );
}

// --- Confirmation dialog ---

function ConfirmDialog({
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  isPending,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  isPending: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-warm-gray-900/40" onClick={onCancel} />
      <div className="relative bg-white rounded-sm border border-cream-500 shadow-lg p-6 max-w-md w-full mx-4">
        <h3 className="text-lg font-semibold text-warm-gray-900 mb-2">{title}</h3>
        <p className="text-sm text-warm-gray-600 mb-6">{message}</p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel} disabled={isPending}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={isPending}>
            {isPending ? (
              <>
                <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                Re-planning...
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </div>
      </div>
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
  const [sortKey, setSortKey] = useState<SortKey>('title');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: cluster, isLoading: isClusterLoading } = useCluster(projectId, clusterId);
  const { data: linkMap, isLoading: isMapLoading } = useLinkMap(projectId, 'cluster', clusterId);
  const planLinksMutation = usePlanLinks();

  const isLoading = isProjectLoading || isClusterLoading || isMapLoading;

  const hierarchy = linkMap?.hierarchy as HierarchyNode | null;

  // Sort pages
  const sortedPages = useMemo(() => {
    if (!linkMap?.pages) return [];
    const pages = [...linkMap.pages];
    pages.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'title':
          cmp = a.title.localeCompare(b.title);
          break;
        case 'role':
          cmp = (a.role ?? '').localeCompare(b.role ?? '');
          break;
        case 'outbound_count':
          cmp = a.outbound_count - b.outbound_count;
          break;
        case 'inbound_count':
          cmp = a.inbound_count - b.inbound_count;
          break;
        case 'method':
          cmp = formatMethodSummary(a.methods).localeCompare(formatMethodSummary(b.methods));
          break;
        case 'validation_status':
          cmp = a.validation_status.localeCompare(b.validation_status);
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    // Always keep parent at top
    const parentIdx = pages.findIndex((p) => p.role === 'parent');
    if (parentIdx > 0) {
      const [parent] = pages.splice(parentIdx, 1);
      pages.unshift(parent);
    }
    return pages;
  }, [linkMap?.pages, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const handleReplan = async () => {
    try {
      await planLinksMutation.mutateAsync({
        projectId,
        scope: 'cluster',
        clusterId,
      });
      setShowReplanConfirm(false);
      setToastMessage('Link re-planning started. You will be redirected when complete.');
      setToastVariant('success');
      setShowToast(true);
      // Redirect to planning trigger page for progress
      router.push(`/projects/${projectId}/clusters/${clusterId}/links`);
    } catch (error) {
      setShowReplanConfirm(false);
      const message = error instanceof Error ? error.message : 'Failed to start re-planning';
      setToastMessage(message);
      setToastVariant('error');
      setShowToast(true);
    }
  };

  const handleRowClick = (page: LinkMapPage) => {
    router.push(`/projects/${projectId}/clusters/${clusterId}/links/page/${page.page_id}`);
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

      {/* Header with Re-plan button */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
            Link Map &mdash; {cluster.name}
          </h1>
          <p className="text-sm text-warm-gray-600">
            Internal linking structure for this silo.
          </p>
        </div>
        {hasLinks && (
          <Button
            variant="secondary"
            onClick={() => setShowReplanConfirm(true)}
          >
            Re-plan Links
          </Button>
        )}
      </div>

      {/* Empty state */}
      {!hasLinks && (
        <div className="bg-white rounded-sm border border-cream-500 p-12 shadow-sm text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cream-100 mb-4">
            <svg className="w-8 h-8 text-warm-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
            </svg>
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

      {/* Main content: sidebar + tree */}
      {hasLinks && linkMap && (
        <>
          <div className="flex gap-6 mb-6">
            <StatsSidebar
              totalLinks={linkMap.total_links}
              totalPages={linkMap.total_pages}
              avgPerPage={linkMap.avg_links_per_page}
              validationPassRate={linkMap.validation_pass_rate}
              methodBreakdown={linkMap.method_breakdown}
              anchorDiversity={linkMap.anchor_diversity}
            />

            {/* Tree visualization */}
            {hierarchy && (
              <TreeVisualization hierarchy={hierarchy} />
            )}
          </div>

          {/* Page table */}
          <div className="bg-white rounded-sm border border-cream-500 shadow-sm overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_80px_60px_60px_160px_60px] gap-3 px-4 py-3 border-b border-cream-400 bg-cream-50">
              <SortableHeader label="Page" sortKey="title" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} />
              <SortableHeader label="Role" sortKey="role" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} className="justify-center" />
              <SortableHeader label="Out" sortKey="outbound_count" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} className="justify-center" />
              <SortableHeader label="In" sortKey="inbound_count" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} className="justify-center" />
              <SortableHeader label="Method" sortKey="method" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} />
              <SortableHeader label="Status" sortKey="validation_status" currentSortKey={sortKey} currentSortDir={sortDir} onSort={handleSort} className="justify-center" />
            </div>

            {/* Table rows */}
            <div className="divide-y divide-cream-300">
              {sortedPages.map((page) => (
                <button
                  key={page.page_id}
                  type="button"
                  onClick={() => handleRowClick(page)}
                  className={`grid grid-cols-[1fr_80px_60px_60px_160px_60px] gap-3 px-4 py-3 w-full text-left hover:bg-cream-50 transition-colors cursor-pointer ${
                    page.role === 'parent' ? 'bg-palm-50/40 border-l-2 border-l-palm-500' : ''
                  }`}
                >
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-warm-gray-900 truncate block">
                      {page.role === 'parent' && <span className="text-palm-600 mr-1">&#9733;</span>}
                      {page.title}
                      {page.role === 'parent' && (
                        <span className="text-xs text-palm-600 ml-1.5">(parent)</span>
                      )}
                    </span>
                  </div>
                  <div className="text-center">
                    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm ${
                      page.role === 'parent'
                        ? 'bg-palm-50 text-palm-700 border border-palm-200'
                        : 'bg-cream-100 text-warm-gray-600 border border-cream-300'
                    }`}>
                      {page.role === 'parent' ? 'Parent' : 'Child'}
                    </span>
                  </div>
                  <div className="text-center text-sm text-warm-gray-900">{page.outbound_count}</div>
                  <div className="text-center text-sm text-warm-gray-900">{page.inbound_count}</div>
                  <div className="text-sm text-warm-gray-700">{formatMethodSummary(page.methods)}</div>
                  <div className="text-center text-sm">
                    <ValidationIcon status={page.validation_status} />
                  </div>
                </button>
              ))}
            </div>

            {/* Footer */}
            <div className="px-4 py-3 border-t border-cream-400 bg-cream-50">
              <p className="text-xs text-warm-gray-500">Click any page to view and edit its links</p>
            </div>
          </div>
        </>
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
