'use client';

import { useCallback, type ChangeEvent } from 'react';

interface SliderInputProps {
  /** Current value (1-10) */
  value: number;
  /** Called when value changes */
  onChange: (value: number) => void;
  /** Main label for the slider */
  label?: string;
  /** Label for the left (low) end of scale */
  leftLabel?: string;
  /** Label for the right (high) end of scale */
  rightLabel?: string;
  /** Whether the slider is disabled */
  disabled?: boolean;
}

/**
 * Slider input component for 1-10 scale inputs.
 * Used for voice dimensions (Formality, Humor, Reverence, Enthusiasm).
 * Styled with tropical oasis palette and palm-500 fill color.
 */
export function SliderInput({
  value,
  onChange,
  label,
  leftLabel,
  rightLabel,
  disabled = false,
}: SliderInputProps) {
  // Validate and clamp value to 1-10 range
  const safeValue = typeof value === 'number' && !isNaN(value)
    ? Math.max(1, Math.min(10, Math.round(value)))
    : 5;

  // Convert 1-10 position to percentage for fill (1 = 0%, 10 = 100%)
  const fillPercent = ((safeValue - 1) / 9) * 100;

  const handleChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const newValue = parseInt(e.target.value, 10);
      if (!isNaN(newValue)) {
        onChange(newValue);
      }
    },
    [onChange]
  );

  return (
    <div className="w-full">
      {/* Header with label and current value */}
      {(label || true) && (
        <div className="flex items-center justify-between mb-2">
          {label && (
            <label className="text-sm font-medium text-warm-gray-700">
              {label}
            </label>
          )}
          <span className="text-lg font-semibold text-palm-600 tabular-nums">
            {safeValue}
          </span>
        </div>
      )}

      {/* Slider container */}
      <div className="relative pt-1 pb-2">
        {/* Custom track background with fill */}
        <div className="relative h-2 rounded-full bg-cream-200">
          {/* Filled portion */}
          <div
            className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-palm-400 to-palm-500 transition-all duration-150"
            style={{ width: `${fillPercent}%` }}
          />
        </div>

        {/* Native range input (positioned over the track) */}
        <input
          type="range"
          min={1}
          max={10}
          step={1}
          value={safeValue}
          onChange={handleChange}
          disabled={disabled}
          className={`
            absolute top-0 left-0 w-full h-2 appearance-none bg-transparent cursor-pointer
            focus:outline-none
            disabled:cursor-not-allowed disabled:opacity-50
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-5
            [&::-webkit-slider-thumb]:h-5
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-palm-500
            [&::-webkit-slider-thumb]:border-2
            [&::-webkit-slider-thumb]:border-white
            [&::-webkit-slider-thumb]:shadow-md
            [&::-webkit-slider-thumb]:cursor-pointer
            [&::-webkit-slider-thumb]:transition-transform
            [&::-webkit-slider-thumb]:duration-150
            [&::-webkit-slider-thumb]:hover:scale-110
            [&::-webkit-slider-thumb]:active:scale-95
            [&::-moz-range-thumb]:appearance-none
            [&::-moz-range-thumb]:w-5
            [&::-moz-range-thumb]:h-5
            [&::-moz-range-thumb]:rounded-full
            [&::-moz-range-thumb]:bg-palm-500
            [&::-moz-range-thumb]:border-2
            [&::-moz-range-thumb]:border-white
            [&::-moz-range-thumb]:shadow-md
            [&::-moz-range-thumb]:cursor-pointer
            focus-visible:[&::-webkit-slider-thumb]:ring-2
            focus-visible:[&::-webkit-slider-thumb]:ring-palm-400
            focus-visible:[&::-webkit-slider-thumb]:ring-offset-2
            focus-visible:[&::-moz-range-thumb]:ring-2
            focus-visible:[&::-moz-range-thumb]:ring-palm-400
            focus-visible:[&::-moz-range-thumb]:ring-offset-2
          `}
          aria-label={label || 'Scale value'}
          aria-valuemin={1}
          aria-valuemax={10}
          aria-valuenow={safeValue}
        />

        {/* Tick marks */}
        <div className="absolute top-4 left-0 right-0 flex justify-between px-[2px] pointer-events-none">
          {Array.from({ length: 10 }, (_, i) => (
            <div
              key={i + 1}
              className={`
                w-0.5 h-2 rounded-full transition-colors duration-150
                ${i + 1 <= safeValue ? 'bg-palm-400' : 'bg-cream-300'}
              `}
            />
          ))}
        </div>
      </div>

      {/* Scale labels */}
      {(leftLabel || rightLabel) && (
        <div className="flex justify-between mt-1">
          <span className="text-xs text-warm-gray-500">{leftLabel || ''}</span>
          <span className="text-xs text-warm-gray-500">{rightLabel || ''}</span>
        </div>
      )}
    </div>
  );
}

export type { SliderInputProps };
