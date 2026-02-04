'use client';

import { useState, useCallback } from 'react';
import { Button } from '@/components/ui';
import { BulletListEditor } from './BulletListEditor';
import { EditableTable, type ColumnSchema } from './EditableTable';
import { type CompetitorContextData, type CompetitorEntry } from '../types';

interface CompetitorContextEditorProps {
  /** The competitor context data to edit */
  data: CompetitorContextData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: CompetitorContextData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

// Column schema for direct competitors table
const competitorColumns: ColumnSchema[] = [
  { key: 'name', header: 'Competitor', placeholder: 'Competitor name...', width: 'w-1/4', required: true },
  { key: 'positioning', header: 'Their Position', placeholder: 'How they position themselves...', width: 'w-1/3' },
  { key: 'our_difference', header: 'Our Difference', placeholder: 'How we differentiate...', width: 'w-5/12' },
];

// Column schema for positioning statements table
const positioningColumns: ColumnSchema[] = [
  { key: 'context', header: 'Context', placeholder: 'e.g., vs Premium Brands', width: 'w-1/4' },
  { key: 'statement', header: 'Statement', placeholder: 'Our positioning statement...', width: 'w-3/4', required: true },
];

/**
 * Editor component for Competitor Context section.
 * Provides editable table for competitors, bullet lists for advantages/weaknesses,
 * and editable table for positioning statements.
 */
export function CompetitorContextEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: CompetitorContextEditorProps) {
  // Direct competitors state (convert to table format)
  const [competitors, setCompetitors] = useState<Record<string, string>[]>(
    (data?.direct_competitors ?? []).map((c) => ({
      name: c.name,
      positioning: c.positioning ?? '',
      our_difference: c.our_difference ?? '',
    }))
  );

  // Competitive advantages and weaknesses state
  const [advantages, setAdvantages] = useState<string[]>(data?.competitive_advantages ?? []);
  const [weaknesses, setWeaknesses] = useState<string[]>(data?.competitive_weaknesses ?? []);

  // Positioning statements state (convert to table format)
  const [positioningStatements, setPositioningStatements] = useState<Record<string, string>[]>(
    (data?.positioning_statements ?? []).map((p) => ({
      context: p.context ?? '',
      statement: p.statement,
    }))
  );

  // Rules state
  const [rules, setRules] = useState<string[]>(data?.rules ?? []);

  const handleSave = useCallback(() => {
    // Convert competitors table data back to typed array, filtering empty rows
    const cleanedCompetitors: CompetitorEntry[] = competitors
      .filter((row) => row.name?.trim())
      .map((row) => ({
        name: row.name?.trim() || '',
        positioning: row.positioning?.trim() || undefined,
        our_difference: row.our_difference?.trim() || undefined,
      }));

    // Convert positioning statements table data back to typed array, filtering empty rows
    const cleanedPositioning = positioningStatements
      .filter((row) => row.statement?.trim())
      .map((row) => ({
        context: row.context?.trim() || undefined,
        statement: row.statement?.trim() || '',
      }));

    const updatedData: CompetitorContextData = {
      direct_competitors: cleanedCompetitors.length > 0 ? cleanedCompetitors : undefined,
      competitive_advantages: advantages.length > 0 ? advantages : undefined,
      competitive_weaknesses: weaknesses.length > 0 ? weaknesses : undefined,
      positioning_statements: cleanedPositioning.length > 0 ? cleanedPositioning : undefined,
      rules: rules.length > 0 ? rules : undefined,
    };

    onSave(updatedData);
  }, [competitors, advantages, weaknesses, positioningStatements, rules, onSave]);

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
          Define your competitive landscape and how you position against competitors.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Direct Competitors */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Direct Competitors
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Your main competitors and how you differentiate from each.
        </p>
        <EditableTable
          value={competitors}
          onChange={setCompetitors}
          columns={competitorColumns}
          addButtonText="Add competitor"
          disabled={isSaving}
        />
      </section>

      {/* Competitive Advantages */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Our Competitive Advantages
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Key strengths that set you apart from the competition.
        </p>
        <BulletListEditor
          value={advantages}
          onChange={setAdvantages}
          placeholder="Add a competitive advantage..."
          addButtonText="Add advantage"
          disabled={isSaving}
        />
      </section>

      {/* Competitive Weaknesses */}
      <section className="bg-coral-50 border border-coral-200 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-coral-800 mb-3 uppercase tracking-wide">
          Competitive Weaknesses
        </h3>
        <p className="text-xs text-coral-600 mb-3">
          Areas where competitors may have advantages over you (internal awareness).
        </p>
        <BulletListEditor
          value={weaknesses}
          onChange={setWeaknesses}
          placeholder="Add a competitive weakness..."
          addButtonText="Add weakness"
          disabled={isSaving}
        />
      </section>

      {/* Positioning Statements */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Positioning Statements
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Context-specific statements about how you position against different competitor types.
        </p>
        <EditableTable
          value={positioningStatements}
          onChange={setPositioningStatements}
          columns={positioningColumns}
          addButtonText="Add statement"
          disabled={isSaving}
        />
      </section>

      {/* Rules */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Competitor Messaging Rules
        </h3>
        <p className="text-xs text-warm-gray-500 mb-3">
          Guidelines for how to reference or respond to competitors in messaging.
        </p>
        <BulletListEditor
          value={rules}
          onChange={setRules}
          placeholder="Add a messaging rule..."
          addButtonText="Add rule"
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

export type { CompetitorContextEditorProps };
