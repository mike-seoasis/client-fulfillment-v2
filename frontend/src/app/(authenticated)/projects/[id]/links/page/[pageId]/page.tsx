'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useProject } from '@/hooks/use-projects';
import {
  usePageLinks,
  useAddLink,
  useRemoveLink,
  useEditLink,
  useAnchorSuggestions,
  useLinkMap,
} from '@/hooks/useLinks';
import { Button, Toast } from '@/components/ui';
import type { InternalLink, LinkMapPage } from '@/lib/api';

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

function SearchIcon({ className }: { className?: string }) {
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
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
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
      <div className="space-y-4">
        <div className="h-64 bg-cream-300 rounded" />
        <div className="h-48 bg-cream-300 rounded" />
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
      <p className="text-warm-gray-600 mb-6">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link href="/">
        <Button>Back to Dashboard</Button>
      </Link>
    </div>
  );
}

// --- Anchor type badge ---

function AnchorTypeBadge({ type }: { type: string }) {
  const label =
    type === 'exact_match'
      ? 'exact'
      : type === 'partial_match'
        ? 'partial'
        : type === 'natural'
          ? 'natural'
          : type;

  const color =
    type === 'exact_match'
      ? 'bg-lagoon-50 text-lagoon-700 border-lagoon-200'
      : type === 'partial_match'
        ? 'bg-palm-50 text-palm-700 border-palm-200'
        : 'bg-cream-100 text-warm-gray-700 border-cream-300';

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border ${color}`}
    >
      {label}
    </span>
  );
}

// --- Placement method label ---

function formatMethod(method: string): string {
  if (method === 'rule_based' || method === 'rule-based') return 'rule-based';
  if (method === 'llm_fallback' || method === 'llm-fallback') return 'LLM fallback';
  if (method === 'generation') return 'generation-time';
  return method;
}

// --- Confirm dialog ---

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
                Removing...
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

// --- Add Link Modal ---

function AddLinkModal({
  projectId,
  sourcePageId,
  existingTargetIds,
  siloPages,
  onClose,
  onSuccess,
}: {
  projectId: string;
  sourcePageId: string;
  existingTargetIds: Set<string>;
  siloPages: LinkMapPage[];
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [targetPageId, setTargetPageId] = useState('');
  const [anchorText, setAnchorText] = useState('');
  const [anchorType, setAnchorType] = useState<'exact_match' | 'partial_match' | 'natural'>('partial_match');
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState('');

  const addLinkMutation = useAddLink();
  const { data: suggestions } = useAnchorSuggestions(projectId, targetPageId);

  // Filter available target pages: exclude self and existing targets
  const availablePages = useMemo(() => {
    let pages = siloPages.filter(
      (p) => p.page_id !== sourcePageId && !existingTargetIds.has(p.page_id)
    );
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      pages = pages.filter((p) => p.title.toLowerCase().includes(q));
    }
    return pages;
  }, [siloPages, sourcePageId, existingTargetIds, searchQuery]);

  const handleSubmit = async () => {
    setError('');

    if (!targetPageId) {
      setError('Please select a target page.');
      return;
    }
    if (!anchorText.trim()) {
      setError('Please enter anchor text.');
      return;
    }
    if (targetPageId === sourcePageId) {
      setError('Cannot create a self-link.');
      return;
    }
    if (existingTargetIds.has(targetPageId)) {
      setError('A link to this target already exists.');
      return;
    }

    try {
      await addLinkMutation.mutateAsync({
        projectId,
        data: {
          source_page_id: sourcePageId,
          target_page_id: targetPageId,
          anchor_text: anchorText.trim(),
          anchor_type: anchorType,
        },
      });
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add link';
      setError(message);
    }
  };

  const selectedPage = siloPages.find((p) => p.page_id === targetPageId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-warm-gray-900/40" onClick={onClose} />
      <div className="relative bg-white rounded-sm border border-cream-500 shadow-lg p-6 max-w-lg w-full mx-4">
        <h3 className="text-lg font-semibold text-warm-gray-900 mb-4">Add Internal Link</h3>

        {/* Target page search + selection */}
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">Target Page</label>
        {!selectedPage ? (
          <div className="mb-4">
            <div className="relative mb-2">
              <SearchIcon className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-warm-gray-400" />
              <input
                type="text"
                placeholder="Search pages in this silo..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-sm border border-cream-400 rounded-sm pl-8 pr-3 py-2 bg-white text-warm-gray-900 placeholder-warm-gray-400 focus:outline-none focus:ring-1 focus:ring-palm-400"
              />
            </div>
            <div className="border border-cream-400 rounded-sm max-h-40 overflow-y-auto">
              {availablePages.length === 0 ? (
                <div className="px-3 py-2 text-sm text-warm-gray-500">No pages available</div>
              ) : (
                availablePages.map((page) => (
                  <button
                    key={page.page_id}
                    type="button"
                    onClick={() => {
                      setTargetPageId(page.page_id);
                      setSearchQuery('');
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-warm-gray-900 hover:bg-cream-50 transition-colors border-b border-cream-200 last:border-b-0"
                  >
                    {page.title}
                  </button>
                ))
              )}
            </div>
          </div>
        ) : (
          <div className="mb-4 flex items-center gap-2">
            <span className="text-sm text-warm-gray-900 font-medium">{selectedPage.title}</span>
            <button
              type="button"
              onClick={() => setTargetPageId('')}
              className="text-xs text-warm-gray-500 hover:text-warm-gray-700 underline"
            >
              change
            </button>
          </div>
        )}

        {/* Anchor text input */}
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">Anchor Text</label>
        <input
          type="text"
          value={anchorText}
          onChange={(e) => setAnchorText(e.target.value)}
          placeholder="Enter anchor text..."
          className="w-full text-sm border border-cream-400 rounded-sm px-3 py-2 bg-white text-warm-gray-900 placeholder-warm-gray-400 focus:outline-none focus:ring-1 focus:ring-palm-400 mb-3"
        />

        {/* Suggested anchors from POP variations */}
        {suggestions && (suggestions.pop_variations.length > 0 || suggestions.primary_keyword) && (
          <div className="mb-4">
            <p className="text-xs font-medium text-warm-gray-600 mb-1.5">Suggested anchors (from POP variations):</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.primary_keyword && (
                <button
                  type="button"
                  onClick={() => setAnchorText(suggestions.primary_keyword)}
                  className="text-xs px-2 py-1 rounded-sm bg-cream-100 text-warm-gray-700 border border-cream-300 hover:bg-cream-200 transition-colors"
                >
                  &ldquo;{suggestions.primary_keyword}&rdquo;
                  {suggestions.usage_counts[suggestions.primary_keyword] != null && (
                    <span className="ml-1 text-warm-gray-400">
                      ({suggestions.usage_counts[suggestions.primary_keyword]}x)
                    </span>
                  )}
                </button>
              )}
              {suggestions.pop_variations.map((variation) => (
                <button
                  key={variation}
                  type="button"
                  onClick={() => setAnchorText(variation)}
                  className="text-xs px-2 py-1 rounded-sm bg-cream-100 text-warm-gray-700 border border-cream-300 hover:bg-cream-200 transition-colors"
                >
                  &ldquo;{variation}&rdquo;
                  {suggestions.usage_counts[variation] != null && (
                    <span className="ml-1 text-warm-gray-400">
                      ({suggestions.usage_counts[variation]}x)
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Anchor type */}
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">Anchor Type</label>
        <div className="flex gap-4 mb-4">
          {(['partial_match', 'exact_match', 'natural'] as const).map((type) => (
            <label key={type} className="flex items-center gap-1.5 text-sm text-warm-gray-700 cursor-pointer">
              <input
                type="radio"
                name="anchor-type"
                value={type}
                checked={anchorType === type}
                onChange={() => setAnchorType(type)}
                className="text-palm-500 focus:ring-palm-400"
              />
              {type === 'partial_match' ? 'Partial match' : type === 'exact_match' ? 'Exact match' : 'Natural'}
            </label>
          ))}
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-coral-600 mb-4">{error}</p>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={addLinkMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={addLinkMutation.isPending}>
            {addLinkMutation.isPending ? (
              <>
                <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                Adding...
              </>
            ) : (
              'Add Link'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- Edit Anchor Modal ---

function EditAnchorModal({
  projectId,
  link,
  targetTitle,
  onClose,
  onSuccess,
}: {
  projectId: string;
  link: InternalLink;
  targetTitle: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [anchorText, setAnchorText] = useState(link.anchor_text);
  const [anchorType, setAnchorType] = useState<'exact_match' | 'partial_match' | 'natural'>(
    (link.anchor_type as 'exact_match' | 'partial_match' | 'natural') || 'partial_match'
  );
  const [error, setError] = useState('');

  const editLinkMutation = useEditLink();
  const { data: suggestions } = useAnchorSuggestions(projectId, link.target_page_id);

  const handleSubmit = async () => {
    setError('');

    if (!anchorText.trim()) {
      setError('Anchor text cannot be empty.');
      return;
    }

    try {
      await editLinkMutation.mutateAsync({
        projectId,
        linkId: link.id,
        data: {
          anchor_text: anchorText.trim(),
          anchor_type: anchorType,
        },
      });
      onSuccess();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to edit link';
      setError(message);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-warm-gray-900/40" onClick={onClose} />
      <div className="relative bg-white rounded-sm border border-cream-500 shadow-lg p-6 max-w-lg w-full mx-4">
        <h3 className="text-lg font-semibold text-warm-gray-900 mb-4">Edit Anchor Text</h3>

        {/* Target name (read-only) */}
        <p className="text-sm text-warm-gray-600 mb-4">
          Target: <span className="font-medium text-warm-gray-900">{targetTitle}</span>
        </p>

        {/* Anchor text input */}
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">Current anchor</label>
        <input
          type="text"
          value={anchorText}
          onChange={(e) => setAnchorText(e.target.value)}
          className="w-full text-sm border border-cream-400 rounded-sm px-3 py-2 bg-white text-warm-gray-900 focus:outline-none focus:ring-1 focus:ring-palm-400 mb-3"
        />

        {/* Suggested variations */}
        {suggestions && (suggestions.pop_variations.length > 0 || suggestions.primary_keyword) && (
          <div className="mb-4">
            <p className="text-xs font-medium text-warm-gray-600 mb-1.5">Suggested variations:</p>
            <div className="flex flex-wrap gap-1.5">
              {suggestions.primary_keyword && (
                <button
                  type="button"
                  onClick={() => setAnchorText(suggestions.primary_keyword)}
                  className="text-xs px-2 py-1 rounded-sm bg-cream-100 text-warm-gray-700 border border-cream-300 hover:bg-cream-200 transition-colors"
                >
                  &ldquo;{suggestions.primary_keyword}&rdquo;
                </button>
              )}
              {suggestions.pop_variations.map((variation) => (
                <button
                  key={variation}
                  type="button"
                  onClick={() => setAnchorText(variation)}
                  className="text-xs px-2 py-1 rounded-sm bg-cream-100 text-warm-gray-700 border border-cream-300 hover:bg-cream-200 transition-colors"
                >
                  &ldquo;{variation}&rdquo;
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Anchor type radio buttons */}
        <label className="block text-sm font-medium text-warm-gray-700 mb-1.5">Anchor type</label>
        <div className="flex flex-col gap-2 mb-4">
          {(['partial_match', 'exact_match', 'natural'] as const).map((type) => (
            <label key={type} className="flex items-center gap-2 text-sm text-warm-gray-700 cursor-pointer">
              <input
                type="radio"
                name="edit-anchor-type"
                value={type}
                checked={anchorType === type}
                onChange={() => setAnchorType(type)}
                className="text-palm-500 focus:ring-palm-400"
              />
              {type === 'partial_match' ? 'Partial match' : type === 'exact_match' ? 'Exact match' : 'Natural'}
            </label>
          ))}
        </div>

        {/* Error */}
        {error && (
          <p className="text-sm text-coral-600 mb-4">{error}</p>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose} disabled={editLinkMutation.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={editLinkMutation.isPending}>
            {editLinkMutation.isPending ? (
              <>
                <SpinnerIcon className="w-4 h-4 mr-1.5 animate-spin" />
                Saving...
              </>
            ) : (
              'Save Anchor'
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// --- Main page component ---

export default function PageLinkDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const pageId = params.pageId as string;

  const [showToast, setShowToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVariant, setToastVariant] = useState<'success' | 'error'>('success');

  // Modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingLink, setEditingLink] = useState<InternalLink | null>(null);
  const [removingLink, setRemovingLink] = useState<InternalLink | null>(null);

  const { data: project, isLoading: isProjectLoading, error: projectError } = useProject(projectId);
  const { data: pageLinks, isLoading: isPageLinksLoading } = usePageLinks(projectId, pageId);

  // Load link map to get silo pages for Add Link target dropdown and page title lookup
  const { data: linkMap } = useLinkMap(projectId, 'onboarding');

  const removeLinkMutation = useRemoveLink();

  const isLoading = isProjectLoading || isPageLinksLoading;

  // Build page_id → title lookup from link map pages
  const pageTitleMap = useMemo(() => {
    const map = new Map<string, string>();
    if (linkMap?.pages) {
      for (const page of linkMap.pages) {
        map.set(page.page_id, page.title);
      }
    }
    return map;
  }, [linkMap?.pages]);

  // Current page info from link map
  const currentPageInfo = useMemo(() => {
    return linkMap?.pages.find((p) => p.page_id === pageId);
  }, [linkMap?.pages, pageId]);

  // Existing outbound target IDs for duplicate validation
  const existingTargetIds = useMemo(() => {
    const ids = new Set<string>();
    if (pageLinks?.outbound_links) {
      for (const link of pageLinks.outbound_links) {
        ids.add(link.target_page_id);
      }
    }
    return ids;
  }, [pageLinks?.outbound_links]);

  // Silo pages for the Add Link target dropdown
  const siloPages = useMemo(() => {
    return linkMap?.pages ?? [];
  }, [linkMap?.pages]);

  // Anchor diversity calculation for this page as target
  const diversityInfo = useMemo(() => {
    if (!pageLinks) return { anchors: [] as { text: string; count: number }[], score: '', label: '' };

    // Count unique anchors pointing to this page (inbound links)
    const anchorCounts = new Map<string, number>();
    for (const link of pageLinks.inbound_links) {
      const text = link.anchor_text;
      anchorCounts.set(text, (anchorCounts.get(text) ?? 0) + 1);
    }

    const anchors = Array.from(anchorCounts.entries())
      .map(([text, count]) => ({ text, count }))
      .sort((a, b) => b.count - a.count);

    const totalInbound = pageLinks.inbound_links.length;
    const uniqueCount = anchors.length;
    const uniqueRatio = totalInbound > 0 ? uniqueCount / totalInbound : 1;

    let score: string;
    let label: string;
    if (uniqueRatio > 0.8) {
      score = 'High';
      label = `${uniqueCount} unique anchors / ${totalInbound} inbound links`;
    } else if (uniqueRatio >= 0.5) {
      score = 'Medium';
      label = `${uniqueCount} unique anchors / ${totalInbound} inbound links`;
    } else {
      score = 'Low';
      label = `${uniqueCount} unique anchors / ${totalInbound} inbound links`;
    }

    return { anchors, score, label };
  }, [pageLinks]);

  const showSuccessToast = (message: string) => {
    setToastMessage(message);
    setToastVariant('success');
    setShowToast(true);
  };

  const showErrorToast = (message: string) => {
    setToastMessage(message);
    setToastVariant('error');
    setShowToast(true);
  };

  const handleRemoveLink = async () => {
    if (!removingLink) return;
    try {
      await removeLinkMutation.mutateAsync({
        projectId,
        linkId: removingLink.id,
      });
      setRemovingLink(null);
      showSuccessToast('Link removed successfully.');
    } catch (err) {
      setRemovingLink(null);
      const message = err instanceof Error ? err.message : 'Failed to remove link';
      showErrorToast(message);
    }
  };

  // Resolve page title: use target_title for outbound, lookup source from pageTitleMap for inbound
  const getSourceTitle = (link: InternalLink): string => {
    return pageTitleMap.get(link.source_page_id) ?? 'Unknown page';
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

  const pageTitle = currentPageInfo?.title ?? pageLinks?.outbound_links[0]?.target_title ?? 'Page';
  const pageUrl = currentPageInfo?.url ?? '';

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-warm-gray-600 mb-6">
        <Link href={`/projects/${projectId}`} className="hover:text-warm-gray-900 flex items-center">
          <BackArrowIcon className="w-4 h-4 mr-1" />
          {project.name}
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <Link href={`/projects/${projectId}/links/map`} className="hover:text-warm-gray-900">
          Link Map
        </Link>
        <span className="mx-2">&rsaquo;</span>
        <span className="text-warm-gray-900 truncate max-w-[200px]">{pageTitle}</span>
      </nav>

      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-warm-gray-900 mb-1">
          Links &mdash; {pageTitle}
        </h1>
        {pageUrl && (
          <p className="text-sm text-warm-gray-500">{pageUrl}</p>
        )}
      </div>

      {/* Outbound Links Section */}
      <div className="bg-white rounded-sm border border-cream-500 shadow-sm mb-6">
        <div className="flex items-center justify-between px-5 py-4 border-b border-cream-400">
          <h2 className="text-sm font-semibold text-warm-gray-900">
            Outbound Links ({pageLinks?.outbound_links.length ?? 0})
          </h2>
          <Button
            variant="secondary"
            onClick={() => setShowAddModal(true)}
          >
            + Add
          </Button>
        </div>

        <div className="divide-y divide-cream-200">
          {pageLinks?.outbound_links.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-warm-gray-500">
              No outbound links yet. Click &ldquo;+ Add&rdquo; to create one.
            </div>
          )}

          {pageLinks?.outbound_links.map((link, idx) => (
            <div
              key={link.id}
              className={`px-5 py-4 ${link.is_mandatory ? 'bg-palm-50/30' : ''}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-medium text-warm-gray-900">
                      {idx + 1}. {link.is_mandatory && <span className="text-palm-600 mr-1">&#9733;</span>}
                      {link.target_title}
                      {link.is_mandatory && (
                        <span className="text-warm-gray-500 text-xs ml-1">(parent)</span>
                      )}
                    </span>
                    {link.is_mandatory && (
                      <span className="inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm bg-palm-100 text-palm-700 border border-palm-200">
                        mandatory
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-warm-gray-600 mb-1">
                    Anchor: &ldquo;{link.anchor_text}&rdquo;
                  </p>
                  <div className="flex items-center gap-2 text-xs text-warm-gray-500">
                    <span>Type:</span>
                    <AnchorTypeBadge type={link.anchor_type} />
                    <span className="mx-1">&middot;</span>
                    <span>Method: {formatMethod(link.placement_method)}</span>
                    {link.position_in_content != null && (
                      <>
                        <span className="mx-1">&middot;</span>
                        <span>Position: paragraph {link.position_in_content}</span>
                      </>
                    )}
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <button
                    type="button"
                    onClick={() => setEditingLink(link)}
                    className="text-xs px-2.5 py-1.5 rounded-sm border border-cream-400 text-warm-gray-700 hover:bg-cream-50 transition-colors"
                  >
                    Edit Anchor
                  </button>
                  {!link.is_mandatory && (
                    <button
                      type="button"
                      onClick={() => setRemovingLink(link)}
                      className="text-xs px-2.5 py-1.5 rounded-sm border border-coral-200 text-coral-600 hover:bg-coral-50 transition-colors"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Inbound Links Section (read-only) */}
      <div className="bg-white rounded-sm border border-cream-500 shadow-sm mb-6">
        <div className="px-5 py-4 border-b border-cream-400">
          <h2 className="text-sm font-semibold text-warm-gray-900">
            Inbound Links ({pageLinks?.inbound_links.length ?? 0})
          </h2>
        </div>

        <div className="divide-y divide-cream-200">
          {pageLinks?.inbound_links.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-warm-gray-500">
              No inbound links to this page.
            </div>
          )}

          {pageLinks?.inbound_links.map((link) => (
            <div key={link.id} className="px-5 py-3">
              <p className="text-sm text-warm-gray-900 mb-0.5">
                From: <span className="font-medium">{getSourceTitle(link)}</span>
              </p>
              <div className="flex items-center gap-2 text-xs text-warm-gray-500">
                <span>Anchor: &ldquo;{link.anchor_text}&rdquo;</span>
                <span className="mx-0.5">&middot;</span>
                <span>Type:</span>
                <AnchorTypeBadge type={link.anchor_type} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Anchor Diversity Section */}
      <div className="bg-white rounded-sm border border-cream-500 shadow-sm mb-6">
        <div className="px-5 py-4 border-b border-cream-400">
          <h2 className="text-sm font-semibold text-warm-gray-900">
            Anchor Diversity for This Page (as target)
          </h2>
        </div>

        <div className="px-5 py-4">
          {diversityInfo.anchors.length === 0 ? (
            <p className="text-sm text-warm-gray-500">No inbound links to analyze.</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2 mb-4">
                {diversityInfo.anchors.map(({ text, count }) => (
                  <span key={text} className="text-sm text-warm-gray-700">
                    &ldquo;{text}&rdquo;{' '}
                    <span className="text-warm-gray-400">&times;{count}</span>
                  </span>
                ))}
              </div>
              <p className="text-sm">
                <span className="text-warm-gray-600">Diversity score: </span>
                <span
                  className={
                    diversityInfo.score === 'High'
                      ? 'text-palm-600 font-medium'
                      : diversityInfo.score === 'Medium'
                        ? 'text-warm-gray-700 font-medium'
                        : 'text-coral-500 font-medium'
                  }
                >
                  {diversityInfo.score}
                  {diversityInfo.score === 'High' && ' \u2713'}
                </span>
                <span className="text-warm-gray-400 ml-2">
                  ({diversityInfo.label})
                </span>
              </p>
            </>
          )}
        </div>
      </div>

      {/* Back button */}
      <div className="flex justify-start">
        <Link href={`/projects/${projectId}/links/map`}>
          <Button variant="secondary">
            <BackArrowIcon className="w-4 h-4 mr-1.5" />
            Back to Link Map
          </Button>
        </Link>
      </div>

      {/* Add Link Modal */}
      {showAddModal && (
        <AddLinkModal
          projectId={projectId}
          sourcePageId={pageId}
          existingTargetIds={existingTargetIds}
          siloPages={siloPages}
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            showSuccessToast('Link added successfully.');
          }}
        />
      )}

      {/* Edit Anchor Modal */}
      {editingLink && (
        <EditAnchorModal
          projectId={projectId}
          link={editingLink}
          targetTitle={editingLink.target_title}
          onClose={() => setEditingLink(null)}
          onSuccess={() => {
            setEditingLink(null);
            showSuccessToast('Anchor text updated.');
          }}
        />
      )}

      {/* Remove Link Confirmation */}
      {removingLink && (
        <ConfirmDialog
          title="Remove Link"
          message={`Remove the link to "${removingLink.target_title}"? This will remove the anchor from the page content.`}
          confirmLabel="Remove Link"
          onConfirm={handleRemoveLink}
          onCancel={() => setRemovingLink(null)}
          isPending={removeLinkMutation.isPending}
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
