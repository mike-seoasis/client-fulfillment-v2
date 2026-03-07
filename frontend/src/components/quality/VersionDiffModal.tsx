'use client';

import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import type { VersionsData } from './QualityPanel';
import { FIELD_LABELS } from './score-utils';

// ---------------------------------------------------------------------------
// Word-level diff using LCS (no external dependencies)
// ---------------------------------------------------------------------------

export interface DiffSegment {
  type: 'equal' | 'added' | 'removed';
  text: string;
}

/** Tokenize text into words + whitespace tokens */
function tokenize(text: string): string[] {
  return text.match(/\S+|\s+/g) ?? [];
}

/** Compute LCS length table for two token arrays */
function lcsTable(a: string[], b: string[]): number[][] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }
  return dp;
}

/** Max token count before we fall back to simple replacement diff */
const MAX_DIFF_TOKENS = 3000;

/** Compute word-level diff between two strings */
export function wordDiff(original: string, modified: string): DiffSegment[] {
  if (original === modified) {
    return original ? [{ type: 'equal', text: original }] : [];
  }
  if (!original) return modified ? [{ type: 'added', text: modified }] : [];
  if (!modified) return [{ type: 'removed', text: original }];

  const aTokens = tokenize(original);
  const bTokens = tokenize(modified);

  // Guard against huge inputs — fall back to simple replacement
  if (aTokens.length > MAX_DIFF_TOKENS || bTokens.length > MAX_DIFF_TOKENS) {
    return [
      { type: 'removed', text: original },
      { type: 'added', text: modified },
    ];
  }

  const dp = lcsTable(aTokens, bTokens);

  // Backtrack to produce diff
  const segments: DiffSegment[] = [];
  let i = aTokens.length;
  let j = bTokens.length;

  const rawSegments: DiffSegment[] = [];
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && aTokens[i - 1] === bTokens[j - 1]) {
      rawSegments.push({ type: 'equal', text: aTokens[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      rawSegments.push({ type: 'added', text: bTokens[j - 1] });
      j--;
    } else {
      rawSegments.push({ type: 'removed', text: aTokens[i - 1] });
      i--;
    }
  }

  rawSegments.reverse();

  // Merge consecutive segments of same type
  for (const seg of rawSegments) {
    const last = segments[segments.length - 1];
    if (last && last.type === seg.type) {
      last.text += seg.text;
    } else {
      segments.push({ ...seg });
    }
  }

  return segments;
}

// ---------------------------------------------------------------------------
// Modal component
// ---------------------------------------------------------------------------

type ViewMode = 'diff' | 'original';

interface VersionDiffModalProps {
  versions: VersionsData;
  currentFields: Record<string, string | null>;
  mode: ViewMode;
  onClose: () => void;
  onRestoreOriginal: () => void;
}

export function VersionDiffModal({
  versions,
  currentFields,
  mode: initialMode,
  onClose,
  onRestoreOriginal,
}: VersionDiffModalProps) {
  const [mode, setMode] = useState<ViewMode>(initialMode);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Reset confirm state when switching modes
  const handleModeSwitch = useCallback((newMode: ViewMode) => {
    setConfirmRestore(false);
    setMode(newMode);
  }, []);

  // Lock body scroll when modal is open
  useEffect(() => {
    const original = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = original; };
  }, []);

  // Close on Escape, focus trap
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
        return;
      }
      // Focus trap
      if (e.key === 'Tab' && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  // Auto-focus dialog on mount
  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const handleRestore = useCallback(() => {
    if (!confirmRestore) {
      setConfirmRestore(true);
      return;
    }
    onRestoreOriginal();
  }, [confirmRestore, onRestoreOriginal]);

  // Fields that have original snapshots
  const snapshotFields = Object.keys(versions.original.content_snapshot);

  const content = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="version-diff-title"
        tabIndex={-1}
        className="bg-white rounded-sm shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col mx-4 outline-none"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-sand-200">
          <div className="flex items-center gap-3">
            <h2 id="version-diff-title" className="text-sm font-semibold text-warm-800">Version Comparison</h2>
            <div className="flex rounded-sm border border-sand-300 overflow-hidden" role="tablist" aria-label="View mode">
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'diff'}
                onClick={() => handleModeSwitch('diff')}
                className={`px-3 py-1 text-xs font-medium transition-colors ${
                  mode === 'diff'
                    ? 'bg-lagoon-50 text-lagoon-700 border-r border-sand-300'
                    : 'text-warm-500 hover:bg-sand-50 border-r border-sand-300'
                }`}
              >
                Diff
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === 'original'}
                onClick={() => handleModeSwitch('original')}
                className={`px-3 py-1 text-xs font-medium transition-colors ${
                  mode === 'original'
                    ? 'bg-lagoon-50 text-lagoon-700'
                    : 'text-warm-500 hover:bg-sand-50'
                }`}
              >
                Original
              </button>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 text-warm-400 hover:text-warm-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Score comparison */}
        <div className="flex items-center gap-4 px-6 py-3 bg-sand-50 border-b border-sand-200">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-warm-500">Original:</span>
            <span className="font-mono font-medium text-warm-700">{versions.original.score}</span>
          </div>
          <svg className="w-3 h-3 text-warm-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 5l7 7m0 0l-7 7m7-7H3" />
          </svg>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-warm-500">Fixed:</span>
            <span className="font-mono font-medium text-palm-600">{versions.fixed.score}</span>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6" role="tabpanel">
          {snapshotFields.length === 0 ? (
            <p className="text-xs text-warm-400 italic">No field snapshots available.</p>
          ) : (
            snapshotFields.map((field) => {
              const originalText = versions.original.content_snapshot[field] ?? '';
              const currentText = (currentFields[field] as string) ?? '';
              const fieldLabel = FIELD_LABELS[field] ?? field;

              return (
                <div key={field}>
                  <h3 className="text-xs font-semibold text-warm-700 uppercase tracking-wider mb-2">
                    {fieldLabel}
                  </h3>
                  <div className="bg-sand-50 rounded-sm border border-sand-200 p-4 text-sm text-warm-800 leading-relaxed overflow-x-auto">
                    {mode === 'original' ? (
                      <OriginalView text={originalText} />
                    ) : (
                      <DiffView original={originalText} current={currentText} />
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer with restore */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-sand-200 bg-sand-50/50">
          <p className="text-xs text-warm-400">
            {mode === 'diff' ? (
              <>
                <span className="inline-block w-2 h-2 rounded-sm bg-coral-100 border border-coral-300 mr-1 align-middle" aria-hidden="true" />
                Removed
                <span className="inline-block w-2 h-2 rounded-sm bg-palm-100 border border-palm-300 mx-1 ml-2 align-middle" aria-hidden="true" />
                Added
              </>
            ) : 'Showing original content before auto-rewrite'}
          </p>
          <div className="flex items-center gap-2">
            {confirmRestore && (
              <span className="text-xs text-coral-600 mr-1" role="alert">Are you sure?</span>
            )}
            <button
              type="button"
              onClick={() => { setConfirmRestore(false); onClose(); }}
              className="px-3 py-1.5 text-xs font-medium text-warm-600 bg-white border border-sand-300 hover:bg-sand-50 rounded-sm transition-colors"
            >
              {confirmRestore ? 'Cancel' : 'Close'}
            </button>
            <button
              type="button"
              onClick={handleRestore}
              className={`px-3 py-1.5 text-xs font-medium rounded-sm transition-colors ${
                confirmRestore
                  ? 'text-white bg-coral-500 hover:bg-coral-600'
                  : 'text-coral-600 bg-coral-50 hover:bg-coral-100'
              }`}
            >
              {confirmRestore ? 'Confirm Restore' : 'Restore Original'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(content, document.body);
}

// ---------------------------------------------------------------------------
// Sub-views
// ---------------------------------------------------------------------------

function OriginalView({ text }: { text: string }) {
  // Strip HTML and display
  const plain = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  return <p className="whitespace-pre-wrap break-words">{plain || <span className="italic text-warm-400">Empty</span>}</p>;
}

function DiffView({ original, current }: { original: string; current: string }) {
  const plainOriginal = original.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const plainCurrent = current.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const segments = useMemo(() => wordDiff(plainOriginal, plainCurrent), [plainOriginal, plainCurrent]);

  if (segments.length === 0) {
    return <p className="italic text-warm-400">No content</p>;
  }

  return (
    <p className="whitespace-pre-wrap break-words">
      {segments.map((seg, idx) => {
        if (seg.type === 'equal') return <span key={idx}>{seg.text}</span>;
        if (seg.type === 'removed') {
          return (
            <span key={idx} className="bg-coral-100 text-coral-700 line-through" aria-label="removed text">
              {seg.text}
            </span>
          );
        }
        return (
          <span key={idx} className="bg-palm-100 text-palm-700 underline decoration-palm-300" aria-label="added text">
            {seg.text}
          </span>
        );
      })}
    </p>
  );
}
