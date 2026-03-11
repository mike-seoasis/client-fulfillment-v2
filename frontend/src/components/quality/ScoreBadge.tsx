'use client';

import { type ScoreTier, SCORE_TIERS } from './score-utils';

interface ScoreBadgeProps {
  score: number;
  tier: ScoreTier;
  isEstimated: boolean;
  checkedAt?: string;
}

export function ScoreBadge({ score, tier, isEstimated, checkedAt }: ScoreBadgeProps) {
  const tierInfo = SCORE_TIERS[tier];
  const timeLabel = checkedAt ? formatRelativeTime(checkedAt) : null;

  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <div
        className={`w-12 h-12 rounded-sm flex items-center justify-center ${tierInfo.colorClass} ${tierInfo.textClass} flex-shrink-0`}
      >
        <span className="text-lg font-bold leading-none">{score}</span>
      </div>
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

function formatRelativeTime(isoString: string): string | null {
  const now = Date.now();
  const then = new Date(isoString).getTime();
  if (Number.isNaN(then)) return null;
  const diffSec = Math.floor((now - then) / 1000);

  if (diffSec < 60) return 'just now';
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} min ago`;
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
  return `${Math.floor(diffSec / 86400)}d ago`;
}
