'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { TagInput } from './TagInput';
import { BulletListEditor } from './BulletListEditor';
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

// Helper to ensure arrays
const toArray = <T,>(val: T[] | undefined | null): T[] => (Array.isArray(val) ? val : []);

/**
 * Editor component for AI Prompt section.
 * Provides comprehensive editing for the full prompt and all supporting metadata.
 */
export function AIPromptEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: AIPromptEditorProps) {
  // Manual override - when filled in, used instead of full_prompt during content generation
  const [promptOverride, setPromptOverride] = useState(data?.prompt_override || '');

  // Main prompt - support both new and legacy field names
  const [fullPrompt, setFullPrompt] = useState(data?.full_prompt || data?.snippet || '');

  // Quick reference
  const [voiceInThreeWords, setVoiceInThreeWords] = useState<string[]>(
    toArray(data?.quick_reference?.voice_in_three_words || data?.voice_in_three_words)
  );
  const [weSoundLike, setWeSoundLike] = useState(
    data?.quick_reference?.we_sound_like || data?.we_sound_like || ''
  );
  const [weNeverSoundLike, setWeNeverSoundLike] = useState(
    data?.quick_reference?.we_never_sound_like || data?.we_never_sound_like || ''
  );
  const [elevatorPitch, setElevatorPitch] = useState(data?.quick_reference?.elevator_pitch || '');

  // Audience profile
  const [primaryPersona, setPrimaryPersona] = useState(data?.audience_profile?.primary_persona || '');
  const [demographics, setDemographics] = useState(data?.audience_profile?.demographics || '');
  const [psychographics, setPsychographics] = useState(data?.audience_profile?.psychographics || '');
  const [howTheyTalk, setHowTheyTalk] = useState(data?.audience_profile?.how_they_talk || '');
  const [whatTheyCareAbout, setWhatTheyCareAbout] = useState<string[]>(
    toArray(data?.audience_profile?.what_they_care_about)
  );

  // Voice guidelines
  const [personalityTraits, setPersonalityTraits] = useState<string[]>(
    toArray(data?.voice_guidelines?.personality_traits)
  );
  const [formalToCasual, setFormalToCasual] = useState(
    data?.voice_guidelines?.tone_spectrum?.formal_to_casual || ''
  );
  const [seriousToPlayful, setSeriousToPlayful] = useState(
    data?.voice_guidelines?.tone_spectrum?.serious_to_playful || ''
  );
  const [reservedToEnthusiastic, setReservedToEnthusiastic] = useState(
    data?.voice_guidelines?.tone_spectrum?.reserved_to_enthusiastic || ''
  );
  const [sentenceStyle, setSentenceStyle] = useState(data?.voice_guidelines?.sentence_style || '');
  const [vocabularyLevel, setVocabularyLevel] = useState(data?.voice_guidelines?.vocabulary_level || '');

  // Writing rules
  const [alwaysDo, setAlwaysDo] = useState<string[]>(
    toArray(data?.writing_rules?.always_do || data?.always_include)
  );
  const [neverDo, setNeverDo] = useState<string[]>(toArray(data?.writing_rules?.never_do));
  const [bannedWords, setBannedWords] = useState<string[]>(
    toArray(data?.writing_rules?.banned_words || data?.never_use_words)
  );

  // Content patterns
  const [headlineFormula, setHeadlineFormula] = useState(data?.content_patterns?.headline_formula || '');
  const [ctaStyle, setCtaStyle] = useState(data?.content_patterns?.cta_style || '');
  const [proofPoints, setProofPoints] = useState<string[]>(
    toArray(data?.content_patterns?.proof_points_to_include)
  );
  const [emotionalTriggers, setEmotionalTriggers] = useState<string[]>(
    toArray(data?.content_patterns?.emotional_triggers)
  );

  // Brand specifics
  const [keyMessages, setKeyMessages] = useState<string[]>(
    toArray(data?.brand_specifics?.key_messages)
  );
  const [uniqueValueProps, setUniqueValueProps] = useState<string[]>(
    toArray(data?.brand_specifics?.unique_value_props || data?.key_differentiators)
  );
  const [competitiveAngles, setCompetitiveAngles] = useState<string[]>(
    toArray(data?.brand_specifics?.competitive_angles)
  );
  const [trustSignals, setTrustSignals] = useState<string[]>(
    toArray(data?.brand_specifics?.trust_signals_to_mention)
  );

  const [errors, setErrors] = useState<{ fullPrompt?: string }>({});

  const validate = useCallback((): boolean => {
    const newErrors: { fullPrompt?: string } = {};
    if (!fullPrompt.trim()) {
      newErrors.fullPrompt = 'Full AI prompt is required';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [fullPrompt]);

  const handleSave = useCallback(() => {
    if (!validate()) return;

    // Helper to convert empty strings/arrays to undefined
    const cleanStr = (s: string): string | undefined => s.trim() || undefined;
    const cleanArr = <T,>(arr: T[]): T[] | undefined => (arr.length > 0 ? arr : undefined);

    const updatedData: AIPromptSnippetData = {
      full_prompt: fullPrompt.trim(),
      prompt_override: promptOverride.trim() || undefined,
      quick_reference: {
        voice_in_three_words: cleanArr(voiceInThreeWords),
        we_sound_like: cleanStr(weSoundLike),
        we_never_sound_like: cleanStr(weNeverSoundLike),
        elevator_pitch: cleanStr(elevatorPitch),
      },
      audience_profile: {
        primary_persona: cleanStr(primaryPersona),
        demographics: cleanStr(demographics),
        psychographics: cleanStr(psychographics),
        how_they_talk: cleanStr(howTheyTalk),
        what_they_care_about: cleanArr(whatTheyCareAbout),
      },
      voice_guidelines: {
        personality_traits: cleanArr(personalityTraits),
        tone_spectrum: {
          formal_to_casual: cleanStr(formalToCasual),
          serious_to_playful: cleanStr(seriousToPlayful),
          reserved_to_enthusiastic: cleanStr(reservedToEnthusiastic),
        },
        sentence_style: cleanStr(sentenceStyle),
        vocabulary_level: cleanStr(vocabularyLevel),
      },
      writing_rules: {
        always_do: cleanArr(alwaysDo),
        never_do: cleanArr(neverDo),
        banned_words: cleanArr(bannedWords),
      },
      content_patterns: {
        headline_formula: cleanStr(headlineFormula),
        cta_style: cleanStr(ctaStyle),
        proof_points_to_include: cleanArr(proofPoints),
        emotional_triggers: cleanArr(emotionalTriggers),
      },
      brand_specifics: {
        key_messages: cleanArr(keyMessages),
        unique_value_props: cleanArr(uniqueValueProps),
        competitive_angles: cleanArr(competitiveAngles),
        trust_signals_to_mention: cleanArr(trustSignals),
      },
    };

    onSave(updatedData);
  }, [
    validate, fullPrompt, promptOverride,
    voiceInThreeWords, weSoundLike, weNeverSoundLike, elevatorPitch,
    primaryPersona, demographics, psychographics, howTheyTalk, whatTheyCareAbout,
    personalityTraits, formalToCasual, seriousToPlayful, reservedToEnthusiastic, sentenceStyle, vocabularyLevel,
    alwaysDo, neverDo, bannedWords,
    headlineFormula, ctaStyle, proofPoints, emotionalTriggers,
    keyMessages, uniqueValueProps, competitiveAngles, trustSignals,
    onSave,
  ]);

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
          Edit the comprehensive AI prompt that powers all content generation. The full prompt is the most important field.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Manual Override */}
      <section className="bg-lagoon-50 border border-lagoon-200 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-lagoon-800 mb-1 uppercase tracking-wide">
          Prompt Override
        </h3>
        <p className="text-xs text-lagoon-600 mb-3">
          When filled in, this text is injected as the brand prompt instead of the generated Full AI Prompt below.
          Leave empty to use the auto-generated prompt.
        </p>
        <Textarea
          value={promptOverride}
          onChange={(e) => setPromptOverride(e.target.value)}
          placeholder="Paste or write a custom brand prompt to override the generated one..."
          disabled={isSaving}
          className="min-h-[160px] font-mono text-sm"
        />
        {promptOverride.trim() && (
          <p className="mt-2 text-xs text-lagoon-700 font-medium">
            Override is active. The Full AI Prompt below will not be used for content generation.
          </p>
        )}
      </section>

      {/* Main Prompt */}
      <section className={`border rounded-sm p-4 ${promptOverride.trim() ? 'bg-warm-gray-800 border-warm-gray-600 opacity-60' : 'bg-warm-gray-900 border-warm-gray-700'}`}>
        <h3 className="text-sm font-semibold text-warm-gray-100 mb-3 uppercase tracking-wide">
          Full AI Prompt {promptOverride.trim() ? '(overridden)' : '*'}
        </h3>
        <Textarea
          value={fullPrompt}
          onChange={(e) => {
            setFullPrompt(e.target.value);
            if (e.target.value.trim() && errors.fullPrompt) {
              setErrors({});
            }
          }}
          placeholder="Write comprehensive brand guidelines (400-600 words)..."
          disabled={isSaving}
          className="min-h-[300px] font-mono text-sm bg-warm-gray-800 text-warm-gray-100 border-warm-gray-600 placeholder:text-warm-gray-500"
        />
        {errors.fullPrompt && (
          <p className="mt-1 text-xs text-coral-400">{errors.fullPrompt}</p>
        )}
        <p className="mt-2 text-xs text-warm-gray-400">
          This is the main prompt that gets copied into AI writing tools. Make it comprehensive (400-600 words).
        </p>
      </section>

      {/* Quick Reference */}
      <section className="bg-palm-50 border border-palm-200 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-palm-800 mb-4 uppercase tracking-wide">
          Quick Reference
        </h3>
        <div className="space-y-4">
          <TagInput
            label="Voice in Three Words"
            value={voiceInThreeWords}
            onChange={setVoiceInThreeWords}
            placeholder="Add a word..."
            variant="success"
            disabled={isSaving}
          />
          <Textarea
            label="Elevator Pitch"
            value={elevatorPitch}
            onChange={(e) => setElevatorPitch(e.target.value)}
            placeholder="2-3 sentences: what the brand does, for whom, and why it matters"
            disabled={isSaving}
            className="min-h-[80px]"
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
        </div>
      </section>

      {/* Audience Profile */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Audience Profile
        </h3>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Primary Persona"
              value={primaryPersona}
              onChange={(e) => setPrimaryPersona(e.target.value)}
              placeholder="Name and 1-sentence description"
              disabled={isSaving}
            />
            <Input
              label="Demographics"
              value={demographics}
              onChange={(e) => setDemographics(e.target.value)}
              placeholder="Age, income, location, lifestyle"
              disabled={isSaving}
            />
          </div>
          <Textarea
            label="Psychographics"
            value={psychographics}
            onChange={(e) => setPsychographics(e.target.value)}
            placeholder="Values, motivations, pain points, aspirations"
            disabled={isSaving}
            className="min-h-[60px]"
          />
          <Input
            label="How They Talk"
            value={howTheyTalk}
            onChange={(e) => setHowTheyTalk(e.target.value)}
            placeholder="Communication style, vocabulary level, references they'd understand"
            disabled={isSaving}
          />
          <TagInput
            label="What They Care About"
            value={whatTheyCareAbout}
            onChange={setWhatTheyCareAbout}
            placeholder="Add something they value..."
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Voice Guidelines */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Voice Guidelines
        </h3>
        <div className="space-y-4">
          <TagInput
            label="Personality Traits"
            value={personalityTraits}
            onChange={setPersonalityTraits}
            placeholder="Add a trait..."
            variant="success"
            disabled={isSaving}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              label="Formal ↔ Casual"
              value={formalToCasual}
              onChange={(e) => setFormalToCasual(e.target.value)}
              placeholder="e.g., 70% casual, 30% professional"
              disabled={isSaving}
            />
            <Input
              label="Serious ↔ Playful"
              value={seriousToPlayful}
              onChange={(e) => setSeriousToPlayful(e.target.value)}
              placeholder="e.g., Mostly serious with light humor"
              disabled={isSaving}
            />
            <Input
              label="Reserved ↔ Enthusiastic"
              value={reservedToEnthusiastic}
              onChange={(e) => setReservedToEnthusiastic(e.target.value)}
              placeholder="e.g., Confident but not over-the-top"
              disabled={isSaving}
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Sentence Style"
              value={sentenceStyle}
              onChange={(e) => setSentenceStyle(e.target.value)}
              placeholder="Length, structure, rhythm"
              disabled={isSaving}
            />
            <Input
              label="Vocabulary Level"
              value={vocabularyLevel}
              onChange={(e) => setVocabularyLevel(e.target.value)}
              placeholder="e.g., Accessible, 8th grade reading level"
              disabled={isSaving}
            />
          </div>
        </div>
      </section>

      {/* Writing Rules */}
      <section className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-palm-50 border border-palm-200 rounded-sm p-4">
            <h3 className="text-sm font-semibold text-palm-800 mb-3 uppercase tracking-wide">
              Always Do
            </h3>
            <BulletListEditor
              value={alwaysDo}
              onChange={setAlwaysDo}
              placeholder="Add a rule..."
              addButtonText="Add rule"
              disabled={isSaving}
            />
          </div>
          <div className="bg-coral-50 border border-coral-200 rounded-sm p-4">
            <h3 className="text-sm font-semibold text-coral-800 mb-3 uppercase tracking-wide">
              Never Do
            </h3>
            <BulletListEditor
              value={neverDo}
              onChange={setNeverDo}
              placeholder="Add a rule..."
              addButtonText="Add rule"
              disabled={isSaving}
            />
          </div>
        </div>
        <div className="bg-coral-50 border border-coral-200 rounded-sm p-4">
          <h3 className="text-sm font-semibold text-coral-800 mb-3 uppercase tracking-wide">
            Banned Words & Phrases
          </h3>
          <TagInput
            value={bannedWords}
            onChange={setBannedWords}
            placeholder="Add a banned word..."
            variant="danger"
            disabled={isSaving}
          />
          <p className="mt-2 text-xs text-coral-600">
            Include em dashes (—), generic AI words (utilize, leverage, synergy), and brand-specific words to avoid.
          </p>
        </div>
      </section>

      {/* Content Patterns */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Content Patterns
        </h3>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Headline Formula"
              value={headlineFormula}
              onChange={(e) => setHeadlineFormula(e.target.value)}
              placeholder="e.g., Benefit + Specificity + Emotion"
              disabled={isSaving}
            />
            <Input
              label="CTA Style"
              value={ctaStyle}
              onChange={(e) => setCtaStyle(e.target.value)}
              placeholder="How CTAs should feel - urgent, inviting, confident"
              disabled={isSaving}
            />
          </div>
          <TagInput
            label="Proof Points to Include"
            value={proofPoints}
            onChange={setProofPoints}
            placeholder="Add a proof point..."
            disabled={isSaving}
          />
          <TagInput
            label="Emotional Triggers"
            value={emotionalTriggers}
            onChange={setEmotionalTriggers}
            placeholder="Add an emotional trigger..."
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Brand Specifics */}
      <section className="bg-cream-50 border border-cream-300 rounded-sm p-4">
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-4 uppercase tracking-wide">
          Brand Specifics
        </h3>
        <div className="space-y-4">
          <BulletListEditor
            label="Key Messages"
            value={keyMessages}
            onChange={setKeyMessages}
            placeholder="Add a key message..."
            addButtonText="Add message"
            disabled={isSaving}
          />
          <TagInput
            label="Unique Value Props"
            value={uniqueValueProps}
            onChange={setUniqueValueProps}
            placeholder="Add a value prop..."
            variant="success"
            disabled={isSaving}
          />
          <TagInput
            label="Competitive Angles"
            value={competitiveAngles}
            onChange={setCompetitiveAngles}
            placeholder="Add a competitive angle..."
            disabled={isSaving}
          />
          <TagInput
            label="Trust Signals to Mention"
            value={trustSignals}
            onChange={setTrustSignals}
            placeholder="Add a trust signal..."
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

export type { AIPromptEditorProps };
