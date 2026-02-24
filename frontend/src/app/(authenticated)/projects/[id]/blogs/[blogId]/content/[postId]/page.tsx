'use client';

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  useBlogPostContent,
  useUpdateBlogPostContent,
  useApproveBlogPostContent,
  useRecheckBlogPostContent,
} from '@/hooks/useBlogs';
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

  const checkTypes = [
    'banned_word',
    'em_dash',
    'ai_pattern',
    'triplet_excess',
    'rhetorical_excess',
    'tier1_ai_word',
    'tier2_ai_excess',
    'negation_contrast',
    'competitor_name',
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
    competitor_name: 'Competitor Names',
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
  contentHtml,
}: {
  wordCount: number;
  headings: { h2: number; h3: number };
  headingTargets: unknown[];
  primaryKeyword: string;
  variations: Set<string>;
  contentHtml: string | null;
}) {
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

  const keywordStats = useMemo(() => {
    if (!contentHtml || !primaryKeyword) return { exact: 0, density: '0' };
    const kw = primaryKeyword.toLowerCase();
    const regex = new RegExp(`\\b${kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
    const stripped = contentHtml.replace(/<[^>]+>/g, ' ');
    const matches = stripped.match(regex);
    const exact = matches?.length ?? 0;
    const words = stripped.split(/\s+/).filter(Boolean);
    const density = words.length > 0 ? ((exact * kw.split(/\s+/).length / words.length) * 100).toFixed(1) : '0';
    return { exact, density };
  }, [contentHtml, primaryKeyword]);

  const variationStats = useMemo(() => {
    if (!contentHtml || variations.size === 0) return { count: 0, words: [] as string[] };
    const stripped = contentHtml.replace(/<[^>]+>/g, ' ');
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
  }, [contentHtml, variations]);

  const paragraphCount = countParagraphs(contentHtml);

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
  contentHtml,
  onJumpToTerm,
}: {
  lsiTerms: string[];
  contentHtml: string | null;
  onJumpToTerm?: (term: string) => void;
}) {
  const termCounts = useMemo(() => {
    if (!contentHtml || lsiTerms.length === 0) return [];
    const text = contentHtml.replace(/<[^>]+>/g, ' ');
    return lsiTerms.map((term) => {
      const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
      const matches = text.match(regex);
      return { term, count: matches?.length ?? 0 };
    });
  }, [contentHtml, lsiTerms]);

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

export default function BlogContentEditorPage() {
  const params = useParams();
  const projectId = params.id as string;
  const blogId = params.blogId as string;
  const postId = params.postId as string;

  const router = useRouter();
  const { data: post, isLoading, isError } = useBlogPostContent(projectId, blogId, postId);
  const updateContent = useUpdateBlogPostContent();
  const approveContent = useApproveBlogPostContent();
  const recheckContent = useRecheckBlogPostContent();

  // Local editable state — initialized from server data (3 fields, no top_description)
  const [pageTitle, setPageTitle] = useState<string | null>(null);
  const [metaDescription, setMetaDescription] = useState<string | null>(null);
  const [contentHtml, setContentHtml] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Auto-save: track last-saved values to detect dirty fields
  const lastSavedRef = useRef<{
    title: string | null;
    meta_description: string | null;
    content: string | null;
  }>({ title: null, meta_description: null, content: null });

  // Auto-save: status indicator state
  const [saveStatus, setSaveStatus] = useState<
    | { state: 'idle' }
    | { state: 'saving' }
    | { state: 'saved'; at: number }
    | { state: 'failed'; error: string }
  >({ state: 'idle' });

  const [savedTimeLabel, setSavedTimeLabel] = useState('just now');

  // Initialize local state when post loads
  if (post && !initialized) {
    setPageTitle(post.title);
    setMetaDescription(post.meta_description);
    setContentHtml(post.content);
    lastSavedRef.current = {
      title: post.title,
      meta_description: post.meta_description,
      content: post.content,
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

  // Derive keyword and brief data from BlogPost.pop_brief
  const primaryKeyword = post?.primary_keyword ?? '';
  const popBrief = post?.pop_brief as Record<string, unknown> | null;

  const lsiTerms = useMemo(() => {
    const rawTerms = popBrief?.lsi_terms;
    if (!rawTerms || !Array.isArray(rawTerms)) return [];
    return (rawTerms as { term?: string; text?: string; phrase?: string }[])
      .map((t) => (typeof t === 'string' ? t : t.term ?? t.text ?? t.phrase ?? ''))
      .filter(Boolean);
  }, [popBrief?.lsi_terms]);

  const headingTargets = useMemo(() => {
    const targets = popBrief?.heading_targets;
    if (!targets || !Array.isArray(targets)) return [];
    return targets;
  }, [popBrief?.heading_targets]);

  const variations = useMemo(() => generateVariations(primaryKeyword), [primaryKeyword]);

  // Clean QA context: strip "..." ellipsis wrappers from context strings
  const cleanContext = useCallback((ctx: string): string => {
    return ctx.replace(/^\.{3}/, '').replace(/\.{3}$/, '').trim();
  }, []);

  // Derive trope ranges from QA issues in content field
  const tropeRanges = useMemo(() => {
    const qa = post?.qa_results as QaResults | null;
    if (!qa?.issues) return [];
    return qa.issues
      .filter((issue) => issue.field === 'content')
      .map((issue) => ({ text: cleanContext(issue.context) }))
      .filter((r) => r.text.length > 3);
  }, [post?.qa_results, cleanContext]);

  // Ref to the content editor container for jump-to
  const editorContainerRef = useRef<HTMLDivElement>(null);

  const handleJumpToTerm = useCallback((term: string) => {
    const container = editorContainerRef.current;
    if (!container) return;

    const lsiSpans = Array.from(container.querySelectorAll('.hl-lsi'));
    let target: HTMLElement | null = null;
    for (const span of lsiSpans) {
      if (span.textContent && span.textContent.toLowerCase().includes(term.toLowerCase())) {
        target = span as HTMLElement;
        break;
      }
    }

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
  const contentWordCount = countWords(contentHtml);
  const totalWordCount = countWords(pageTitle) + countWords(metaDescription) + contentWordCount;
  const headingCounts = countHeadings(contentHtml);

  // Auto-save on blur: saves only dirty fields
  const handleBlurSave = useCallback(() => {
    if (!post) return;
    const last = lastSavedRef.current;
    const dirty: Record<string, string | null> = {};
    if (pageTitle !== last.title) dirty.title = pageTitle;
    if (metaDescription !== last.meta_description) dirty.meta_description = metaDescription;
    if (contentHtml !== last.content) dirty.content = contentHtml;

    if (Object.keys(dirty).length === 0) return;

    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      { projectId, blogId, postId, data: dirty },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            title: pageTitle,
            meta_description: metaDescription,
            content: contentHtml,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, blogId, postId, pageTitle, metaDescription, contentHtml, post, updateContent]);

  // Manual save: saves all fields regardless of dirty state
  const handleSave = useCallback(() => {
    if (!post) return;
    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      {
        projectId,
        blogId,
        postId,
        data: {
          title: pageTitle,
          meta_description: metaDescription,
          content: contentHtml,
        },
      },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            title: pageTitle,
            meta_description: metaDescription,
            content: contentHtml,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, blogId, postId, pageTitle, metaDescription, contentHtml, post, updateContent]);

  // Approve handler — approve and navigate back to the blog content list
  const handleApprove = useCallback(() => {
    approveContent.mutate(
      {
        projectId,
        blogId,
        postId,
        value: !post?.content_approved,
      },
      {
        onSuccess: () => {
          router.push(`/projects/${projectId}/blogs/${blogId}/content`);
        },
      },
    );
  }, [projectId, blogId, postId, post?.content_approved, approveContent, router]);

  // Recheck handler
  const handleRecheck = useCallback(() => {
    setSaveStatus({ state: 'saving' });
    updateContent.mutate(
      {
        projectId,
        blogId,
        postId,
        data: {
          title: pageTitle,
          meta_description: metaDescription,
          content: contentHtml,
        },
      },
      {
        onSuccess: () => {
          lastSavedRef.current = {
            title: pageTitle,
            meta_description: metaDescription,
            content: contentHtml,
          };
          setSaveStatus({ state: 'saved', at: Date.now() });
          recheckContent.mutate({ projectId, blogId, postId });
        },
        onError: () => {
          setSaveStatus({ state: 'failed', error: 'Save failed — click to retry' });
        },
      },
    );
  }, [projectId, blogId, postId, pageTitle, metaDescription, contentHtml, updateContent, recheckContent]);

  const qaResults = post?.qa_results as QaResults | null;
  const hlClasses = highlightVisibilityClasses(hlVisibility);

  // Loading state
  if (isLoading) {
    return (
      <div className="max-w-[1600px] mx-auto">
        <div className="bg-white rounded-sm border border-sand-400/60 p-6 shadow-sm animate-pulse">
          <div className="h-6 bg-sand-300 rounded w-64 mb-4" />
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
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
          <p className="text-warm-600 mb-4">Failed to load content for this blog post.</p>
          <Link href={`/projects/${projectId}/blogs/${blogId}/content`}>
            <Button variant="secondary">Back to Content</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!post) return null;

  return (
    <div className="max-w-[1600px] mx-auto pb-24">
      {/* Page Header */}
      <div className="pt-1 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <Link
              href={`/projects/${projectId}/blogs/${blogId}/content`}
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
                {post.primary_keyword}
              </h1>
              {post.url_slug && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-sm text-xs font-medium bg-palm-100 text-palm-700 border border-palm-200">
                  /{post.url_slug}
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

          {/* Field 3: Content (Lexical Editor) */}
          <div ref={editorContainerRef} className={`field-section bg-white rounded-sm border border-sand-400/60 ${hlClasses}`}>
            <div className="flex items-center justify-between px-5 pt-4 pb-0">
              <label className="text-sm font-semibold text-warm-800">Content</label>
            </div>

            <ContentEditorWithSource
              initialHtml={contentHtml ?? ''}
              onChange={setContentHtml}
              onBlur={handleBlurSave}
              primaryKeyword={primaryKeyword}
              variations={variations}
              lsiTerms={lsiTerms}
              tropeRanges={tropeRanges}
            />

            {/* Word count + heading count footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-sand-200 bg-sand-50/50">
              <span className="text-xs font-mono text-warm-500">{contentWordCount} words</span>
              <div className="flex items-center gap-4 text-xs text-warm-400">
                <span>{headingCounts.h2} H2</span>
                <span className="text-warm-300">·</span>
                <span>{headingCounts.h3} H3</span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Sidebar (~35%) */}
        <div className="w-[340px] flex-shrink-0 space-y-4 sticky top-[72px] max-h-[calc(100vh-140px)] overflow-y-auto pb-4 sidebar-scroll">
          <QualityStatusCard qaResults={qaResults} />
          <ContentStatsCard
            wordCount={totalWordCount}
            headings={headingCounts}
            headingTargets={headingTargets}
            primaryKeyword={primaryKeyword}
            variations={variations}
            contentHtml={contentHtml}
          />
          <LsiTermsCard lsiTerms={lsiTerms} contentHtml={contentHtml} onJumpToTerm={handleJumpToTerm} />
          <HeadingOutlineCard html={contentHtml} onJumpToHeading={handleJumpToHeading} />
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
              className="px-4 py-2 text-sm font-medium text-warm-600 bg-sand-200 hover:bg-sand-300 rounded-sm transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {recheckContent.isPending && (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              )}
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
              className={`px-5 py-2 text-sm font-semibold rounded-sm transition-colors flex items-center gap-2 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed ${
                post.content_approved
                  ? 'text-palm-700 bg-palm-100 hover:bg-palm-200 border border-palm-200'
                  : 'text-white bg-palm-500 hover:bg-palm-600'
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
              {post.content_approved ? 'Approved' : 'Approve'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
