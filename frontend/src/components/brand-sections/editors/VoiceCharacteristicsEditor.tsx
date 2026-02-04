'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { BulletListEditor } from './BulletListEditor';
import { type VoiceCharacteristicsData, type VoiceTraitExample } from '../types';

interface VoiceCharacteristicsEditorProps {
  /** The voice characteristics data to edit */
  data: VoiceCharacteristicsData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: VoiceCharacteristicsData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

interface TraitCardEditorProps {
  trait: VoiceTraitExample;
  index: number;
  disabled?: boolean;
  onChange: (updatedTrait: VoiceTraitExample) => void;
  onRemove: () => void;
  canRemove: boolean;
}

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
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
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

function PlusIcon({ className }: { className?: string }) {
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
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
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
      <polyline points="3,6 5,6 21,6" />
      <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2" />
    </svg>
  );
}

/**
 * Card for editing a single voice trait with do/dont examples.
 */
function TraitCardEditor({
  trait,
  index,
  disabled,
  onChange,
  onRemove,
  canRemove,
}: TraitCardEditorProps) {
  const updateField = <K extends keyof VoiceTraitExample>(
    field: K,
    value: VoiceTraitExample[K]
  ) => {
    onChange({ ...trait, [field]: value });
  };

  return (
    <div className="bg-cream-50 border border-cream-300 rounded-sm overflow-hidden mb-4">
      {/* Header */}
      <div className="bg-palm-50 px-4 py-3 border-b border-cream-300">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-palm-600 font-semibold text-sm">{index + 1}.</span>
            <Input
              value={trait.trait_name}
              onChange={(e) => updateField('trait_name', e.target.value)}
              placeholder="Trait name (e.g., Warm, Confident)"
              disabled={disabled}
              className="font-semibold uppercase tracking-wide"
            />
          </div>
          {canRemove && (
            <button
              type="button"
              onClick={onRemove}
              disabled={disabled}
              className="p-2 text-coral-500 hover:text-coral-700 hover:bg-coral-50 rounded-sm transition-colors disabled:opacity-50"
              aria-label="Remove trait"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        <Textarea
          value={trait.description ?? ''}
          onChange={(e) => updateField('description', e.target.value || undefined)}
          placeholder="Brief description of this trait..."
          disabled={disabled}
          className="mt-2 min-h-[60px] text-sm"
        />
      </div>

      {/* Do/Dont Examples */}
      <div className="p-4 space-y-4">
        {/* DO Example */}
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-palm-100 flex items-center justify-center mt-2">
            <CheckIcon className="w-4 h-4 text-palm-600" />
          </div>
          <div className="flex-1">
            <label className="text-xs font-semibold text-palm-600 uppercase tracking-wider block mb-1">
              DO:
            </label>
            <Textarea
              value={trait.do_example ?? ''}
              onChange={(e) => updateField('do_example', e.target.value || undefined)}
              placeholder="Example of how to write with this trait..."
              disabled={disabled}
              className="min-h-[60px] text-sm"
            />
          </div>
        </div>

        {/* DONT Example */}
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 w-6 h-6 rounded-full bg-coral-100 flex items-center justify-center mt-2">
            <XIcon className="w-4 h-4 text-coral-600" />
          </div>
          <div className="flex-1">
            <label className="text-xs font-semibold text-coral-600 uppercase tracking-wider block mb-1">
              DO NOT:
            </label>
            <Textarea
              value={trait.dont_example ?? ''}
              onChange={(e) => updateField('dont_example', e.target.value || undefined)}
              placeholder="Example of what NOT to write..."
              disabled={disabled}
              className="min-h-[60px] text-sm"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Editor component for Voice Characteristics section.
 * Provides editing for "We Are" traits with do/dont examples and "We Are NOT" list.
 */
export function VoiceCharacteristicsEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: VoiceCharacteristicsEditorProps) {
  // Initialize form state from data
  const [weAre, setWeAre] = useState<VoiceTraitExample[]>(
    data?.we_are?.map((t) => ({ ...t })) ?? []
  );
  const [weAreNot, setWeAreNot] = useState<string[]>(
    // Handle both string and object formats defensively
    data?.we_are_not?.map((item) =>
      typeof item === 'string'
        ? item
        : (item as { trait_name?: string })?.trait_name || ''
    ) ?? []
  );

  const handleTraitChange = useCallback((index: number, updatedTrait: VoiceTraitExample) => {
    setWeAre((prev) => {
      const next = [...prev];
      next[index] = updatedTrait;
      return next;
    });
  }, []);

  const handleRemoveTrait = useCallback((index: number) => {
    setWeAre((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleAddTrait = useCallback(() => {
    setWeAre((prev) => [
      ...prev,
      {
        trait_name: '',
        description: undefined,
        do_example: undefined,
        dont_example: undefined,
      },
    ]);
  }, []);

  const handleSave = useCallback(() => {
    // Clean up data before saving
    const cleanedWeAre = weAre
      .filter((t) => t.trait_name.trim()) // Remove traits without names
      .map((t) => ({
        trait_name: t.trait_name.trim(),
        description: t.description?.trim() || undefined,
        do_example: t.do_example?.trim() || undefined,
        dont_example: t.dont_example?.trim() || undefined,
      }));

    const cleanedWeAreNot = weAreNot.filter((s) => s.trim()).map((s) => s.trim());

    const updatedData: VoiceCharacteristicsData = {
      we_are: cleanedWeAre.length > 0 ? cleanedWeAre : undefined,
      we_are_not: cleanedWeAreNot.length > 0 ? cleanedWeAreNot : undefined,
    };

    onSave(updatedData);
  }, [weAre, weAreNot, onSave]);

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
          Define your brand voice characteristics below. Each trait should have a name, description,
          and examples of what to do and what not to do.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* We Are Section */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-warm-gray-800 uppercase tracking-wide">
            We Are:
          </h3>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleAddTrait}
            disabled={isSaving}
            className="flex items-center gap-1"
          >
            <PlusIcon className="w-4 h-4" />
            Add Trait
          </Button>
        </div>

        {weAre.length === 0 ? (
          <div className="bg-cream-50 border border-cream-300 rounded-sm p-6 text-center">
            <p className="text-sm text-warm-gray-500 mb-3">No voice traits defined yet.</p>
            <Button variant="secondary" onClick={handleAddTrait} disabled={isSaving}>
              <PlusIcon className="w-4 h-4 mr-1" />
              Add Your First Trait
            </Button>
          </div>
        ) : (
          weAre.map((trait, index) => (
            <TraitCardEditor
              key={`trait-${index}`}
              trait={trait}
              index={index}
              disabled={isSaving}
              onChange={(updated) => handleTraitChange(index, updated)}
              onRemove={() => handleRemoveTrait(index)}
              canRemove={weAre.length > 1}
            />
          ))
        )}
      </section>

      {/* We Are NOT Section */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          We Are NOT:
        </h3>
        <BulletListEditor
          value={weAreNot}
          onChange={setWeAreNot}
          placeholder="Add what the brand voice is NOT (e.g., corporate, stuffy)..."
          addButtonText="Add item"
          disabled={isSaving}
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

export type { VoiceCharacteristicsEditorProps };
