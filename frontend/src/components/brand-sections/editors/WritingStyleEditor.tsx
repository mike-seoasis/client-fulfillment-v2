'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { type WritingStyleData } from '../types';

interface WritingStyleEditorProps {
  /** The writing style data to edit */
  data: WritingStyleData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: WritingStyleData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

/**
 * Editor component for Writing Style section.
 * Provides grouped inputs for sentence structure, capitalization, punctuation, and formatting rules.
 */
export function WritingStyleEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: WritingStyleEditorProps) {
  // Sentence Structure state
  const [avgSentenceLength, setAvgSentenceLength] = useState(data?.sentence_structure?.average_sentence_length ?? '');
  const [paragraphLength, setParagraphLength] = useState(data?.sentence_structure?.paragraph_length ?? '');
  const [useContractions, setUseContractions] = useState(data?.sentence_structure?.use_contractions ?? '');
  const [activeVsPassive, setActiveVsPassive] = useState(data?.sentence_structure?.active_vs_passive ?? '');

  // Capitalization state
  const [headlines, setHeadlines] = useState(data?.capitalization?.headlines ?? '');
  const [productNames, setProductNames] = useState(data?.capitalization?.product_names ?? '');
  const [featureNames, setFeatureNames] = useState(data?.capitalization?.feature_names ?? '');

  // Punctuation state
  const [serialComma, setSerialComma] = useState(data?.punctuation?.serial_comma ?? '');
  const [emDashes, setEmDashes] = useState(data?.punctuation?.em_dashes ?? '');
  const [exclamationPoints, setExclamationPoints] = useState(data?.punctuation?.exclamation_points ?? '');
  const [ellipses, setEllipses] = useState(data?.punctuation?.ellipses ?? '');

  // Numbers & Formatting state
  const [spellOutRules, setSpellOutRules] = useState(data?.numbers_formatting?.spell_out_rules ?? '');
  const [currency, setCurrency] = useState(data?.numbers_formatting?.currency ?? '');
  const [percentages, setPercentages] = useState(data?.numbers_formatting?.percentages ?? '');
  const [boldUsage, setBoldUsage] = useState(data?.numbers_formatting?.bold_usage ?? '');
  const [bulletUsage, setBulletUsage] = useState(data?.numbers_formatting?.bullet_usage ?? '');

  const handleSave = useCallback(() => {
    // Build the save data, converting empty strings to undefined
    const cleanString = (s: string): string | undefined => s.trim() || undefined;

    const updatedData: WritingStyleData = {
      sentence_structure: {
        average_sentence_length: cleanString(avgSentenceLength),
        paragraph_length: cleanString(paragraphLength),
        use_contractions: cleanString(useContractions),
        active_vs_passive: cleanString(activeVsPassive),
      },
      capitalization: {
        headlines: cleanString(headlines),
        product_names: cleanString(productNames),
        feature_names: cleanString(featureNames),
      },
      punctuation: {
        serial_comma: cleanString(serialComma),
        em_dashes: cleanString(emDashes),
        exclamation_points: cleanString(exclamationPoints),
        ellipses: cleanString(ellipses),
      },
      numbers_formatting: {
        spell_out_rules: cleanString(spellOutRules),
        currency: cleanString(currency),
        percentages: cleanString(percentages),
        bold_usage: cleanString(boldUsage),
        bullet_usage: cleanString(bulletUsage),
      },
    };

    onSave(updatedData);
  }, [
    avgSentenceLength, paragraphLength, useContractions, activeVsPassive,
    headlines, productNames, featureNames,
    serialComma, emDashes, exclamationPoints, ellipses,
    spellOutRules, currency, percentages, boldUsage, bulletUsage,
    onSave,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
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
    },
    [handleSave, onCancel]
  );

  return (
    <div className="space-y-6" onKeyDown={handleKeyDown}>
      {/* Instructions */}
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Define the writing style rules for your brand. These rules guide how content should be formatted and structured.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Sentence Structure */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Sentence Structure
        </h3>
        <div className="space-y-4">
          <Input
            label="Average Sentence Length"
            value={avgSentenceLength}
            onChange={(e) => setAvgSentenceLength(e.target.value)}
            placeholder="e.g., Short to medium (10-20 words)"
            disabled={isSaving}
          />
          <Input
            label="Paragraph Length"
            value={paragraphLength}
            onChange={(e) => setParagraphLength(e.target.value)}
            placeholder="e.g., 2-3 sentences max, keep it scannable"
            disabled={isSaving}
          />
          <Input
            label="Contractions"
            value={useContractions}
            onChange={(e) => setUseContractions(e.target.value)}
            placeholder="e.g., Yes, always use contractions for a friendly tone"
            disabled={isSaving}
          />
          <Input
            label="Active vs Passive Voice"
            value={activeVsPassive}
            onChange={(e) => setActiveVsPassive(e.target.value)}
            placeholder="e.g., Active voice preferred, passive only when necessary"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Capitalization */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Capitalization
        </h3>
        <div className="space-y-4">
          <Input
            label="Headlines"
            value={headlines}
            onChange={(e) => setHeadlines(e.target.value)}
            placeholder="e.g., Sentence case for all headlines"
            disabled={isSaving}
          />
          <Input
            label="Product Names"
            value={productNames}
            onChange={(e) => setProductNames(e.target.value)}
            placeholder="e.g., Title Case for product names"
            disabled={isSaving}
          />
          <Input
            label="Feature Names"
            value={featureNames}
            onChange={(e) => setFeatureNames(e.target.value)}
            placeholder="e.g., lowercase unless a proper noun"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Punctuation */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Punctuation
        </h3>
        <div className="space-y-4">
          <Input
            label="Serial Comma"
            value={serialComma}
            onChange={(e) => setSerialComma(e.target.value)}
            placeholder="e.g., Always use the Oxford comma"
            disabled={isSaving}
          />
          <Textarea
            label="Em Dashes"
            value={emDashes}
            onChange={(e) => setEmDashes(e.target.value)}
            placeholder="e.g., Never use em dashes. Use commas, parentheses, or separate sentences instead."
            disabled={isSaving}
            className="min-h-[60px]"
          />
          <Input
            label="Exclamation Points"
            value={exclamationPoints}
            onChange={(e) => setExclamationPoints(e.target.value)}
            placeholder="e.g., Use sparingly, max one per paragraph"
            disabled={isSaving}
          />
          <Input
            label="Ellipses"
            value={ellipses}
            onChange={(e) => setEllipses(e.target.value)}
            placeholder="e.g., Avoid in formal copy, OK in casual social media"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Numbers & Formatting */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Numbers & Formatting
        </h3>
        <div className="space-y-4">
          <Input
            label="Spell Out Rules"
            value={spellOutRules}
            onChange={(e) => setSpellOutRules(e.target.value)}
            placeholder="e.g., Spell out one through nine, use numerals for 10+"
            disabled={isSaving}
          />
          <Input
            label="Currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            placeholder="e.g., $XX.XX format, always include cents"
            disabled={isSaving}
          />
          <Input
            label="Percentages"
            value={percentages}
            onChange={(e) => setPercentages(e.target.value)}
            placeholder="e.g., Use % symbol, no space (50%)"
            disabled={isSaving}
          />
          <Input
            label="Bold Usage"
            value={boldUsage}
            onChange={(e) => setBoldUsage(e.target.value)}
            placeholder="e.g., Use for key benefits and CTAs only"
            disabled={isSaving}
          />
          <Input
            label="Bullet Usage"
            value={bulletUsage}
            onChange={(e) => setBulletUsage(e.target.value)}
            placeholder="e.g., Prefer bullets for lists of 3+ items"
            disabled={isSaving}
          />
        </div>
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

export type { WritingStyleEditorProps };
