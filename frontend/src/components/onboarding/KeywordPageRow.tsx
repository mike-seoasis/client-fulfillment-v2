'use client';

import { useState, useRef, useEffect } from 'react';
import type { PageWithKeywords } from '@/lib/api';
import { useApproveKeyword, useTogglePriority, useUpdatePrimaryKeyword } from '@/hooks/useKeywordMutations';
import { AlternativeKeywordDropdown } from './AlternativeKeywordDropdown';
import { PriorityToggle } from './PriorityToggle';
import { ApproveButton } from './ApproveButton';

interface KeywordPageRowProps {
  /** Page with keyword data */
  page: PageWithKeywords;
  /** Project ID for API calls */
  projectId: string;
  /** Callback when keyword is clicked (for opening edit dropdown) - optional, if not provided uses built-in dropdown */
  onKeywordClick?: (pageId: string) => void;
}

// SVG Icons
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

function PencilIcon({ className }: { className?: string }) {
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
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
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
  const updatePrimaryKeyword = useUpdatePrimaryKeyword();

  // State for built-in dropdown
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [keywordButtonRect, setKeywordButtonRect] = useState<DOMRect | null>(null);
  const keywordButtonRef = useRef<HTMLButtonElement>(null);

  // State for inline editing
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const hasKeyword = !!page.keywords?.primary_keyword;
  const isApproved = page.keywords?.is_approved ?? false;
  const isPriority = page.keywords?.is_priority ?? false;
  const displayUrl = extractPath(page.url);

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

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
    if (!hasKeyword) return;

    // If a custom handler is provided, use that
    if (onKeywordClick) {
      onKeywordClick(page.id);
      return;
    }

    // Otherwise, use built-in dropdown
    if (keywordButtonRef.current) {
      setKeywordButtonRect(keywordButtonRef.current.getBoundingClientRect());
      setIsDropdownOpen(true);
    }
  };

  const handleDropdownClose = () => {
    setIsDropdownOpen(false);
    setKeywordButtonRect(null);
  };

  // Start inline editing mode
  const handleStartEdit = () => {
    if (!hasKeyword || isEditing) return;
    setEditValue(page.keywords?.primary_keyword || '');
    setIsEditing(true);
    // Close dropdown if open
    setIsDropdownOpen(false);
  };

  // Handle double-click on keyword button to enable editing
  const handleKeywordDoubleClick = () => {
    handleStartEdit();
  };

  // Save the edited keyword
  const handleSaveEdit = async () => {
    const trimmedValue = editValue.trim();

    // Don't save if empty or same as current
    if (!trimmedValue || trimmedValue.toLowerCase() === page.keywords?.primary_keyword?.toLowerCase()) {
      setIsEditing(false);
      return;
    }

    try {
      await updatePrimaryKeyword.mutateAsync({
        projectId,
        pageId: page.id,
        keyword: trimmedValue,
      });
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update keyword:', error);
      // Keep editing mode open on error so user can retry
    }
  };

  // Cancel editing
  const handleCancelEdit = () => {
    setIsEditing(false);
    setEditValue('');
  };

  // Handle keydown in edit input
  const handleEditKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  };

  // Handle blur - save on blur
  const handleEditBlur = () => {
    // Only save if not already saving (prevents double-save)
    if (!updatePrimaryKeyword.isPending) {
      handleSaveEdit();
    }
  };

  return (
    <div className="py-3 px-4 border-b border-cream-500 last:border-b-0 hover:bg-sand-50 transition-colors">
      <div className="flex items-start gap-3">
        {/* Priority toggle */}
        <div className="flex-shrink-0 mt-0.5">
          <PriorityToggle
            isPriority={isPriority}
            disabled={!hasKeyword}
            isLoading={togglePriority.isPending}
            onToggle={handleTogglePriority}
          />
        </div>

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
              {/* Inline edit input or keyword button */}
              {isEditing ? (
                <div className="inline-flex items-center gap-2">
                  <input
                    ref={inputRef}
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={handleEditKeyDown}
                    onBlur={handleEditBlur}
                    disabled={updatePrimaryKeyword.isPending}
                    className="px-2.5 py-1 text-sm border border-lagoon-300 rounded-sm bg-white focus:outline-none focus:ring-2 focus:ring-palm-400 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed min-w-[200px]"
                    placeholder="Enter keyword..."
                    aria-label="Edit primary keyword"
                  />
                  {updatePrimaryKeyword.isPending && (
                    <SpinnerIcon className="w-4 h-4 text-lagoon-500 animate-spin flex-shrink-0" />
                  )}
                </div>
              ) : (
                <>
                  {/* Primary keyword (clickable to open dropdown, double-click to edit) */}
                  <button
                    ref={keywordButtonRef}
                    onClick={handleKeywordClick}
                    onDoubleClick={handleKeywordDoubleClick}
                    className="inline-flex items-center gap-1 px-2.5 py-1 text-sm bg-lagoon-100 text-lagoon-700 rounded-sm font-medium hover:bg-lagoon-200 transition-colors"
                    title="Click for alternatives, double-click to edit"
                    aria-haspopup="listbox"
                    aria-expanded={isDropdownOpen}
                  >
                    {page.keywords?.primary_keyword}
                    <ChevronDownIcon className="w-3 h-3" />
                  </button>

                  {/* Edit button */}
                  <button
                    onClick={handleStartEdit}
                    className="inline-flex items-center gap-1 px-2 py-1 text-xs text-warm-gray-500 hover:text-warm-gray-700 hover:bg-cream-100 rounded-sm transition-colors"
                    title="Edit keyword"
                    aria-label="Edit keyword"
                  >
                    <PencilIcon className="w-3.5 h-3.5" />
                    <span>Edit</span>
                  </button>
                </>
              )}

              {/* Alternative keyword dropdown */}
              {page.keywords && !onKeywordClick && !isEditing && (
                <AlternativeKeywordDropdown
                  primaryKeyword={page.keywords.primary_keyword}
                  alternatives={page.keywords.alternative_keywords || []}
                  primaryVolume={page.keywords.search_volume}
                  projectId={projectId}
                  pageId={page.id}
                  isOpen={isDropdownOpen}
                  onClose={handleDropdownClose}
                  anchorRect={keywordButtonRect}
                />
              )}

              {/* Search volume badge - show dash for custom keywords without volume */}
              <span className="inline-flex items-center px-2 py-0.5 text-xs bg-cream-100 text-warm-gray-600 rounded-sm">
                {formatNumber(page.keywords?.search_volume)} vol
              </span>

              {/* Composite score - show dash for custom keywords without score */}
              <ScoreTooltip compositeScore={page.keywords?.composite_score ?? null}>
                <span className="inline-flex items-center px-2 py-0.5 text-xs bg-palm-100 text-palm-700 rounded-sm font-medium">
                  {page.keywords?.composite_score !== null && page.keywords?.composite_score !== undefined
                    ? `${page.keywords.composite_score.toFixed(1)} score`
                    : '— score'}
                </span>
              </ScoreTooltip>
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
          <ApproveButton
            isApproved={isApproved}
            isLoading={approveKeyword.isPending}
            disabled={!hasKeyword}
            onApprove={handleApprove}
          />
        </div>
      </div>
    </div>
  );
}

export default KeywordPageRow;
