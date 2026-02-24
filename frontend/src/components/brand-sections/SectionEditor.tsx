'use client';

import { useState, useCallback, useEffect } from 'react';
import { Button, Textarea } from '@/components/ui';

interface SectionEditorProps {
  /** The section data to edit */
  sectionData: Record<string, unknown> | undefined;
  /** Whether the save operation is in progress */
  isSaving: boolean;
  /** Called when the user saves their changes */
  onSave: (data: Record<string, unknown>) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

/**
 * Editor component for brand config sections.
 * Displays section data as formatted JSON for editing.
 */
export function SectionEditor({
  sectionData,
  isSaving,
  onSave,
  onCancel,
}: SectionEditorProps) {
  // Initialize with formatted JSON
  const [jsonValue, setJsonValue] = useState(() =>
    JSON.stringify(sectionData ?? {}, null, 2)
  );
  const [error, setError] = useState<string | undefined>();

  // Update textarea when section data changes externally
  useEffect(() => {
    setJsonValue(JSON.stringify(sectionData ?? {}, null, 2));
  }, [sectionData]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setJsonValue(e.target.value);
    // Clear error when user starts typing
    if (error) {
      setError(undefined);
    }
  }, [error]);

  const handleSave = useCallback(() => {
    try {
      const parsed = JSON.parse(jsonValue);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setError('Section data must be a JSON object');
        return;
      }
      onSave(parsed);
    } catch {
      setError('Invalid JSON format');
    }
  }, [jsonValue, onSave]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    // Save on Cmd/Ctrl + S
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
    // Cancel on Escape
    if (e.key === 'Escape') {
      e.preventDefault();
      onCancel();
    }
  }, [handleSave, onCancel]);

  return (
    <div className="space-y-4">
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Edit the section data below. Changes will be saved to your brand configuration.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      <Textarea
        value={jsonValue}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        error={error}
        className="font-mono text-sm min-h-[400px]"
        disabled={isSaving}
        autoFocus
      />

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-2">
        <Button
          variant="secondary"
          onClick={onCancel}
          disabled={isSaving}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={isSaving}
        >
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
