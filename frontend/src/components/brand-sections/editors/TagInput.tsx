'use client';

import { useState, useCallback, type KeyboardEvent, type ChangeEvent } from 'react';

interface TagInputProps {
  /** Current array of tags */
  value: string[];
  /** Called when tags change */
  onChange: (tags: string[]) => void;
  /** Optional placeholder text */
  placeholder?: string;
  /** Optional label */
  label?: string;
  /** Visual variant for tags */
  variant?: 'default' | 'success' | 'danger';
  /** Whether the input is disabled */
  disabled?: boolean;
}

/**
 * Tag input component for editable word lists.
 * Supports adding tags via input + enter and removing via X button.
 * Styled with tropical oasis palette.
 */
export function TagInput({
  value,
  onChange,
  placeholder = 'Type and press Enter to add...',
  label,
  variant = 'default',
  disabled = false,
}: TagInputProps) {
  // Defensive: ensure value is always an array
  const tags = Array.isArray(value) ? value : [];

  const [inputValue, setInputValue] = useState('');

  const variantStyles = {
    default: 'bg-cream-100 text-warm-gray-700 border-cream-300',
    success: 'bg-palm-50 text-palm-700 border-palm-200',
    danger: 'bg-coral-50 text-coral-700 border-coral-200',
  };

  const removeButtonStyles = {
    default: 'text-warm-gray-400 hover:text-warm-gray-600 hover:bg-cream-200',
    success: 'text-palm-400 hover:text-palm-600 hover:bg-palm-100',
    danger: 'text-coral-400 hover:text-coral-600 hover:bg-coral-100',
  };

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const trimmed = inputValue.trim();
        if (trimmed && !tags.includes(trimmed)) {
          onChange([...tags, trimmed]);
          setInputValue('');
        }
      }
      // Allow removing last tag with backspace when input is empty
      if (e.key === 'Backspace' && inputValue === '' && tags.length > 0) {
        onChange(tags.slice(0, -1));
      }
    },
    [inputValue, tags, onChange]
  );

  const handleRemoveTag = useCallback(
    (indexToRemove: number) => {
      onChange(tags.filter((_, index) => index !== indexToRemove));
    },
    [tags, onChange]
  );

  return (
    <div className="w-full">
      {label && (
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
          {label}
        </label>
      )}
      <div
        className={`
          flex flex-wrap items-center gap-2 p-2 min-h-[44px]
          bg-white border border-cream-400 rounded-sm
          focus-within:border-palm-400 focus-within:ring-2 focus-within:ring-palm-200 focus-within:ring-offset-1
          transition-colors duration-150
          ${disabled ? 'bg-cream-100 cursor-not-allowed' : ''}
        `}
      >
        {/* Existing tags */}
        {tags.map((tag, index) => (
          <span
            key={`${tag}-${index}`}
            className={`
              inline-flex items-center gap-1 px-2.5 py-1 text-sm border rounded-sm
              ${variantStyles[variant]}
            `}
          >
            {tag}
            {!disabled && (
              <button
                type="button"
                onClick={() => handleRemoveTag(index)}
                className={`
                  ml-0.5 p-0.5 rounded-sm transition-colors duration-150
                  focus:outline-none focus:ring-1 focus:ring-palm-400
                  ${removeButtonStyles[variant]}
                `}
                aria-label={`Remove ${tag}`}
              >
                <svg
                  className="w-3 h-3"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            )}
          </span>
        ))}

        {/* Input field */}
        <input
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={tags.length === 0 ? placeholder : ''}
          disabled={disabled}
          className={`
            flex-1 min-w-[120px] px-1 py-1 text-sm text-warm-gray-900
            bg-transparent border-none outline-none
            placeholder:text-warm-gray-400
            disabled:cursor-not-allowed
          `}
        />
      </div>
    </div>
  );
}

export type { TagInputProps };
