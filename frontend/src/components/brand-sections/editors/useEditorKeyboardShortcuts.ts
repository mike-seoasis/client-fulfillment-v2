'use client';

import { useEffect, useCallback } from 'react';

interface UseEditorKeyboardShortcutsOptions {
  /** Called when the user presses Cmd/Ctrl+S */
  onSave: () => void;
  /** Called when the user presses Escape (when not in a conflicting context) */
  onCancel: () => void;
  /** Whether keyboard shortcuts are disabled (e.g., during save) */
  disabled?: boolean;
}

/**
 * Custom hook for consistent keyboard shortcut handling across section editors.
 *
 * Handles:
 * - Cmd/Ctrl+S: Triggers save (prevents browser save dialog)
 * - Escape: Triggers cancel (only when not in an input that handles escape itself)
 *
 * Uses document-level event listener to ensure shortcuts work regardless of focus.
 * This ensures shortcuts work even when focus is on elements that might not
 * properly bubble keyboard events.
 */
export function useEditorKeyboardShortcuts({
  onSave,
  onCancel,
  disabled = false,
}: UseEditorKeyboardShortcutsOptions) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (disabled) return;

      // Save on Cmd/Ctrl + S
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        onSave();
        return;
      }

      // Cancel on Escape
      // Only trigger if we're not in an element that has its own Escape handling
      // (e.g., EditableTable cells, select dropdowns, modals)
      if (e.key === 'Escape') {
        // Check if we're in an input/textarea that might be in "edit mode"
        // and wants to handle Escape itself first
        const activeElement = document.activeElement;
        const tagName = activeElement?.tagName.toLowerCase();

        // If in an input or textarea, check if it's part of a component
        // that handles Escape (like EditableTable inline editing)
        if (tagName === 'input' || tagName === 'textarea') {
          // Check if this input is within an editable table cell
          // EditableTable adds a specific class for inline editing inputs
          const isInEditableCell = activeElement?.closest('[data-editable-cell]');

          if (isInEditableCell) {
            // Let the EditableTable handle Escape first
            // The editor cancel will be triggered on the second Escape
            return;
          }
        }

        // For all other cases, trigger cancel
        e.preventDefault();
        onCancel();
      }
    },
    [disabled, onSave, onCancel]
  );

  useEffect(() => {
    // Attach to document to ensure shortcuts work regardless of focus
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);
}

export type { UseEditorKeyboardShortcutsOptions };
