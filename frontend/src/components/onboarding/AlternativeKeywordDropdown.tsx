'use client';

import { useState, useRef, useEffect } from 'react';
import type { KeywordCandidate } from '@/lib/api';
import { useUpdatePrimaryKeyword } from '@/hooks/useKeywordMutations';

interface AlternativeKeywordDropdownProps {
  /** Current primary keyword */
  primaryKeyword: string;
  /** List of alternative keywords (up to 4) */
  alternatives: KeywordCandidate[];
  /** Current primary keyword's search volume (null if custom) */
  primaryVolume: number | null;
  /** Project ID for API calls */
  projectId: string;
  /** Page ID for API calls */
  pageId: string;
  /** Whether the dropdown is open */
  isOpen: boolean;
  /** Callback when dropdown should close */
  onClose: () => void;
  /** Anchor element position (from getBoundingClientRect) */
  anchorRect?: DOMRect | null;
  /** Callback to show toast notification */
  onShowToast?: (message: string, variant: 'success' | 'error') => void;
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
 * Format a number with commas as thousands separators.
 */
function formatNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '—';
  return num.toLocaleString();
}

/**
 * AlternativeKeywordDropdown displays the current primary keyword and
 * alternatives in a dropdown. Selecting an alternative updates the primary
 * keyword via API.
 */
export function AlternativeKeywordDropdown({
  primaryKeyword,
  alternatives,
  primaryVolume,
  projectId,
  pageId,
  isOpen,
  onClose,
  anchorRect,
  onShowToast,
}: AlternativeKeywordDropdownProps) {
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

  const updatePrimaryKeyword = useUpdatePrimaryKeyword();

  // Close on click outside
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        onClose();
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    // Delay adding listener to avoid immediate close from the click that opened it
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }, 0);

    return () => {
      clearTimeout(timeoutId);
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  // Handle keyword selection
  const handleSelect = async (keyword: string) => {
    // Don't select if already primary or currently updating
    if (keyword.toLowerCase() === primaryKeyword.toLowerCase() || updatePrimaryKeyword.isPending) {
      return;
    }

    setSelectedKeyword(keyword);

    try {
      await updatePrimaryKeyword.mutateAsync({
        projectId,
        pageId,
        keyword,
      });
      onShowToast?.('Keyword updated', 'success');
      onClose();
    } catch (error) {
      console.error('Failed to update primary keyword:', error);
      const message = error instanceof Error ? error.message : 'Failed to update keyword';
      onShowToast?.(message, 'error');
    } finally {
      setSelectedKeyword(null);
    }
  };

  if (!isOpen || !anchorRect) {
    return null;
  }

  // Position dropdown below the anchor, accounting for viewport bounds
  const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 800;
  const dropdownHeight = 250; // Estimated max height
  const spaceBelow = viewportHeight - anchorRect.bottom;
  const showAbove = spaceBelow < dropdownHeight && anchorRect.top > dropdownHeight;

  const positionStyle = showAbove
    ? {
        bottom: viewportHeight - anchorRect.top + 4,
        left: anchorRect.left,
      }
    : {
        top: anchorRect.bottom + 4,
        left: anchorRect.left,
      };

  // Limit alternatives to 4 as per spec
  const displayAlternatives = alternatives.slice(0, 4);

  return (
    <div
      ref={dropdownRef}
      className="fixed z-50 bg-white border border-cream-500 rounded-sm shadow-lg min-w-[280px] max-w-[400px]"
      style={positionStyle}
      role="listbox"
      aria-label="Select keyword"
    >
      {/* Current primary keyword (selected) */}
      <div
        className="flex items-center justify-between px-3 py-2.5 bg-palm-50 border-b border-cream-500 cursor-default"
        role="option"
        aria-selected="true"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <CheckIcon className="w-4 h-4 text-palm-600 flex-shrink-0" />
            <span className="text-sm font-medium text-palm-700 truncate">
              {primaryKeyword}
            </span>
          </div>
        </div>
        {primaryVolume !== null && (
          <span className="text-xs text-palm-600 ml-3 flex-shrink-0">
            {formatNumber(primaryVolume)} vol
          </span>
        )}
      </div>

      {/* Alternatives list */}
      {displayAlternatives.length > 0 ? (
        <div className="py-1">
          {displayAlternatives.map((alt) => {
            const isLoading = selectedKeyword === alt.keyword && updatePrimaryKeyword.isPending;
            const isSelected = alt.keyword.toLowerCase() === primaryKeyword.toLowerCase();

            return (
              <button
                key={alt.keyword}
                onClick={() => handleSelect(alt.keyword)}
                disabled={isSelected || updatePrimaryKeyword.isPending}
                className={`w-full flex items-center justify-between px-3 py-2 text-left transition-colors ${
                  isSelected
                    ? 'bg-cream-100 cursor-not-allowed'
                    : 'hover:bg-sand-50 cursor-pointer'
                } ${updatePrimaryKeyword.isPending && !isLoading ? 'opacity-50' : ''}`}
                role="option"
                aria-selected={isSelected}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    {isLoading ? (
                      <SpinnerIcon className="w-4 h-4 text-lagoon-500 animate-spin flex-shrink-0" />
                    ) : (
                      <div className="w-4 h-4 flex-shrink-0" /> // Spacer for alignment
                    )}
                    <span className="text-sm text-warm-gray-700 truncate">
                      {alt.keyword}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                  {alt.volume !== null && (
                    <span className="text-xs text-warm-gray-500">
                      {formatNumber(alt.volume)} vol
                    </span>
                  )}
                  {alt.composite_score !== null && (
                    <span className="text-xs text-palm-600 bg-palm-50 px-1.5 py-0.5 rounded-sm">
                      {alt.composite_score.toFixed(1)}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="px-3 py-4 text-center text-sm text-warm-gray-500">
          No alternatives available
        </div>
      )}
    </div>
  );
}

export default AlternativeKeywordDropdown;
