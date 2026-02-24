/**
 * VoiceDimensionSlider component for brand voice dimension configuration
 *
 * A slider component with 1-10 scale for configuring voice dimensions
 * (formality, humor, reverence, enthusiasm) with example text at each end.
 *
 * Features:
 * - 1-10 scale slider
 * - Current value display
 * - Low/high example text
 * - Accessible with keyboard navigation
 * - Brand color theming
 */

import { cn } from '@/lib/utils'
import { useState, useId } from 'react'

export interface VoiceDimensionSliderProps {
  /** Dimension name (e.g., "Formality") */
  name: string
  /** Current value (1-10) */
  value: number
  /** Callback when value changes */
  onChange: (value: number) => void
  /** Example text for low end (value 1) */
  lowExample: string
  /** Example text for high end (value 10) */
  highExample: string
  /** Label for low end */
  lowLabel?: string
  /** Label for high end */
  highLabel?: string
  /** Optional description */
  description?: string
  /** Whether the slider is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}

/**
 * VoiceDimensionSlider for configuring brand voice on a 1-10 scale
 *
 * @example
 * <VoiceDimensionSlider
 *   name="Formality"
 *   value={4}
 *   onChange={setFormality}
 *   lowExample="Hey! Let's chat about..."
 *   highExample="Dear Valued Customer, We are pleased..."
 *   lowLabel="Very Casual"
 *   highLabel="Very Formal"
 * />
 */
export function VoiceDimensionSlider({
  name,
  value,
  onChange,
  lowExample,
  highExample,
  lowLabel = 'Low',
  highLabel = 'High',
  description,
  disabled = false,
  className,
}: VoiceDimensionSliderProps) {
  const id = useId()
  const [isDragging, setIsDragging] = useState(false)

  // Calculate percentage for gradient/indicator positioning
  const percentage = ((value - 1) / 9) * 100

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <label
            htmlFor={id}
            className="text-sm font-medium text-warmgray-900"
          >
            {name}
          </label>
          {description && (
            <p className="mt-0.5 text-xs text-warmgray-500">
              {description}
            </p>
          )}
        </div>
        {/* Current value badge */}
        <span
          className={cn(
            'inline-flex items-center justify-center w-10 h-10 rounded-full text-lg font-semibold transition-colors',
            isDragging
              ? 'bg-primary-500 text-white'
              : 'bg-primary-100 text-primary-700'
          )}
        >
          {value}
        </span>
      </div>

      {/* Slider track */}
      <div className="relative">
        {/* Track background */}
        <div className="h-3 bg-cream-200 rounded-full overflow-hidden">
          {/* Filled portion */}
          <div
            className="h-full bg-gradient-to-r from-primary-300 to-primary-500 transition-all duration-150"
            style={{ width: `${percentage}%` }}
          />
        </div>

        {/* Native range input (invisible but accessible) */}
        <input
          id={id}
          type="range"
          min={1}
          max={10}
          step={1}
          value={value}
          onChange={(e) => onChange(parseInt(e.target.value, 10))}
          onMouseDown={() => setIsDragging(true)}
          onMouseUp={() => setIsDragging(false)}
          onTouchStart={() => setIsDragging(true)}
          onTouchEnd={() => setIsDragging(false)}
          disabled={disabled}
          className={cn(
            'absolute inset-0 w-full h-3 opacity-0 cursor-pointer',
            disabled && 'cursor-not-allowed'
          )}
          aria-label={`${name}: ${value} out of 10`}
        />

        {/* Visual thumb */}
        <div
          className={cn(
            'absolute top-1/2 -translate-y-1/2 w-6 h-6 bg-white rounded-full shadow-md border-2 border-primary-500 transition-all duration-150 pointer-events-none',
            isDragging && 'scale-110 shadow-lg'
          )}
          style={{ left: `calc(${percentage}% - 12px)` }}
        />
      </div>

      {/* Scale labels */}
      <div className="flex justify-between">
        <span className="text-xs font-medium text-warmgray-500">
          1 - {lowLabel}
        </span>
        <span className="text-xs font-medium text-warmgray-500">
          10 - {highLabel}
        </span>
      </div>

      {/* Example text cards */}
      <div className="grid grid-cols-2 gap-4">
        {/* Low example */}
        <div
          className={cn(
            'p-3 rounded-lg border transition-colors',
            value <= 3
              ? 'bg-primary-50 border-primary-200'
              : 'bg-cream-50 border-cream-200'
          )}
        >
          <p className="text-xs font-medium text-warmgray-500 mb-1">
            At 1-3:
          </p>
          <p className="text-sm text-warmgray-700 italic">
            "{lowExample}"
          </p>
        </div>

        {/* High example */}
        <div
          className={cn(
            'p-3 rounded-lg border transition-colors',
            value >= 8
              ? 'bg-primary-50 border-primary-200'
              : 'bg-cream-50 border-cream-200'
          )}
        >
          <p className="text-xs font-medium text-warmgray-500 mb-1">
            At 8-10:
          </p>
          <p className="text-sm text-warmgray-700 italic">
            "{highExample}"
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * Predefined voice dimensions with default examples
 */
export const VOICE_DIMENSIONS = {
  formality: {
    name: 'Formality',
    lowLabel: 'Very Casual',
    highLabel: 'Very Formal',
    lowExample: "Hey! Let's chat about what you need.",
    highExample: 'Dear Valued Customer, We are pleased to assist you.',
  },
  humor: {
    name: 'Humor',
    lowLabel: 'Playful/Funny',
    highLabel: 'Very Serious',
    lowExample: "Oops, we goofed! But we've got your back.",
    highExample: 'We apologize for any inconvenience caused.',
  },
  reverence: {
    name: 'Reverence',
    lowLabel: 'Irreverent/Edgy',
    highLabel: 'Highly Respectful',
    lowExample: 'The boring competitors can keep doing it their way.',
    highExample: 'Other solutions in the market take a different approach.',
  },
  enthusiasm: {
    name: 'Enthusiasm',
    lowLabel: 'Very Enthusiastic',
    highLabel: 'Matter-of-Fact',
    lowExample: "We're SO excited to share this with you!",
    highExample: 'Now available for purchase.',
  },
} as const
