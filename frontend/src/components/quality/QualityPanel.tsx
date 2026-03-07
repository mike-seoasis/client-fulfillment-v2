'use client';

import {
  type QaIssue,
  CONTENT_CHECK_TYPES,
  CONTENT_CHECK_LABELS,
  BIBLE_CHECK_TYPES,
  BIBLE_CHECK_LABELS,
  estimateScoreFromIssues,
  getScoreTier,
} from './score-utils';
import { ScoreBadge } from './ScoreBadge';
import { CheckGroup } from './CheckGroup';
import { CheckRow } from './CheckRow';
import { FlaggedPassages } from './FlaggedPassages';

export interface Tier2Results {
  model: string;
  naturalness: number;
  brief_adherence: number;
  heading_structure: number;
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
  score?: number;
  issues: QaIssue[];
  checked_at?: string;
  tier2?: Tier2Results;
  bibles_matched?: string[];
  rewrite?: RewriteResults;
}

export interface QualityPanelProps {
  qaResults: QaResults | null;
  onJumpTo?: (context: string) => void;
}

export function QualityPanel({ qaResults, onJumpTo }: QualityPanelProps) {
  if (!qaResults) return null;

  const isEstimated = qaResults.score === undefined;
  const rawScore = qaResults.score ?? estimateScoreFromIssues(qaResults.issues ?? []);
  const score = Math.max(0, Math.min(100, rawScore));
  const tier = getScoreTier(score);

  const issues = qaResults.issues ?? [];
  const issuesByType: Record<string, number> = {};
  for (const issue of issues) {
    issuesByType[issue.type] = (issuesByType[issue.type] ?? 0) + 1;
  }

  const contentIssueCount = CONTENT_CHECK_TYPES.reduce(
    (sum, type) => sum + (issuesByType[type] ?? 0),
    0
  );

  const bibleIssueCount = BIBLE_CHECK_TYPES.reduce(
    (sum, type) => sum + (issuesByType[type] ?? 0),
    0
  );

  const bibleNames = (qaResults.bibles_matched ?? []).filter(Boolean);
  const bibleBadge = bibleNames.length > 0
    ? bibleNames.length === 1
      ? formatBibleName(bibleNames[0])
      : `${bibleNames.length} bibles`
    : undefined;

  const hasBibles = bibleNames.length > 0;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      <ScoreBadge
        score={score}
        tier={tier}
        isEstimated={isEstimated}
        checkedAt={qaResults.checked_at}
      />

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

      {qaResults.tier2 && (
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

      <FlaggedPassages issues={issues} onJumpTo={onJumpTo} />
    </div>
  );
}

function formatBibleName(slug: string): string {
  return slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
