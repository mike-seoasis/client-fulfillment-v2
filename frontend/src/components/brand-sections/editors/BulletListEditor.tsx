'use client';

import { useState, useCallback, useRef, type KeyboardEvent, type ChangeEvent } from 'react';

interface BulletListEditorProps {
  /** Current array of items */
  value: string[];
  /** Called when items change */
  onChange: (items: string[]) => void;
  /** Optional placeholder text for input */
  placeholder?: string;
  /** Optional label */
  label?: string;
  /** Whether the editor is disabled */
  disabled?: boolean;
  /** Add button text (defaults to "Add item") */
  addButtonText?: string;
}

/**
 * Bullet list editor component for array of strings.
 * Supports adding new items via input + button, reordering via up/down buttons,
 * and removing items.
 * Styled with tropical oasis palette.
 */
export function BulletListEditor({
  value,
  onChange,
  placeholder = 'Add new item...',
  label,
  disabled = false,
  addButtonText = 'Add item',
}: BulletListEditorProps) {
  const [inputValue, setInputValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const handleAddItem = useCallback(() => {
    const trimmed = inputValue.trim();
    if (trimmed) {
      onChange([...value, trimmed]);
      setInputValue('');
      inputRef.current?.focus();
    }
  }, [inputValue, value, onChange]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddItem();
      }
    },
    [handleAddItem]
  );

  const handleRemoveItem = useCallback(
    (indexToRemove: number) => {
      onChange(value.filter((_, index) => index !== indexToRemove));
    },
    [value, onChange]
  );

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index <= 0) return;
      const newItems = [...value];
      [newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]];
      onChange(newItems);
    },
    [value, onChange]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index >= value.length - 1) return;
      const newItems = [...value];
      [newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]];
      onChange(newItems);
    },
    [value, onChange]
  );

  return (
    <div className="w-full">
      {label && (
        <label className="block mb-1.5 text-sm font-medium text-warm-gray-700">
          {label}
        </label>
      )}

      <div className="border border-cream-400 rounded-sm overflow-hidden">
        {/* List of items */}
        <ul className="divide-y divide-cream-200">
          {value.length === 0 ? (
            <li className="py-6 text-center text-warm-gray-400 text-sm">
              No items yet. Add one below.
            </li>
          ) : (
            value.map((item, index) => (
              <li
                key={`${item}-${index}`}
                className="flex items-center gap-2 py-2 px-3 bg-white hover:bg-cream-50 transition-colors duration-100"
              >
                {/* Bullet marker */}
                <span className="text-palm-500 text-lg leading-none" aria-hidden="true">
                  •
                </span>

                {/* Item text */}
                <span className="flex-1 text-sm text-warm-gray-800 min-w-0 break-words">
                  {item}
                </span>

                {/* Reorder & delete buttons */}
                {!disabled && (
                  <div className="flex items-center gap-1 flex-shrink-0">
                    {/* Move up */}
                    <button
                      type="button"
                      onClick={() => handleMoveUp(index)}
                      disabled={index === 0}
                      className={`
                        p-1 rounded-sm transition-colors duration-150
                        focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                        ${
                          index === 0
                            ? 'text-warm-gray-300 cursor-not-allowed'
                            : 'text-warm-gray-400 hover:text-palm-600 hover:bg-palm-50'
                        }
                      `}
                      aria-label={`Move "${item}" up`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M5 15l7-7 7 7"
                        />
                      </svg>
                    </button>

                    {/* Move down */}
                    <button
                      type="button"
                      onClick={() => handleMoveDown(index)}
                      disabled={index === value.length - 1}
                      className={`
                        p-1 rounded-sm transition-colors duration-150
                        focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                        ${
                          index === value.length - 1
                            ? 'text-warm-gray-300 cursor-not-allowed'
                            : 'text-warm-gray-400 hover:text-palm-600 hover:bg-palm-50'
                        }
                      `}
                      aria-label={`Move "${item}" down`}
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </button>

                    {/* Delete */}
                    <button
                      type="button"
                      onClick={() => handleRemoveItem(index)}
                      className="
                        p-1 rounded-sm transition-colors duration-150
                        text-warm-gray-400 hover:text-coral-600 hover:bg-coral-50
                        focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                      "
                      aria-label={`Remove "${item}"`}
                    >
                      <svg
                        className="w-4 h-4"
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
                  </div>
                )}
              </li>
            ))
          )}
        </ul>

        {/* Add item input */}
        {!disabled && (
          <div className="flex items-center gap-2 border-t border-cream-300 bg-cream-50 px-3 py-2">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={disabled}
              className="
                flex-1 px-3 py-1.5 text-sm text-warm-gray-900
                bg-white border border-cream-400 rounded-sm
                placeholder:text-warm-gray-400
                focus:outline-none focus:border-palm-400 focus:ring-2 focus:ring-palm-200 focus:ring-offset-1
                disabled:bg-cream-100 disabled:cursor-not-allowed
                transition-colors duration-150
              "
            />
            <button
              type="button"
              onClick={handleAddItem}
              disabled={!inputValue.trim()}
              className={`
                inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                rounded-sm transition-colors duration-150
                focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                ${
                  inputValue.trim()
                    ? 'text-palm-600 hover:text-palm-700 hover:bg-palm-50'
                    : 'text-warm-gray-400 cursor-not-allowed'
                }
              `}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              {addButtonText}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export type { BulletListEditorProps };
