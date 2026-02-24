/**
 * Step 5: Writing Rules
 *
 * Sentence/paragraph rules, toggles, and vocabulary configuration.
 *
 * Features:
 * - Writing style toggles (contractions, first person, etc.)
 * - Length preferences
 * - Power words and banned words
 * - Preferred terminology
 */

import { cn } from '@/lib/utils'
import { WizardStepHeader } from '../WizardContainer'
import { ChipInput } from '../ChipInput'
import type { WizardStepBaseProps, WritingRules, Vocabulary } from '../types'

/** Default writing rules */
const DEFAULT_WRITING_RULES: WritingRules = {
  sentence_length: 'medium',
  paragraph_length: 'medium',
  use_contractions: true,
  use_first_person: false,
  use_oxford_comma: true,
  use_exclamation_marks: 'sparingly',
  capitalization_style: 'sentence',
}

/**
 * Step5WritingRules - writing rules and vocabulary step
 */
export function Step5WritingRules({
  formData,
  onChange,
  disabled = false,
  className,
}: WizardStepBaseProps) {
  const rules = formData.writing_rules || DEFAULT_WRITING_RULES
  const vocabulary = formData.vocabulary || {
    power_words: [],
    banned_words: [],
    preferred_terms: {},
    industry_terms: [],
  }

  const updateRules = (updates: Partial<WritingRules>) => {
    onChange({
      writing_rules: {
        ...rules,
        ...updates,
      },
    })
  }

  const updateVocabulary = (updates: Partial<Vocabulary>) => {
    onChange({
      vocabulary: {
        ...vocabulary,
        ...updates,
      },
    })
  }

  return (
    <div className={cn('space-y-10', className)}>
      <WizardStepHeader
        title="Writing Rules"
        description="Set specific writing guidelines that AI will follow when generating content for your brand."
      />

      {/* Writing Style */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Writing Style
        </h3>

        <div className="grid md:grid-cols-2 gap-6">
          {/* Sentence Length */}
          <SelectField
            label="Sentence Length"
            value={rules.sentence_length}
            onChange={(v) => updateRules({ sentence_length: v as WritingRules['sentence_length'] })}
            options={[
              { value: 'short', label: 'Short (punchy, direct)' },
              { value: 'medium', label: 'Medium (balanced)' },
              { value: 'long', label: 'Long (detailed, flowing)' },
              { value: 'varied', label: 'Varied (dynamic mix)' },
            ]}
            disabled={disabled}
          />

          {/* Paragraph Length */}
          <SelectField
            label="Paragraph Length"
            value={rules.paragraph_length}
            onChange={(v) => updateRules({ paragraph_length: v as WritingRules['paragraph_length'] })}
            options={[
              { value: 'short', label: 'Short (1-2 sentences)' },
              { value: 'medium', label: 'Medium (3-4 sentences)' },
              { value: 'long', label: 'Long (5+ sentences)' },
            ]}
            disabled={disabled}
          />

          {/* Exclamation Marks */}
          <SelectField
            label="Exclamation Marks"
            value={rules.use_exclamation_marks}
            onChange={(v) => updateRules({ use_exclamation_marks: v as WritingRules['use_exclamation_marks'] })}
            options={[
              { value: 'never', label: 'Never use' },
              { value: 'sparingly', label: 'Use sparingly' },
              { value: 'freely', label: 'Use freely' },
            ]}
            disabled={disabled}
          />

          {/* Capitalization */}
          <SelectField
            label="Capitalization Style"
            value={rules.capitalization_style}
            onChange={(v) => updateRules({ capitalization_style: v as WritingRules['capitalization_style'] })}
            options={[
              { value: 'sentence', label: 'Sentence case' },
              { value: 'title', label: 'Title Case' },
              { value: 'all_caps', label: 'ALL CAPS (headlines only)' },
            ]}
            disabled={disabled}
          />
        </div>
      </section>

      {/* Toggles */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Style Preferences
        </h3>

        <div className="space-y-4">
          <ToggleField
            label="Use Contractions"
            description="Use 'we're' instead of 'we are', 'don't' instead of 'do not'"
            checked={rules.use_contractions ?? true}
            onChange={(v) => updateRules({ use_contractions: v })}
            disabled={disabled}
          />
          <ToggleField
            label="Use First Person"
            description="Use 'we' and 'our' instead of brand name or third person"
            checked={rules.use_first_person ?? false}
            onChange={(v) => updateRules({ use_first_person: v })}
            disabled={disabled}
          />
          <ToggleField
            label="Use Oxford Comma"
            description="Add comma before 'and' in lists (e.g., 'red, white, and blue')"
            checked={rules.use_oxford_comma ?? true}
            onChange={(v) => updateRules({ use_oxford_comma: v })}
            disabled={disabled}
          />
          <ToggleField
            label="Allow Emojis"
            description="Include emojis in content when appropriate"
            checked={vocabulary.emojis_allowed ?? false}
            onChange={(v) => updateVocabulary({ emojis_allowed: v })}
            disabled={disabled}
          />
        </div>
      </section>

      {/* Vocabulary */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Vocabulary
        </h3>

        <div className="space-y-6">
          {/* Power Words */}
          <div className="p-5 bg-success-50 rounded-xl border border-success-200">
            <h4 className="font-medium text-success-800 mb-3">
              Power Words
            </h4>
            <p className="text-sm text-success-700 mb-3">
              Words that resonate with your brand and should be used often
            </p>
            <ChipInput
              values={vocabulary.power_words}
              onChange={(v) => updateVocabulary({ power_words: v })}
              placeholder="Add power word..."
              disabled={disabled}
              maxChips={20}
            />
          </div>

          {/* Banned Words */}
          <div className="p-5 bg-error-50 rounded-xl border border-error-200">
            <h4 className="font-medium text-error-800 mb-3">
              Banned Words
            </h4>
            <p className="text-sm text-error-700 mb-3">
              Words to never use in your brand's content
            </p>
            <ChipInput
              values={vocabulary.banned_words}
              onChange={(v) => updateVocabulary({ banned_words: v })}
              placeholder="Add banned word..."
              disabled={disabled}
              maxChips={20}
            />
          </div>

          {/* Industry Terms */}
          <div className="p-5 bg-primary-50 rounded-xl border border-primary-200">
            <h4 className="font-medium text-primary-800 mb-3">
              Industry Terms
            </h4>
            <p className="text-sm text-primary-700 mb-3">
              Specialized terminology that your audience understands
            </p>
            <ChipInput
              values={vocabulary.industry_terms}
              onChange={(v) => updateVocabulary({ industry_terms: v })}
              placeholder="Add industry term..."
              disabled={disabled}
              maxChips={20}
            />
          </div>
        </div>
      </section>

      {/* Help text */}
      <div className="text-sm text-warmgray-500 bg-warmgray-50 rounded-lg p-4">
        <p className="font-medium text-warmgray-700 mb-2">Writing rules tips:</p>
        <ul className="space-y-1 list-disc list-inside">
          <li>Be specific with banned words - include competitor names, outdated terms, etc.</li>
          <li>Power words should evoke emotion and align with your brand personality</li>
          <li>Industry terms help AI use the right vocabulary for your audience</li>
          <li>These rules apply to all AI-generated content for consistency</li>
        </ul>
      </div>
    </div>
  )
}

/** Select field helper */
function SelectField({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string
  value?: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
  disabled?: boolean
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-warmgray-700 mb-1.5">
        {label}
      </label>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          'w-full px-3 py-2 text-sm border border-cream-200 rounded-lg',
          'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
          disabled && 'bg-cream-50 cursor-not-allowed'
        )}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}

/** Toggle field helper */
function ToggleField({
  label,
  description,
  checked,
  onChange,
  disabled,
}: {
  label: string
  description: string
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}) {
  return (
    <label
      className={cn(
        'flex items-start gap-4 p-4 bg-white border border-cream-200 rounded-lg cursor-pointer',
        'hover:border-cream-300 transition-colors',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
        className={cn(
          'mt-0.5 h-5 w-5 rounded border-cream-300 text-primary-600',
          'focus:ring-primary-500 focus:ring-offset-0'
        )}
      />
      <div>
        <span className="block font-medium text-warmgray-900">{label}</span>
        <span className="block text-sm text-warmgray-500">{description}</span>
      </div>
    </label>
  )
}
