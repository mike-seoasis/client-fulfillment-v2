'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { TagInput } from './TagInput';
import { useEditorKeyboardShortcuts } from './useEditorKeyboardShortcuts';
import { type AIPromptSnippetData } from '../types';

interface AIPromptEditorProps {
  /** The AI prompt snippet data to edit */
  data: AIPromptSnippetData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: AIPromptSnippetData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

interface ValidationErrors {
  snippet?: string;
}

/**
 * Editor component for AI Prompt Snippet section.
 * Provides a large textarea for the main snippet and additional metadata fields.
 */
export function AIPromptEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: AIPromptEditorProps) {
  // Main snippet state
  const [snippet, setSnippet] = useState(data?.snippet ?? '');

  // Voice metadata state
  const [voiceInThreeWords, setVoiceInThreeWords] = useState<string[]>(data?.voice_in_three_words ?? []);
  const [weSoundLike, setWeSoundLike] = useState(data?.we_sound_like ?? '');
  const [weNeverSoundLike, setWeNeverSoundLike] = useState(data?.we_never_sound_like ?? '');

  // Additional metadata
  const [neverUseWords, setNeverUseWords] = useState<string[]>(data?.never_use_words ?? []);

  const [errors, setErrors] = useState<ValidationErrors>({});

  const validate = useCallback((): boolean => {
    const newErrors: ValidationErrors = {};

    if (!snippet.trim()) {
      newErrors.snippet = 'AI prompt snippet is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [snippet]);

  const handleSave = useCallback(() => {
    if (!validate()) {
      return;
    }

    // Build the save data, converting empty strings/arrays to undefined
    const cleanString = (s: string): string | undefined => s.trim() || undefined;
    const cleanArray = (arr: string[]): string[] | undefined => arr.length > 0 ? arr : undefined;

    const updatedData: AIPromptSnippetData = {
      snippet: snippet.trim() || '',
      voice_in_three_words: cleanArray(voiceInThreeWords),
      we_sound_like: cleanString(weSoundLike),
      we_never_sound_like: cleanString(weNeverSoundLike),
      never_use_words: cleanArray(neverUseWords),
    };

    onSave(updatedData);
  }, [
    validate,
    snippet,
    voiceInThreeWords,
    weSoundLike,
    weNeverSoundLike,
    neverUseWords,
    onSave,
  ]);

  // Compute whether form has validation errors (for disabling save button)
  const hasValidationErrors = Object.keys(errors).length > 0;

  // Use document-level keyboard shortcuts for consistent behavior
  useEditorKeyboardShortcuts({
    onSave: handleSave,
    onCancel,
    disabled: isSaving,
  });

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Edit the AI prompt snippet that gets copied into AI writing tools. This snippet should capture your brand voice in a format AI tools can use.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Main Prompt Snippet */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          AI Prompt Snippet *
        </h3>
        <Textarea
          label="The complete prompt snippet"
          value={snippet}
          onChange={(e) => {
            setSnippet(e.target.value);
            if (e.target.value.trim() && errors.snippet) {
              setErrors((prev) => ({ ...prev, snippet: undefined }));
            }
          }}
          error={errors.snippet}
          placeholder="Write as [Brand Name]. Our voice is [description]... We always [guidelines]... Never [restrictions]..."
          disabled={isSaving}
          className="min-h-[200px] font-mono text-sm"
        />
        <p className="mt-2 text-xs text-warm-gray-500">
          This is the main snippet that gets copied and pasted into AI writing tools like ChatGPT or Claude.
        </p>
      </section>

      {/* Voice Description */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Voice Description
        </h3>
        <div className="space-y-4">
          <TagInput
            label="Voice in Three Words"
            value={voiceInThreeWords}
            onChange={setVoiceInThreeWords}
            placeholder="Add a word and press Enter..."
            disabled={isSaving}
          />
          <Input
            label="We Sound Like"
            value={weSoundLike}
            onChange={(e) => setWeSoundLike(e.target.value)}
            placeholder="e.g., A knowledgeable friend who genuinely wants to help"
            disabled={isSaving}
          />
          <Input
            label="We Never Sound Like"
            value={weNeverSoundLike}
            onChange={(e) => setWeNeverSoundLike(e.target.value)}
            placeholder="e.g., A pushy salesperson or corporate press release"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Words to Avoid */}
      <section className="bg-coral-50 border border-coral-200 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-coral-800 mb-4 uppercase tracking-wide">
          Words to Never Use
        </h3>
        <TagInput
          label="Never Use These Words"
          value={neverUseWords}
          onChange={setNeverUseWords}
          placeholder="Add a word or phrase and press Enter..."
          variant="danger"
          disabled={isSaving}
        />
        <p className="mt-2 text-xs text-coral-600">
          These words and phrases should be avoided in all brand communications.
        </p>
      </section>

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
        <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving || hasValidationErrors}>
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

export type { AIPromptEditorProps };
