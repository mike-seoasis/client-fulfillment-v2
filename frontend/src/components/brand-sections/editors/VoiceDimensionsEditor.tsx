'use client';

import { useState, useCallback } from 'react';
import { Button, Textarea } from '@/components/ui';
import { SliderInput } from './SliderInput';
import { type VoiceDimensionsData, type VoiceDimensionScale } from '../types';

interface VoiceDimensionsEditorProps {
  /** The voice dimensions data to edit */
  data: VoiceDimensionsData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: VoiceDimensionsData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

interface DimensionConfig {
  key: keyof Pick<VoiceDimensionsData, 'formality' | 'humor' | 'reverence' | 'enthusiasm'>;
  label: string;
  leftLabel: string;
  rightLabel: string;
}

const DIMENSION_CONFIGS: DimensionConfig[] = [
  { key: 'formality', label: 'Formality', leftLabel: 'Casual', rightLabel: 'Formal' },
  { key: 'humor', label: 'Humor', leftLabel: 'Funny', rightLabel: 'Serious' },
  { key: 'reverence', label: 'Reverence', leftLabel: 'Irreverent', rightLabel: 'Respectful' },
  { key: 'enthusiasm', label: 'Enthusiasm', leftLabel: 'Enthusiastic', rightLabel: 'Matter-of-Fact' },
];

/**
 * Editor component for Voice Dimensions section.
 * Provides slider-based editing for the four voice dimensions plus voice summary.
 */
export function VoiceDimensionsEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: VoiceDimensionsEditorProps) {
  // Helper to get initial scale value with defaults
  const getInitialScale = (scale?: VoiceDimensionScale): VoiceDimensionScale => ({
    position: typeof scale?.position === 'number' && !isNaN(scale.position) && scale.position >= 1 && scale.position <= 10
      ? scale.position
      : 5,
    description: scale?.description ?? '',
    example: scale?.example ?? '',
  });

  // Initialize form state from data
  const [formality, setFormality] = useState<VoiceDimensionScale>(getInitialScale(data?.formality));
  const [humor, setHumor] = useState<VoiceDimensionScale>(getInitialScale(data?.humor));
  const [reverence, setReverence] = useState<VoiceDimensionScale>(getInitialScale(data?.reverence));
  const [enthusiasm, setEnthusiasm] = useState<VoiceDimensionScale>(getInitialScale(data?.enthusiasm));
  const [voiceSummary, setVoiceSummary] = useState(data?.voice_summary ?? '');

  // Map dimension key to state
  const dimensionState: Record<string, { value: VoiceDimensionScale; setValue: (v: VoiceDimensionScale) => void }> = {
    formality: { value: formality, setValue: setFormality },
    humor: { value: humor, setValue: setHumor },
    reverence: { value: reverence, setValue: setReverence },
    enthusiasm: { value: enthusiasm, setValue: setEnthusiasm },
  };

  const handleSave = useCallback(() => {
    // Build the save data, converting empty strings to undefined
    const cleanScale = (scale: VoiceDimensionScale): VoiceDimensionScale => ({
      position: scale.position,
      description: scale.description?.trim() || undefined,
      example: scale.example?.trim() || undefined,
    });

    const updatedData: VoiceDimensionsData = {
      formality: cleanScale(formality),
      humor: cleanScale(humor),
      reverence: cleanScale(reverence),
      enthusiasm: cleanScale(enthusiasm),
      voice_summary: voiceSummary.trim() || undefined,
    };

    onSave(updatedData);
  }, [formality, humor, reverence, enthusiasm, voiceSummary, onSave]);

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
          Adjust your brand voice dimensions using the sliders below. Add descriptions and examples to clarify each position.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Voice Dimensions */}
      {DIMENSION_CONFIGS.map((config) => {
        const { value, setValue } = dimensionState[config.key];

        return (
          <section key={config.key} className="bg-cream-50 border border-cream-300 rounded-sm p-4">
            {/* Slider */}
            <SliderInput
              label={config.label}
              leftLabel={config.leftLabel}
              rightLabel={config.rightLabel}
              value={value.position}
              onChange={(position) => setValue({ ...value, position })}
              disabled={isSaving}
            />

            {/* Description & Example */}
            <div className="mt-4 space-y-3">
              <Textarea
                label="Description"
                value={value.description ?? ''}
                onChange={(e) => setValue({ ...value, description: e.target.value })}
                placeholder={`Describe what ${config.label.toLowerCase()} means for your brand...`}
                disabled={isSaving}
                className="min-h-[60px]"
              />
              <Textarea
                label="Example"
                value={value.example ?? ''}
                onChange={(e) => setValue({ ...value, example: e.target.value })}
                placeholder={`An example of your brand at this ${config.label.toLowerCase()} level...`}
                disabled={isSaving}
                className="min-h-[60px]"
              />
            </div>
          </section>
        );
      })}

      {/* Voice Summary */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Voice Summary
        </h3>
        <Textarea
          value={voiceSummary}
          onChange={(e) => setVoiceSummary(e.target.value)}
          placeholder="A brief summary of your overall brand voice..."
          disabled={isSaving}
          className="min-h-[100px]"
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

export type { VoiceDimensionsEditorProps };
