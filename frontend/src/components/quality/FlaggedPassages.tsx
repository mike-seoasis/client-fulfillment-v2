'use client';

import { useMemo } from 'react';
import {
  type QaIssue,
  CONTENT_CHECK_LABELS,
  BIBLE_CHECK_LABELS,
  BIBLE_CHECK_TYPES,
  FIELD_LABELS,
} from './score-utils';

interface FlaggedPassagesProps {
  issues: QaIssue[];
  onJumpTo?: (context: string) => void;
}

export function FlaggedPassages({ issues, onJumpTo }: FlaggedPassagesProps) {
  const groups = useMemo(() => {
    if (!issues || issues.length === 0) return [];
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

  if (groups.length === 0) return null;

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
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold text-warm-800">{group.label}</span>
              <span className="text-xs font-mono text-coral-500 bg-coral-50 px-1.5 py-0.5 rounded-sm">
                {group.items.length}
              </span>
            </div>
            <div className="space-y-1.5">
              {group.items.map((issue, idx) => {
                const ctx = displayContext(issue.context);
                const canJump =
                  onJumpTo &&
                  (issue.field === 'bottom_description' || issue.field === 'content');
                return (
                  <div key={`${issue.type}-${issue.field}-${idx}`}>
                    <div
                      className={`flex items-start gap-2 text-xs py-1 px-2 rounded-sm ${
                        canJump ? 'hover:bg-sand-100 cursor-pointer group' : ''
                      }`}
                      {...(canJump
                        ? {
                            role: 'button',
                            tabIndex: 0,
                            onClick: () => onJumpTo(issue.context),
                            onKeyDown: (e: React.KeyboardEvent) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                onJumpTo(issue.context);
                              }
                            },
                          }
                        : {})}
                    >
                      <span className="text-warm-400 font-mono flex-shrink-0 mt-px">
                        {FIELD_LABELS[issue.field] ?? issue.field}
                      </span>
                      <span
                        className="text-warm-600 leading-relaxed min-w-0 line-clamp-2"
                        title={ctx}
                      >
                        {ctx}
                      </span>
                      {canJump && (
                        <span className="text-lagoon-500 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-px" aria-hidden="true">
                          ↓
                        </span>
                      )}
                    </div>
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
