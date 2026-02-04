'use client';

import { useState, useRef, useEffect, useCallback } from 'react';

// Minimum and maximum labels allowed per page
export const MIN_LABELS = 2;
export const MAX_LABELS = 5;

interface TaxonomyLabel {
  name: string;
  description: string;
  examples: string[];
}

interface LabelEditDropdownProps {
  /** All available taxonomy labels */
  taxonomyLabels: TaxonomyLabel[];
  /** Currently selected labels for the page */
  selectedLabels: string[];
  /** Callback when labels selection changes */
  onLabelsChange: (labels: string[]) => void;
  /** Callback to close the dropdown */
  onClose: () => void;
  /** Whether save is in progress */
  isSaving?: boolean;
  /** Callback to save labels */
  onSave: (labels: string[]) => Promise<void>;
}

/**
 * Validate label selection count
 * Returns error message if invalid, null if valid
 */
export function validateLabelCount(count: number): string | null {
  if (count < MIN_LABELS) {
    return `Select at least ${MIN_LABELS} labels`;
  }
  if (count > MAX_LABELS) {
    return `Select at most ${MAX_LABELS} labels`;
  }
  return null;
}

function CheckboxIcon({ checked }: { checked: boolean }) {
  if (checked) {
    return (
      <svg
        className="w-4 h-4 text-palm-600"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
      </svg>
    );
  }
  return (
    <svg
      className="w-4 h-4 text-warm-gray-400"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
    </svg>
  );
}

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
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

export function LabelEditDropdown({
  taxonomyLabels,
  selectedLabels,
  onLabelsChange,
  onClose,
  isSaving = false,
  onSave,
}: LabelEditDropdownProps) {
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [localSelection, setLocalSelection] = useState<Set<string>>(
    new Set(selectedLabels)
  );

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        onClose();
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  // Close dropdown on Escape key
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]);

  const handleToggleLabel = useCallback((labelName: string) => {
    setLocalSelection((prev) => {
      const newSelection = new Set(prev);
      if (newSelection.has(labelName)) {
        newSelection.delete(labelName);
      } else {
        newSelection.add(labelName);
      }
      return newSelection;
    });
  }, []);

  const handleSave = useCallback(async () => {
    const labelsArray = Array.from(localSelection);
    onLabelsChange(labelsArray);
    await onSave(labelsArray);
  }, [localSelection, onLabelsChange, onSave]);

  const validationError = validateLabelCount(localSelection.size);
  const hasChanges = (() => {
    if (localSelection.size !== selectedLabels.length) return true;
    return !selectedLabels.every((label) => localSelection.has(label));
  })();

  return (
    <div
      ref={dropdownRef}
      className="absolute z-50 mt-1 bg-white rounded-sm border border-cream-300 shadow-lg min-w-[280px] max-w-[320px]"
      role="dialog"
      aria-label="Edit labels"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-cream-200">
        <span className="text-sm font-medium text-warm-gray-900">
          Edit Labels
        </span>
        <button
          onClick={onClose}
          className="p-1 text-warm-gray-400 hover:text-warm-gray-600 rounded-sm"
          aria-label="Close"
        >
          <CloseIcon className="w-4 h-4" />
        </button>
      </div>

      {/* Selection count indicator */}
      <div className="px-3 py-2 bg-cream-50 border-b border-cream-200">
        <span className={`text-xs ${validationError ? 'text-coral-600' : 'text-warm-gray-600'}`}>
          {localSelection.size} of {MIN_LABELS}-{MAX_LABELS} labels selected
          {validationError && ` • ${validationError}`}
        </span>
      </div>

      {/* Checkbox list */}
      <div className="max-h-64 overflow-y-auto py-1">
        {taxonomyLabels.map((label) => {
          const isChecked = localSelection.has(label.name);
          return (
            <button
              key={label.name}
              type="button"
              onClick={() => handleToggleLabel(label.name)}
              className={`w-full flex items-start gap-2 px-3 py-2 text-left hover:bg-cream-50 transition-colors ${
                isChecked ? 'bg-palm-50' : ''
              }`}
              role="checkbox"
              aria-checked={isChecked}
            >
              <div className="flex-shrink-0 mt-0.5">
                <CheckboxIcon checked={isChecked} />
              </div>
              <div className="flex-1 min-w-0">
                <span className={`text-sm ${isChecked ? 'text-palm-700 font-medium' : 'text-warm-gray-900'}`}>
                  {label.name}
                </span>
                {label.description && (
                  <p className="text-xs text-warm-gray-500 mt-0.5 line-clamp-2">
                    {label.description}
                  </p>
                )}
              </div>
            </button>
          );
        })}
      </div>

      {/* Footer with save button */}
      <div className="flex items-center justify-end gap-2 px-3 py-2 border-t border-cream-200 bg-cream-50">
        <button
          onClick={onClose}
          className="px-3 py-1.5 text-sm text-warm-gray-600 hover:text-warm-gray-900"
          disabled={isSaving}
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={!!validationError || !hasChanges || isSaving}
          className="px-3 py-1.5 text-sm font-medium text-white bg-palm-500 hover:bg-palm-600 rounded-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  );
}

export default LabelEditDropdown;
