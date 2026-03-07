'use client';

import { useState } from 'react';
import {
  type QaIssue,
  type ScoreTier,
  CONTENT_CHECK_TYPES,
  CONTENT_CHECK_LABELS,
  BIBLE_CHECK_TYPES,
  BIBLE_CHECK_LABELS,
  LLM_CHECK_TYPES,
  estimateScoreFromIssues,
  getScoreTier,
} from './score-utils';
import { ScoreBadge } from './ScoreBadge';
import { CheckGroup } from './CheckGroup';
import { CheckRow } from './CheckRow';
import { FlaggedPassages } from './FlaggedPassages';
import { RewriteBanner } from './RewriteBanner';
import { VersionDiffModal } from './VersionDiffModal';
import { ScoreBar } from './ScoreBar';

export interface Tier2Results {
  model: string;
  naturalness: number;
  brief_adherence: number;
  heading_structure: number;
  cost_usd: number;
  latency_ms: number;
  error?: string;
}

export interface RewriteResults {
  triggered: boolean;
  original_score: number;
  fixed_score: number | null;
  issues_sent: number;
  issues_resolved: number;
  issues_remaining: number;
  new_issues_introduced: number;
  cost_usd: number;
  latency_ms: number;
  kept_version: 'original' | 'fixed';
  skip_reason?: string;
  error?: string;
}

export interface VersionsData {
  original: { score: number; content_snapshot: Record<string, string> };
  fixed: { score: number; changes_made: string[] };
}

export interface QaResults {
  passed: boolean;
  score?: number;
  score_tier?: string;
  short_circuited?: boolean;
  issues: QaIssue[];
  checked_at?: string;
  tier2?: Tier2Results;
  bibles_matched?: string[];
  rewrite?: RewriteResults;
  versions?: VersionsData;
}

export interface QualityPanelProps {
  qaResults: QaResults | null;
  onJumpTo?: (context: string) => void;
  /** Current content fields (for diff modal comparison) */
  currentFields?: Record<string, string | null>;
  /** Callback to restore original content before auto-rewrite */
  onRestoreOriginal?: () => void;
}

export function QualityPanel({ qaResults, onJumpTo, currentFields, onRestoreOriginal }: QualityPanelProps) {
  const [modalMode, setModalMode] = useState<'diff' | 'original' | null>(null);

  if (!qaResults) return null;

  const isEstimated = qaResults.score === undefined;
  const rawScore = qaResults.score ?? estimateScoreFromIssues(qaResults.issues ?? []);
  const score = Math.max(0, Math.min(100, rawScore));
  const tier = (qaResults.score_tier as ScoreTier) ?? getScoreTier(score);

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

  const llmIssueCount = LLM_CHECK_TYPES.reduce(
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

  const modelBadge = qaResults.tier2 && !qaResults.tier2.error ? (
    <span className="text-xs font-mono text-warm-400 bg-sand-100 px-1.5 py-0.5 rounded-sm">
      {qaResults.tier2.model}
    </span>
  ) : undefined;

  return (
    <div className="bg-white rounded-sm border border-sand-400/60 overflow-hidden">
      <ScoreBadge
        score={score}
        tier={tier}
        isEstimated={isEstimated}
        checkedAt={qaResults.checked_at}
      />

      {/* Rewrite Banner — between score badge and check groups */}
      {qaResults.rewrite?.triggered && (
        <RewriteBanner
          rewrite={qaResults.rewrite}
          versions={qaResults.versions}
          onViewOriginal={() => setModalMode('original')}
          onViewDiff={() => setModalMode('diff')}
        />
      )}

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

      {qaResults.short_circuited && !qaResults.tier2 && (
        <div role="status" className="px-4 py-2.5 text-xs text-warm-400 bg-sand-50 border-t border-sand-200">
          AI evaluation skipped (critical issues found)
        </div>
      )}

      {qaResults.tier2 && (
        <CheckGroup
          title="AI Evaluation"
          issueCount={llmIssueCount}
          badge={modelBadge}
          defaultOpen={llmIssueCount > 0 || !!qaResults.tier2}
        >
          {qaResults.tier2.error ? (
            <div role="alert" className="px-4 py-2.5 text-xs text-coral-600">
              AI evaluation error: {qaResults.tier2.error}
            </div>
          ) : (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-xs py-0.5">
                <span className="text-warm-600">Naturalness</span>
                <div className="w-28"><ScoreBar value={qaResults.tier2.naturalness} /></div>
              </div>
              <div className="flex items-center justify-between text-xs py-0.5">
                <span className="text-warm-600">Brief Adherence</span>
                <div className="w-28"><ScoreBar value={qaResults.tier2.brief_adherence} /></div>
              </div>
              <div className="flex items-center justify-between text-xs py-0.5">
                <span className="text-warm-600">Heading Structure</span>
                <div className="w-28"><ScoreBar value={qaResults.tier2.heading_structure} /></div>
              </div>
              {/* Show explanations for low scores */}
              {qaResults.tier2.naturalness < 0.7 && (
                <LowScoreNote label="Naturalness" value={qaResults.tier2.naturalness} />
              )}
              {qaResults.tier2.brief_adherence < 0.7 && (
                <LowScoreNote label="Brief Adherence" value={qaResults.tier2.brief_adherence} />
              )}
              {qaResults.tier2.heading_structure < 0.7 && (
                <LowScoreNote label="Heading Structure" value={qaResults.tier2.heading_structure} />
              )}
            </div>
          )}
        </CheckGroup>
      )}

      <FlaggedPassages issues={issues} onJumpTo={onJumpTo} />

      {/* Version Diff Modal */}
      {modalMode && qaResults.versions && (
        <VersionDiffModal
          versions={qaResults.versions}
          currentFields={currentFields ?? {}}
          mode={modalMode}
          onClose={() => setModalMode(null)}
          onRestoreOriginal={() => {
            setModalMode(null);
            onRestoreOriginal?.();
          }}
        />
      )}
    </div>
  );
}

function LowScoreNote({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-xs text-coral-600 bg-coral-50/50 px-2 py-1 rounded-sm" role="note">
      {label} score is low ({value.toFixed(2)}) — may need manual editing
    </div>
  );
}

function formatBibleName(slug: string): string {
  return slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
