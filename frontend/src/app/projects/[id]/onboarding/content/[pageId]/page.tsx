'use client';

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  usePageContent,
  useContentGenerationStatus,
  useUpdatePageContent,
  useApprovePageContent,
  useRecheckPageContent,
} from '@/hooks/useContentGeneration';
import { ContentEditorWithSource } from '@/components/content-editor/ContentEditorWithSource';
import {
  HighlightToggleControls,
  type HighlightVisibility,
  highlightVisibilityClasses,
} from '@/components/content-editor/HighlightToggleControls';
import { generateVariations } from '@/lib/keyword-variations';
import { Button } from '@/components/ui';

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

function countWords(text: string | null | undefined): number {
  if (!text) return 0;
  const stripped = text.replace(/<[^>]+>/g, ' ');
  return stripped.split(/\s+/).filter(Boolean).length;
}

function countHeadings(html: string | null | undefined): { h2: number; h3: number } {
  if (!html) return { h2: 0, h3: 0 };
  const h2 = (html.match(/<h2[\s>]/gi) || []).length;
  const h3 = (html.match(/<h3[\s>]/gi) || []).length;
  return { h2, h3 };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CharCounter({ value, max }: { value: number; max: number }) {
  const isOver = value > max;
  return (
    <span className={`text-xs font-mono ${isOver ? 'text-coral-600' : 'text-palm-600'}`}>
      {value} / {max}
    </span>
  );
}

function WordCounter({ count }: { count: number }) {
  return <span className="text-xs font-mono text-warm-500">{count} words</span>;
}

interface QaIssue {
  type: string;
  field: string;
  description: string;
  context: string;
}

interface QaResults {
  passed: boolean;
  issues: QaIssue[];
  checked_at?: string;
}

function QualityStatusCard({ qaResults }: { qaResults: QaResults | null }) {
  if (!qaResults) return null;

  const issueCount = qaResults.issues?.length ?? 0;
  const passed = qaResults.passed;

  // Build check result summary — group by type to show pass/fail per check category
  const checkTypes = [
    'banned_word',
    'em_dash',
    'ai_pattern',
    'triplet_excess',
    'rhetorical_excess',
    'tier1_ai_word',
    'tier2_ai_excess',
    'negation_contrast',
  ];
  const checkLabels: Record<string, string> = {
    banned_word: 'Banned Words',
    em_dash: 'Em Dashes',
    ai_pattern: 'AI Openers',
    triplet_excess: 'Triplet Lists',
    rhetorical_excess: 'Rhetorical Questions',
    tier1_ai_word: 'Tier 1 AI Words',
    tier2_ai_excess: 'Tier 2 AI Words',
    negation_contrast: 'Negation Contrast',
  };

  const issuesByType: Record<string, number> = {};
  for (const issue of qaResults.issues ?? []) {
    issuesByType[issue.type] = (issuesByType[issue.type] ?? 0) + 1;
  }

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      <div className={`px-4 py-3 border-b ${passed ? 'bg-palm-50 border-palm-100' : 'bg-coral-50 border-coral-100'}`}>
        <div className="flex items-center gap-2">
          <div className={`w-5 h-5 rounded-full flex items-center justify-center ${passed ? 'bg-palm-100' : 'bg-coral-100'}`}>
            {passed ? (
              <svg className="w-3 h-3 text-palm-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-3 h-3 text-coral-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            )}
          </div>
          <span className={`text-sm font-semibold ${passed ? 'text-palm-800' : 'text-coral-800'}`}>
            {passed ? 'All Checks Passed' : `${issueCount} Issue${issueCount !== 1 ? 's' : ''} Found`}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-2">
        {checkTypes.map((type) => {
          const count = issuesByType[type] ?? 0;
          return (
            <div key={type} className="flex items-center justify-between text-xs">
              <span className="text-warm-600">{checkLabels[type] ?? type}</span>
              {count > 0 ? (
                <span className="text-coral-600 font-medium">{count} found</span>
              ) : (
                <span className="text-palm-600 font-medium">Pass</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FlaggedPassagesCard({
  issues,
  onJumpTo,
}: {
  issues: QaIssue[];
  onJumpTo?: (context: string) => void;
}) {
  if (!issues || issues.length === 0) return null;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 p-4">
      <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Flagged Passages</h3>
      <div className="space-y-3">
        {issues.map((issue, idx) => (
          <div key={idx} className="flex items-start gap-2.5">
            <div className="w-1.5 h-1.5 rounded-full bg-coral-500 mt-1.5 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-xs font-medium text-warm-800">{issue.description}</p>
              <p className="text-xs text-warm-500 mt-0.5 leading-relaxed">
                &ldquo;{issue.context}&rdquo;
              </p>
              {onJumpTo && (
                <button
                  type="button"
                  onClick={() => onJumpTo(issue.context)}
                  className="text-xs text-lagoon-600 hover:text-lagoon-700 mt-1 font-medium"
                >
                  Jump to &darr;
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function countParagraphs(html: string | null | undefined): number {
  if (!html) return 0;
  return (html.match(/<p[\s>]/gi) || []).length;
}

function ContentStatsCard({
  wordCount,
  headings,
  headingTargets,
  primaryKeyword,
  variations,
  bottomHtml,
}: {
  wordCount: number;
  headings: { h2: number; h3: number };
  headingTargets: unknown[];
  primaryKeyword: string;
  variations: Set<string>;
  bottomHtml: string | null;
}) {
  // Derive heading target ranges from brief
  const headingTargetDisplay = useMemo(() => {
    const targets = headingTargets as { level?: string; min_count?: number; max_count?: number }[];
    const h2Target = targets.find((t) => t.level === 'h2');
    const h3Target = targets.find((t) => t.level === 'h3');
    const h2 = h2Target ? `${h2Target.min_count ?? 0}–${h2Target.max_count ?? '?'}` : null;
    const h3 = h3Target ? `${h3Target.min_count ?? 0}–${h3Target.max_count ?? '?'}` : null;
    if (!h2 && !h3) return null;
    const parts: string[] = [];
    if (h2) parts.push(`${h2} H2`);
    if (h3) parts.push(`${h3} H3`);
    return `Target: ${parts.join(', ')}`;
  }, [headingTargets]);

  // Count exact keyword matches in bottom description
  const keywordStats = useMemo(() => {
    if (!bottomHtml || !primaryKeyword) return { exact: 0, density: '0' };
    const kw = primaryKeyword.toLowerCase();
    const regex = new RegExp(`\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
    const stripped = bottomHtml.replace(/<[^>]+>/g, ' ');
    const matches = stripped.match(regex);
    const exact = matches?.length ?? 0;
    const words = stripped.split(/\s+/).filter(Boolean);
    const density = words.length > 0 ? ((exact * kw.split(/\s+/).length / words.length) * 100).toFixed(1) : '0';
    return { exact, density };
  }, [bottomHtml, primaryKeyword]);

  // Count variation matches in bottom description
  const variationStats = useMemo(() => {
    if (!bottomHtml || variations.size === 0) return { count: 0, words: [] as string[] };
    const stripped = bottomHtml.replace(/<[^>]+>/g, ' ');
    const found: { word: string; count: number }[] = [];
    for (const v of Array.from(variations)) {
      const regex = new RegExp(`\\b${v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      const matches = stripped.match(regex);
      if (matches && matches.length > 0) {
        found.push({ word: v, count: matches.length });
      }
    }
    return {
      count: found.reduce((sum, f) => sum + f.count, 0),
      words: found.map((f) => f.word),
    };
  }, [bottomHtml, variations]);

  const paragraphCount = countParagraphs(bottomHtml);

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 p-4">
      <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Content Stats</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="text-warm-600">Word Count</span>
          <span className="font-mono font-medium text-warm-800">{wordCount}</span>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-warm-600">Headings</span>
            <span className="font-mono font-medium text-warm-800">{headings.h2} H2 · {headings.h3} H3</span>
          </div>
          {headingTargetDisplay && (
            <div className="text-xs text-warm-400">{headingTargetDisplay}</div>
          )}
        </div>
        <div className="h-px bg-sand-200" />
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-warm-600">Exact match</span>
            <span className="font-mono font-medium text-warm-800">{keywordStats.exact} uses</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 bg-sand-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-palm-400 rounded-full"
                style={{ width: `${Math.min(parseFloat(keywordStats.density) * 25, 100)}%` }}
              />
            </div>
            <span className="text-xs font-mono text-warm-500">{keywordStats.density}%</span>
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-warm-600">Variations</span>
            <span className="font-mono font-medium text-warm-800">{variationStats.count} uses</span>
          </div>
          {variationStats.words.length > 0 && (
            <div className="text-xs text-warm-400">{variationStats.words.join(', ')}</div>
          )}
        </div>
        <div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-warm-600">Paragraphs</span>
            <span className="font-mono font-medium text-warm-800">{paragraphCount}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LsiTermsCard({
  lsiTerms,
  bottomHtml,
  onJumpToTerm,
}: {
  lsiTerms: string[];
  bottomHtml: string | null;
  onJumpToTerm?: (term: string) => void;
}) {
  const termCounts = useMemo(() => {
    if (!bottomHtml || lsiTerms.length === 0) return [];
    const text = bottomHtml.replace(/<[^>]+>/g, ' ');
    return lsiTerms.map((term) => {
      const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      const matches = text.match(regex);
      return { term, count: matches?.length ?? 0 };
    });
  }, [bottomHtml, lsiTerms]);

  const found = termCounts.filter((t) => t.count > 0);
  const missing = termCounts.filter((t) => t.count === 0);

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider">LSI Terms</h3>
        <span className="text-xs font-mono text-palm-600 font-medium">
          {found.length} / {termCounts.length}
        </span>
      </div>
      <p className="text-xs text-warm-500 mb-2">
        {found.length} of {termCounts.length} terms used
      </p>
      <div className="space-y-1.5">
        {found.map((t) => (
          <div
            key={t.term}
            className="relative flex items-center justify-between py-1 px-2 rounded-sm hover:bg-sand-50 cursor-pointer group lsi-found"
            onClick={() => onJumpToTerm?.(t.term)}
          >
            <div className="absolute left-[-8px] top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-palm-500" />
            <span className="text-xs text-warm-800">{t.term}</span>
            <span className="text-xs font-mono text-palm-600 opacity-0 group-hover:opacity-100 transition-opacity">
              {t.count}×
            </span>
          </div>
        ))}
        {missing.length > 0 && found.length > 0 && <div className="h-px bg-sand-200 my-1" />}
        {missing.map((t) => (
          <div key={t.term} className="flex items-center justify-between py-1 px-2 rounded-sm">
            <span className="text-xs text-warm-600">{t.term}</span>
            <span className="text-xs text-warm-400 italic">not found</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HeadingOutlineCard({
  html,
  onJumpToHeading,
}: {
  html: string | null;
  onJumpToHeading?: (text: string, level: string) => void;
}) {
  const headings = useMemo(() => {
    if (!html) return [];
    const regex = /<(h[23])[^>]*>(.*?)<\/\1>/gi;
    const result: { level: string; text: string }[] = [];
    let match;
    while ((match = regex.exec(html)) !== null) {
      const text = match[2].replace(/<[^>]+>/g, '');
      result.push({ level: match[1].toUpperCase(), text });
    }
    return result;
  }, [html]);

  if (headings.length === 0) return null;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 p-4">
      <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-3">Structure</h3>
      <div className="space-y-1">
        {headings.map((h, idx) => (
          <div
            key={idx}
            role="button"
            tabIndex={0}
            onClick={() => onJumpToHeading?.(h.text, h.level)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onJumpToHeading?.(h.text, h.level); }}
            className={`text-xs py-0.5 cursor-pointer transition-colors hover:text-palm-600 ${
              h.level === 'H2'
                ? 'text-warm-700 font-medium'
                : 'text-warm-500 pl-4'
            } ${h.level === 'H2' && idx > 0 ? 'mt-1' : ''}`}
          >
            {h.level} — {h.text}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function ContentEditorPage() {
  const params = useParams();
  const projectId = params.id as string;
  const pageId = params.pageId as string;

  const { data: content, isLoading, isError } = usePageContent(projectId, pageId);
  const { data: status } = useContentGenerationStatus(projectId);
  const updateContent = useUpdatePageContent();
  const approveContent = useApprovePageContent();
  const recheckContent = useRecheckPageContent();

  // Find this page's metadata from the status endpoint
  const pageInfo = useMemo(() => {
    if (!status?.pages) return null;
    return status.pages.find((p) => p.page_id === pageId) ?? null;
  }, [status, pageId]);

  // Local editable state — initialized from server data
  const [pageTitle, setPageTitle] = useState<string | null>(null);
  const [metaDescription, setMetaDescription] = useState<string | null>(null);
  const [topDescription, setTopDescription] = useState<string | null>(null);
  const [bottomDescription, setBottomDescription] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Auto-save: track last-saved values to detect dirty fields
  const lastSavedRef = useRef<{
    page_title: string | null;
    meta_description: string | null;
    top_description: string | null;
    bottom_description: string | null;
  }>({ page_title: null, meta_description: null, top_description: null, bottom_description: null });

  // Auto-save: status indicator state
  const [saveStatus, setSaveStatus] = useState<
    | { state: 'idle' }
    | { state: 'saving' }
    | { state: 'saved'; at: number }
    | { state: 'failed'; error: string }
  >({ state: 'idle' });

  // Relative time label for "Auto-saved X ago"
  const [savedTimeLabel, setSavedTimeLabel] = useState('just now');

  // Initialize local state when content loads
  if (content && !initialized) {
    setPageTitle(content.page_title);
    setMetaDescription(content.meta_description);
    setTopDescription(content.top_description);
    setBottomDescription(content.bottom_description);
    lastSavedRef.current = {
      page_title: content.page_title,
      meta_description: content.meta_description,
      top_description: content.top_description,
      bottom_description: content.bottom_description,
    };
    setInitialized(true);
  }

  // Update the relative time label periodically
  useEffect(() => {
    if (saveStatus.state !== 'saved') return;
    const update = () => {
      const elapsed = Math.floor((Date.now() - (saveStatus as { state: 'saved'; at: number }).at) / 1000);
      if (elapsed < 5) setSavedTimeLabel('just now');
      else if (elapsed < 60) setSavedTimeLabel(`${elapsed}s ago`);
      else setSavedTimeLabel(`${Math.floor(elapsed / 60)} min ago`);
    };
    update();
    const interval = setInterval(update, 10_000);
    return () => clearInterval(interval);
  }, [saveStatus]);

  // Highlight visibility
  const [hlVisibility, setHlVisibility] = useState<HighlightVisibility>({
    keyword: true,
    lsi: true,
    trope: true,
  });

  // Derive keyword and brief data
  const primaryKeyword = content?.brief?.keyword ?? content?.brief_summary?.keyword ?? '';
  const lsiTerms = useMemo(() => {
    if (!content?.brief?.lsi_terms) return [];
    return (content.brief.lsi_terms as { term?: string; text?: string }[])
      .map((t) => (typeof t === 'string' ? t : t.term ?? t.text ?? ''))
      .filter(Boolean);
  }, [content?.brief?.lsi_terms]);

  const variations = useMemo(() => generateVariations(primaryKeyword), [primaryKeyword]);

  // Derive trope ranges from QA issues
  const tropeRanges = useMemo(() => {
    const qa = content?.qa_results as QaResults | null;
    if (!qa?.issues) return [];
    return qa.issues.map((issue) => ({ text: issue.context }));
  }, [content?.qa_results]);

  // Ref to the bottom description editor container for jump-to
  const editorContainerRef = useRef<HTMLDivElement>(null);

  // Jump to flagged passage in the Lexical editor
  const handleJumpTo = useCallback((context: string) => {
    const container = editorContainerRef.current;
    if (!container) return;

    // Search for hl-trope spans whose text includes the context
    const tropeSpans = Array.from(container.querySelectorAll('.hl-trope'));
    let target: HTMLElement | null = null;
    for (const span of tropeSpans) {
      if (span.textContent && span.textContent.includes(context.slice(0, 20))) {
        target = span as HTMLElement;
        break;
      }
    }

    // Fallback: search all text in the editor for context substring
    if (!target) {
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      let node: Node | null;
      while ((node = walker.nextNode())) {
        if (node.textContent && node.textContent.includes(context.slice(0, 20))) {
          target = node.parentElement;
          break;
        }
      }
    }

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.classList.add('violation-pulse');
      setTimeout(() => target!.classList.remove('violation-pulse'), 1500);
    }
  }, []);

  const handleJumpToTerm = useCallback((term: string) => {
    const container = editorContainerRef.current;
    if (!container) return;

    // Search for hl-lsi spans whose text matches the term
    const lsiSpans = Array.from(container.querySelectorAll('.hl-lsi'));
    let target: HTMLElement | null = null;
    for (const span of lsiSpans) {
      if (span.textContent && span.textContent.toLowerCase().includes(term.toLowerCase())) {
        target = span as HTMLElement;
        break;
      }
    }

    // Fallback: search all text in the editor for the term
    if (!target) {
      const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      let node: Node | null;
      const termLower = term.toLowerCase();
      while ((node = walker.nextNode())) {
        if (node.textContent && node.textContent.toLowerCase().includes(termLower)) {
          target = node.parentElement;
          break;
        }
      }
    }

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.classList.add('violation-pulse');
      setTimeout(() => target!.classList.remove('violation-pulse'), 1500);
    }
  }, []);

  const handleJumpToHeading = useCallback((text: string, level: string) => {
    const container = editorContainerRef.current;
    if (!container) return;

    const tag = level.toLowerCase();
    const headingEls = Array.from(container.querySelectorAll(tag));
    let target: HTMLElement | null = null;
    for (const el of headingEls) {
      if (el.textContent?.trim() === text.trim()) {
        target = el as HTMLElement;
        break;
      }
    }

    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.classList.add('violation-pulse');
      setTimeout(() => target!.classList.remove('violation-pulse'), 1500);
    }
  }, []);

  // Computed counts
  const titleLen = pageTitle?.length ?? 0;
  const metaLen = metaDescription?.length ?? 0;
  const topWordCount = countWords(topDescription);
  const bottomWordCount = countWords(bottomDescription);
  const totalWordCount = countWords(pageTitle) + countWords(metaDescription) + topWordCount + bottomWordCount;
  const headings = countHeadings(bottomDescription);

  // Auto-save on blur: saves only dirty fields
  const handleBlurSave = useCallback(() => {
    if (!content) return;
    const last = lastSavedRef.current;
    const dirty: Record<string, string | null> = {};
    if (pageTitle !== last.page_title) dirty.page_title = pageTitle;
    if (metaDescription !== last.meta_description) dirty.meta_description = metaDescription;
    if (topDescription !== last.top_description) dirty.top_description = topDescription;
    if (bottomDescription !== last.bottom_description) dirty.bottom_description = bottomDescription;

    if (Object.keys(dirty).length === 0) return;

    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      { projectId, pageId, data: dirty },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            page_title: pageTitle,
            meta_description: metaDescription,
            top_description: topDescription,
            bottom_description: bottomDescription,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, pageId, pageTitle, metaDescription, topDescription, bottomDescription, content, updateContent]);

  // Manual save: saves all fields regardless of dirty state
  const handleSave = useCallback(() => {
    if (!content) return;
    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      {
        projectId,
        pageId,
        data: {
          page_title: pageTitle,
          meta_description: metaDescription,
          top_description: topDescription,
          bottom_description: bottomDescription,
        },
      },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            page_title: pageTitle,
            meta_description: metaDescription,
            top_description: topDescription,
            bottom_description: bottomDescription,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, pageId, pageTitle, metaDescription, topDescription, bottomDescription, content, updateContent]);

  // Approve handler
  const handleApprove = useCallback(() => {
    approveContent.mutate({
      projectId,
      pageId,
      value: !content?.is_approved,
    });
  }, [projectId, pageId, content?.is_approved, approveContent]);

  // Recheck handler
  const handleRecheck = useCallback(() => {
    // Save first, then recheck
    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      {
        projectId,
        pageId,
        data: {
          page_title: pageTitle,
          meta_description: metaDescription,
          top_description: topDescription,
          bottom_description: bottomDescription,
        },
      },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            page_title: pageTitle,
            meta_description: metaDescription,
            top_description: topDescription,
            bottom_description: bottomDescription,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
          recheckContent.mutate({ projectId, pageId });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, pageId, pageTitle, metaDescription, topDescription, bottomDescription, updateContent, recheckContent]);

  const qaResults = content?.qa_results as QaResults | null;
  const hlClasses = highlightVisibilityClasses(hlVisibility);

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-[1600px] mx-auto">
        <div className="bg-white rounded-sm border border-sand-400/60 p-6 shadow-sm animate-pulse">
          <div className="h-6 bg-sand-300 rounded w-64 mb-4" />
          <div className="space-y-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-sand-200 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="max-w-[1600px] mx-auto">
        <div className="bg-white rounded-sm border border-sand-400/60 p-6 shadow-sm text-center py-12">
          <p className="text-warm-600 mb-4">Failed to load content for this page.</p>
          <Link href={`/projects/${projectId}/onboarding/content`}>
            <Button variant="secondary">Back to Content</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!content) return null;

  return (
    <div className="max-w-[1600px] mx-auto pb-24">
      {/* Page Header */}
      <div className="pt-1 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <Link
              href={`/projects/${projectId}/onboarding/content`}
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
                {pageInfo?.url ?? pageId}
              </h1>
              {primaryKeyword && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-sm text-xs font-medium bg-palm-100 text-palm-700 border border-palm-200">
                  {primaryKeyword}
                </span>
              )}
            </div>
          </div>

          {/* Highlight Controls */}
          <div className="mt-6">
            <HighlightToggleControls onChange={setHlVisibility} />
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="flex gap-6 items-start">
        {/* Left Column: Editor (~65%) */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* Field 1: Page Title */}
          <div className="field-section bg-white rounded-sm border border-sand-400/60 p-5">
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-sm font-semibold text-warm-800">Page Title</label>
              <CharCounter value={titleLen} max={70} />
            </div>
            <input
              type="text"
              value={pageTitle ?? ''}
              onChange={(e) => setPageTitle(e.target.value)}
              onBlur={handleBlurSave}
              className="w-full px-3 py-2.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all"
            />
          </div>

          {/* Field 2: Meta Description */}
          <div className="field-section bg-white rounded-sm border border-sand-400/60 p-5">
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-sm font-semibold text-warm-800">Meta Description</label>
              <CharCounter value={metaLen} max={160} />
            </div>
            <textarea
              rows={2}
              value={metaDescription ?? ''}
              onChange={(e) => setMetaDescription(e.target.value)}
              onBlur={handleBlurSave}
              className="w-full px-3 py-2.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all resize-none"
            />
          </div>

          {/* Field 3: Top Description */}
          <div className="field-section bg-white rounded-sm border border-sand-400/60 p-5">
            <div className="flex items-center justify-between mb-2.5">
              <label className="text-sm font-semibold text-warm-800">Top Description</label>
              <WordCounter count={topWordCount} />
            </div>
            <textarea
              rows={3}
              value={topDescription ?? ''}
              onChange={(e) => setTopDescription(e.target.value)}
              onBlur={handleBlurSave}
              className="w-full px-3 py-2.5 text-sm bg-sand-50 border border-sand-300 rounded-sm text-warm-900 placeholder-warm-400 focus:outline-none focus:ring-2 focus:ring-palm-400/30 focus:border-palm-400 transition-all resize-none leading-relaxed"
            />
          </div>

          {/* Field 4: Bottom Description (Lexical Editor) */}
          <div ref={editorContainerRef} className={`field-section bg-white rounded-sm border border-sand-400/60 ${hlClasses}`}>
            <div className="flex items-center justify-between px-5 pt-4 pb-0">
              <label className="text-sm font-semibold text-warm-800">Bottom Description</label>
            </div>

            <ContentEditorWithSource
              initialHtml={bottomDescription ?? ''}
              onChange={setBottomDescription}
              onBlur={handleBlurSave}
              primaryKeyword={primaryKeyword}
              variations={variations}
              lsiTerms={lsiTerms}
              tropeRanges={tropeRanges}
            />

            {/* Word count footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-sand-200 bg-sand-50/50">
              <span className="text-xs font-mono text-warm-500">{bottomWordCount} words</span>
              <div className="flex items-center gap-4 text-xs text-warm-400">
                <span>{headings.h2} H2</span>
                <span className="text-warm-300">·</span>
                <span>{headings.h3} H3</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebar (~35%) */}
        <div className="w-[340px] flex-shrink-0 space-y-4 sticky top-[72px] max-h-[calc(100vh-140px)] overflow-y-auto pb-4 sidebar-scroll">
          <QualityStatusCard qaResults={qaResults} />
          <FlaggedPassagesCard issues={qaResults?.issues ?? []} onJumpTo={handleJumpTo} />
          <ContentStatsCard
            wordCount={totalWordCount}
            headings={headings}
            headingTargets={content?.brief?.heading_targets ?? []}
            primaryKeyword={primaryKeyword}
            variations={variations}
            bottomHtml={bottomDescription}
          />
          <LsiTermsCard lsiTerms={lsiTerms} bottomHtml={bottomDescription} onJumpToTerm={handleJumpToTerm} />
          <HeadingOutlineCard html={bottomDescription} onJumpToHeading={handleJumpToHeading} />
        </div>
      </div>

      {/* Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-sand-300 z-30 shadow-[0_-1px_0_rgba(201,189,168,0.4),0_-4px_16px_rgba(0,0,0,0.04)]">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex items-center justify-between">
          {/* Left: save status */}
          <div className="flex items-center gap-2 text-xs text-warm-400">
            {saveStatus.state === 'saving' ? (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-lagoon-400 animate-pulse" />
                Saving&hellip;
              </>
            ) : saveStatus.state === 'saved' ? (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-palm-400" />
                <span className="text-palm-600">Auto-saved {savedTimeLabel}</span>
              </>
            ) : saveStatus.state === 'failed' ? (
              <button
                type="button"
                onClick={handleSave}
                className="flex items-center gap-2 text-coral-600 hover:text-coral-700 transition-colors"
              >
                <div className="w-1.5 h-1.5 rounded-full bg-coral-400" />
                {saveStatus.error}
              </button>
            ) : (
              <>
                <div className="w-1.5 h-1.5 rounded-full bg-warm-300" />
                Unsaved changes
              </>
            )}
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleRecheck}
              disabled={recheckContent.isPending || saveStatus.state === 'saving'}
              className="px-4 py-2 text-sm font-medium text-warm-600 bg-sand-200 hover:bg-sand-300 rounded-sm transition-colors disabled:opacity-50"
            >
              {recheckContent.isPending ? 'Checking...' : 'Re-run Checks'}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saveStatus.state === 'saving'}
              className="px-4 py-2 text-sm font-medium text-warm-700 bg-white border border-sand-400 hover:bg-sand-50 rounded-sm transition-colors disabled:opacity-50"
            >
              {saveStatus.state === 'saving' ? 'Saving...' : 'Save Draft'}
            </button>
            <button
              type="button"
              onClick={handleApprove}
              disabled={approveContent.isPending}
              className={`px-5 py-2 text-sm font-semibold rounded-sm transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50 ${
                content.is_approved
                  ? 'text-warm-700 bg-sand-200 hover:bg-sand-300'
                  : 'text-white bg-palm-500 hover:bg-palm-600'
              }`}
            >
              {content.is_approved ? (
                'Unapprove'
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                  </svg>
                  Approve
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
