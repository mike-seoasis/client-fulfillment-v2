'use client';

import { useState, useMemo, useCallback } from 'react';
import { usePagesWithKeywords } from '@/hooks/usePagesWithKeywords';
import type { PageWithKeywords } from '@/lib/api';

interface KeywordsTabProps {
  projectId: string;
}

export function KeywordsTab({ projectId }: KeywordsTabProps) {
  const { data: pages, isLoading } = usePagesWithKeywords(projectId);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);
  const [search, setSearch] = useState('');

  // Filter to only approved keywords
  const approvedPages = useMemo(() => {
    if (!pages) return [];
    return pages.filter(
      (p): p is PageWithKeywords & { keywords: NonNullable<PageWithKeywords['keywords']> } =>
        p.keywords !== null && p.keywords.is_approved
    );
  }, [pages]);

  // Apply search filter
  const filteredPages = useMemo(() => {
    if (!search.trim()) return approvedPages;
    const q = search.toLowerCase();
    return approvedPages.filter(
      (p) =>
        p.keywords.primary_keyword.toLowerCase().includes(q) ||
        (p.title && p.title.toLowerCase().includes(q)) ||
        p.url.toLowerCase().includes(q)
    );
  }, [approvedPages, search]);

  const allSelected =
    filteredPages.length > 0 && filteredPages.every((p) => selectedIds.has(p.id));

  const toggleAll = useCallback(() => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredPages.map((p) => p.id)));
    }
  }, [allSelected, filteredPages]);

  const toggleOne = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectedKeywords = useMemo(
    () =>
      filteredPages
        .filter((p) => selectedIds.has(p.id))
        .map((p) => p.keywords.primary_keyword),
    [filteredPages, selectedIds]
  );

  const copyToClipboard = useCallback(async () => {
    const text = selectedKeywords.join('\n');
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [selectedKeywords]);

  if (isLoading) {
    return (
      <div className="bg-white rounded-sm border border-cream-500 p-8">
        <div className="animate-pulse space-y-3">
          <div className="h-5 bg-cream-200 rounded w-48" />
          <div className="h-4 bg-cream-200 rounded w-full" />
          <div className="h-4 bg-cream-200 rounded w-full" />
          <div className="h-4 bg-cream-200 rounded w-3/4" />
        </div>
      </div>
    );
  }

  if (approvedPages.length === 0) {
    return (
      <div className="bg-white rounded-sm border border-cream-500 p-12 text-center">
        <div className="text-warm-gray-400 mb-2">
          <svg className="w-10 h-10 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>
        <p className="text-warm-gray-600 font-medium">No approved keywords yet</p>
        <p className="text-warm-gray-400 text-sm mt-1">
          Approve keywords in the onboarding flow and they&apos;ll appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-sm border border-cream-500 shadow-sm">
      {/* Header bar */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-cream-300">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-warm-gray-900">
            Approved Keywords
          </h3>
          <span className="text-xs bg-palm-50 text-palm-700 px-2 py-0.5 rounded-full font-medium">
            {approvedPages.length}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <svg
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-warm-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
            <input
              type="text"
              placeholder="Filter keywords..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs border border-cream-400 rounded-sm bg-cream-50 text-warm-gray-700 placeholder:text-warm-gray-400 focus:outline-none focus:ring-1 focus:ring-palm-400 focus:border-palm-400 w-48"
            />
          </div>

          {/* Copy button */}
          <button
            onClick={copyToClipboard}
            disabled={selectedKeywords.length === 0}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm transition-colors ${
              selectedKeywords.length === 0
                ? 'bg-cream-200 text-warm-gray-400 cursor-not-allowed'
                : copied
                  ? 'bg-palm-500 text-white'
                  : 'bg-palm-500 text-white hover:bg-palm-600'
            }`}
          >
            {copied ? (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                </svg>
                Copy to Clipboard
                {selectedKeywords.length > 0 && (
                  <span className="bg-white/20 px-1.5 py-0.5 rounded text-[10px]">
                    {selectedKeywords.length}
                  </span>
                )}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-cream-50 text-warm-gray-500 text-xs uppercase tracking-wider">
              <th className="w-10 px-4 py-2.5 text-left">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="rounded-sm border-cream-400 text-palm-500 focus:ring-palm-400 cursor-pointer"
                />
              </th>
              <th className="px-4 py-2.5 text-left font-medium">Keyword</th>
              <th className="px-4 py-2.5 text-left font-medium">Page</th>
              <th className="px-4 py-2.5 text-right font-medium w-24">Volume</th>
              <th className="px-4 py-2.5 text-right font-medium w-24">Difficulty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-cream-200">
            {filteredPages.map((page) => (
              <tr
                key={page.id}
                className={`transition-colors ${
                  selectedIds.has(page.id)
                    ? 'bg-palm-50/50'
                    : 'hover:bg-cream-50'
                }`}
              >
                <td className="px-4 py-2.5">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(page.id)}
                    onChange={() => toggleOne(page.id)}
                    className="rounded-sm border-cream-400 text-palm-500 focus:ring-palm-400 cursor-pointer"
                  />
                </td>
                <td className="px-4 py-2.5 font-medium text-warm-gray-900">
                  {page.keywords.primary_keyword}
                </td>
                <td className="px-4 py-2.5 text-warm-gray-500 truncate max-w-xs">
                  {page.title || page.url}
                </td>
                <td className="px-4 py-2.5 text-right text-warm-gray-600 tabular-nums">
                  {page.keywords.search_volume != null
                    ? page.keywords.search_volume.toLocaleString()
                    : '\u2014'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {page.keywords.difficulty_score != null ? (
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs font-medium tabular-nums ${
                        page.keywords.difficulty_score <= 30
                          ? 'bg-green-50 text-green-700'
                          : page.keywords.difficulty_score <= 60
                            ? 'bg-yellow-50 text-yellow-700'
                            : 'bg-red-50 text-red-700'
                      }`}
                    >
                      {page.keywords.difficulty_score}
                    </span>
                  ) : (
                    <span className="text-warm-gray-400">{'\u2014'}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer with count */}
      {filteredPages.length !== approvedPages.length && (
        <div className="px-5 py-2.5 border-t border-cream-200 text-xs text-warm-gray-400">
          Showing {filteredPages.length} of {approvedPages.length} keywords
        </div>
      )}
    </div>
  );
}
