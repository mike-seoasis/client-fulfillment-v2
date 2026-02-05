'use client';

import { useState, useRef, useEffect } from 'react';
import type { PageWithKeywords } from '@/lib/api';
import { useApproveKeyword, useTogglePriority } from '@/hooks/useKeywordMutations';

interface KeywordPageRowProps {
  /** Page with keyword data */
  page: PageWithKeywords;
  /** Project ID for API calls */
  projectId: string;
  /** Callback when keyword is clicked (for opening edit dropdown) */
  onKeywordClick?: (pageId: string) => void;
}

// SVG Icons
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

function StarIcon({ className, filled }: { className?: string; filled?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill={filled ? 'currentColor' : 'none'}
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="10" opacity="0.25" />
      <path d="M12 2a10 10 0 0 1 10 10" />
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

/**
 * Simple tooltip component that appears on hover.
 */
function Tooltip({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();

      // Position tooltip above the trigger, centered
      setPosition({
        top: triggerRect.top - tooltipRect.height - 8,
        left: triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2),
      });
    }
  }, [isVisible]);

  return (
    <div
      ref={triggerRef}
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          ref={tooltipRef}
          className="fixed z-50 px-2 py-1 text-xs text-white bg-warm-gray-800 rounded-sm shadow-lg max-w-xs break-all"
          style={{ top: position.top, left: position.left }}
        >
          {text}
          {/* Tooltip arrow */}
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-warm-gray-800 rotate-45" />
        </div>
      )}
    </div>
  );
}

/**
 * Score tooltip showing breakdown of composite score components.
 */
function ScoreTooltip({
  compositeScore,
  children,
}: {
  compositeScore: number | null;
  children: React.ReactNode;
}) {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isVisible && triggerRef.current && tooltipRef.current) {
      const triggerRect = triggerRef.current.getBoundingClientRect();
      const tooltipRect = tooltipRef.current.getBoundingClientRect();

      setPosition({
        top: triggerRect.top - tooltipRect.height - 8,
        left: triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2),
      });
    }
  }, [isVisible]);

  if (compositeScore === null) {
    return <>{children}</>;
  }

  return (
    <div
      ref={triggerRef}
      className="relative inline-block cursor-help"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          ref={tooltipRef}
          className="fixed z-50 px-3 py-2 text-xs bg-warm-gray-800 text-white rounded-sm shadow-lg whitespace-nowrap"
          style={{ top: position.top, left: position.left }}
        >
          <div className="font-medium mb-1">Score Breakdown</div>
          <div className="space-y-0.5 text-warm-gray-300">
            <div>Volume: 50% weight</div>
            <div>Relevance: 35% weight</div>
            <div>Competition: 15% weight</div>
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-1 w-2 h-2 bg-warm-gray-800 rotate-45" />
        </div>
      )}
    </div>
  );
}

/**
 * Format a number with commas as thousands separators.
 */
function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '—';
  return num.toLocaleString();
}

/**
 * Extract path from a full URL for display.
 */
function extractPath(url: string): string {
  try {
    const parsed = new URL(url);
    return parsed.pathname + parsed.search;
  } catch {
    return url;
  }
}

/**
 * KeywordPageRow component displays a single page's keyword data
 * with interactive controls for approval and priority.
 */
export function KeywordPageRow({ page, projectId, onKeywordClick }: KeywordPageRowProps) {
  const approveKeyword = useApproveKeyword();
  const togglePriority = useTogglePriority();

  const hasKeyword = !!page.keywords?.primary_keyword;
  const isApproved = page.keywords?.is_approved ?? false;
  const isPriority = page.keywords?.is_priority ?? false;
  const displayUrl = extractPath(page.url);

  const handleApprove = async () => {
    if (!page.keywords || isApproved) return;

    try {
      await approveKeyword.mutateAsync({
        projectId,
        pageId: page.id,
      });
    } catch (error) {
      console.error('Failed to approve keyword:', error);
    }
  };

  const handleTogglePriority = async () => {
    if (!page.keywords) return;

    try {
      await togglePriority.mutateAsync({
        projectId,
        pageId: page.id,
      });
    } catch (error) {
      console.error('Failed to toggle priority:', error);
    }
  };

  const handleKeywordClick = () => {
    if (hasKeyword && onKeywordClick) {
      onKeywordClick(page.id);
    }
  };

  return (
    <div className="py-3 px-4 border-b border-cream-200 last:border-b-0 hover:bg-sand-50 transition-colors">
      <div className="flex items-start gap-3">
        {/* Priority toggle */}
        <button
          onClick={handleTogglePriority}
          disabled={!hasKeyword || togglePriority.isPending}
          className={`flex-shrink-0 mt-0.5 p-1 rounded-sm transition-colors ${
            hasKeyword
              ? 'hover:bg-cream-200 cursor-pointer'
              : 'cursor-not-allowed opacity-50'
          }`}
          title={isPriority ? 'Remove priority' : 'Mark as priority for internal linking'}
          aria-label={isPriority ? 'Remove priority' : 'Mark as priority'}
        >
          {togglePriority.isPending ? (
            <SpinnerIcon className="w-5 h-5 text-warm-gray-400 animate-spin" />
          ) : (
            <StarIcon
              className={`w-5 h-5 ${
                isPriority ? 'text-palm-500' : 'text-warm-gray-300'
              }`}
              filled={isPriority}
            />
          )}
        </button>

        {/* Main content */}
        <div className="flex-1 min-w-0">
          {/* URL with tooltip for full URL */}
          <div className="flex items-center gap-2 mb-1">
            <Tooltip text={page.url}>
              <span className="text-warm-gray-900 font-mono text-sm truncate block max-w-md">
                {displayUrl}
              </span>
            </Tooltip>
          </div>

          {/* Title */}
          {page.title && (
            <div className="text-sm text-warm-gray-600 truncate mb-2">
              {page.title}
            </div>
          )}

          {/* Keyword and metrics row */}
          {hasKeyword && (
            <div className="flex items-center gap-3 flex-wrap">
              {/* Primary keyword (clickable to edit) */}
              <button
                onClick={handleKeywordClick}
                className="inline-flex items-center gap-1 px-2.5 py-1 text-sm bg-lagoon-100 text-lagoon-700 rounded-sm font-medium hover:bg-lagoon-200 transition-colors"
                title="Click to select alternative keyword"
              >
                {page.keywords?.primary_keyword}
                <ChevronDownIcon className="w-3 h-3" />
              </button>

              {/* Search volume badge */}
              {page.keywords?.search_volume !== null && page.keywords?.search_volume !== undefined && (
                <span className="inline-flex items-center px-2 py-0.5 text-xs bg-cream-100 text-warm-gray-600 rounded-sm">
                  {formatNumber(page.keywords.search_volume)} vol
                </span>
              )}

              {/* Composite score */}
              {page.keywords?.composite_score !== null && page.keywords?.composite_score !== undefined && (
                <ScoreTooltip compositeScore={page.keywords.composite_score}>
                  <span className="inline-flex items-center px-2 py-0.5 text-xs bg-palm-100 text-palm-700 rounded-sm font-medium">
                    {page.keywords.composite_score.toFixed(1)} score
                  </span>
                </ScoreTooltip>
              )}
            </div>
          )}

          {/* No keyword state */}
          {!hasKeyword && (
            <span className="text-sm text-warm-gray-400 italic">
              No keyword generated
            </span>
          )}
        </div>

        {/* Approval status */}
        <div className="flex-shrink-0">
          {isApproved ? (
            <div
              className="flex items-center gap-1 px-2 py-1 bg-palm-100 text-palm-700 rounded-sm text-xs font-medium"
              title="Approved"
            >
              <CheckIcon className="w-4 h-4" />
              <span>Approved</span>
            </div>
          ) : hasKeyword ? (
            <button
              onClick={handleApprove}
              disabled={approveKeyword.isPending}
              className="flex items-center gap-1 px-2 py-1 bg-lagoon-100 text-lagoon-700 hover:bg-lagoon-200 rounded-sm text-xs font-medium transition-colors disabled:opacity-50"
            >
              {approveKeyword.isPending ? (
                <>
                  <SpinnerIcon className="w-4 h-4 animate-spin" />
                  <span>Approving...</span>
                </>
              ) : (
                <>
                  <CheckIcon className="w-4 h-4" />
                  <span>Approve</span>
                </>
              )}
            </button>
          ) : (
            <span className="text-xs text-warm-gray-400 px-2 py-1">
              Pending
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default KeywordPageRow;
