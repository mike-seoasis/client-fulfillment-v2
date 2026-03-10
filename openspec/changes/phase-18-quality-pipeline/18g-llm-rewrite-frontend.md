# 18g: LLM + Rewrite Frontend

## Overview

Add AI Evaluation scores and auto-rewrite status display to the content editor sidebar. This phase assumes 18d (QualityPanel extraction), 18e (LLM Judge backend), and 18f (Auto-Rewrite backend) are complete, so the frontend has structured data to render.

**Scope:** Three new components (`ScoreBar`, `RewriteBanner`, `VersionDiffModal`), plus modifications to `QualityPanel.tsx` and the three content editor pages.

**Data contract:** All data comes from `qa_results` on the `PageContentResponse`. After 18e+18f, the shape expands to:

```typescript
interface QaResults {
  passed: boolean;
  issues: QaIssue[];
  checked_at?: string;
  composite_score?: number;       // 0-100, from quality_pipeline.py
  score_tier?: string;            // 'publish_ready' | 'minor_issues' | 'needs_attention' | 'needs_rewrite'
  tier2?: {
    model: string;                // e.g. 'gpt-5.4'
    naturalness: number;          // 0.0 - 1.0
    brief_adherence: number;      // 0.0 - 1.0
    heading_structure: number;    // 0.0 - 1.0
    explanations?: {
      naturalness?: string;
      brief_adherence?: string;
      heading_structure?: string;
    };
  };
  bible_checks?: {
    bible_name: string;
    bible_id: string;
    issues: QaIssue[];
  }[];
  rewrite?: {
    triggered: boolean;
    original_score: number;
    fixed_score: number;
    issues_sent: number;
    issues_resolved: number;
    issues_remaining: number;
    issues_new: number;
    changes_made: string[];       // e.g. ['"leverage" -> "choosing"', '"In today\'s world" -> removed']
  };
  versions?: {
    original: {
      content_snapshot: {
        page_title: string | null;
        meta_description: string | null;
        top_description: string | null;
        bottom_description: string | null;
      };
      score: number;
    };
    fixed: {
      content_snapshot: {
        page_title: string | null;
        meta_description: string | null;
        top_description: string | null;
        bottom_description: string | null;
      };
      score: number;
      changes_made: string[];
    };
  };
}
```

---

## Decisions (from planner/advocate debate)

### 1. Do we need a full diff modal?

**Planner:** The wireframes spec "View Original" and "View Diff" buttons. A proper side-by-side diff gives operators confidence the auto-rewrite didn't damage content.

**Advocate:** Side-by-side diff on rich HTML content is a disaster. Tables, headings, lists all break. Even GitHub's diff renderer struggles with HTML. The "changes_made" list already tells operators what changed. A full diff modal is over-engineering for a feature that will be used rarely -- operators care about the result, not the process.

**Consensus:** Build a **lightweight VersionDiffModal** that shows:
- Per-field text comparison (plain text, not HTML-rendered) using a simple inline-diff approach
- The `changes_made` summary list prominently at the top
- **No** third-party diff library. Use a simple custom word-level diff function (~30 lines) that wraps added/removed words in `<ins>`/`<del>` tags. For 80% of cases, the `changes_made` list is sufficient; the diff view is a "trust but verify" escape hatch.
- If the diff looks bad for a particular field (e.g., entire paragraphs rewritten), fall back to showing both versions side-by-side as plain text blocks without diff highlighting.

**Decision:** Implement a minimal diff utility. If it proves insufficient, we can add `diff-match-patch` later (4.6KB gzipped, no deps). Do NOT install it preemptively.

### 2. Score bar color scheme

**Planner:** Use the same 4-tier color system as the score badge: palm-500 (green, >= 80), sand-600 (amber, >= 70), coral-400 (orange, >= 50), coral-600 (red, < 50).

**Advocate:** The score bars show 0-1 float values, not 0-100 integers. Using the same exact color tiers would need different thresholds. Also, three separate bars with independent colors create visual noise.

**Consensus:** Score bars use a **single gradient approach**: the bar fill color transitions from coral-500 (0.0) through sand-500 (0.5) to palm-500 (1.0). This is simpler to implement (one function that returns a color based on the value) and more intuitive than discrete tiers. The composite score badge (from 18d) already uses the 4-tier system for the overall score.

```typescript
function scoreBarColor(value: number): string {
  if (value >= 0.8) return 'bg-palm-500';
  if (value >= 0.6) return 'bg-palm-400';
  if (value >= 0.4) return 'bg-sand-500';
  if (value >= 0.2) return 'bg-coral-400';
  return 'bg-coral-500';
}
```

### 3. Should we show cost/latency data to operators?

**Planner:** The backend tracks model name, token counts, and duration. We could show "Evaluated in 2.3s" or cost.

**Advocate:** Operators do not care about cost or latency. That is admin/engineering data. Showing it clutters the UI and creates questions operators cannot answer ("Why did this one take 5 seconds?").

**Consensus:** Show **only** the model name as a small badge (e.g., "GPT-5.4") in the AI Evaluation section header. This gives transparency about what evaluated the content without exposing operational metrics. Cost/latency data stays in backend logs and admin dashboards.

### 4. Should the rewrite banner be collapsible?

**Planner:** The wireframe shows it expanded by default with significant vertical space. Operators may want to dismiss it after reviewing.

**Advocate:** Yes, it must be collapsible. When there are 3 changes, the banner is fine. When there are 8+ changes, it pushes all other sidebar content below the fold. The sidebar is already dense with Content Stats, LSI Terms, Heading Outline, etc.

**Consensus:** The rewrite banner is **collapsible**, defaulting to **expanded** (so operators notice it). It uses the same expand/collapse pattern as the check groups in the QualityPanel (chevron toggle). When collapsed, it shows a single-line summary: "Auto-fixed: 52 -> 88 (3 changes)".

### 5. What about "Revert to Original"?

**Planner:** If the auto-rewrite made things worse (or the operator prefers the original voice), they need a way to revert.

**Advocate:** The backend already keeps the original version. But adding a "Revert" button is dangerous -- it replaces all 4 content fields at once with no undo. This needs confirmation UX.

**Consensus:** Add a **"Restore Original"** button inside the VersionDiffModal (not in the banner itself -- too easy to hit accidentally). When clicked, show a confirmation dialog: "This will replace all content fields with the pre-rewrite version. This cannot be undone. Continue?" On confirm, call `updatePageContent` with the original content snapshot, then trigger a recheck.

### 6. Recheck flow after auto-rewrite

**Planner:** The "Re-run Checks" button currently calls `recheckPageContent` which runs Tier 1 only. After 18e, it should run the full pipeline.

**Advocate:** If recheck runs the full pipeline including auto-rewrite, and the content still scores < 70, it would auto-rewrite again. The plan says "max 1 retry -- no cascading," but does the backend enforce this per-recheck or per-generation?

**Consensus:** The backend (18f) enforces max 1 rewrite per pipeline run. So rechecking always runs the full pipeline (Tier 1 + Tier 2 + potential rewrite). This is correct behavior -- if the operator manually edits content and rechecks, a new rewrite is appropriate because the content changed. The "no cascading" rule means the rewrite step itself won't trigger another rewrite. **No frontend changes needed** beyond what 18e/18f already handle. The existing `recheckPageContent` mutation just needs the backend to call the full pipeline. The frontend shows a loading state during recheck, then renders whatever data comes back.

### 7. Animations/transitions

**Planner:** The design principles say "Subtle, purposeful -- enhance understanding, never distract."

**Advocate:** Animating the rewrite banner on initial load adds unnecessary complexity. CSS transitions on collapse/expand are fine. Don't animate the score bars filling up -- it's not a progress indicator, it's a static score.

**Consensus:**
- **Yes:** Collapse/expand transitions on the rewrite banner (CSS `max-height` + `overflow-hidden` + `transition-all`).
- **No:** Score bar fill animation. No entrance animation for the rewrite banner.
- **Yes:** The existing `violation-pulse` CSS animation for jump-to behavior (already implemented).

### 8. Tier 2 loading state

**Planner:** When the user clicks "Re-run Checks" and the backend runs the full pipeline (Tier 1 fast, Tier 2 slow via OpenAI API), we need to handle the intermediate state.

**Advocate:** The recheck endpoint is synchronous -- it blocks until the pipeline completes (including the OpenAI call). So the loading state is just the existing `recheckContent.isPending` spinner on the button. No need for a separate "Tier 2 running" state.

**Consensus:** Keep it simple. The recheck button shows a spinner while the mutation is pending. If Tier 2 is slow (2-5s), the button stays in loading state. When it resolves, the full QA results (including tier2 and potential rewrite) render immediately. If the OpenAI call fails, the backend returns results without tier2 data, and the frontend conditionally hides the AI Evaluation section. **No polling, no partial results.**

---

## ScoreBar Component

**File:** `frontend/src/components/quality/ScoreBar.tsx`

A horizontal bar representing a 0.0 to 1.0 score with a color-coded fill.

```tsx
'use client';

interface ScoreBarProps {
  /** Score value between 0.0 and 1.0 */
  value: number;
  /** Label shown to the left of the bar */
  label: string;
  /** Optional: show the numeric value to the right. Default: true */
  showValue?: boolean;
}

function scoreBarColor(value: number): string {
  if (value >= 0.8) return 'bg-palm-500';
  if (value >= 0.6) return 'bg-palm-400';
  if (value >= 0.4) return 'bg-sand-500';
  if (value >= 0.2) return 'bg-coral-400';
  return 'bg-coral-500';
}

export function ScoreBar({ value, label, showValue = true }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const percentage = Math.round(clamped * 100);

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-warm-600 w-[120px] flex-shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-sand-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreBarColor(clamped)}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showValue && (
        <span className="text-xs font-mono text-warm-700 w-[36px] text-right flex-shrink-0">
          {clamped.toFixed(2)}
        </span>
      )}
    </div>
  );
}
```

**Design notes:**
- Label width is fixed at 120px to align bars vertically across the three metrics.
- Bar height is 8px (`h-2`) -- slightly thicker than the keyword density bar (6px / `h-1.5`) for visual weight. These are important scores, not secondary indicators.
- Rounded-full bar caps match existing bar styling in `ContentStatsCard`.
- Font mono for the numeric value matches existing stats typography.

---

## RewriteBanner Component

**File:** `frontend/src/components/quality/RewriteBanner.tsx`

Displayed in the QualityPanel sidebar when `qa_results.rewrite?.triggered === true`. Collapsible, expanded by default.

```tsx
'use client';

import { useState } from 'react';

interface RewriteData {
  triggered: boolean;
  original_score: number;
  fixed_score: number;
  issues_sent: number;
  issues_resolved: number;
  issues_remaining: number;
  issues_new: number;
  changes_made: string[];
}

interface RewriteBannerProps {
  rewrite: RewriteData;
  onViewOriginal: () => void;
  onViewDiff: () => void;
}

export function RewriteBanner({ rewrite, onViewOriginal, onViewDiff }: RewriteBannerProps) {
  const [expanded, setExpanded] = useState(true);

  const improvement = rewrite.fixed_score - rewrite.original_score;
  const improvementPercent = Math.round(
    ((rewrite.fixed_score - rewrite.original_score) / Math.max(rewrite.original_score, 1)) * 100
  );

  // Progress bar: shows the improvement range from original to fixed
  const originalPercent = rewrite.original_score;
  const fixedPercent = rewrite.fixed_score;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      {/* Header (always visible, clickable to toggle) */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between bg-palm-50/50 border-b border-palm-100 hover:bg-palm-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-3.5 h-3.5 text-warm-500 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>
          <span className="text-xs font-semibold text-warm-700 uppercase tracking-wider">
            Auto-Rewrite
          </span>
        </div>
        {/* Collapsed summary */}
        {!expanded && (
          <span className="text-xs font-mono text-palm-600">
            {rewrite.original_score} &rarr; {rewrite.fixed_score} ({rewrite.changes_made.length} changes)
          </span>
        )}
      </button>

      {/* Expandable body */}
      <div
        className={`transition-all duration-200 ease-in-out overflow-hidden ${
          expanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="p-4 space-y-4">
          {/* Score improvement bar */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-warm-500">Score improvement</span>
              <span className="text-xs font-mono font-medium text-palm-700">
                {rewrite.original_score} &rarr; {rewrite.fixed_score}
                <span className="text-palm-500 ml-1">(+{improvement})</span>
              </span>
            </div>
            <div className="relative h-2 bg-sand-200 rounded-full overflow-hidden">
              {/* Original score region (coral/red) */}
              <div
                className="absolute left-0 top-0 h-full bg-coral-300 rounded-full"
                style={{ width: `${originalPercent}%` }}
              />
              {/* Improvement region (green) */}
              <div
                className="absolute top-0 h-full bg-palm-400 rounded-full"
                style={{
                  left: `${originalPercent}%`,
                  width: `${fixedPercent - originalPercent}%`,
                }}
              />
            </div>
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-2 text-xs text-warm-600">
            <span>{rewrite.issues_sent} sent</span>
            <span className="text-warm-300">&middot;</span>
            <span className="text-palm-600 font-medium">{rewrite.issues_resolved} resolved</span>
            <span className="text-warm-300">&middot;</span>
            {rewrite.issues_remaining > 0 && (
              <>
                <span className="text-coral-500">{rewrite.issues_remaining} remaining</span>
                <span className="text-warm-300">&middot;</span>
              </>
            )}
            {rewrite.issues_new > 0 && (
              <span className="text-coral-500">{rewrite.issues_new} new</span>
            )}
          </div>

          {/* Changes made list */}
          {rewrite.changes_made.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-warm-700 mb-1.5">Changes made:</h4>
              <ul className="space-y-1">
                {rewrite.changes_made.map((change, idx) => (
                  <li key={idx} className="text-xs text-warm-600 flex items-start gap-1.5">
                    <span className="text-palm-400 mt-0.5 flex-shrink-0">&bull;</span>
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2 pt-1">
            <button
              type="button"
              onClick={onViewOriginal}
              className="px-3 py-1.5 text-xs font-medium text-warm-600 bg-sand-100 hover:bg-sand-200 border border-sand-300 rounded-sm transition-colors"
            >
              View Original
            </button>
            <button
              type="button"
              onClick={onViewDiff}
              className="px-3 py-1.5 text-xs font-medium text-warm-600 bg-sand-100 hover:bg-sand-200 border border-sand-300 rounded-sm transition-colors"
            >
              View Diff
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

**Design notes:**
- Follows the same card pattern as `QualityStatusCard`: white bg, `rounded-sm`, `border-sand-400/60`.
- Header uses `bg-palm-50/50` (subtle green tint) to differentiate from regular check groups.
- The score improvement bar uses a layered approach: coral base (original score) with a green extension (improvement). This is more visually clear than a single bar that changes color.
- Collapse animation uses `max-h-[500px]` with CSS transitions. This is simpler than JS-measured height and sufficient for the expected content size.
- Buttons use a neutral `sand-100` style (not primary green) because these are secondary exploration actions, not primary CTAs.

---

## VersionDiffModal Component

**File:** `frontend/src/components/quality/VersionDiffModal.tsx`

A full-screen overlay modal showing original vs. fixed content. Displays per-field comparisons with inline diff highlighting.

### Diff Utility

The diff algorithm is a simple word-level comparison, not character-level. This is intentional -- word-level diffs are more readable for prose content.

```tsx
// Inline in VersionDiffModal.tsx -- no separate file needed for ~30 lines.

interface DiffSegment {
  type: 'equal' | 'added' | 'removed';
  text: string;
}

/**
 * Compute a simple word-level diff between two strings.
 * Uses Longest Common Subsequence on word arrays.
 * Returns segments tagged as equal, added, or removed.
 */
function wordDiff(oldText: string, newText: string): DiffSegment[] {
  const oldWords = oldText.split(/(\s+)/);  // preserve whitespace
  const newWords = newText.split(/(\s+)/);

  // LCS table
  const m = oldWords.length;
  const n = newWords.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (oldWords[i - 1] === newWords[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Backtrack
  const segments: DiffSegment[] = [];
  let i = m, j = n;
  const raw: DiffSegment[] = [];

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldWords[i - 1] === newWords[j - 1]) {
      raw.push({ type: 'equal', text: oldWords[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      raw.push({ type: 'added', text: newWords[j - 1] });
      j--;
    } else {
      raw.push({ type: 'removed', text: oldWords[i - 1] });
      i--;
    }
  }

  raw.reverse();

  // Merge consecutive same-type segments
  for (const seg of raw) {
    const last = segments[segments.length - 1];
    if (last && last.type === seg.type) {
      last.text += seg.text;
    } else {
      segments.push({ ...seg });
    }
  }

  return segments;
}
```

**Why not `diff-match-patch`?** It is an excellent library, but adding a dependency for a feature used by ~5% of page views is premature. The LCS approach above handles the common cases (word substitutions, phrase additions/removals). If operators report issues with diff quality, we add `diff-match-patch` in a follow-up (4.6KB gzipped, zero deps, drop-in replacement).

### Strip HTML Utility

Content fields contain HTML. The diff should compare visible text only.

```typescript
function stripHtml(html: string): string {
  return html
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/?(p|div|h[1-6]|li|tr)[\s>]/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&nbsp;/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
```

### Modal Component

```tsx
'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { Button } from '@/components/ui';

interface ContentSnapshot {
  page_title: string | null;
  meta_description: string | null;
  top_description: string | null;
  bottom_description: string | null;
}

interface VersionDiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  original: ContentSnapshot;
  fixed: ContentSnapshot;
  changesMade: string[];
  originalScore: number;
  fixedScore: number;
  onRestoreOriginal?: () => void;
}

type ViewMode = 'diff' | 'original';

const FIELD_LABELS: Record<string, string> = {
  page_title: 'Page Title',
  meta_description: 'Meta Description',
  top_description: 'Top Description',
  bottom_description: 'Bottom Description',
};

const FIELDS = ['page_title', 'meta_description', 'top_description', 'bottom_description'] as const;

export function VersionDiffModal({
  isOpen,
  onClose,
  original,
  fixed,
  changesMade,
  originalScore,
  fixedScore,
  onRestoreOriginal,
}: VersionDiffModalProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('diff');
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Close on backdrop click
  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    },
    [onClose]
  );

  if (!isOpen) return null;

  const handleRestore = () => {
    onRestoreOriginal?.();
    setShowRestoreConfirm(false);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-8 pb-8 overflow-y-auto"
      onClick={handleBackdropClick}
    >
      <div className="absolute inset-0 bg-warm-gray-900/40" />
      <div
        ref={modalRef}
        className="relative bg-white rounded-sm border border-cream-500 shadow-xl w-full max-w-4xl mx-4"
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-sand-200">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-warm-900">
              {viewMode === 'diff' ? 'Content Diff' : 'Original Content'}
            </h2>
            <span className="text-xs font-mono text-warm-500">
              Score: {originalScore} &rarr; {fixedScore}
            </span>
          </div>
          <div className="flex items-center gap-3">
            {/* View mode toggle */}
            <div className="flex rounded-sm border border-sand-300 overflow-hidden">
              <button
                type="button"
                onClick={() => setViewMode('diff')}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === 'diff'
                    ? 'bg-palm-100 text-palm-700 border-r border-sand-300'
                    : 'bg-white text-warm-600 hover:bg-sand-50 border-r border-sand-300'
                }`}
              >
                Diff
              </button>
              <button
                type="button"
                onClick={() => setViewMode('original')}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  viewMode === 'original'
                    ? 'bg-palm-100 text-palm-700'
                    : 'bg-white text-warm-600 hover:bg-sand-50'
                }`}
              >
                Original
              </button>
            </div>
            {/* Close button */}
            <button
              type="button"
              onClick={onClose}
              className="text-warm-400 hover:text-warm-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Modal body */}
        <div className="px-6 py-4 space-y-6 max-h-[calc(100vh-200px)] overflow-y-auto">
          {/* Changes summary (shown in diff mode) */}
          {viewMode === 'diff' && changesMade.length > 0 && (
            <div className="bg-palm-50/50 border border-palm-100 rounded-sm p-4">
              <h3 className="text-xs font-semibold text-palm-800 uppercase tracking-wider mb-2">
                Changes Made ({changesMade.length})
              </h3>
              <ul className="space-y-1">
                {changesMade.map((change, idx) => (
                  <li key={idx} className="text-sm text-warm-700 flex items-start gap-2">
                    <span className="text-palm-400 mt-0.5">&bull;</span>
                    <span>{change}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Per-field comparison */}
          {FIELDS.map((field) => {
            const origVal = original[field] ?? '';
            const fixedVal = fixed[field] ?? '';
            const origText = stripHtml(origVal);
            const fixedText = stripHtml(fixedVal);

            // Skip fields with no changes
            if (origText === fixedText) return null;

            return (
              <div key={field}>
                <h3 className="text-sm font-semibold text-warm-800 mb-2">
                  {FIELD_LABELS[field]}
                </h3>
                {viewMode === 'diff' ? (
                  <DiffView oldText={origText} newText={fixedText} />
                ) : (
                  <div className="bg-sand-50 border border-sand-200 rounded-sm p-4">
                    <p className="text-sm text-warm-700 whitespace-pre-wrap leading-relaxed">
                      {origText}
                    </p>
                  </div>
                )}
              </div>
            );
          })}

          {/* All fields identical message */}
          {FIELDS.every((f) => stripHtml(original[f] ?? '') === stripHtml(fixed[f] ?? '')) && (
            <p className="text-sm text-warm-500 text-center py-8">
              No visible text differences between versions.
            </p>
          )}
        </div>

        {/* Modal footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-sand-200 bg-sand-50/50">
          {onRestoreOriginal ? (
            !showRestoreConfirm ? (
              <button
                type="button"
                onClick={() => setShowRestoreConfirm(true)}
                className="text-xs text-coral-600 hover:text-coral-700 font-medium transition-colors"
              >
                Restore Original
              </button>
            ) : (
              <div className="flex items-center gap-3">
                <span className="text-xs text-coral-600">
                  Replace all content with pre-rewrite version?
                </span>
                <button
                  type="button"
                  onClick={handleRestore}
                  className="px-3 py-1.5 text-xs font-medium text-white bg-coral-500 hover:bg-coral-600 rounded-sm transition-colors"
                >
                  Yes, Restore
                </button>
                <button
                  type="button"
                  onClick={() => setShowRestoreConfirm(false)}
                  className="px-3 py-1.5 text-xs font-medium text-warm-600 bg-sand-200 hover:bg-sand-300 rounded-sm transition-colors"
                >
                  Cancel
                </button>
              </div>
            )
          ) : (
            <div />
          )}
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}

/** Renders inline diff with <ins>/<del> styling. */
function DiffView({ oldText, newText }: { oldText: string; newText: string }) {
  const segments = wordDiff(oldText, newText);

  return (
    <div className="bg-sand-50 border border-sand-200 rounded-sm p-4 text-sm leading-relaxed whitespace-pre-wrap">
      {segments.map((seg, idx) => {
        if (seg.type === 'removed') {
          return (
            <del key={idx} className="bg-coral-100 text-coral-700 line-through decoration-coral-400/50">
              {seg.text}
            </del>
          );
        }
        if (seg.type === 'added') {
          return (
            <ins key={idx} className="bg-palm-100 text-palm-700 no-underline">
              {seg.text}
            </ins>
          );
        }
        return <span key={idx}>{seg.text}</span>;
      })}
    </div>
  );
}
```

**Design notes:**
- The modal follows the existing pattern from `AddAccountModal` and `ConfirmDialog`: fixed overlay with backdrop click to close, Escape key handler.
- Max width is `max-w-4xl` (896px) because we're showing full content text. The sidebar modals (AddLink, etc.) use `max-w-md`.
- The "Restore Original" button is intentionally placed in the footer (not the banner) behind a two-click confirmation to prevent accidental data loss.
- View mode toggle uses a segmented control pattern (Diff / Original) instead of two separate buttons to make it clear these are mutually exclusive views.
- Fields with no changes are hidden to reduce noise. Only modified fields appear.

---

## QualityPanel AI Evaluation Section

**File to modify:** `frontend/src/components/quality/QualityPanel.tsx` (created in 18d)

Since 18d creates the `QualityPanel` as a shared component with collapsible check groups, the AI Evaluation section is added as a new group at the bottom.

### Integration approach

The QualityPanel component (from 18d) will accept the full `qa_results` object. Within it, we add:

1. The `RewriteBanner` component (between the score badge header and the check groups, when rewrite is triggered)
2. An "AI Evaluation" collapsible group (after Domain Checks, when tier2 data exists)

```tsx
// Inside QualityPanel.tsx, after the Domain Checks group:

{/* AI Evaluation Group -- only shown when tier2 data exists */}
{qaResults.tier2 && (
  <CheckGroup
    title="AI Evaluation"
    issueCount={0}
    badge={
      <span className="text-[10px] font-mono text-warm-400 bg-sand-100 px-1.5 py-0.5 rounded-sm">
        {qaResults.tier2.model}
      </span>
    }
    defaultExpanded={true}
  >
    <div className="space-y-3 py-1">
      <ScoreBar label="Naturalness" value={qaResults.tier2.naturalness} />
      <ScoreBar label="Brief Adherence" value={qaResults.tier2.brief_adherence} />
      <ScoreBar label="Heading Structure" value={qaResults.tier2.heading_structure} />
    </div>
    {/* Show LLM explanations if low scores */}
    {qaResults.tier2.explanations && (
      <div className="mt-3 space-y-2">
        {Object.entries(qaResults.tier2.explanations).map(([key, explanation]) => {
          if (!explanation) return null;
          const score = qaResults.tier2?.[key as keyof typeof qaResults.tier2];
          if (typeof score !== 'number' || score >= 0.7) return null; // only show for low scores
          return (
            <div key={key} className="text-xs text-warm-500 bg-sand-50 px-3 py-2 rounded-sm border border-sand-100">
              <span className="font-medium text-warm-600 capitalize">{key.replace('_', ' ')}:</span>{' '}
              {explanation}
            </div>
          );
        })}
      </div>
    )}
  </CheckGroup>
)}
```

### Rewrite Banner placement

```tsx
// Inside QualityPanel.tsx, after the ScoreBadge header and before check groups:

{qaResults.rewrite?.triggered && qaResults.versions && (
  <RewriteBanner
    rewrite={qaResults.rewrite}
    onViewOriginal={() => setModalMode('original')}
    onViewDiff={() => setModalMode('diff')}
  />
)}

{/* Modal -- rendered outside the sidebar scroll container for correct z-index */}
{modalMode && qaResults.versions && (
  <VersionDiffModal
    isOpen={!!modalMode}
    onClose={() => setModalMode(null)}
    original={qaResults.versions.original.content_snapshot}
    fixed={qaResults.versions.fixed.content_snapshot}
    changesMade={qaResults.versions.fixed.changes_made ?? []}
    originalScore={qaResults.versions.original.score}
    fixedScore={qaResults.versions.fixed.score}
    onRestoreOriginal={onRestoreOriginal}
  />
)}
```

The `QualityPanel` component will need a new prop for the restore callback:

```tsx
interface QualityPanelProps {
  qaResults: QaResults | null;
  onJumpTo?: (context: string) => void;
  onRestoreOriginal?: () => void;  // NEW: called when user confirms restore from VersionDiffModal
}
```

### CheckGroup badge prop extension

The `CheckGroup` component (from 18d) needs a `badge` prop for rendering the model name badge:

```tsx
interface CheckGroupProps {
  title: string;
  issueCount: number;
  defaultExpanded?: boolean;
  badge?: React.ReactNode;  // NEW: optional badge/tag rendered in the header
  children: React.ReactNode;
}
```

---

## Loading & Error States

### During recheck (Tier 2 running)

No new loading state needed. The existing `recheckContent.isPending` boolean controls the spinner on the "Re-run Checks" button. The backend returns a complete response when done.

### Tier 2 absent (feature flagged off)

When `qa_results.tier2` is `undefined` or `null`, the AI Evaluation section simply does not render. No "Tier 2 disabled" message -- the operator doesn't need to know about feature flags.

### Tier 2 error (OpenAI call failed)

If the backend's OpenAI call fails gracefully, `qa_results.tier2` will be absent but `composite_score` will still be computed from Tier 1 checks only. The frontend renders normally without the AI Evaluation section.

### Rewrite absent (score >= 70 or feature flagged off)

When `qa_results.rewrite` is `undefined` or `qa_results.rewrite.triggered === false`, the RewriteBanner does not render. No placeholder, no "Rewrite not needed" message.

### Backward compatibility

The `QualityPanel` must handle old-format `qa_results` that lack `composite_score`, `tier2`, `rewrite`, and `versions` fields. Conditional rendering on each field ensures this. The 18d panel already handles the basic `passed` + `issues` format.

---

## Recheck Flow Updates

### Current flow (pre-18g)
1. User clicks "Re-run Checks"
2. Frontend saves content, then calls `recheckPageContent(projectId, pageId)`
3. Backend runs `run_quality_checks()` (Tier 1 only)
4. Returns updated `PageContentResponse` with new `qa_results`
5. Frontend re-renders QualityPanel

### Updated flow (post-18e/18f, displayed by 18g)
1. User clicks "Re-run Checks"
2. Frontend saves content, then calls `recheckPageContent(projectId, pageId)` (same mutation)
3. Backend runs the full quality pipeline (Tier 1 + Tier 2 + potential rewrite)
4. Returns updated `PageContentResponse` with enriched `qa_results` (including tier2, rewrite, versions)
5. Frontend re-renders QualityPanel with AI Evaluation section and optional RewriteBanner

**Key point:** No frontend changes to the recheck mutation itself. The backend response shape just has more data now, and the frontend renders it conditionally.

### Restore Original flow
1. User opens VersionDiffModal, clicks "Restore Original", confirms
2. Frontend calls `updatePageContent` with the original content snapshot fields
3. On success, calls `recheckPageContent` to re-run quality checks on the restored content
4. The rewrite data in the new qa_results will reflect the restored (original) content

Implementation in the parent page component:

```tsx
const handleRestoreOriginal = useCallback(() => {
  const originalSnapshot = (content?.qa_results as any)?.versions?.original?.content_snapshot;
  if (!originalSnapshot) return;

  // Update content with original version
  updateContent.mutate(
    {
      projectId,
      pageId,
      data: {
        page_title: originalSnapshot.page_title,
        meta_description: originalSnapshot.meta_description,
        top_description: originalSnapshot.top_description,
        bottom_description: originalSnapshot.bottom_description,
      },
    },
    {
      onSuccess: () => {
        // Update local state
        setPageTitle(originalSnapshot.page_title);
        setMetaDescription(originalSnapshot.meta_description);
        setTopDescription(originalSnapshot.top_description);
        setBottomDescription(originalSnapshot.bottom_description);
        lastSavedRef.current = { ...originalSnapshot };
        setSaveStatus({ state: 'saved', at: Date.now() });
        // Re-run checks on the restored content
        recheckContent.mutate({ projectId, pageId });
      },
    },
  );
}, [content?.qa_results, projectId, pageId, updateContent, recheckContent]);
```

---

## Test Plan

### Unit tests

**File:** `frontend/src/components/quality/__tests__/ScoreBar.test.tsx`
- Renders with value 0.0, 0.5, 1.0
- Clamps values outside 0-1 range
- Shows/hides numeric value based on `showValue` prop
- Applies correct color class for each tier

**File:** `frontend/src/components/quality/__tests__/RewriteBanner.test.tsx`
- Renders score improvement correctly
- Shows changes_made list
- Calls onViewOriginal when button clicked
- Calls onViewDiff when button clicked
- Collapses/expands on header click
- Shows collapsed summary when collapsed

**File:** `frontend/src/components/quality/__tests__/VersionDiffModal.test.tsx`
- Does not render when isOpen is false
- Renders diff view by default
- Switches between diff and original view modes
- Shows only modified fields (hides unchanged)
- Calls onClose on Escape key
- Calls onClose on backdrop click
- Shows restore confirmation on "Restore Original" click
- Calls onRestoreOriginal on confirmation
- Cancels restore on "Cancel" click

**File:** `frontend/src/components/quality/__tests__/wordDiff.test.tsx`
- Simple word substitution: "hello world" vs "hello earth" -> [equal "hello ", removed "world", added "earth"]
- Addition: "hello" vs "hello world" -> [equal "hello", added " world"]
- Removal: "hello world" vs "hello" -> [equal "hello", removed " world"]
- No change: "hello world" vs "hello world" -> [equal "hello world"]
- Empty strings: "" vs "hello" -> [added "hello"]
- Multi-word changes: realistic content rewrites

### Integration tests

**File:** Update existing `frontend/src/app/(authenticated)/projects/[id]/onboarding/content/[pageId]/__tests__/page.test.tsx`
- When qa_results has tier2 data, AI Evaluation section renders with three score bars
- When qa_results has no tier2 data, AI Evaluation section does not render
- When qa_results.rewrite.triggered is true, RewriteBanner renders
- When qa_results.rewrite.triggered is false, RewriteBanner does not render
- "View Original" button opens VersionDiffModal
- "View Diff" button opens VersionDiffModal in diff mode

### Manual verification
- [ ] Generate content that triggers auto-rewrite (score < 70)
- [ ] Verify RewriteBanner shows with correct scores and changes
- [ ] Click "View Original" and verify pre-fix content displays
- [ ] Click "View Diff" and verify inline diff renders
- [ ] Click "Restore Original" and confirm it reverts content
- [ ] After restore, verify recheck runs and new QA results display
- [ ] Generate content that does NOT trigger rewrite (score >= 70)
- [ ] Verify RewriteBanner is hidden, AI Evaluation shows scores
- [ ] Collapse/expand the RewriteBanner
- [ ] With QUALITY_TIER2_ENABLED=false, verify AI Evaluation section is hidden
- [ ] Verify backward compatibility with old qa_results format (no composite_score)
- [ ] Test on all 3 content pages (onboarding, cluster, blog)

---

## Files to Create

| File | Purpose | Estimated Lines |
|------|---------|-----------------|
| `frontend/src/components/quality/ScoreBar.tsx` | Horizontal score bar 0-1 with color gradient | ~35 |
| `frontend/src/components/quality/RewriteBanner.tsx` | Auto-rewrite status banner with collapse | ~120 |
| `frontend/src/components/quality/VersionDiffModal.tsx` | Modal with per-field diff and restore | ~250 |
| `frontend/src/components/quality/__tests__/ScoreBar.test.tsx` | Unit tests for ScoreBar | ~50 |
| `frontend/src/components/quality/__tests__/RewriteBanner.test.tsx` | Unit tests for RewriteBanner | ~80 |
| `frontend/src/components/quality/__tests__/VersionDiffModal.test.tsx` | Unit tests for VersionDiffModal | ~120 |
| `frontend/src/components/quality/__tests__/wordDiff.test.tsx` | Unit tests for diff utility | ~60 |

**Total new code:** ~715 lines

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/components/quality/QualityPanel.tsx` | Add AI Evaluation section with ScoreBar. Add RewriteBanner placement. Add `onRestoreOriginal` prop. Add modal state management. Import new components. (~60 lines added) |
| `frontend/src/components/quality/CheckGroup.tsx` | Add optional `badge` prop for model name tag. (~5 lines) |
| `frontend/src/app/(authenticated)/projects/[id]/onboarding/content/[pageId]/page.tsx` | Add `handleRestoreOriginal` callback. Pass it to QualityPanel. (~20 lines) |
| `frontend/src/app/(authenticated)/projects/[id]/clusters/[clusterId]/content/[pageId]/page.tsx` | Same `handleRestoreOriginal` callback. (~20 lines) |
| `frontend/src/app/(authenticated)/projects/[id]/blogs/[blogId]/content/[postId]/page.tsx` | Same `handleRestoreOriginal` callback. (~20 lines) |
| `frontend/src/app/(authenticated)/projects/[id]/onboarding/content/[pageId]/__tests__/page.test.tsx` | Add integration tests for tier2 and rewrite rendering. (~40 lines) |

**Total modified code:** ~165 lines added across existing files

---

## Verification Checklist

- [ ] `ScoreBar` renders correctly at boundaries (0.0, 0.5, 1.0)
- [ ] `ScoreBar` color transitions match the defined tiers
- [ ] AI Evaluation section shows 3 score bars with model badge
- [ ] AI Evaluation section hidden when `tier2` absent
- [ ] LLM explanations display for low-score metrics only
- [ ] `RewriteBanner` shows score improvement visualization
- [ ] `RewriteBanner` collapses/expands correctly
- [ ] `RewriteBanner` collapsed state shows summary
- [ ] `RewriteBanner` hidden when no rewrite occurred
- [ ] "View Original" opens modal in original view
- [ ] "View Diff" opens modal in diff view
- [ ] Modal view mode toggle works
- [ ] Diff highlights additions (green) and removals (red strikethrough)
- [ ] Unchanged fields are hidden in diff view
- [ ] "Restore Original" shows confirmation
- [ ] Restore confirmation writes original content and triggers recheck
- [ ] Modal closes on Escape and backdrop click
- [ ] All 3 content pages (onboarding, cluster, blog) show the new components
- [ ] Backward compatible with old `qa_results` format
- [ ] No console errors or warnings
- [ ] All existing tests still pass
- [ ] New tests pass
- [ ] Sidebar scroll behavior still works with new components
- [ ] `max-h-[500px]` on RewriteBanner collapse is sufficient for all realistic content

---

## Dependency Notes

- **No new npm dependencies.** The word-level diff utility is implemented inline (~60 lines).
- **Depends on 18d** being complete (QualityPanel, CheckGroup, ScoreBadge components must exist).
- **Depends on 18e+18f** backend producing the `tier2` and `rewrite` data in `qa_results`. Frontend work can proceed in parallel since we code against the data contract above and conditionally render.
- If 18d is not yet complete, the components in this plan (`ScoreBar`, `RewriteBanner`, `VersionDiffModal`) can still be built as standalone components and integrated after 18d lands.
