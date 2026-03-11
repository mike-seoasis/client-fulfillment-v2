'use client';

import { useState } from 'react';
import type { RewriteResults, VersionsData } from './QualityPanel';

interface RewriteBannerProps {
  rewrite: RewriteResults;
  versions?: VersionsData;
  onViewOriginal: () => void;
  onViewDiff: () => void;
}

const PANEL_ID = 'rewrite-banner-panel';

export function RewriteBanner({ rewrite, versions, onViewOriginal, onViewDiff }: RewriteBannerProps) {
  const [expanded, setExpanded] = useState(true);

  if (!rewrite.triggered) return null;

  const improved = rewrite.fixed_score !== null && rewrite.fixed_score > rewrite.original_score;
  const keptFixed = rewrite.kept_version === 'fixed';
  const changesMade = versions?.fixed?.changes_made ?? [];

  // Collapsed summary: "52 → 88 (3 changes)"
  const collapsedSummary = rewrite.fixed_score !== null
    ? `${rewrite.original_score} \u2192 ${rewrite.fixed_score} (${changesMade.length} change${changesMade.length !== 1 ? 's' : ''})`
    : `Score ${rewrite.original_score} (no fix applied)`;

  return (
    <div className="border-t border-sand-200">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        aria-controls={PANEL_ID}
        className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-sand-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-3.5 h-3.5 text-warm-400 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5l7 7-7 7" />
          </svg>

          <svg className="w-3.5 h-3.5 text-lagoon-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>

          <span className="text-xs font-semibold text-warm-700">Auto-Rewrite</span>

          {keptFixed && improved ? (
            <span className="text-xs font-mono text-palm-600 bg-palm-50 px-1.5 py-0.5 rounded-sm">
              improved
            </span>
          ) : rewrite.error || rewrite.skip_reason ? (
            <span className="text-xs font-mono text-warm-400 bg-sand-100 px-1.5 py-0.5 rounded-sm">
              skipped
            </span>
          ) : (
            <span className="text-xs font-mono text-warm-400 bg-sand-100 px-1.5 py-0.5 rounded-sm">
              kept original
            </span>
          )}
        </div>

        {!expanded && (
          <span className="text-xs text-warm-400 font-mono truncate ml-2">{collapsedSummary}</span>
        )}
      </button>

      {expanded && (
        <div id={PANEL_ID} className="px-4 pb-3 space-y-3">
          {/* Score improvement bar */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs flex-shrink-0">
              <span className="font-mono text-warm-500">{rewrite.original_score}</span>
              {rewrite.fixed_score !== null && (
                <>
                  <svg className="w-3 h-3 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                  <span className={`font-mono font-medium ${improved ? 'text-palm-600' : 'text-warm-500'}`}>
                    {rewrite.fixed_score}
                  </span>
                </>
              )}
            </div>
            {rewrite.fixed_score !== null && (
              <div className="flex-1 h-1.5 bg-sand-200 rounded-sm overflow-hidden">
                <div
                  className={`h-full rounded-sm transition-all ${improved ? 'bg-palm-400' : 'bg-sand-400'}`}
                  style={{ width: `${Math.min(rewrite.fixed_score, 100)}%` }}
                />
              </div>
            )}
          </div>

          {/* Stats row */}
          <div className="flex items-center gap-4 text-xs text-warm-500 flex-wrap">
            {rewrite.issues_resolved > 0 && (
              <span>
                <span className="font-medium text-palm-600">{rewrite.issues_resolved}</span> resolved
              </span>
            )}
            {rewrite.issues_remaining > 0 && (
              <span>
                <span className="font-medium text-warm-600">{rewrite.issues_remaining}</span> remaining
              </span>
            )}
            {rewrite.new_issues_introduced > 0 && (
              <span>
                <span className="font-medium text-coral-600">{rewrite.new_issues_introduced}</span> new
              </span>
            )}
          </div>

          {/* Changes list */}
          {changesMade.length > 0 && (
            <div className="space-y-1">
              {changesMade.map((change, idx) => (
                <div key={idx} className="flex items-start gap-1.5 text-xs text-warm-600">
                  <span className="text-palm-500 mt-0.5 flex-shrink-0" aria-hidden="true">-</span>
                  <span className="break-words min-w-0">{change}</span>
                </div>
              ))}
            </div>
          )}

          {/* Error message */}
          {rewrite.error && (
            <div role="alert" className="text-xs text-coral-600 bg-coral-50 px-2 py-1.5 rounded-sm">
              {rewrite.error}
            </div>
          )}

          {/* Action buttons */}
          {versions && (
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={onViewOriginal}
                className="px-2.5 py-1 text-xs font-medium text-warm-600 bg-sand-100 hover:bg-sand-200 rounded-sm transition-colors"
              >
                View Original
              </button>
              <button
                type="button"
                onClick={onViewDiff}
                className="px-2.5 py-1 text-xs font-medium text-lagoon-600 bg-lagoon-50 hover:bg-lagoon-100 rounded-sm transition-colors"
              >
                View Diff
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
