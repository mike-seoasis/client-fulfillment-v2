# 18d: Quality Panel Upgrade

## Overview

Replace the inline `QualityStatusCard` and `FlaggedPassagesCard` components -- currently duplicated across all 3 content editor pages -- with a shared `QualityPanel` component tree under `frontend/src/components/quality/`. The new panel adds composite scoring (0-100), collapsible check groups (Content, Domain, AI Evaluation), bible match indicators, and forward-compatible slots for Tier 2 LLM data and auto-rewrite status.

**Current state:** Simple pass/fail list of 9 hardcoded check types, copy-pasted in:
- `frontend/src/app/(authenticated)/projects/[id]/onboarding/content/[pageId]/page.tsx`
- `frontend/src/app/(authenticated)/projects/[id]/clusters/[clusterId]/content/[pageId]/page.tsx`
- `frontend/src/app/(authenticated)/projects/[id]/blogs/[blogId]/content/[postId]/page.tsx`

**Target state:** Single shared component that renders score badge, grouped checks, flagged passages -- driven entirely by the `qa_results` JSONB shape from the backend.

---

## Decisions (from Planner/Advocate Debate)

### 1. Should we extract to shared components, or will the 3 pages diverge?

**Planner:** The three pages already have identical QualityStatusCard and FlaggedPassagesCard implementations (verified: line-for-line identical logic, only the blog page uses `content` instead of `bottom_description` as the field name for the rich editor). The quality panel is purely data-driven -- it reads `qa_results` and renders. There is zero page-specific logic. Extraction eliminates ~400 lines of duplication.

**Advocate:** The pages could diverge. Blog posts don't have `top_description`, and Reddit comments (mentioned in the master plan) will have a completely different field structure.

**Resolution:** Extract. The component accepts a `qa_results` object and an `onJumpTo` callback -- it does not know or care about field structure. The field labels (`top`, `body`, `meta`, `content`) come from the data itself. If Reddit comments need different grouping later, we add a prop, not a new component. The duplication is already causing bugs: the blog page lacks a `FlaggedPassagesCard` entirely (it was forgotten during the copy). Shared components prevent this drift.

### 2. Should the score formula live in the frontend or come from the backend?

**Planner:** Compute in the frontend from the issues list -- it's simple arithmetic and avoids a backend change for 18d.

**Advocate:** The score formula involves weights (-5 per error, -2 per warning, -10 for naturalness < 0.6, etc.). If we compute on the frontend, and the backend later computes and stores a `score` field (per the master plan in 18e), we'll have two sources of truth that might disagree.

**Resolution:** The backend is the canonical score source. In 18d, the backend does NOT yet produce a `score` field. So the frontend will compute a **display-only estimated score** from Tier 1 issues using a lightweight formula. When 18e lands and `qa_results.score` exists, the component reads it directly and the frontend formula becomes dead code. To make this explicit:

```typescript
// If backend provides a score, use it. Otherwise, estimate from issues.
const score = qaResults.score ?? estimateScoreFromIssues(qaResults.issues);
```

The `estimateScoreFromIssues` function uses a simplified version of the formula (no Tier 2 components, since those don't exist yet). This avoids blocking 18d on 18e while ensuring the backend is always the source of truth once it ships.

**Simplified Tier-1-only formula:**
```
Start at 100
- Each issue with type in CRITICAL_TYPES: -5 points
- Each issue with type in WARNING_TYPES: -2 points
Floor at 0
```

Where:
- CRITICAL_TYPES = `tier1_ai_word`, `banned_word`, `competitor_name`, `bible_banned_claim`, `bible_wrong_attribution`
- WARNING_TYPES = everything else (`em_dash`, `ai_pattern`, `triplet_excess`, `rhetorical_excess`, `tier2_ai_excess`, `negation_contrast`, `bible_preferred_term`, `bible_term_context`)

### 3. Should the score badge exist before 18e (LLM Judge)?

**Planner:** Yes, the score gives operators a quick "how bad is this?" signal.

**Advocate:** Without Tier 2, the score is just counting regex matches. A piece with 1 em dash and 1 triplet list (minor stylistic issues) would score 96, while a piece with 3 banned words would score 85. Both are arbitrary. Operators will fixate on the number.

**Resolution:** Show the score badge, but with a clear **"Estimated"** label when `qa_results.score` is absent (meaning backend hasn't computed the real score yet). The badge subtitle says "Estimated from checks" instead of "Publish Ready" / "Minor Issues" when running in estimation mode. This signals to operators that the number is approximate. When 18e lands with the real score, the label switches to the proper tier label and the "Estimated" qualifier disappears.

### 4. Are collapsible groups worth it for 3-4 items per group?

**Planner:** Collapsible groups reduce visual noise -- operators can see "Content Checks (0 issues)" collapsed and skip it.

**Advocate:** With only 3-4 items per group, collapsing saves maybe 80px of vertical space. The interaction cost (clicking to expand) may exceed the benefit. Also, all groups start expanded since the operator needs to see everything on first visit.

**Resolution:** Groups default to **collapsed if 0 issues, expanded if any issues**. This is the best of both worlds: clean groups are hidden, problematic groups are visible. The collapse is a single chevron toggle, not a heavy accordion. Total interaction surface is small, and the visual benefit of grouping (Content vs Domain vs AI) is worth it for scan-ability even when expanded.

### 5. Should we show the model name "GPT-5.4" to operators?

**Advocate:** That's an implementation detail. Operators don't care which model evaluated their content. It could confuse them ("I thought we used Claude?").

**Resolution:** Do NOT show the model name in 18d. The AI Evaluation section header will just say "AI Evaluation" with an info tooltip that says "Content evaluated by an independent AI model for quality signals." The model name is stored in `qa_results.tier2.model` for debugging but not displayed. This also future-proofs against model changes. The wireframe shows "GPT-5.4" as a reference, but the implementation should use a generic label.

### 6. How do we handle the "Recheck" button for the new pipeline?

**Advocate:** The recheck button currently just re-runs Tier 1 checks. When 18e adds Tier 2, recheck needs to re-run the full pipeline (which costs money). Should the button change?

**Resolution:** The "Re-run Checks" button stays exactly as-is in 18d. It already saves + calls the recheck endpoint. The backend decides what to run. When 18e upgrades the backend to run the full pipeline, the same button triggers it. No frontend change needed for the button itself. In 18g (LLM + Rewrite FE), we may add a cost indicator ("Re-run Checks (~$0.04)") but that's out of scope for 18d.

### 7. FlaggedPassagesCard in blog page

**Observation during review:** The blog content editor page (`blogs/[blogId]/content/[postId]/page.tsx`) does NOT render a `FlaggedPassagesCard` at all. The onboarding and cluster pages both render it. This is a bug caused by the copy-paste approach.

**Resolution:** The shared QualityPanel will include FlaggedPassages as an integrated section, ensuring all 3 pages get it.

---

## Component Architecture

```
frontend/src/components/quality/
  QualityPanel.tsx        -- Main container (score badge + groups + flagged passages)
  ScoreBadge.tsx          -- 0-100 circle with color tier + label
  CheckGroup.tsx          -- Collapsible section (header + children)
  CheckRow.tsx            -- Individual check: pass/fail or count
  FlaggedPassages.tsx     -- Flagged passages list (bible + LLM support)
  score-utils.ts          -- Score estimation, tier mapping, type constants
  index.ts                -- Barrel export
```

### Data Flow

```
Page Component
  |
  +-- qa_results (from API response)
  |
  +-- <QualityPanel qaResults={qaResults} onJumpTo={...} />
        |
        +-- <ScoreBadge score={...} tier={...} checkedAt={...} isEstimated={...} />
        |
        +-- <CheckGroup title="Content Checks" issueCount={n} defaultOpen={n > 0}>
        |     +-- <CheckRow label="Banned Words" count={0} status="pass" />
        |     +-- <CheckRow label="Tier 1 AI Words" count={2} status="fail" />
        |     +-- ...
        |   </CheckGroup>
        |
        +-- <CheckGroup title="Domain Checks" issueCount={n} badge="Cartridge Needles" defaultOpen={n > 0}>
        |     +-- <CheckRow label="Preferred Terms" count={0} status="pass" />
        |     +-- ...
        |   </CheckGroup>  (hidden entirely when no bibles matched)
        |
        +-- <CheckGroup title="AI Evaluation" issueCount={0} defaultOpen={true}>
        |     +-- (placeholder: "Available after Tier 2 is enabled")
        |     +-- (in 18g: ScoreBar components for naturalness, brief adherence, heading structure)
        |   </CheckGroup>  (hidden entirely when no tier2 data)
        |
        +-- <FlaggedPassages issues={...} onJumpTo={...} />
```

---

## QualityPanel Props Interface

```typescript
// frontend/src/components/quality/score-utils.ts

// ----- Issue type categorization -----

export const CONTENT_CHECK_TYPES = [
  'banned_word',
  'em_dash',
  'ai_pattern',
  'triplet_excess',
  'rhetorical_excess',
  'tier1_ai_word',
  'tier2_ai_excess',
  'negation_contrast',
  'competitor_name',
] as const;

export const CONTENT_CHECK_LABELS: Record<string, string> = {
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

export const BIBLE_CHECK_TYPES = [
  'bible_preferred_term',
  'bible_banned_claim',
  'bible_wrong_attribution',
  'bible_term_context',
] as const;

export const BIBLE_CHECK_LABELS: Record<string, string> = {
  bible_preferred_term: 'Preferred Terms',
  bible_banned_claim: 'Banned Claims',
  bible_wrong_attribution: 'Feature Attribution',
  bible_term_context: 'Term Context',
};

export const LLM_CHECK_TYPES = [
  'llm_naturalness',
  'llm_brief_adherence',
  'llm_heading_structure',
] as const;

// ----- Score tiers -----

export type ScoreTier = 'publish_ready' | 'minor_issues' | 'needs_attention' | 'needs_rewrite';

export interface TierInfo {
  label: string;
  colorClass: string;       // Tailwind bg class for the badge
  textClass: string;        // Tailwind text class
  borderClass: string;      // Tailwind border class
}

export const SCORE_TIERS: Record<ScoreTier, TierInfo> = {
  publish_ready: {
    label: 'Publish Ready',
    colorClass: 'bg-palm-500',
    textClass: 'text-white',
    borderClass: 'border-palm-500',
  },
  minor_issues: {
    label: 'Minor Issues',
    colorClass: 'bg-sand-500',
    textClass: 'text-warm-900',
    borderClass: 'border-sand-500',
  },
  needs_attention: {
    label: 'Needs Attention',
    colorClass: 'bg-coral-400',
    textClass: 'text-white',
    borderClass: 'border-coral-400',
  },
  needs_rewrite: {
    label: 'Needs Rewrite',
    colorClass: 'bg-coral-600',
    textClass: 'text-white',
    borderClass: 'border-coral-600',
  },
};

export function getScoreTier(score: number): ScoreTier {
  if (score >= 90) return 'publish_ready';
  if (score >= 70) return 'minor_issues';
  if (score >= 50) return 'needs_attention';
  return 'needs_rewrite';
}

// ----- Score estimation (Tier 1 only, used before 18e) -----

const CRITICAL_TYPES = new Set([
  'tier1_ai_word',
  'banned_word',
  'competitor_name',
  'bible_banned_claim',
  'bible_wrong_attribution',
]);

// Everything else is a warning
const WARNING_TYPES_PENALTY = 2;
const CRITICAL_TYPES_PENALTY = 5;

export function estimateScoreFromIssues(issues: QaIssue[]): number {
  let score = 100;
  for (const issue of issues) {
    if (CRITICAL_TYPES.has(issue.type)) {
      score -= CRITICAL_TYPES_PENALTY;
    } else {
      score -= WARNING_TYPES_PENALTY;
    }
  }
  return Math.max(0, score);
}

// ----- Field label mapping -----

export const FIELD_LABELS: Record<string, string> = {
  page_title: 'title',
  meta_description: 'meta',
  top_description: 'top',
  bottom_description: 'body',
  content: 'content',      // blog post field name
  faq_answers: 'faq',
};
```

```typescript
// frontend/src/components/quality/QualityPanel.tsx

export interface QaIssue {
  type: string;
  field: string;
  description: string;
  context: string;
  confidence?: number;     // 0-1, present on Tier 2 issues (18e)
  tier?: number;           // 1, 1.5 (bible), or 2 (LLM) -- added by 18e
  bible_name?: string;     // present on bible_* issues
}

export interface Tier2Results {
  model: string;
  naturalness: number;       // 0-1
  brief_adherence: number;   // 0-1
  heading_structure: number; // 0-1
  cost_usd: number;
  latency_ms: number;
}

export interface RewriteResults {
  triggered: boolean;
  original_score: number;
  fixed_score: number;
  issues_sent: number;
  issues_resolved: number;
  issues_remaining: number;
  new_issues_introduced: number;
  cost_usd: number;
  latency_ms: number;
  kept_version: 'original' | 'fixed';
}

export interface QaResults {
  passed: boolean;
  score?: number;            // 0-100, present after 18e
  issues: QaIssue[];
  checked_at?: string;
  tier2?: Tier2Results;      // present after 18e when QUALITY_TIER2_ENABLED=true
  bibles_matched?: string[]; // e.g. ["tattoo-cartridge-needles"]
  rewrite?: RewriteResults;  // present after 18f when auto-rewrite triggers
}

export interface QualityPanelProps {
  /** The qa_results object from the page content or blog post API response */
  qaResults: QaResults | null;

  /**
   * Callback when the operator clicks a flagged passage.
   * Receives the raw `context` string from the issue.
   * The parent page handles scrolling to the passage in the editor.
   */
  onJumpTo?: (context: string) => void;
}
```

---

## ScoreBadge Component

```typescript
// frontend/src/components/quality/ScoreBadge.tsx

interface ScoreBadgeProps {
  score: number;
  tier: ScoreTier;
  isEstimated: boolean;  // true when score came from frontend estimation
  checkedAt?: string;     // ISO timestamp
}
```

### Rendering logic

```tsx
export function ScoreBadge({ score, tier, isEstimated, checkedAt }: ScoreBadgeProps) {
  const tierInfo = SCORE_TIERS[tier];

  // Relative time for "Checked X ago"
  const timeLabel = checkedAt ? formatRelativeTime(checkedAt) : null;

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      {/* Score circle */}
      <div
        className={`w-12 h-12 rounded-sm flex items-center justify-center ${tierInfo.colorClass} ${tierInfo.textClass} flex-shrink-0`}
      >
        <span className="text-lg font-bold leading-none">{score}</span>
      </div>

      {/* Label + timestamp */}
      <div className="min-w-0">
        <div className="text-sm font-semibold text-warm-800">
          {isEstimated ? 'Estimated Score' : tierInfo.label}
        </div>
        <div className="text-xs text-warm-400">
          {isEstimated
            ? 'Based on content checks'
            : timeLabel
              ? `Checked ${timeLabel}`
              : 'Just checked'}
        </div>
      </div>
    </div>
  );
}

// Simple relative time formatter (no deps)
function formatRelativeTime(isoString: string): string {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffSec = Math.floor((now - then) / 1000);

  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}
```

### Score badge colors (from wireframe)

| Score Range | Tier | Badge Background | Text |
|-------------|------|-----------------|------|
| 90-100 | Publish Ready | `bg-palm-500` (green) | `text-white` |
| 70-89 | Minor Issues | `bg-sand-500` (amber) | `text-warm-900` |
| 50-69 | Needs Attention | `bg-coral-400` (orange) | `text-white` |
| 0-49 | Needs Rewrite | `bg-coral-600` (red) | `text-white` |

---

## CheckGroup Component

```typescript
// frontend/src/components/quality/CheckGroup.tsx

interface CheckGroupProps {
  title: string;
  issueCount: number;
  badge?: string;          // e.g. bible name "Cartridge Needles"
  defaultOpen: boolean;
  children: React.ReactNode;
}
```

### Rendering logic

```tsx
export function CheckGroup({ title, issueCount, badge, defaultOpen, children }: CheckGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border-t border-sand-200">
      {/* Header row -- always visible, clickable */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-sand-50/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {/* Chevron */}
          <svg
            className={`w-3.5 h-3.5 text-warm-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>

          <span className="text-xs font-semibold text-warm-700">{title}</span>

          {/* Issue count badge */}
          {issueCount > 0 ? (
            <span className="text-xs font-mono text-coral-600 bg-coral-50 px-1.5 py-0.5 rounded-sm">
              {issueCount} issue{issueCount !== 1 ? 's' : ''}
            </span>
          ) : (
            <span className="text-xs font-mono text-palm-600 bg-palm-50 px-1.5 py-0.5 rounded-sm">
              pass
            </span>
          )}
        </div>

        {/* Optional bible name badge */}
        {badge && (
          <span className="text-xs text-lagoon-600 bg-lagoon-50 px-1.5 py-0.5 rounded-sm font-medium truncate max-w-[140px]">
            {badge}
          </span>
        )}
      </button>

      {/* Collapsible body */}
      {isOpen && (
        <div className="px-4 pb-3 space-y-1">
          {children}
        </div>
      )}
    </div>
  );
}
```

### Collapse behavior

- **0 issues in group:** Collapsed by default. Shows "pass" badge in green.
- **1+ issues in group:** Expanded by default. Shows "{n} issue(s)" badge in coral.
- All groups are manually toggleable regardless of default state.

---

## CheckRow Component

```typescript
// frontend/src/components/quality/CheckRow.tsx

interface CheckRowProps {
  label: string;
  count: number;            // 0 = pass, >0 = number of issues
  // Future: score bar mode for Tier 2 (18g)
  scoreValue?: number;      // 0-1 for LLM scores
}
```

### Rendering logic

```tsx
export function CheckRow({ label, count, scoreValue }: CheckRowProps) {
  // Score bar mode (for 18g -- Tier 2 LLM scores)
  if (scoreValue !== undefined) {
    return (
      <div className="flex items-center justify-between text-xs py-0.5">
        <span className="text-warm-600">{label}</span>
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-sand-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${scoreValue >= 0.7 ? 'bg-palm-400' : scoreValue >= 0.5 ? 'bg-sand-500' : 'bg-coral-400'}`}
              style={{ width: `${scoreValue * 100}%` }}
            />
          </div>
          <span className="font-mono text-warm-500 w-8 text-right">{scoreValue.toFixed(2)}</span>
        </div>
      </div>
    );
  }

  // Pass/fail mode (standard checks)
  return (
    <div className="flex items-center justify-between text-xs py-0.5">
      <span className="text-warm-600">{label}</span>
      {count > 0 ? (
        <span className="text-coral-600 font-medium">{count} found</span>
      ) : (
        <span className="text-palm-600 font-medium">Pass</span>
      )}
    </div>
  );
}
```

---

## FlaggedPassages Updates

The `FlaggedPassages` component is extracted from the existing `FlaggedPassagesCard` and extended to handle bible issues and (later) LLM issues.

### Changes from current implementation

1. **Bible issues** get an additional explanation line below the context. Bible issues carry a `description` field with the explanation (e.g., "Membrane is a cartridge needle feature, not a pen feature"). These render as a second line in a muted style.

2. **LLM issues** (18g) use `field: "all_fields"` and show a score + reasoning snippet. These are visually distinguished with a lagoon-colored left border. Not implemented in 18d but the data shape is forward-compatible.

3. **Field label mapping** uses the shared `FIELD_LABELS` from `score-utils.ts` instead of a local constant.

```typescript
// frontend/src/components/quality/FlaggedPassages.tsx

interface FlaggedPassagesProps {
  issues: QaIssue[];
  onJumpTo?: (context: string) => void;
}
```

### Rendering logic

```tsx
export function FlaggedPassages({ issues, onJumpTo }: FlaggedPassagesProps) {
  if (!issues || issues.length === 0) return null;

  // Group issues by type (preserving encounter order)
  const groups = useMemo(() => {
    const result: { type: string; label: string; items: QaIssue[] }[] = [];
    const seen = new Set<string>();
    for (const issue of issues) {
      if (!seen.has(issue.type)) {
        seen.add(issue.type);
        const label =
          CONTENT_CHECK_LABELS[issue.type] ??
          BIBLE_CHECK_LABELS[issue.type] ??
          issue.type;
        result.push({
          type: issue.type,
          label,
          items: issues.filter((i) => i.type === issue.type),
        });
      }
    }
    return result;
  }, [issues]);

  const displayContext = (ctx: string) =>
    ctx.replace(/^\.{3}/, '').replace(/\.{3}$/, '').trim();

  const isBibleIssue = (type: string) =>
    (BIBLE_CHECK_TYPES as readonly string[]).includes(type);

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      <div className="px-4 py-3 border-b border-sand-200">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider">
            Flagged Passages
          </h3>
          <span className="text-xs font-mono text-coral-600">{issues.length}</span>
        </div>
      </div>
      <div className="divide-y divide-sand-100">
        {groups.map((group) => (
          <div key={group.type} className="px-4 py-3">
            {/* Group header */}
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-warm-800">{group.label}</span>
              <span className="text-xs font-mono text-coral-500 bg-coral-50 px-1.5 py-0.5 rounded-sm">
                {group.items.length}
              </span>
            </div>
            {/* Individual issues */}
            <div className="space-y-1.5">
              {group.items.map((issue, idx) => {
                const ctx = displayContext(issue.context);
                const canJump =
                  onJumpTo &&
                  (issue.field === 'bottom_description' || issue.field === 'content');
                return (
                  <div key={idx}>
                    <div
                      className={`flex items-start gap-2 text-xs py-1 px-2 rounded-sm ${
                        canJump ? 'hover:bg-sand-50 cursor-pointer group' : ''
                      }`}
                      onClick={canJump ? () => onJumpTo(issue.context) : undefined}
                    >
                      <span className="text-warm-400 font-mono flex-shrink-0 mt-px">
                        {FIELD_LABELS[issue.field] ?? issue.field}
                      </span>
                      <span
                        className="text-warm-600 leading-relaxed min-w-0 truncate"
                        title={ctx}
                      >
                        {ctx}
                      </span>
                      {canJump && (
                        <span className="text-lagoon-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-px">
                          &darr;
                        </span>
                      )}
                    </div>
                    {/* Bible issue explanation line */}
                    {isBibleIssue(issue.type) && issue.description && (
                      <div className="text-xs text-warm-400 italic pl-2 ml-[3.5ch] mt-0.5 leading-relaxed">
                        {issue.description}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## QualityPanel Assembly

```tsx
// frontend/src/components/quality/QualityPanel.tsx

export function QualityPanel({ qaResults, onJumpTo }: QualityPanelProps) {
  if (!qaResults) return null;

  // ----- Score computation -----
  const isEstimated = qaResults.score === undefined;
  const score = qaResults.score ?? estimateScoreFromIssues(qaResults.issues ?? []);
  const tier = getScoreTier(score);

  // ----- Issue grouping -----
  const issues = qaResults.issues ?? [];
  const issuesByType: Record<string, number> = {};
  for (const issue of issues) {
    issuesByType[issue.type] = (issuesByType[issue.type] ?? 0) + 1;
  }

  // Content check issues (Tier 1 deterministic)
  const contentIssueCount = CONTENT_CHECK_TYPES.reduce(
    (sum, type) => sum + (issuesByType[type] ?? 0),
    0
  );

  // Bible check issues
  const bibleIssueCount = BIBLE_CHECK_TYPES.reduce(
    (sum, type) => sum + (issuesByType[type] ?? 0),
    0
  );

  // Bible name for badge (first matched bible, truncated)
  const bibleNames = qaResults.bibles_matched ?? [];
  const bibleBadge = bibleNames.length > 0
    ? bibleNames.length === 1
      ? formatBibleName(bibleNames[0])
      : `${bibleNames.length} bibles`
    : undefined;

  // Whether to show bible section
  const hasBibles = bibleNames.length > 0;

  // Whether to show AI Evaluation section (only when tier2 data exists)
  const hasTier2 = !!qaResults.tier2;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      {/* Score badge header */}
      <ScoreBadge
        score={score}
        tier={tier}
        isEstimated={isEstimated}
        checkedAt={qaResults.checked_at}
      />

      {/* Content Checks group */}
      <CheckGroup
        title="Content Checks"
        issueCount={contentIssueCount}
        defaultOpen={contentIssueCount > 0}
      >
        {CONTENT_CHECK_TYPES.map((type) => (
          <CheckRow
            key={type}
            label={CONTENT_CHECK_LABELS[type] ?? type}
            count={issuesByType[type] ?? 0}
          />
        ))}
      </CheckGroup>

      {/* Domain Checks group (hidden when no bibles matched) */}
      {hasBibles && (
        <CheckGroup
          title="Domain Checks"
          issueCount={bibleIssueCount}
          badge={bibleBadge}
          defaultOpen={bibleIssueCount > 0}
        >
          {BIBLE_CHECK_TYPES.map((type) => (
            <CheckRow
              key={type}
              label={BIBLE_CHECK_LABELS[type] ?? type}
              count={issuesByType[type] ?? 0}
            />
          ))}
        </CheckGroup>
      )}

      {/* AI Evaluation group (hidden when no tier2 data) */}
      {hasTier2 && qaResults.tier2 && (
        <CheckGroup
          title="AI Evaluation"
          issueCount={0}
          defaultOpen={true}
        >
          <CheckRow label="Naturalness" count={0} scoreValue={qaResults.tier2.naturalness} />
          <CheckRow label="Brief Adherence" count={0} scoreValue={qaResults.tier2.brief_adherence} />
          <CheckRow label="Heading Structure" count={0} scoreValue={qaResults.tier2.heading_structure} />
        </CheckGroup>
      )}
    </div>
  );
}

/** Convert slug "tattoo-cartridge-needles" to display name "Cartridge Needles" */
function formatBibleName(slug: string): string {
  return slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
```

---

## Backward Compatibility Strategy

### Problem

Existing `qa_results` in the database look like:

```json
{
  "passed": true,
  "issues": [
    { "type": "em_dash", "field": "bottom_description", "description": "...", "context": "..." }
  ],
  "checked_at": "2026-03-01T..."
}
```

New `qa_results` (after 18b/18e) will look like:

```json
{
  "passed": true,
  "score": 88,
  "issues": [
    { "type": "em_dash", "field": "bottom_description", "description": "...", "context": "...", "confidence": 1.0, "tier": 1 }
  ],
  "checked_at": "2026-03-06T...",
  "tier2": { "model": "gpt-5.4", "naturalness": 0.82, ... },
  "bibles_matched": ["tattoo-cartridge-needles"]
}
```

### Strategy: Optional fields with fallbacks

Every new field in `QaResults` is optional:

| Field | Old format | New format | Component behavior when missing |
|-------|-----------|------------|-------------------------------|
| `score` | absent | `88` | Frontend estimates from issues, shows "Estimated" label |
| `tier2` | absent | `{...}` | AI Evaluation group hidden entirely |
| `bibles_matched` | absent | `["slug"]` | Domain Checks group hidden entirely |
| `issues[].confidence` | absent | `1.0` | Not used in 18d display |
| `issues[].tier` | absent | `1` | Not used for grouping; type prefix used instead |
| `issues[].bible_name` | absent | `"Cartridge Needles"` | Not displayed (bible name comes from `bibles_matched`) |
| `rewrite` | absent | `{...}` | Rewrite banner hidden entirely (18g scope) |

**Zero-migration approach:** The component reads what it finds and hides what's missing. Old content that has never been rechecked shows the old pass/fail format gracefully -- with an estimated score of 100 (if 0 issues) or lower.

### Edge case: `qa_results` is `null`

If `qa_results` is null (content was never checked), `QualityPanel` returns `null` and nothing renders. This matches current behavior.

### Edge case: `qa_results` has no `issues` key

Defensive: `qaResults.issues ?? []` throughout.

---

## Migration from Inline to Shared

### Step-by-step for each page

#### 1. Onboarding page (`onboarding/content/[pageId]/page.tsx`)

**Remove:**
- `QualityStatusCard` function definition (lines ~71-143)
- `ISSUE_TYPE_LABELS` constant (lines ~146-156)
- `FIELD_LABELS` constant (lines ~158-163)
- `FlaggedPassagesCard` function definition (lines ~165-241)
- `QaIssue` interface (lines ~58-63)
- `QaResults` interface (lines ~65-69)

**Add import:**
```typescript
import { QualityPanel } from '@/components/quality';
```

**Replace sidebar usage (around line 981):**
```tsx
// Before:
<QualityStatusCard qaResults={qaResults} />
<FlaggedPassagesCard issues={qaResults?.issues ?? []} onJumpTo={handleJumpTo} />

// After:
<QualityPanel qaResults={qaResults} onJumpTo={handleJumpTo} />
```

**Keep:** The `qaResults` local variable cast (`content?.qa_results as QaResults | null`) stays, but now uses the type from the shared module.

#### 2. Cluster page (`clusters/[clusterId]/content/[pageId]/page.tsx`)

Identical changes as onboarding page. Same line locations (identical file structure).

#### 3. Blog page (`blogs/[blogId]/content/[postId]/page.tsx`)

**Remove:**
- `QualityStatusCard` function definition (lines ~64-136)
- `QaIssue` interface (lines ~51-56)
- `QaResults` interface (lines ~58-62)

**Add import:**
```typescript
import { QualityPanel } from '@/components/quality';
```

**Replace sidebar usage (around line 779):**
```tsx
// Before:
<QualityStatusCard qaResults={qaResults} />
// (Note: FlaggedPassagesCard was never added to blog page -- a bug)

// After:
<QualityPanel qaResults={qaResults} onJumpTo={handleJumpTo} />
```

**Add:** Blog page needs a `handleJumpTo` callback for flagged passages. Currently missing because `FlaggedPassagesCard` was never added. Copy the pattern from onboarding page, adapted for the blog's `content` field instead of `bottom_description`:

```typescript
const handleJumpTo = useCallback((context: string) => {
  const container = editorContainerRef.current;
  if (!container) return;

  const cleaned = cleanContext(context);
  const searchText = cleaned.slice(0, 40);
  if (!searchText) return;

  const tropeSpans = Array.from(container.querySelectorAll('.hl-trope'));
  let target: HTMLElement | null = null;
  for (const span of tropeSpans) {
    if (span.textContent && span.textContent.includes(searchText)) {
      target = span as HTMLElement;
      break;
    }
  }

  if (!target) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
      if (node.textContent && node.textContent.includes(searchText)) {
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
}, [cleanContext]);
```

Note: The blog page already has `editorContainerRef` and `cleanContext`, so this callback just needs to be added.

### What stays inline

The following components remain inline in each page because they ARE page-specific:
- `ContentStatsCard` (uses page-specific brief data, heading targets, keyword variations)
- `LsiTermsCard` (page-specific LSI terms)
- `HeadingOutlineCard` (page-specific heading structure)
- `CharCounter`, `WordCounter` (trivial, page-specific)

These could be extracted later but are not duplicated in a problematic way (each page's variant has small differences in field names and data sources).

---

## Test Plan

### Unit tests (`frontend/src/components/quality/__tests__/`)

#### `score-utils.test.ts`

```typescript
describe('estimateScoreFromIssues', () => {
  it('returns 100 for empty issues list', () => {
    expect(estimateScoreFromIssues([])).toBe(100);
  });

  it('deducts 5 for each critical issue', () => {
    const issues = [
      { type: 'tier1_ai_word', field: 'body', description: '', context: '' },
      { type: 'banned_word', field: 'body', description: '', context: '' },
    ];
    expect(estimateScoreFromIssues(issues)).toBe(90);
  });

  it('deducts 2 for each warning issue', () => {
    const issues = [
      { type: 'em_dash', field: 'body', description: '', context: '' },
      { type: 'triplet_excess', field: 'body', description: '', context: '' },
    ];
    expect(estimateScoreFromIssues(issues)).toBe(96);
  });

  it('floors at 0', () => {
    const issues = Array(30).fill({
      type: 'tier1_ai_word', field: 'body', description: '', context: '',
    });
    expect(estimateScoreFromIssues(issues)).toBe(0);
  });
});

describe('getScoreTier', () => {
  it('returns publish_ready for 90-100', () => {
    expect(getScoreTier(90)).toBe('publish_ready');
    expect(getScoreTier(100)).toBe('publish_ready');
  });

  it('returns minor_issues for 70-89', () => {
    expect(getScoreTier(70)).toBe('minor_issues');
    expect(getScoreTier(89)).toBe('minor_issues');
  });

  it('returns needs_attention for 50-69', () => {
    expect(getScoreTier(50)).toBe('needs_attention');
    expect(getScoreTier(69)).toBe('needs_attention');
  });

  it('returns needs_rewrite for 0-49', () => {
    expect(getScoreTier(0)).toBe('needs_rewrite');
    expect(getScoreTier(49)).toBe('needs_rewrite');
  });
});
```

#### `QualityPanel.test.tsx`

```typescript
describe('QualityPanel', () => {
  it('returns null when qaResults is null', () => {
    // renders nothing
  });

  it('shows estimated score when score field is absent', () => {
    // renders ScoreBadge with isEstimated=true
  });

  it('shows backend score when score field is present', () => {
    // renders ScoreBadge with isEstimated=false
  });

  it('shows Content Checks group with correct pass/fail for each type', () => {
    // 9 CheckRow components, some with count > 0
  });

  it('hides Domain Checks group when bibles_matched is absent', () => {
    // no CheckGroup with title "Domain Checks"
  });

  it('shows Domain Checks group when bibles_matched has entries', () => {
    // CheckGroup with bible badge
  });

  it('hides AI Evaluation group when tier2 is absent', () => {
    // no CheckGroup with title "AI Evaluation"
  });

  it('shows AI Evaluation with score bars when tier2 is present', () => {
    // 3 CheckRow components with scoreValue
  });

  it('handles legacy qa_results format (no score, no tier2, no bibles_matched)', () => {
    // should render without errors, show estimated score
  });

  it('handles qa_results with empty issues array', () => {
    // score 100, all groups pass
  });
});
```

#### `CheckGroup.test.tsx`

```typescript
describe('CheckGroup', () => {
  it('renders collapsed when defaultOpen is false', () => {
    // children not visible
  });

  it('renders expanded when defaultOpen is true', () => {
    // children visible
  });

  it('toggles on click', () => {
    // click header, state changes
  });

  it('shows issue count badge when issueCount > 0', () => {
    // coral badge with count
  });

  it('shows pass badge when issueCount is 0', () => {
    // palm badge with "pass"
  });

  it('shows bible name badge when badge prop is provided', () => {
    // lagoon badge with name
  });
});
```

### Manual verification

- [ ] Open an onboarding content page with issues -- see score badge, expanded Content Checks, flagged passages
- [ ] Open an onboarding content page with 0 issues -- see score 100, all groups collapsed
- [ ] Open a cluster content page -- same behavior (shared component)
- [ ] Open a blog content page -- see flagged passages (previously missing)
- [ ] Click a flagged passage in the blog page -- scrolls to the passage in the editor
- [ ] Verify old content (no `score` field) shows "Estimated Score" label
- [ ] Verify no bible-related groups appear on projects without bibles
- [ ] Verify no AI Evaluation section appears (no tier2 data yet)
- [ ] Click "Re-run Checks" -- panel updates with fresh results
- [ ] Collapse/expand groups manually
- [ ] Verify responsive layout in the 340px sidebar width

---

## Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/components/quality/score-utils.ts` | Score estimation, tier mapping, check type constants, field labels |
| `frontend/src/components/quality/ScoreBadge.tsx` | Score badge with color tiers |
| `frontend/src/components/quality/CheckGroup.tsx` | Collapsible check group container |
| `frontend/src/components/quality/CheckRow.tsx` | Individual pass/fail or score bar row |
| `frontend/src/components/quality/FlaggedPassages.tsx` | Flagged passages list with bible support |
| `frontend/src/components/quality/QualityPanel.tsx` | Main container assembling all sub-components |
| `frontend/src/components/quality/index.ts` | Barrel export: `export { QualityPanel } from './QualityPanel'` (and sub-components for testing) |
| `frontend/src/components/quality/__tests__/score-utils.test.ts` | Unit tests for score utility functions |
| `frontend/src/components/quality/__tests__/QualityPanel.test.tsx` | Component integration tests |
| `frontend/src/components/quality/__tests__/CheckGroup.test.tsx` | CheckGroup toggle tests |

---

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/app/(authenticated)/projects/[id]/onboarding/content/[pageId]/page.tsx` | Remove ~180 lines (QualityStatusCard, FlaggedPassagesCard, interfaces, constants). Add import + `<QualityPanel>` in sidebar. |
| `frontend/src/app/(authenticated)/projects/[id]/clusters/[clusterId]/content/[pageId]/page.tsx` | Same removal/replacement as onboarding page. |
| `frontend/src/app/(authenticated)/projects/[id]/blogs/[blogId]/content/[postId]/page.tsx` | Remove ~75 lines (QualityStatusCard, interfaces). Add import + `<QualityPanel>` in sidebar. Add `handleJumpTo` callback (currently missing). |

---

## Verification Checklist

- [ ] All 3 content editor pages render `<QualityPanel>` from the shared module
- [ ] No inline `QualityStatusCard` or `FlaggedPassagesCard` remain in any page file
- [ ] Score badge shows correct number and color for each tier boundary (0, 49, 50, 69, 70, 89, 90, 100)
- [ ] "Estimated Score" label shown when `qa_results.score` is absent
- [ ] Content Checks group lists all 9 check types with correct pass/fail
- [ ] Domain Checks group hidden when `bibles_matched` is absent or empty
- [ ] Domain Checks group visible with bible name badge when `bibles_matched` has entries
- [ ] AI Evaluation group hidden when `tier2` is absent
- [ ] Flagged passages clickable in bottom_description/content field (jump-to works)
- [ ] Bible issue descriptions shown as secondary line in flagged passages
- [ ] Blog page now has flagged passages (bug fix)
- [ ] Collapsible groups default: collapsed if 0 issues, expanded if issues
- [ ] All existing tests pass (no regression)
- [ ] New unit tests pass for score-utils, QualityPanel, CheckGroup
- [ ] Re-run Checks button still works on all 3 pages
- [ ] Component handles `qa_results: null` gracefully (returns null)
- [ ] Component handles `qa_results.issues: undefined` gracefully
