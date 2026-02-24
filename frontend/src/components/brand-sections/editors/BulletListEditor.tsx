'use client';

import { useState, useCallback, useRef, useEffect, type KeyboardEvent, type ChangeEvent } from 'react';

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
 * inline editing of existing items, and removing items.
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
  // Defensive: ensure value is always an array
  const items = Array.isArray(value) ? value : [];

  const [inputValue, setInputValue] = useState('');
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const editTextareaRef = useRef<HTMLTextAreaElement>(null);

  // Focus textarea when entering edit mode
  useEffect(() => {
    if (editingIndex !== null && editTextareaRef.current) {
      editTextareaRef.current.focus();
      editTextareaRef.current.select();
    }
  }, [editingIndex]);

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
  }, []);

  const handleAddItem = useCallback(() => {
    const trimmed = inputValue.trim();
    if (trimmed) {
      onChange([...items, trimmed]);
      setInputValue('');
      inputRef.current?.focus();
    }
  }, [inputValue, items, onChange]);

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
      onChange(items.filter((_, index) => index !== indexToRemove));
    },
    [items, onChange]
  );

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index <= 0) return;
      const newItems = [...items];
      [newItems[index - 1], newItems[index]] = [newItems[index], newItems[index - 1]];
      onChange(newItems);
    },
    [items, onChange]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index >= items.length - 1) return;
      const newItems = [...items];
      [newItems[index], newItems[index + 1]] = [newItems[index + 1], newItems[index]];
      onChange(newItems);
    },
    [items, onChange]
  );

  // Inline editing handlers
  const handleStartEdit = useCallback(
    (index: number) => {
      if (disabled) return;
      setEditingIndex(index);
      setEditValue(items[index]);
    },
    [disabled, items]
  );

  const handleSaveEdit = useCallback(() => {
    if (editingIndex === null) return;
    const trimmed = editValue.trim();
    if (trimmed) {
      const newItems = [...items];
      newItems[editingIndex] = trimmed;
      onChange(newItems);
    }
    setEditingIndex(null);
    setEditValue('');
  }, [editingIndex, editValue, items, onChange]);

  const handleCancelEdit = useCallback(() => {
    setEditingIndex(null);
    setEditValue('');
  }, []);

  const handleEditKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Cmd/Ctrl+Enter to save
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSaveEdit();
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCancelEdit();
      }
    },
    [handleSaveEdit, handleCancelEdit]
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
          {items.length === 0 ? (
            <li className="py-6 text-center text-warm-gray-400 text-sm">
              No items yet. Add one below.
            </li>
          ) : (
            items.map((item, index) => (
              <li
                key={`${item}-${index}`}
                className="flex items-start gap-2 py-2 px-3 bg-white hover:bg-cream-50 transition-colors duration-100"
              >
                {/* Bullet marker */}
                <span className="text-palm-500 text-lg leading-none mt-0.5" aria-hidden="true">
                  •
                </span>

                {/* Item text or edit textarea */}
                {editingIndex === index ? (
                  <div className="flex-1 min-w-0">
                    <textarea
                      ref={editTextareaRef}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={handleSaveEdit}
                      onKeyDown={handleEditKeyDown}
                      rows={3}
                      className="
                        w-full px-2 py-1.5 text-sm text-warm-gray-900
                        bg-white border-2 border-palm-400 rounded-sm
                        focus:outline-none resize-y min-h-[60px]
                      "
                    />
                    <p className="text-xs text-warm-gray-400 mt-1">
                      Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘Enter</kbd> to save or{' '}
                      <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel
                    </p>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => handleStartEdit(index)}
                    disabled={disabled}
                    className={`
                      flex-1 text-left text-sm text-warm-gray-800 min-w-0 break-words
                      ${disabled ? 'cursor-default' : 'cursor-text hover:bg-cream-100 rounded px-1 -mx-1'}
                    `}
                  >
                    {item}
                  </button>
                )}

                {/* Reorder & delete buttons */}
                {!disabled && editingIndex !== index && (
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
                      disabled={index === items.length - 1}
                      className={`
                        p-1 rounded-sm transition-colors duration-150
                        focus:outline-none focus:ring-2 focus:ring-palm-400 focus:ring-offset-1
                        ${
                          index === items.length - 1
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
