'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui';
import { TagInput } from './TagInput';
import { EditableTable, type ColumnSchema } from './EditableTable';
import { BulletListEditor } from './BulletListEditor';
import { useEditorKeyboardShortcuts } from './useEditorKeyboardShortcuts';
import { type VocabularyData, type WordSubstitution, type IndustryTerm } from '../types';

interface VocabularyEditorProps {
  /** The vocabulary data to edit */
  data: VocabularyData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: VocabularyData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

// Column schema for word substitutions table
const substitutionColumns: ColumnSchema[] = [
  { key: 'instead_of', header: 'Instead of...', placeholder: 'Word to avoid', width: 'w-1/2' },
  { key: 'we_say', header: 'We say...', placeholder: 'Preferred word', width: 'w-1/2' },
];

// Column schema for industry terms table
const industryTermColumns: ColumnSchema[] = [
  { key: 'term', header: 'Term', placeholder: 'Industry term', width: 'w-1/3' },
  { key: 'usage', header: 'Usage', placeholder: 'How to use this term correctly', width: 'w-2/3' },
];

/**
 * Editor component for Vocabulary section.
 * Provides tag inputs for power/banned words, tables for substitutions and terms,
 * and bullet list for signature phrases.
 */
export function VocabularyEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: VocabularyEditorProps) {
  // Defensive helper to ensure array
  const toArray = <T,>(val: T[] | undefined | null): T[] => (Array.isArray(val) ? val : []);

  // State for each field
  const [powerWords, setPowerWords] = useState<string[]>(toArray(data?.power_words));
  const [bannedWords, setBannedWords] = useState<string[]>(toArray(data?.banned_words));
  const [competitors, setCompetitors] = useState<string[]>(toArray(data?.competitors));
  const [wordSubstitutions, setWordSubstitutions] = useState<Record<string, string>[]>(
    toArray(data?.word_substitutions).map((sub) => ({
      instead_of: sub.instead_of,
      we_say: sub.we_say,
    }))
  );
  const [industryTerms, setIndustryTerms] = useState<Record<string, string>[]>(
    toArray(data?.industry_terms).map((term) => ({
      term: term.term,
      usage: term.usage,
    }))
  );
  const [signaturePhrases, setSignaturePhrases] = useState<string[]>(toArray(data?.signature_phrases));
  const [shopifyPlaceholderTag, setShopifyPlaceholderTag] = useState<string>(data?.shopify_placeholder_tag ?? '');

  const handleSave = useCallback(() => {
    // Convert table data back to typed arrays, filtering out empty rows
    const cleanedSubstitutions: WordSubstitution[] = wordSubstitutions
      .filter((row) => row.instead_of?.trim() || row.we_say?.trim())
      .map((row) => ({
        instead_of: row.instead_of?.trim() || '',
        we_say: row.we_say?.trim() || '',
      }));

    const cleanedTerms: IndustryTerm[] = industryTerms
      .filter((row) => row.term?.trim() || row.usage?.trim())
      .map((row) => ({
        term: row.term?.trim() || '',
        usage: row.usage?.trim() || '',
      }));

    const updatedData: VocabularyData = {
      power_words: powerWords.length > 0 ? powerWords : undefined,
      banned_words: bannedWords.length > 0 ? bannedWords : undefined,
      competitors: competitors.length > 0 ? competitors : undefined,
      word_substitutions: cleanedSubstitutions.length > 0 ? cleanedSubstitutions : undefined,
      industry_terms: cleanedTerms.length > 0 ? cleanedTerms : undefined,
      signature_phrases: signaturePhrases.length > 0 ? signaturePhrases : undefined,
      shopify_placeholder_tag: shopifyPlaceholderTag.trim() || undefined,
    };

    onSave(updatedData);
  }, [powerWords, bannedWords, competitors, wordSubstitutions, industryTerms, signaturePhrases, shopifyPlaceholderTag, onSave]);

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
          Build your brand vocabulary guide. Define words to use, words to avoid, and preferred terminology.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Power Words */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Power Words (Use These)
        </h3>
        <TagInput
          value={powerWords}
          onChange={setPowerWords}
          variant="success"
          placeholder="Type a power word and press Enter..."
          disabled={isSaving}
        />
      </section>

      {/* Banned Words */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Banned Words (Never Use)
        </h3>
        <TagInput
          value={bannedWords}
          onChange={setBannedWords}
          variant="danger"
          placeholder="Type a banned word and press Enter..."
          disabled={isSaving}
        />
      </section>

      {/* Competitor Brands */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Competitor Brands (Never Mention)
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Competitor names are auto-populated from brand research and POP analysis. Add or remove as needed.
        </p>
        <TagInput
          value={competitors}
          onChange={setCompetitors}
          variant="danger"
          placeholder="Type a competitor name and press Enter..."
          disabled={isSaving}
        />
      </section>

      {/* Word Substitutions */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Word Substitutions
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Define words to avoid and their preferred alternatives.
        </p>
        <EditableTable
          value={wordSubstitutions}
          onChange={setWordSubstitutions}
          columns={substitutionColumns}
          addButtonText="Add substitution"
          disabled={isSaving}
        />
      </section>

      {/* Industry Terms */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Industry Terms (Use Correctly)
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Define industry-specific terms and how to use them properly.
        </p>
        <EditableTable
          value={industryTerms}
          onChange={setIndustryTerms}
          columns={industryTermColumns}
          addButtonText="Add term"
          disabled={isSaving}
        />
      </section>

      {/* Signature Phrases */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Signature Phrases
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Memorable phrases and taglines unique to your brand.
        </p>
        <BulletListEditor
          value={signaturePhrases}
          onChange={setSignaturePhrases}
          placeholder="Add a signature phrase..."
          addButtonText="Add phrase"
          disabled={isSaving}
        />
      </section>

      {/* Shopify Placeholder Tag */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Shopify Placeholder Tag
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          A product tag from the Shopify store used as the Rule: Condition in Matrixify exports. This is a placeholder — real collection rules are configured in Shopify.
        </p>
        <input
          type="text"
          value={shopifyPlaceholderTag}
          onChange={(e) => setShopifyPlaceholderTag(e.target.value)}
          placeholder="e.g. running-shoes"
          disabled={isSaving}
          className="w-full px-3 py-2 text-sm border border-cream-300 rounded-sm bg-white text-warm-gray-800 placeholder:text-warm-gray-400 focus:outline-none focus:ring-2 focus:ring-palm-400 focus:border-palm-400 disabled:opacity-50"
        />
      </section>

      {/* Action buttons */}
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

export type { VocabularyEditorProps };
