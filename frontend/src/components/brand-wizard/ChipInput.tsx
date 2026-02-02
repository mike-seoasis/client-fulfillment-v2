/**
 * ChipInput component for adding/removing string values as chips
 *
 * Used for power words, banned words, values, etc.
 *
 * Features:
 * - Add chips by typing and pressing Enter
 * - Remove chips by clicking X
 * - Keyboard navigation
 * - Paste multiple (comma-separated)
 */

import { cn } from '@/lib/utils'
import { useState, useRef, KeyboardEvent, useId } from 'react'
import { X, Plus } from 'lucide-react'

export interface ChipInputProps {
  /** Current values */
  values: string[]
  /** Callback when values change */
  onChange: (values: string[]) => void
  /** Label for the input */
  label?: string
  /** Placeholder text */
  placeholder?: string
  /** Maximum number of chips allowed */
  maxChips?: number
  /** Whether the input is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}

/**
 * ChipInput for managing lists of string values
 *
 * @example
 * <ChipInput
 *   label="Power Words"
 *   values={powerWords}
 *   onChange={setPowerWords}
 *   placeholder="Add a power word..."
 * />
 */
export function ChipInput({
  values,
  onChange,
  label,
  placeholder = 'Add item...',
  maxChips = 50,
  disabled = false,
  className,
}: ChipInputProps) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const id = useId()

  const addChip = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (values.includes(trimmed)) return // No duplicates
    if (values.length >= maxChips) return

    onChange([...values, trimmed])
    setInputValue('')
  }

  const removeChip = (index: number) => {
    onChange(values.filter((_, i) => i !== index))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addChip(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && values.length > 0) {
      // Remove last chip when backspacing on empty input
      removeChip(values.length - 1)
    } else if (e.key === ',' && inputValue) {
      e.preventDefault()
      addChip(inputValue.replace(',', ''))
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text')
    // Split by comma or newline
    const items = pasted.split(/[,\n]+/).map((s) => s.trim()).filter(Boolean)
    const newValues = [...values]
    for (const item of items) {
      if (!newValues.includes(item) && newValues.length < maxChips) {
        newValues.push(item)
      }
    }
    onChange(newValues)
  }

  const atLimit = values.length >= maxChips

  return (
    <div className={cn('space-y-2', className)}>
      {label && (
        <label htmlFor={id} className="block text-sm font-medium text-warmgray-700">
          {label}
          {maxChips && (
            <span className="ml-2 text-warmgray-400 font-normal">
              ({values.length}/{maxChips})
            </span>
          )}
        </label>
      )}

      <div
        className={cn(
          'min-h-[80px] p-3 bg-white border border-cream-200 rounded-lg',
          'focus-within:border-primary-400 focus-within:ring-1 focus-within:ring-primary-400',
          disabled && 'bg-cream-50 cursor-not-allowed'
        )}
        onClick={() => inputRef.current?.focus()}
      >
        <div className="flex flex-wrap gap-2">
          {/* Chips */}
          {values.map((value, index) => (
            <span
              key={index}
              className={cn(
                'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm',
                'bg-primary-100 text-primary-700'
              )}
            >
              {value}
              {!disabled && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeChip(index)
                  }}
                  className="p-0.5 hover:bg-primary-200 rounded-full transition-colors"
                  aria-label={`Remove ${value}`}
                >
                  <X className="w-3 h-3" />
                </button>
              )}
            </span>
          ))}

          {/* Input */}
          {!disabled && !atLimit && (
            <input
              ref={inputRef}
              id={id}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={values.length === 0 ? placeholder : ''}
              className={cn(
                'flex-1 min-w-[120px] bg-transparent border-none outline-none text-sm',
                'placeholder:text-warmgray-400'
              )}
            />
          )}
        </div>
      </div>

      {/* Helper text */}
      <p className="text-xs text-warmgray-500">
        Press Enter or comma to add. Paste multiple items separated by commas.
      </p>
    </div>
  )
}
