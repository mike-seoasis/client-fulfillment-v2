'use client';

import { useState, useCallback, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  useUpdateOutline,
  useApproveOutline,
  useGenerateFromOutline,
  useExportOutline,
} from '@/hooks/useContentGeneration';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OutlineSectionDetail {
  headline: string;
  purpose: string;
  key_points: string[];
  client_notes: string;
}

interface OutlineSection {
  order: number;
  label: string;
  tag: string;
  headline: string;
}

interface OutlineData {
  page_name?: string;
  primary_keyword?: string;
  secondary_keywords?: string[];
  date?: string;
  keyword_reference?: {
    lsi_terms?: { term: string; target_count?: number }[];
    keyword_variations?: { variation: string; verbatim_required?: boolean }[];
  };
  people_also_ask?: string[];
  top_ranked_results?: { url: string; title?: string; word_count?: number }[];
  audience?: string;
  page_progression?: OutlineSection[];
  section_details?: OutlineSectionDetail[];
}

// ---------------------------------------------------------------------------
// OutlineEditor
// ---------------------------------------------------------------------------

export function OutlineEditor({
  content,
  projectId,
  pageId,
  pageInfo,
  backUrl,
  onGenerateRedirectUrl,
  isRevising = false,
}: {
  content: { outline_json: any; outline_status: string | null; google_doc_url?: string | null; [key: string]: any };
  projectId: string;
  pageId: string;
  pageInfo: { url?: string } | null;
  /** URL for the "Back to content list" link */
  backUrl: string;
  /** URL to navigate to after triggering "Generate Full Copy" */
  onGenerateRedirectUrl: string;
  /** True when revising an outline that already has generated content */
  isRevising?: boolean;
}) {
  const router = useRouter();
  const updateOutlineMutation = useUpdateOutline();
  const approveOutlineMutation = useApproveOutline();
  const generateFromOutlineMutation = useGenerateFromOutline();
  const exportOutlineMutation = useExportOutline();

  // Local outline state
  const [outline, setOutline] = useState<OutlineData>(() => content.outline_json ?? {});
  const [isDirty, setIsDirty] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'failed'>('idle');

  // Re-sync local state from server when not dirty
  useEffect(() => {
    if (!isDirty && content.outline_json) {
      setOutline(content.outline_json);
    }
  }, [content.outline_json, isDirty]);

  const isDraft = content.outline_status === 'draft';
  const isApproved = content.outline_status === 'approved';

  // Update a field and mark dirty
  const updateField = useCallback(<K extends keyof OutlineData>(key: K, value: OutlineData[K]) => {
    setOutline((prev) => ({ ...prev, [key]: value }));
    setIsDirty(true);
  }, []);

  // Move section up/down
  const moveSection = useCallback((fromIndex: number, direction: 'up' | 'down') => {
    setOutline((prev) => {
      const progression = [...(prev.page_progression ?? [])];
      const details = [...(prev.section_details ?? [])];
      const toIndex = direction === 'up' ? fromIndex - 1 : fromIndex + 1;
      if (toIndex < 0 || toIndex >= progression.length) return prev;
      [progression[fromIndex], progression[toIndex]] = [progression[toIndex], progression[fromIndex]];
      progression.forEach((s, i) => { s.order = i + 1; });
      if (details[fromIndex] && details[toIndex]) {
        [details[fromIndex], details[toIndex]] = [details[toIndex], details[fromIndex]];
      }
      return { ...prev, page_progression: progression, section_details: details };
    });
    setIsDirty(true);
  }, []);

  const updateSectionHeadline = useCallback((index: number, headline: string) => {
    setOutline((prev) => {
      const progression = [...(prev.page_progression ?? [])];
      if (progression[index]) {
        progression[index] = { ...progression[index], headline };
      }
      return { ...prev, page_progression: progression };
    });
    setIsDirty(true);
  }, []);

  const updateSectionDetail = useCallback((index: number, field: keyof OutlineSectionDetail, value: any) => {
    setOutline((prev) => {
      const details = [...(prev.section_details ?? [])];
      if (details[index]) {
        details[index] = { ...details[index], [field]: value };
      }
      return { ...prev, section_details: details };
    });
    setIsDirty(true);
  }, []);

  const addKeyPoint = useCallback((sectionIndex: number) => {
    setOutline((prev) => {
      const details = [...(prev.section_details ?? [])];
      if (details[sectionIndex]) {
        details[sectionIndex] = {
          ...details[sectionIndex],
          key_points: [...(details[sectionIndex].key_points ?? []), ''],
        };
      }
      return { ...prev, section_details: details };
    });
    setIsDirty(true);
  }, []);

  const removeKeyPoint = useCallback((sectionIndex: number, pointIndex: number) => {
    setOutline((prev) => {
      const details = [...(prev.section_details ?? [])];
      if (details[sectionIndex]) {
        const points = [...(details[sectionIndex].key_points ?? [])];
        points.splice(pointIndex, 1);
        details[sectionIndex] = { ...details[sectionIndex], key_points: points };
      }
      return { ...prev, section_details: details };
    });
    setIsDirty(true);
  }, []);

  const updateKeyPoint = useCallback((sectionIndex: number, pointIndex: number, value: string) => {
    setOutline((prev) => {
      const details = [...(prev.section_details ?? [])];
      if (details[sectionIndex]) {
        const points = [...(details[sectionIndex].key_points ?? [])];
        points[pointIndex] = value;
        details[sectionIndex] = { ...details[sectionIndex], key_points: points };
      }
      return { ...prev, section_details: details };
    });
    setIsDirty(true);
  }, []);

  // Save draft
  const handleSaveDraft = useCallback(async () => {
    setSaveStatus('saving');
    try {
      await updateOutlineMutation.mutateAsync({ projectId, pageId, outlineJson: outline });
      setSaveStatus('saved');
      setIsDirty(false);
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch {
      setSaveStatus('failed');
    }
  }, [projectId, pageId, outline, updateOutlineMutation]);

  // Approve outline
  const handleApprove = useCallback(async () => {
    if (isDirty) {
      try {
        await updateOutlineMutation.mutateAsync({ projectId, pageId, outlineJson: outline });
        setIsDirty(false);
      } catch {
        return;
      }
    }
    await approveOutlineMutation.mutateAsync({ projectId, pageId });
  }, [projectId, pageId, outline, isDirty, updateOutlineMutation, approveOutlineMutation]);

  // Export to Google Doc
  const [exportError, setExportError] = useState<string | null>(null);
  const handleExport = useCallback(async (force?: boolean) => {
    setExportError(null);
    if (isDirty) {
      try {
        await updateOutlineMutation.mutateAsync({ projectId, pageId, outlineJson: outline });
        setIsDirty(false);
      } catch {
        return;
      }
    }
    exportOutlineMutation.mutate(
      { projectId, pageId, force },
      {
        onSuccess: (data) => { window.open(data.google_doc_url, '_blank'); },
        onError: (err) => { setExportError(err instanceof Error ? err.message : 'Export failed'); },
      }
    );
  }, [projectId, pageId, outline, isDirty, updateOutlineMutation, exportOutlineMutation]);

  // Generate full copy
  const [generateError, setGenerateError] = useState<string | null>(null);
  const handleGenerateFullCopy = useCallback(async () => {
    setGenerateError(null);
    try {
      await generateFromOutlineMutation.mutateAsync({ projectId, pageId });
      router.push(onGenerateRedirectUrl);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to start content generation';
      setGenerateError(msg);
    }
  }, [projectId, pageId, generateFromOutlineMutation, router, onGenerateRedirectUrl]);

  const lsiTerms = outline.keyword_reference?.lsi_terms ?? [];
  const variations = outline.keyword_reference?.keyword_variations ?? [];
  const paa = outline.people_also_ask ?? [];
  const competitors = outline.top_ranked_results ?? [];
  const progression = outline.page_progression ?? [];
  const details = outline.section_details ?? [];

  return (
    <div className="max-w-[1600px] mx-auto pb-24">
      {/* Page Header */}
      <div className="pt-1 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <Link
              href={backUrl}
              className="inline-flex items-center gap-1.5 text-sm text-warm-500 hover:text-warm-700 mb-3 group"
            >
              <svg
                className="w-4 h-4 transition-transform group-hover:-translate-x-0.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 19l-7-7 7-7" />
              </svg>
              Back to content list
            </Link>
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-semibold text-warm-900">
                {outline.page_name ?? pageInfo?.url ?? pageId}
              </h1>
              {outline.primary_keyword && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-sm text-xs font-medium bg-palm-100 text-palm-700 border border-palm-200">
                  {outline.primary_keyword}
                </span>
              )}
              <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium ${
                isDraft ? 'bg-lagoon-100 text-lagoon-700 border border-lagoon-200' : 'bg-palm-100 text-palm-700 border border-palm-200'
              }`}>
                {isDraft ? 'Draft Outline' : 'Approved Outline'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Revision warning */}
      {isRevising && (
        <div className="mb-4 px-4 py-3 bg-coral-50 border border-coral-200 rounded-sm flex items-center gap-2.5">
          <svg className="w-4 h-4 text-coral-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
          <p className="text-sm text-coral-700">
            Regenerating content from this outline will replace the current content.
          </p>
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-6 items-start">
        {/* Left column: Editable sections */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Audience */}
          <div className="bg-white rounded-sm border border-sand-500 p-5">
            <label className="text-sm font-semibold text-warm-800 mb-2.5 block">Audience</label>
            <textarea
              value={outline.audience ?? ''}
              onChange={(e) => updateField('audience', e.target.value)}
              rows={3}
              className="w-full px-3 py-2.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all resize-none"
              style={{ minHeight: '60px', height: 'auto' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = 'auto';
                target.style.height = target.scrollHeight + 'px';
              }}
            />
          </div>

          {/* Page Progression */}
          <div className="bg-white rounded-sm border border-sand-500 p-5">
            <label className="text-sm font-semibold text-warm-800 mb-3 block">Page Progression</label>
            <div className="space-y-2">
              {progression.map((section, index) => (
                <div key={index} className="flex items-center gap-2 group">
                  <span className="text-xs font-mono text-warm-400 w-6 text-right shrink-0">{index + 1}.</span>
                  <span className="text-xs font-mono text-warm-400 w-8 shrink-0">{section.tag}</span>
                  <input
                    type="text"
                    value={section.headline}
                    onChange={(e) => updateSectionHeadline(index, e.target.value)}
                    className="flex-1 px-2.5 py-1.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all"
                  />
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button type="button" onClick={() => moveSection(index, 'up')} disabled={index === 0} className="p-1 text-warm-400 hover:text-warm-600 disabled:opacity-30" title="Move up">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7" /></svg>
                    </button>
                    <button type="button" onClick={() => moveSection(index, 'down')} disabled={index === progression.length - 1} className="p-1 text-warm-400 hover:text-warm-600 disabled:opacity-30" title="Move down">
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" /></svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section Details */}
          <div className="space-y-4">
            {details.map((detail, index) => {
              const sectionLabel = progression[index]?.headline ?? `Section ${index + 1}`;
              const sectionTag = progression[index]?.tag ?? 'h2';
              return (
                <div key={index} className="bg-white rounded-sm border border-sand-500 p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-xs font-mono text-warm-400 px-1.5 py-0.5 bg-sand-100 rounded-sm">{sectionTag}</span>
                    <h3 className="text-sm font-semibold text-warm-800">{sectionLabel}</h3>
                  </div>
                  <div className="mb-3">
                    <label className="text-xs font-medium text-warm-600 mb-1 block">Headline</label>
                    <input type="text" value={detail.headline ?? ''} onChange={(e) => updateSectionDetail(index, 'headline', e.target.value)} className="w-full px-2.5 py-1.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all" />
                  </div>
                  <div className="mb-3">
                    <label className="text-xs font-medium text-warm-600 mb-1 block">Purpose</label>
                    <input type="text" value={detail.purpose ?? ''} onChange={(e) => updateSectionDetail(index, 'purpose', e.target.value)} className="w-full px-2.5 py-1.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all" />
                  </div>
                  <div className="mb-3">
                    <label className="text-xs font-medium text-warm-600 mb-1 block">Key Points</label>
                    <div className="space-y-1.5">
                      {(detail.key_points ?? []).map((point, ptIdx) => (
                        <div key={ptIdx} className="flex items-center gap-2">
                          <span className="text-xs text-warm-400">-</span>
                          <input type="text" value={point} onChange={(e) => updateKeyPoint(index, ptIdx, e.target.value)} className="flex-1 px-2.5 py-1.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all" />
                          <button type="button" onClick={() => removeKeyPoint(index, ptIdx)} className="p-1 text-warm-400 hover:text-coral-500 transition-colors" title="Remove">
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                          </button>
                        </div>
                      ))}
                      <button type="button" onClick={() => addKeyPoint(index)} className="text-xs text-lagoon-600 hover:text-lagoon-700 font-medium mt-1">+ Add point</button>
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-medium text-warm-600 mb-1 block">Client Notes</label>
                    <textarea value={detail.client_notes ?? ''} onChange={(e) => updateSectionDetail(index, 'client_notes', e.target.value)} rows={2} className="w-full px-2.5 py-2 text-sm bg-amber-50 border border-amber-200 rounded-sm text-warm-900 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all resize-none" placeholder="Add notes for the writer..." />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Sidebar: Read-only reference */}
        <div className="w-[340px] flex-shrink-0 space-y-4 sticky top-[72px] max-h-[calc(100vh-140px)] overflow-y-auto pb-4 sidebar-scroll">
          {lsiTerms.length > 0 && (
            <div className="bg-white rounded-sm border border-sand-500 p-4">
              <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">LSI Terms</h3>
              <div className="space-y-1">
                {lsiTerms.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-warm-700">{item.term}</span>
                    {item.target_count != null && <span className="font-mono text-warm-400">target: {item.target_count}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {variations.length > 0 && (
            <div className="bg-white rounded-sm border border-sand-500 p-4">
              <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Keyword Variations</h3>
              <div className="space-y-1">
                {variations.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-warm-700">{item.variation}</span>
                    {item.verbatim_required && <span className="text-xs text-palm-600 font-medium">verbatim</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
          {paa.length > 0 && (
            <div className="bg-white rounded-sm border border-sand-500 p-4">
              <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">People Also Ask</h3>
              <ul className="space-y-1.5">
                {paa.map((q, i) => <li key={i} className="text-xs text-warm-600 leading-relaxed">{q}</li>)}
              </ul>
            </div>
          )}
          {competitors.length > 0 && (
            <div className="bg-white rounded-sm border border-sand-500 p-4">
              <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Top Competitors</h3>
              <div className="space-y-2">
                {competitors.map((comp, i) => (
                  <div key={i} className="text-xs">
                    <p className="text-warm-700 font-medium truncate" title={comp.url}>{comp.title ?? comp.url}</p>
                    <div className="flex items-center gap-2 text-warm-400">
                      <span className="truncate max-w-[200px]">{comp.url}</span>
                      {comp.word_count != null && <span className="font-mono shrink-0">{comp.word_count} words</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(outline.secondary_keywords ?? []).length > 0 && (
            <div className="bg-white rounded-sm border border-sand-500 p-4">
              <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Secondary Keywords</h3>
              <div className="flex flex-wrap gap-1.5">
                {(outline.secondary_keywords ?? []).map((kw, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 bg-sand-100 text-warm-600 rounded-sm">{kw}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-sand-300 z-30 shadow-[0_-1px_0_rgba(201,189,168,0.4),0_-4px_16px_rgba(0,0,0,0.04)]">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-warm-400">
            {saveStatus === 'saving' ? (
              <><div className="w-1.5 h-1.5 rounded-full bg-lagoon-400 animate-pulse" />Saving...</>
            ) : saveStatus === 'saved' ? (
              <><div className="w-1.5 h-1.5 rounded-full bg-palm-400" /><span className="text-palm-600">Saved</span></>
            ) : saveStatus === 'failed' ? (
              <><div className="w-1.5 h-1.5 rounded-full bg-coral-400" /><span className="text-coral-600">Save failed</span></>
            ) : isDirty ? (
              <><div className="w-1.5 h-1.5 rounded-full bg-warm-300" />Unsaved changes</>
            ) : (
              <><div className="w-1.5 h-1.5 rounded-full bg-warm-300" />No changes</>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button type="button" onClick={handleSaveDraft} disabled={updateOutlineMutation.isPending || !isDirty} className="px-4 py-2 text-sm font-medium text-white bg-palm-500 hover:bg-palm-600 rounded-sm transition-colors disabled:opacity-50">
              {updateOutlineMutation.isPending ? 'Saving...' : 'Save Draft'}
            </button>

            {/* Export to Google Doc */}
            {content.google_doc_url ? (
              <div className="flex items-center gap-1.5">
                <a href={content.google_doc_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-lagoon-700 bg-lagoon-50 hover:bg-lagoon-100 border border-lagoon-200 rounded-sm transition-colors">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                  Open Google Doc
                </a>
                <button type="button" disabled={exportOutlineMutation.isPending || updateOutlineMutation.isPending} onClick={() => handleExport(true)} className="inline-flex items-center gap-1 px-2.5 py-2 text-sm text-warm-500 hover:text-warm-700 hover:bg-sand-100 rounded-sm transition-colors disabled:opacity-50" title="Re-export outline to Google Doc">
                  {exportOutlineMutation.isPending ? (
                    <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                  )}
                </button>
                {exportError && <p className="text-xs text-coral-600">{exportError}</p>}
              </div>
            ) : (
              <button type="button" disabled={!content.outline_json || exportOutlineMutation.isPending || updateOutlineMutation.isPending} onClick={() => handleExport()} className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-warm-600 bg-sand-200 hover:bg-sand-300 rounded-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                {exportOutlineMutation.isPending ? (
                  <><svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>Exporting...</>
                ) : 'Export to Google Doc'}
              </button>
            )}

            {/* Approve Outline (draft only) */}
            {isDraft && (
              <button type="button" onClick={handleApprove} disabled={approveOutlineMutation.isPending} className="px-5 py-2 text-sm font-semibold text-white bg-palm-500 hover:bg-palm-600 rounded-sm transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                {approveOutlineMutation.isPending ? 'Approving...' : 'Approve Outline'}
              </button>
            )}

            {/* Generate Full Copy (approved only) */}
            {isApproved && (
              <>
                <button type="button" onClick={handleGenerateFullCopy} disabled={generateFromOutlineMutation.isPending} className="px-5 py-2 text-sm font-semibold text-white bg-palm-500 hover:bg-palm-600 rounded-sm transition-colors shadow-sm disabled:opacity-50 flex items-center gap-2">
                  {generateFromOutlineMutation.isPending ? (
                    <><svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>Generating...</>
                  ) : 'Generate Full Copy'}
                </button>
                {generateError && <p className="text-sm text-coral-600">{generateError}</p>}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
