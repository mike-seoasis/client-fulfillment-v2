'use client';

import { useState, useCallback } from 'react';
import { Button, Input } from '@/components/ui';
import { useEditorKeyboardShortcuts } from './useEditorKeyboardShortcuts';
import { type ContentLimitsData } from '../types';

export interface ContentLimitsEditorProps {
  data: ContentLimitsData | undefined;
  isSaving?: boolean;
  onSave: (data: ContentLimitsData) => void;
  onCancel: () => void;
}

export function ContentLimitsEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: ContentLimitsEditorProps) {
  const [collectionMaxWords, setCollectionMaxWords] = useState<string>(
    (data?.collection_max_words ?? data?.max_word_count ?? '').toString().replace('null', '')
  );
  const [blogMaxWords, setBlogMaxWords] = useState<string>(
    (data?.blog_max_words ?? '').toString().replace('null', '')
  );

  const handleSave = useCallback(() => {
    const collectionVal = collectionMaxWords.trim() ? parseInt(collectionMaxWords, 10) : null;
    const blogVal = blogMaxWords.trim() ? parseInt(blogMaxWords, 10) : null;

    const updatedData: ContentLimitsData = {
      collection_max_words: collectionVal && collectionVal > 0 ? collectionVal : null,
      blog_max_words: blogVal && blogVal > 0 ? blogVal : null,
    };

    onSave(updatedData);
  }, [collectionMaxWords, blogMaxWords, onSave]);

  useEditorKeyboardShortcuts({
    onSave: handleSave,
    onCancel,
    disabled: isSaving,
  });

  return (
    <div className="space-y-6">
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Set per-project word count limits for generated content. Leave empty to use the global default.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">&#8984;S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <Input
            label="Collection Page Max Words"
            type="number"
            min={0}
            value={collectionMaxWords}
            onChange={(e) => setCollectionMaxWords(e.target.value)}
            placeholder="No limit (global default)"
            disabled={isSaving}
          />
          <p className="text-xs text-warm-gray-500 mt-1">
            Max word count for bottom_description on collection pages
          </p>
        </div>
        <div>
          <Input
            label="Blog Post Max Words"
            type="number"
            min={0}
            value={blogMaxWords}
            onChange={(e) => setBlogMaxWords(e.target.value)}
            placeholder="No limit (global default)"
            disabled={isSaving}
          />
          <p className="text-xs text-warm-gray-500 mt-1">
            Max word count for blog post content field
          </p>
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
        <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
