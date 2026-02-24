/**
 * Step 4: Voice
 *
 * Voice dimensions (4 sliders) and voice characteristics.
 *
 * Features:
 * - 4 voice dimension sliders (formality, humor, reverence, enthusiasm)
 * - "We are" / "We are not" characteristics
 * - Example phrases
 */

import { cn } from '@/lib/utils'
import { WizardStepHeader } from '../WizardContainer'
import { VoiceDimensionSlider, VOICE_DIMENSIONS } from '../VoiceDimensionSlider'
import { ChipInput } from '../ChipInput'
import type { WizardStepBaseProps, VoiceDimensions, VoiceCharacteristics } from '../types'

/** Default voice dimension values */
const DEFAULT_VOICE_DIMENSIONS: VoiceDimensions = {
  formality: 5,
  humor: 5,
  reverence: 5,
  enthusiasm: 5,
}

/**
 * Step4Voice - voice configuration step
 */
export function Step4Voice({
  formData,
  onChange,
  disabled = false,
  className,
}: WizardStepBaseProps) {
  const dimensions = formData.voice_dimensions || DEFAULT_VOICE_DIMENSIONS
  const characteristics = formData.voice_characteristics || { we_are: [], we_are_not: [] }

  const updateDimension = (dimension: keyof VoiceDimensions, value: number) => {
    onChange({
      voice_dimensions: {
        ...dimensions,
        [dimension]: value,
      },
    })
  }

  const updateCharacteristics = (updates: Partial<VoiceCharacteristics>) => {
    onChange({
      voice_characteristics: {
        ...characteristics,
        ...updates,
      },
    })
  }

  return (
    <div className={cn('space-y-10', className)}>
      <WizardStepHeader
        title="Brand Voice"
        description="Define how your brand sounds. These voice dimensions will guide the tone and style of all AI-generated content."
      />

      {/* Voice Dimensions */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-6">
          Voice Dimensions
        </h3>
        <p className="text-sm text-warmgray-600 mb-6">
          Adjust each slider to define where your brand falls on the spectrum.
          The examples at each end show how content would sound at that extreme.
        </p>

        <div className="space-y-8">
          {(Object.keys(VOICE_DIMENSIONS) as Array<keyof typeof VOICE_DIMENSIONS>).map((key) => {
            const dim = VOICE_DIMENSIONS[key]
            return (
              <VoiceDimensionSlider
                key={key}
                name={dim.name}
                value={dimensions[key]}
                onChange={(value) => updateDimension(key, value)}
                lowLabel={dim.lowLabel}
                highLabel={dim.highLabel}
                lowExample={dim.lowExample}
                highExample={dim.highExample}
                disabled={disabled}
              />
            )
          })}
        </div>
      </section>

      {/* Voice Characteristics */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Voice Characteristics
        </h3>
        <p className="text-sm text-warmgray-600 mb-6">
          Define what your brand voice IS and IS NOT. This helps AI understand
          the personality traits and communication style you want to project.
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          {/* We Are */}
          <div className="p-5 bg-success-50 rounded-xl border border-success-200">
            <h4 className="font-medium text-success-800 mb-3">
              We Are...
            </h4>
            <ChipInput
              values={characteristics.we_are}
              onChange={(v) => updateCharacteristics({ we_are: v })}
              placeholder="Add characteristic (e.g., confident, helpful)"
              disabled={disabled}
              maxChips={10}
            />
            <p className="mt-2 text-xs text-success-700">
              Traits that define your brand personality
            </p>
          </div>

          {/* We Are Not */}
          <div className="p-5 bg-error-50 rounded-xl border border-error-200">
            <h4 className="font-medium text-error-800 mb-3">
              We Are NOT...
            </h4>
            <ChipInput
              values={characteristics.we_are_not}
              onChange={(v) => updateCharacteristics({ we_are_not: v })}
              placeholder="Add what to avoid (e.g., pushy, condescending)"
              disabled={disabled}
              maxChips={10}
            />
            <p className="mt-2 text-xs text-error-700">
              Traits to actively avoid in communication
            </p>
          </div>
        </div>
      </section>

      {/* Example Phrases */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Example Phrases
        </h3>
        <p className="text-sm text-warmgray-600 mb-4">
          Add phrases that capture your brand voice. These help AI understand
          your style through examples.
        </p>
        <ChipInput
          values={characteristics.example_phrases || []}
          onChange={(v) => updateCharacteristics({ example_phrases: v })}
          placeholder="Add example phrase..."
          disabled={disabled}
          maxChips={15}
        />
      </section>

      {/* Help text */}
      <div className="text-sm text-warmgray-500 bg-warmgray-50 rounded-lg p-4">
        <p className="font-medium text-warmgray-700 mb-2">Voice calibration tips:</p>
        <ul className="space-y-1 list-disc list-inside">
          <li>Think about how you'd describe your brand if it were a person</li>
          <li>Consider your audience - what tone resonates with them?</li>
          <li>Review your existing content to identify consistent patterns</li>
          <li>When in doubt, aim for the middle and adjust after seeing results</li>
        </ul>
      </div>
    </div>
  )
}
