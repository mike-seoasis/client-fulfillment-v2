'use client';

import { useState } from 'react';
import { EmptySection } from './SectionCard';
import { type AIPromptSnippetData, type BaseSectionProps } from './types';

interface AIPromptSectionProps extends BaseSectionProps {
  data?: AIPromptSnippetData;
}

function CopyIcon({ className }: { className?: string }) {
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
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
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

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
      {children}
    </h4>
  );
}

function TagList({ tags, variant = 'default' }: { tags: string[]; variant?: 'default' | 'danger' | 'success' }) {
  const variantStyles = {
    default: 'bg-cream-100 text-warm-gray-700 border-cream-300',
    danger: 'bg-coral-50 text-coral-700 border-coral-200',
    success: 'bg-palm-50 text-palm-700 border-palm-200',
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag, i) => (
        <span
          key={i}
          className={`inline-block px-2 py-0.5 text-xs border rounded-sm ${variantStyles[variant]}`}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

/**
 * Displays the AI Prompt section with comprehensive brand guidelines.
 * Shows the full prompt plus all supporting reference material.
 */
export function AIPromptSection({ data }: AIPromptSectionProps) {
  const [copied, setCopied] = useState(false);

  // Get the main prompt text (support both new and legacy field names)
  const promptText = data?.full_prompt || data?.snippet;

  if (!data || !promptText) {
    return <EmptySection message="AI prompt not available" />;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  // Extract data with fallbacks for legacy format
  const quickRef = data.quick_reference || {
    voice_in_three_words: data.voice_in_three_words,
    we_sound_like: data.we_sound_like,
    we_never_sound_like: data.we_never_sound_like,
  };
  const audience = data.audience_profile;
  const voice = data.voice_guidelines;
  const rules = data.writing_rules || {
    banned_words: data.never_use_words,
    always_do: data.always_include,
  };
  const patterns = data.content_patterns;
  const specifics = data.brand_specifics || {
    unique_value_props: data.key_differentiators,
  };

  return (
    <div className="space-y-6">
      {/* Main Prompt - Copyable */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <SectionHeader>Full AI Prompt</SectionHeader>
          <button
            onClick={handleCopy}
            className={`
              inline-flex items-center gap-1.5 px-2.5 py-1
              text-xs font-medium rounded-sm
              transition-all duration-150
              ${
                copied
                  ? 'bg-palm-100 text-palm-700 border border-palm-300'
                  : 'bg-white text-warm-gray-600 border border-cream-300 hover:bg-cream-50 hover:border-cream-400'
              }
            `}
          >
            {copied ? (
              <>
                <CheckIcon className="w-3.5 h-3.5" />
                Copied!
              </>
            ) : (
              <>
                <CopyIcon className="w-3.5 h-3.5" />
                Copy Prompt
              </>
            )}
          </button>
        </div>
        <div className="bg-warm-gray-900 rounded-sm p-4 max-h-[400px] overflow-y-auto">
          <pre className="text-sm text-warm-gray-100 whitespace-pre-wrap font-mono leading-relaxed">
            {promptText}
          </pre>
        </div>
      </div>

      {/* Quick Reference */}
      {(quickRef.voice_in_three_words?.length || quickRef.we_sound_like || quickRef.elevator_pitch) && (
        <div className="bg-palm-50 border border-palm-200 rounded-sm p-4">
          <SectionHeader>Quick Reference</SectionHeader>
          <div className="space-y-3">
            {quickRef.voice_in_three_words && quickRef.voice_in_three_words.length > 0 && (
              <div>
                <span className="text-xs text-warm-gray-500">Voice in 3 words:</span>
                <p className="text-sm font-medium text-palm-800">
                  {quickRef.voice_in_three_words.join(' • ')}
                </p>
              </div>
            )}
            {quickRef.elevator_pitch && (
              <div>
                <span className="text-xs text-warm-gray-500">Elevator Pitch:</span>
                <p className="text-sm text-warm-gray-700">{quickRef.elevator_pitch}</p>
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {quickRef.we_sound_like && (
                <div>
                  <span className="text-xs text-warm-gray-500">We sound like:</span>
                  <p className="text-sm text-warm-gray-700">{quickRef.we_sound_like}</p>
                </div>
              )}
              {quickRef.we_never_sound_like && (
                <div>
                  <span className="text-xs text-warm-gray-500">We never sound like:</span>
                  <p className="text-sm text-warm-gray-700">{quickRef.we_never_sound_like}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Two Column Layout for Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Audience Profile */}
        {audience && (
          <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
            <SectionHeader>Audience Profile</SectionHeader>
            <div className="space-y-2 text-sm">
              {audience.primary_persona && (
                <div>
                  <span className="text-warm-gray-500">Persona:</span>{' '}
                  <span className="text-warm-gray-800">{audience.primary_persona}</span>
                </div>
              )}
              {audience.demographics && (
                <div>
                  <span className="text-warm-gray-500">Demographics:</span>{' '}
                  <span className="text-warm-gray-700">{audience.demographics}</span>
                </div>
              )}
              {audience.psychographics && (
                <div>
                  <span className="text-warm-gray-500">Psychographics:</span>{' '}
                  <span className="text-warm-gray-700">{audience.psychographics}</span>
                </div>
              )}
              {audience.how_they_talk && (
                <div>
                  <span className="text-warm-gray-500">How they talk:</span>{' '}
                  <span className="text-warm-gray-700">{audience.how_they_talk}</span>
                </div>
              )}
              {audience.what_they_care_about && audience.what_they_care_about.length > 0 && (
                <div className="pt-1">
                  <span className="text-warm-gray-500 block mb-1">What they care about:</span>
                  <TagList tags={audience.what_they_care_about} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Voice Guidelines */}
        {voice && (
          <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
            <SectionHeader>Voice Guidelines</SectionHeader>
            <div className="space-y-2 text-sm">
              {voice.personality_traits && voice.personality_traits.length > 0 && (
                <div>
                  <span className="text-warm-gray-500 block mb-1">Personality:</span>
                  <TagList tags={voice.personality_traits} variant="success" />
                </div>
              )}
              {voice.tone_spectrum && (
                <div className="space-y-1 pt-1">
                  {voice.tone_spectrum.formal_to_casual && (
                    <div className="text-xs">
                      <span className="text-warm-gray-500">Formal ↔ Casual:</span>{' '}
                      <span className="text-warm-gray-700">{voice.tone_spectrum.formal_to_casual}</span>
                    </div>
                  )}
                  {voice.tone_spectrum.serious_to_playful && (
                    <div className="text-xs">
                      <span className="text-warm-gray-500">Serious ↔ Playful:</span>{' '}
                      <span className="text-warm-gray-700">{voice.tone_spectrum.serious_to_playful}</span>
                    </div>
                  )}
                  {voice.tone_spectrum.reserved_to_enthusiastic && (
                    <div className="text-xs">
                      <span className="text-warm-gray-500">Reserved ↔ Enthusiastic:</span>{' '}
                      <span className="text-warm-gray-700">{voice.tone_spectrum.reserved_to_enthusiastic}</span>
                    </div>
                  )}
                </div>
              )}
              {voice.sentence_style && (
                <div>
                  <span className="text-warm-gray-500">Sentence style:</span>{' '}
                  <span className="text-warm-gray-700">{voice.sentence_style}</span>
                </div>
              )}
              {voice.vocabulary_level && (
                <div>
                  <span className="text-warm-gray-500">Vocabulary:</span>{' '}
                  <span className="text-warm-gray-700">{voice.vocabulary_level}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Writing Rules */}
      {rules && (rules.always_do?.length || rules.never_do?.length || rules.banned_words?.length) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Always Do */}
          {rules.always_do && rules.always_do.length > 0 && (
            <div className="bg-palm-50 border border-palm-200 rounded-sm p-4">
              <SectionHeader>Always Do</SectionHeader>
              <ul className="space-y-1">
                {rules.always_do.map((item, i) => (
                  <li key={i} className="text-sm text-palm-800 flex items-start gap-2">
                    <span className="text-palm-500 mt-0.5">✓</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Never Do */}
          {rules.never_do && rules.never_do.length > 0 && (
            <div className="bg-coral-50 border border-coral-200 rounded-sm p-4">
              <SectionHeader>Never Do</SectionHeader>
              <ul className="space-y-1">
                {rules.never_do.map((item, i) => (
                  <li key={i} className="text-sm text-coral-800 flex items-start gap-2">
                    <span className="text-coral-500 mt-0.5">✗</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Banned Words */}
      {rules?.banned_words && rules.banned_words.length > 0 && (
        <div className="bg-coral-50 border border-coral-200 rounded-sm p-4">
          <SectionHeader>Banned Words & Phrases</SectionHeader>
          <TagList tags={rules.banned_words} variant="danger" />
        </div>
      )}

      {/* Content Patterns */}
      {patterns && (patterns.headline_formula || patterns.cta_style || patterns.proof_points_to_include?.length) && (
        <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
          <SectionHeader>Content Patterns</SectionHeader>
          <div className="space-y-3 text-sm">
            {patterns.headline_formula && (
              <div>
                <span className="text-warm-gray-500">Headline formula:</span>{' '}
                <span className="text-warm-gray-800 font-medium">{patterns.headline_formula}</span>
              </div>
            )}
            {patterns.cta_style && (
              <div>
                <span className="text-warm-gray-500">CTA style:</span>{' '}
                <span className="text-warm-gray-700">{patterns.cta_style}</span>
              </div>
            )}
            {patterns.proof_points_to_include && patterns.proof_points_to_include.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Proof points to include:</span>
                <TagList tags={patterns.proof_points_to_include} />
              </div>
            )}
            {patterns.emotional_triggers && patterns.emotional_triggers.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Emotional triggers:</span>
                <TagList tags={patterns.emotional_triggers} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Brand Specifics */}
      {specifics && (specifics.key_messages?.length || specifics.unique_value_props?.length) && (
        <div className="bg-cream-50 border border-cream-300 rounded-sm p-4">
          <SectionHeader>Brand Specifics</SectionHeader>
          <div className="space-y-3 text-sm">
            {specifics.key_messages && specifics.key_messages.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Key messages:</span>
                <ul className="space-y-1">
                  {specifics.key_messages.map((msg, i) => (
                    <li key={i} className="text-warm-gray-700">• {msg}</li>
                  ))}
                </ul>
              </div>
            )}
            {specifics.unique_value_props && specifics.unique_value_props.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Unique value props:</span>
                <TagList tags={specifics.unique_value_props} variant="success" />
              </div>
            )}
            {specifics.competitive_angles && specifics.competitive_angles.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Competitive angles:</span>
                <TagList tags={specifics.competitive_angles} />
              </div>
            )}
            {specifics.trust_signals_to_mention && specifics.trust_signals_to_mention.length > 0 && (
              <div>
                <span className="text-warm-gray-500 block mb-1">Trust signals:</span>
                <TagList tags={specifics.trust_signals_to_mention} />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Usage Tip */}
      <div className="p-3 bg-lagoon-50 border border-lagoon-200 rounded-sm">
        <p className="text-sm text-lagoon-700">
          <span className="font-semibold">Tip:</span> Copy the full prompt above and paste it at the beginning of your
          AI writing requests. The supporting details below provide additional context for fine-tuning.
        </p>
      </div>
    </div>
  );
}
