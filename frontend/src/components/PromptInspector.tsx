'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { contentGenerationKeys } from '@/hooks/useContentGeneration';
import { getPagePrompts, type PromptLogResponse } from '@/lib/api';
import { Toast } from '@/components/ui';

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function CloseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  );
}

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function ChevronDownIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Collapsible section for prompt text
// ---------------------------------------------------------------------------

function CollapsibleSection({
  label,
  text,
  mono,
}: {
  label: string;
  text: string | null;
  mono?: boolean;
}) {
  const [expanded, setExpanded] = useState(true);

  if (!text) return null;

  const isLong = text.length > 200;
  const preview = isLong ? text.slice(0, 200) + '...' : text;

  return (
    <div className="border border-cream-400 rounded-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-left bg-cream-100 hover:bg-cream-200 transition-colors"
      >
        <span className="text-xs font-medium text-warm-gray-700 uppercase tracking-wide">
          {label}
        </span>
        <ChevronDownIcon
          className={`w-3.5 h-3.5 text-warm-gray-500 transition-transform duration-150 ${
            expanded ? 'rotate-180' : ''
          }`}
        />
      </button>
      <div className={`px-3 py-2 ${mono ? 'font-mono' : ''} text-xs text-warm-gray-800 leading-relaxed`}>
        <pre className="whitespace-pre-wrap break-words">
          {expanded ? text : preview}
        </pre>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: ignore if clipboard unavailable
    }
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 text-xs text-warm-gray-500 hover:text-warm-gray-700 transition-colors"
      title={label ?? 'Copy to clipboard'}
    >
      {copied ? (
        <CheckIcon className="w-3.5 h-3.5 text-palm-500" />
      ) : (
        <CopyIcon className="w-3.5 h-3.5" />
      )}
      <span>{copied ? 'Copied' : 'Copy'}</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Single prompt log entry
// ---------------------------------------------------------------------------

function PromptEntry({ entry }: { entry: PromptLogResponse }) {
  const fullPromptText = [entry.prompt_text, entry.response_text].filter(Boolean).join('\n\n---\n\n');

  return (
    <div className="space-y-2">
      {/* Meta row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded-sm ${
              entry.role === 'system'
                ? 'bg-lagoon-100 text-lagoon-700'
                : 'bg-palm-100 text-palm-700'
            }`}
          >
            {entry.role}
          </span>
          {entry.model && (
            <span className="text-[10px] text-warm-gray-400 font-mono">{entry.model}</span>
          )}
        </div>
        <CopyButton text={fullPromptText} label="Copy prompt + response" />
      </div>

      {/* Prompt text */}
      <CollapsibleSection label="Prompt" text={entry.prompt_text} mono />

      {/* Response text */}
      {entry.response_text && (
        <CollapsibleSection label="Response" text={entry.response_text} mono />
      )}

      {/* Token usage + duration */}
      {(entry.input_tokens != null || entry.output_tokens != null || entry.duration_ms != null) && (
        <div className="flex items-center gap-3 text-[10px] text-warm-gray-500 font-mono">
          {entry.input_tokens != null && (
            <span>{entry.input_tokens.toLocaleString()} in</span>
          )}
          {entry.output_tokens != null && (
            <span>{entry.output_tokens.toLocaleString()} out</span>
          )}
          {entry.duration_ms != null && (
            <span>
              {entry.duration_ms >= 1000
                ? `${(entry.duration_ms / 1000).toFixed(1)}s`
                : `${Math.round(entry.duration_ms)}ms`}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step group
// ---------------------------------------------------------------------------

function StepGroup({
  step,
  entries,
}: {
  step: string;
  entries: PromptLogResponse[];
}) {
  const totalIn = entries.reduce((acc, e) => acc + (e.input_tokens ?? 0), 0);
  const totalOut = entries.reduce((acc, e) => acc + (e.output_tokens ?? 0), 0);

  const stepLabel =
    step === 'content_writing' ? 'Content Writing' :
    step === 'content_brief' ? 'Content Brief' :
    step === 'quality_check' ? 'Quality Check' :
    step.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div>
      {/* Step header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-warm-gray-900">{stepLabel}</h4>
        {(totalIn > 0 || totalOut > 0) && (
          <span className="text-[10px] text-warm-gray-400 font-mono">
            {totalIn.toLocaleString()} in / {totalOut.toLocaleString()} out
          </span>
        )}
      </div>

      {/* Entries */}
      <div className="space-y-4">
        {entries.map((entry) => (
          <PromptEntry key={entry.id} entry={entry} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Group prompts by step, preserving order
// ---------------------------------------------------------------------------

function groupByStep(prompts: PromptLogResponse[]): { step: string; entries: PromptLogResponse[] }[] {
  const map = new Map<string, PromptLogResponse[]>();
  for (const prompt of prompts) {
    const existing = map.get(prompt.step);
    if (existing) {
      existing.push(prompt);
    } else {
      map.set(prompt.step, [prompt]);
    }
  }
  return Array.from(map.entries()).map(([step, entries]) => ({ step, entries }));
}

// ---------------------------------------------------------------------------
// Group prompts into runs (by time gap), then by step within each run
// ---------------------------------------------------------------------------

interface Run {
  index: number; // 1-based run number
  startedAt: Date;
  entries: PromptLogResponse[];
  steps: { step: string; entries: PromptLogResponse[] }[];
}

/** Gap threshold in ms — entries more than 60s apart are treated as separate runs */
const RUN_GAP_MS = 60_000;

function groupIntoRuns(prompts: PromptLogResponse[]): Run[] {
  if (prompts.length === 0) return [];

  // Sort by created_at ascending
  const sorted = [...prompts].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  const runs: Run[] = [];
  let currentEntries: PromptLogResponse[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i++) {
    const prev = new Date(sorted[i - 1].created_at).getTime();
    const curr = new Date(sorted[i].created_at).getTime();

    if (curr - prev > RUN_GAP_MS) {
      // Start a new run
      runs.push({
        index: runs.length + 1,
        startedAt: new Date(currentEntries[0].created_at),
        entries: currentEntries,
        steps: groupByStep(currentEntries),
      });
      currentEntries = [sorted[i]];
    } else {
      currentEntries.push(sorted[i]);
    }
  }

  // Push last run
  runs.push({
    index: runs.length + 1,
    startedAt: new Date(currentEntries[0].created_at),
    entries: currentEntries,
    steps: groupByStep(currentEntries),
  });

  return runs;
}

// ---------------------------------------------------------------------------
// Run group component
// ---------------------------------------------------------------------------

const RUN_COLORS = [
  { border: 'border-l-lagoon-400', badge: 'bg-lagoon-100 text-lagoon-700' },
  { border: 'border-l-palm-400', badge: 'bg-palm-100 text-palm-700' },
  { border: 'border-l-coral-400', badge: 'bg-coral-100 text-coral-700' },
  { border: 'border-l-warm-gray-400', badge: 'bg-warm-gray-100 text-warm-gray-700' },
];

function formatRunTime(date: Date): string {
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}

function RunGroup({ run, totalRuns }: { run: Run; totalRuns: number }) {
  const colors = RUN_COLORS[run.index % RUN_COLORS.length];
  const totalIn = run.entries.reduce((a, e) => a + (e.input_tokens ?? 0), 0);
  const totalOut = run.entries.reduce((a, e) => a + (e.output_tokens ?? 0), 0);
  const isLatest = run.index === totalRuns;

  return (
    <div className={`border-l-[3px] ${colors.border} pl-4`}>
      {/* Run header */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-sm ${colors.badge}`}>
          Run {run.index}
        </span>
        {isLatest && totalRuns > 1 && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-sm bg-palm-500 text-white">
            Latest
          </span>
        )}
        <span className="text-[10px] text-warm-gray-400 font-mono">
          {formatRunTime(run.startedAt)}
        </span>
        <span className="text-[10px] text-warm-gray-400 font-mono ml-auto">
          {totalIn.toLocaleString()} in / {totalOut.toLocaleString()} out
        </span>
      </div>

      {/* Steps within this run */}
      <div className="space-y-5">
        {run.steps.map((group) => (
          <StepGroup key={`${run.index}-${group.step}`} step={group.step} entries={group.entries} />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main PromptInspector panel
// ---------------------------------------------------------------------------

interface PromptInspectorProps {
  projectId: string;
  pageId: string;
  pageUrl: string;
  isOpen: boolean;
  onClose: () => void;
  isGenerating?: boolean;
}

export function PromptInspector({
  projectId,
  pageId,
  pageUrl,
  isOpen,
  onClose,
  isGenerating,
}: PromptInspectorProps) {
  const [showToast, setShowToast] = useState(false);

  // Fetch prompt logs, polling every 3s while the pipeline is still running
  const { data: prompts, isLoading } = useQuery({
    queryKey: contentGenerationKeys.pagePrompts(projectId, pageId),
    queryFn: () => getPagePrompts(projectId, pageId),
    enabled: isOpen && !!pageId,
    refetchInterval: isGenerating ? 3000 : false,
  });

  if (!isOpen) return null;

  const runs = groupIntoRuns(prompts ?? []);

  // Display path from URL
  let displayPath = pageUrl;
  try {
    const url = new URL(pageUrl);
    displayPath = url.pathname + url.search;
  } catch {
    // use raw value
  }

  const handleCopyAll = async () => {
    if (!prompts?.length) return;
    const fullText = prompts
      .map((p) => {
        const parts = [`[${p.role.toUpperCase()}] ${p.step}`];
        parts.push(p.prompt_text);
        if (p.response_text) parts.push('--- RESPONSE ---\n' + p.response_text);
        return parts.join('\n\n');
      })
      .join('\n\n========================================\n\n');

    try {
      await navigator.clipboard.writeText(fullText);
      setShowToast(true);
    } catch {
      // ignore
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-warm-gray-900/20 z-40 transition-opacity"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed top-0 right-0 h-full w-full max-w-xl bg-white border-l border-cream-500 shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-cream-400 bg-cream-50 shrink-0">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-warm-gray-900">Prompt Inspector</h3>
            <p className="text-xs text-warm-gray-500 truncate mt-0.5" title={pageUrl}>
              {displayPath}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {prompts && prompts.length > 0 && (
              <button
                type="button"
                onClick={handleCopyAll}
                className="inline-flex items-center gap-1 text-xs text-warm-gray-500 hover:text-warm-gray-700 px-2 py-1 rounded-sm hover:bg-cream-200 transition-colors"
              >
                <CopyIcon className="w-3.5 h-3.5" />
                Copy All
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-sm hover:bg-cream-200 transition-colors"
              aria-label="Close prompt inspector"
            >
              <CloseIcon className="w-4 h-4 text-warm-gray-600" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {isLoading && (
            <div className="space-y-4 animate-pulse">
              {[...Array(3)].map((_, i) => (
                <div key={i}>
                  <div className="h-4 bg-cream-300 rounded w-32 mb-3" />
                  <div className="h-20 bg-cream-200 rounded" />
                </div>
              ))}
            </div>
          )}

          {!isLoading && runs.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm text-warm-gray-500">
                {isGenerating
                  ? 'Waiting for prompts... They will appear here as the pipeline runs.'
                  : 'No prompt logs found for this page.'}
              </p>
            </div>
          )}

          {!isLoading && runs.length > 0 && (
            <div className="space-y-8">
              {runs.map((run) => (
                <RunGroup key={run.index} run={run} totalRuns={runs.length} />
              ))}
            </div>
          )}
        </div>

        {/* Footer stats */}
        {prompts && prompts.length > 0 && (
          <div className="px-4 py-2 border-t border-cream-400 bg-cream-50 shrink-0">
            <div className="flex items-center justify-between text-[10px] text-warm-gray-500 font-mono">
              <span>{prompts.length} prompt entries</span>
              <span>
                {prompts.reduce((a, p) => a + (p.input_tokens ?? 0), 0).toLocaleString()} in /{' '}
                {prompts.reduce((a, p) => a + (p.output_tokens ?? 0), 0).toLocaleString()} out total
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Toast for copy-all */}
      {showToast && (
        <Toast
          message="All prompts copied to clipboard"
          variant="success"
          onClose={() => setShowToast(false)}
        />
      )}
    </>
  );
}
