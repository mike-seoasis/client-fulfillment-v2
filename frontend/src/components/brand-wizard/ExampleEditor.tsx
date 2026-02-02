/**
 * ExampleEditor component for editing good/bad example pairs
 *
 * Used for headlines, product descriptions, CTAs, etc.
 * Shows side-by-side good/bad examples with explanations.
 *
 * Features:
 * - Good example (required)
 * - Bad example (optional)
 * - Explanation field
 * - Add/remove examples
 */

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Plus, Trash2, ThumbsUp, ThumbsDown } from 'lucide-react'

export interface ExamplePair {
  good: string
  bad?: string
  explanation?: string
}

export interface ExampleEditorProps {
  /** Label for the example group */
  label: string
  /** Current examples */
  examples: ExamplePair[]
  /** Callback when examples change */
  onChange: (examples: ExamplePair[]) => void
  /** Whether to require bad examples */
  requireBad?: boolean
  /** Placeholder for good example */
  goodPlaceholder?: string
  /** Placeholder for bad example */
  badPlaceholder?: string
  /** Maximum number of examples */
  maxExamples?: number
  /** Whether editing is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}

/**
 * ExampleEditor for managing good/bad example pairs
 *
 * @example
 * <ExampleEditor
 *   label="Headlines"
 *   examples={headlines}
 *   onChange={setHeadlines}
 *   goodPlaceholder="Machines Built for All-Day Sessions"
 *   badPlaceholder="Revolutionary game-changing tattoo solutions!"
 * />
 */
export function ExampleEditor({
  label,
  examples,
  onChange,
  requireBad = false,
  goodPlaceholder = 'Write a good example...',
  badPlaceholder = 'Write what to avoid...',
  maxExamples = 10,
  disabled = false,
  className,
}: ExampleEditorProps) {
  const addExample = () => {
    if (examples.length >= maxExamples) return
    onChange([...examples, { good: '', bad: '', explanation: '' }])
  }

  const updateExample = (index: number, updated: ExamplePair) => {
    const newExamples = [...examples]
    newExamples[index] = updated
    onChange(newExamples)
  }

  const removeExample = (index: number) => {
    onChange(examples.filter((_, i) => i !== index))
  }

  const canAdd = examples.length < maxExamples && !disabled

  return (
    <div className={cn('space-y-4', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-warmgray-700">
          {label}
          <span className="ml-2 text-warmgray-400 font-normal">
            ({examples.length}/{maxExamples})
          </span>
        </label>
        {canAdd && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={addExample}
          >
            <Plus className="w-4 h-4 mr-1" />
            Add example
          </Button>
        )}
      </div>

      {/* Examples list */}
      {examples.length === 0 ? (
        <div className="text-center py-8 bg-cream-50 rounded-lg border border-dashed border-cream-300">
          <p className="text-sm text-warmgray-500">
            No examples yet. Add your first example to help define your brand voice.
          </p>
          {canAdd && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={addExample}
              className="mt-3"
            >
              <Plus className="w-4 h-4 mr-1" />
              Add first example
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          {examples.map((example, index) => (
            <ExamplePairCard
              key={index}
              example={example}
              onChange={(updated) => updateExample(index, updated)}
              onRemove={() => removeExample(index)}
              requireBad={requireBad}
              goodPlaceholder={goodPlaceholder}
              badPlaceholder={badPlaceholder}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** Individual example pair card */
function ExamplePairCard({
  example,
  onChange,
  onRemove,
  requireBad,
  goodPlaceholder,
  badPlaceholder,
  disabled,
}: {
  example: ExamplePair
  onChange: (example: ExamplePair) => void
  onRemove: () => void
  requireBad?: boolean
  goodPlaceholder?: string
  badPlaceholder?: string
  disabled?: boolean
}) {
  return (
    <div className="bg-white border border-cream-200 rounded-lg overflow-hidden">
      <div className="grid md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-cream-200">
        {/* Good example */}
        <div className="p-4">
          <label className="flex items-center gap-2 text-xs font-medium text-success-600 mb-2">
            <ThumbsUp className="w-3.5 h-3.5" />
            Good Example
          </label>
          <textarea
            value={example.good}
            onChange={(e) => onChange({ ...example, good: e.target.value })}
            placeholder={goodPlaceholder}
            disabled={disabled}
            className={cn(
              'w-full px-3 py-2 text-sm border border-cream-200 rounded-md resize-y min-h-[80px]',
              'focus:border-success-400 focus:ring-1 focus:ring-success-400',
              disabled && 'bg-cream-50'
            )}
          />
        </div>

        {/* Bad example */}
        <div className="p-4">
          <label className="flex items-center gap-2 text-xs font-medium text-error-600 mb-2">
            <ThumbsDown className="w-3.5 h-3.5" />
            Bad Example {!requireBad && <span className="text-warmgray-400 font-normal">(optional)</span>}
          </label>
          <textarea
            value={example.bad || ''}
            onChange={(e) => onChange({ ...example, bad: e.target.value })}
            placeholder={badPlaceholder}
            disabled={disabled}
            className={cn(
              'w-full px-3 py-2 text-sm border border-cream-200 rounded-md resize-y min-h-[80px]',
              'focus:border-error-400 focus:ring-1 focus:ring-error-400',
              disabled && 'bg-cream-50'
            )}
          />
        </div>
      </div>

      {/* Explanation and actions */}
      <div className="px-4 py-3 bg-cream-50 border-t border-cream-200 flex items-start gap-4">
        <div className="flex-1">
          <label className="text-xs text-warmgray-500 mb-1 block">
            Why? (optional explanation)
          </label>
          <input
            type="text"
            value={example.explanation || ''}
            onChange={(e) => onChange({ ...example, explanation: e.target.value })}
            placeholder="Explain why the good example works better..."
            disabled={disabled}
            className={cn(
              'w-full px-3 py-1.5 text-sm border border-cream-200 rounded-md',
              'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
              disabled && 'bg-cream-100'
            )}
          />
        </div>
        {!disabled && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onRemove}
            className="text-warmgray-400 hover:text-error-600 hover:bg-error-50 mt-5"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
