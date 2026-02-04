'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { TagInput } from './TagInput';
import { type TargetAudienceData, type PersonaData } from '../types';

interface TargetAudienceEditorProps {
  /** The target audience data to edit */
  data: TargetAudienceData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: TargetAudienceData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

/**
 * Creates a new empty persona with default structure.
 */
function createEmptyPersona(): PersonaData {
  return {
    name: '',
    percentage: '',
    demographics: {
      age_range: '',
      gender: '',
      location: '',
      income_level: '',
      profession: '',
      education: '',
    },
    psychographics: {
      values: [],
      aspirations: [],
      fears: [],
      frustrations: [],
      identity: '',
    },
    behavioral: {
      discovery_channels: [],
      research_behavior: '',
      decision_factors: [],
      buying_triggers: [],
      objections: [],
    },
    communication: {
      tone_preference: '',
      language_style: '',
      content_consumed: [],
      trust_signals: [],
    },
    summary: '',
  };
}

interface PersonaEditorCardProps {
  persona: PersonaData;
  index: number;
  isPrimary: boolean;
  disabled: boolean;
  canDelete: boolean;
  onChange: (index: number, persona: PersonaData) => void;
  onDelete: (index: number) => void;
}

/**
 * Individual persona editor card with all editable fields.
 */
function PersonaEditorCard({
  persona,
  index,
  isPrimary,
  disabled,
  canDelete,
  onChange,
  onDelete,
}: PersonaEditorCardProps) {
  // Helper to update persona fields
  const updatePersona = useCallback(
    (updates: Partial<PersonaData>) => {
      onChange(index, { ...persona, ...updates });
    },
    [index, persona, onChange]
  );

  // Helper to update nested demographics
  const updateDemographics = useCallback(
    (field: keyof NonNullable<PersonaData['demographics']>, value: string) => {
      onChange(index, {
        ...persona,
        demographics: { ...persona.demographics, [field]: value },
      });
    },
    [index, persona, onChange]
  );

  // Helper to update nested psychographics
  const updatePsychographics = useCallback(
    (field: keyof NonNullable<PersonaData['psychographics']>, value: string | string[]) => {
      onChange(index, {
        ...persona,
        psychographics: { ...persona.psychographics, [field]: value },
      });
    },
    [index, persona, onChange]
  );

  // Helper to update nested behavioral
  const updateBehavioral = useCallback(
    (field: keyof NonNullable<PersonaData['behavioral']>, value: string | string[]) => {
      onChange(index, {
        ...persona,
        behavioral: { ...persona.behavioral, [field]: value },
      });
    },
    [index, persona, onChange]
  );

  // Helper to update nested communication
  const updateCommunication = useCallback(
    (field: keyof NonNullable<PersonaData['communication']>, value: string | string[]) => {
      onChange(index, {
        ...persona,
        communication: { ...persona.communication, [field]: value },
      });
    },
    [index, persona, onChange]
  );

  return (
    <div className="bg-cream-50 border border-cream-300 rounded-sm overflow-hidden">
      {/* Persona Header */}
      <div className={`px-4 py-3 border-b border-cream-300 ${isPrimary ? 'bg-palm-50' : 'bg-cream-100'}`}>
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1 flex items-center gap-3">
            <Input
              value={persona.name}
              onChange={(e) => updatePersona({ name: e.target.value })}
              placeholder="Persona name (e.g., 'The Wellness Seeker')"
              disabled={disabled}
              className="font-semibold"
            />
            <Input
              value={persona.percentage ?? ''}
              onChange={(e) => updatePersona({ percentage: e.target.value })}
              placeholder="%"
              disabled={disabled}
              className="w-20 text-center"
            />
          </div>
          <div className="flex items-center gap-2">
            {isPrimary && (
              <span className="text-xs text-palm-600 font-medium bg-palm-100 px-2 py-1 rounded-sm">
                Primary
              </span>
            )}
            {canDelete && (
              <button
                type="button"
                onClick={() => onDelete(index)}
                disabled={disabled}
                className="p-1.5 text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50 rounded-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Delete persona"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Persona Content */}
      <div className="p-4 space-y-6">
        {/* Demographics Section */}
        <section>
          <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3">
            Demographics
          </h5>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Age Range"
              value={persona.demographics?.age_range ?? ''}
              onChange={(e) => updateDemographics('age_range', e.target.value)}
              placeholder="e.g., 25-45"
              disabled={disabled}
            />
            <Input
              label="Gender"
              value={persona.demographics?.gender ?? ''}
              onChange={(e) => updateDemographics('gender', e.target.value)}
              placeholder="e.g., Predominantly female"
              disabled={disabled}
            />
            <Input
              label="Location"
              value={persona.demographics?.location ?? ''}
              onChange={(e) => updateDemographics('location', e.target.value)}
              placeholder="e.g., Urban/suburban US"
              disabled={disabled}
            />
            <Input
              label="Income Level"
              value={persona.demographics?.income_level ?? ''}
              onChange={(e) => updateDemographics('income_level', e.target.value)}
              placeholder="e.g., $75k-150k"
              disabled={disabled}
            />
            <Input
              label="Profession"
              value={persona.demographics?.profession ?? ''}
              onChange={(e) => updateDemographics('profession', e.target.value)}
              placeholder="e.g., Professional/Manager"
              disabled={disabled}
            />
            <Input
              label="Education"
              value={persona.demographics?.education ?? ''}
              onChange={(e) => updateDemographics('education', e.target.value)}
              placeholder="e.g., College educated"
              disabled={disabled}
            />
          </div>
        </section>

        {/* Psychographics Section */}
        <section>
          <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3">
            Psychographics
          </h5>
          <div className="space-y-4">
            <TagInput
              label="Values"
              value={persona.psychographics?.values ?? []}
              onChange={(values) => updatePsychographics('values', values)}
              placeholder="Add a value..."
              disabled={disabled}
            />
            <TagInput
              label="Aspirations"
              value={persona.psychographics?.aspirations ?? []}
              onChange={(aspirations) => updatePsychographics('aspirations', aspirations)}
              placeholder="Add an aspiration..."
              disabled={disabled}
            />
            <TagInput
              label="Fears"
              value={persona.psychographics?.fears ?? []}
              onChange={(fears) => updatePsychographics('fears', fears)}
              placeholder="Add a fear..."
              variant="danger"
              disabled={disabled}
            />
            <TagInput
              label="Frustrations"
              value={persona.psychographics?.frustrations ?? []}
              onChange={(frustrations) => updatePsychographics('frustrations', frustrations)}
              placeholder="Add a frustration..."
              variant="danger"
              disabled={disabled}
            />
            <Textarea
              label="Identity"
              value={persona.psychographics?.identity ?? ''}
              onChange={(e) => updatePsychographics('identity', e.target.value)}
              placeholder="How they see themselves..."
              disabled={disabled}
              className="min-h-[60px]"
            />
          </div>
        </section>

        {/* Behavioral Section */}
        <section>
          <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3">
            Behavior
          </h5>
          <div className="space-y-4">
            <TagInput
              label="Discovery Channels"
              value={persona.behavioral?.discovery_channels ?? []}
              onChange={(channels) => updateBehavioral('discovery_channels', channels)}
              placeholder="Add a channel..."
              disabled={disabled}
            />
            <Textarea
              label="Research Behavior"
              value={persona.behavioral?.research_behavior ?? ''}
              onChange={(e) => updateBehavioral('research_behavior', e.target.value)}
              placeholder="How they research before buying..."
              disabled={disabled}
              className="min-h-[60px]"
            />
            <TagInput
              label="Decision Factors"
              value={persona.behavioral?.decision_factors ?? []}
              onChange={(factors) => updateBehavioral('decision_factors', factors)}
              placeholder="Add a decision factor..."
              disabled={disabled}
            />
            <TagInput
              label="Buying Triggers"
              value={persona.behavioral?.buying_triggers ?? []}
              onChange={(triggers) => updateBehavioral('buying_triggers', triggers)}
              placeholder="Add a trigger..."
              variant="success"
              disabled={disabled}
            />
            <TagInput
              label="Objections"
              value={persona.behavioral?.objections ?? []}
              onChange={(objections) => updateBehavioral('objections', objections)}
              placeholder="Add an objection..."
              variant="danger"
              disabled={disabled}
            />
          </div>
        </section>

        {/* Communication Section */}
        <section>
          <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-3">
            Communication Preferences
          </h5>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Input
                label="Tone Preference"
                value={persona.communication?.tone_preference ?? ''}
                onChange={(e) => updateCommunication('tone_preference', e.target.value)}
                placeholder="e.g., Warm and reassuring"
                disabled={disabled}
              />
              <Input
                label="Language Style"
                value={persona.communication?.language_style ?? ''}
                onChange={(e) => updateCommunication('language_style', e.target.value)}
                placeholder="e.g., Conversational, no jargon"
                disabled={disabled}
              />
            </div>
            <TagInput
              label="Content They Consume"
              value={persona.communication?.content_consumed ?? []}
              onChange={(content) => updateCommunication('content_consumed', content)}
              placeholder="Add content type..."
              disabled={disabled}
            />
            <TagInput
              label="Trust Signals"
              value={persona.communication?.trust_signals ?? []}
              onChange={(signals) => updateCommunication('trust_signals', signals)}
              placeholder="Add trust signal..."
              variant="success"
              disabled={disabled}
            />
          </div>
        </section>

        {/* Summary */}
        <section>
          <Textarea
            label="Persona Summary"
            value={persona.summary ?? ''}
            onChange={(e) => updatePersona({ summary: e.target.value })}
            placeholder="A brief summary of this persona..."
            disabled={disabled}
            className="min-h-[80px]"
          />
        </section>
      </div>
    </div>
  );
}

/**
 * Editor component for Target Audience section.
 * Provides form-based editing for audience overview and persona cards.
 */
export function TargetAudienceEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: TargetAudienceEditorProps) {
  // Initialize personas state - ensure at least one persona
  const [personas, setPersonas] = useState<PersonaData[]>(() => {
    if (data?.personas && data.personas.length > 0) {
      return data.personas;
    }
    return [createEmptyPersona()];
  });

  // Initialize audience overview state
  const [primaryPersona, setPrimaryPersona] = useState(data?.audience_overview?.primary_persona ?? '');
  const [secondaryPersona, setSecondaryPersona] = useState(data?.audience_overview?.secondary_persona ?? '');
  const [tertiaryPersona, setTertiaryPersona] = useState(data?.audience_overview?.tertiary_persona ?? '');

  const handlePersonaChange = useCallback((index: number, updatedPersona: PersonaData) => {
    setPersonas((prev) => {
      const newPersonas = [...prev];
      newPersonas[index] = updatedPersona;
      return newPersonas;
    });
  }, []);

  const handleAddPersona = useCallback(() => {
    setPersonas((prev) => [...prev, createEmptyPersona()]);
  }, []);

  const handleDeletePersona = useCallback((index: number) => {
    setPersonas((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSave = useCallback(() => {
    // Clean up personas - remove empty ones and trim values
    const cleanedPersonas = personas
      .filter((p) => p.name.trim() !== '') // Only keep personas with names
      .map((p) => ({
        ...p,
        name: p.name.trim(),
        percentage: p.percentage?.trim() || undefined,
        demographics: p.demographics ? {
          age_range: p.demographics.age_range?.trim() || undefined,
          gender: p.demographics.gender?.trim() || undefined,
          location: p.demographics.location?.trim() || undefined,
          income_level: p.demographics.income_level?.trim() || undefined,
          profession: p.demographics.profession?.trim() || undefined,
          education: p.demographics.education?.trim() || undefined,
        } : undefined,
        psychographics: p.psychographics ? {
          values: p.psychographics.values?.length ? p.psychographics.values : undefined,
          aspirations: p.psychographics.aspirations?.length ? p.psychographics.aspirations : undefined,
          fears: p.psychographics.fears?.length ? p.psychographics.fears : undefined,
          frustrations: p.psychographics.frustrations?.length ? p.psychographics.frustrations : undefined,
          identity: p.psychographics.identity?.trim() || undefined,
        } : undefined,
        behavioral: p.behavioral ? {
          discovery_channels: p.behavioral.discovery_channels?.length ? p.behavioral.discovery_channels : undefined,
          research_behavior: p.behavioral.research_behavior?.trim() || undefined,
          decision_factors: p.behavioral.decision_factors?.length ? p.behavioral.decision_factors : undefined,
          buying_triggers: p.behavioral.buying_triggers?.length ? p.behavioral.buying_triggers : undefined,
          objections: p.behavioral.objections?.length ? p.behavioral.objections : undefined,
        } : undefined,
        communication: p.communication ? {
          tone_preference: p.communication.tone_preference?.trim() || undefined,
          language_style: p.communication.language_style?.trim() || undefined,
          content_consumed: p.communication.content_consumed?.length ? p.communication.content_consumed : undefined,
          trust_signals: p.communication.trust_signals?.length ? p.communication.trust_signals : undefined,
        } : undefined,
        summary: p.summary?.trim() || undefined,
      }));

    const updatedData: TargetAudienceData = {
      personas: cleanedPersonas.length > 0 ? cleanedPersonas : undefined,
      audience_overview: {
        primary_persona: primaryPersona.trim() || undefined,
        secondary_persona: secondaryPersona.trim() || undefined,
        tertiary_persona: tertiaryPersona.trim() || undefined,
      },
    };

    onSave(updatedData);
  }, [personas, primaryPersona, secondaryPersona, tertiaryPersona, onSave]);

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
          Edit your target audience personas below. Add details about demographics, psychographics, and communication preferences.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Audience Overview */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Audience Overview
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <Input
            label="Primary Persona"
            value={primaryPersona}
            onChange={(e) => setPrimaryPersona(e.target.value)}
            placeholder="e.g., The Wellness Seeker"
            disabled={isSaving}
          />
          <Input
            label="Secondary Persona"
            value={secondaryPersona}
            onChange={(e) => setSecondaryPersona(e.target.value)}
            placeholder="e.g., The Gift Giver"
            disabled={isSaving}
          />
          <Input
            label="Tertiary Persona"
            value={tertiaryPersona}
            onChange={(e) => setTertiaryPersona(e.target.value)}
            placeholder="e.g., The Impulse Buyer"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Persona Cards */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-warm-gray-800 uppercase tracking-wide">
            Customer Personas
          </h3>
          <Button
            variant="secondary"
            onClick={handleAddPersona}
            disabled={isSaving}
            className="text-sm"
          >
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Persona
          </Button>
        </div>

        <div className="space-y-4">
          {personas.map((persona, index) => (
            <PersonaEditorCard
              key={index}
              persona={persona}
              index={index}
              isPrimary={index === 0}
              disabled={isSaving}
              canDelete={personas.length > 1}
              onChange={handlePersonaChange}
              onDelete={handleDeletePersona}
            />
          ))}
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

export type { TargetAudienceEditorProps };
