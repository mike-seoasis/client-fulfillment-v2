/**
 * Step 6: Proof & Examples
 *
 * Statistics, credentials, quotes, guarantees, and example content.
 *
 * Features:
 * - Statistics with context
 * - Customer quotes
 * - Credentials and certifications
 * - Good/bad example pairs for headlines, descriptions, CTAs
 */

import { cn } from '@/lib/utils'
import { useState } from 'react'
import { WizardStepHeader } from '../WizardContainer'
import { ChipInput } from '../ChipInput'
import { ExampleEditor } from '../ExampleEditor'
import { Button } from '@/components/ui/button'
import { Plus, Trash2, Quote, BarChart3, Award, Shield } from 'lucide-react'
import type { WizardStepBaseProps, ProofElements, ExamplesBank } from '../types'

/** Default proof elements */
const DEFAULT_PROOF_ELEMENTS: ProofElements = {
  statistics: [],
  credentials: [],
  customer_quotes: [],
  guarantees: [],
  certifications: [],
}

/** Default examples bank */
const DEFAULT_EXAMPLES_BANK: ExamplesBank = {
  headlines: [],
  product_descriptions: [],
  ctas: [],
  email_subject_lines: [],
  social_posts: [],
}

/**
 * Step6ProofExamples - proof elements and examples step
 */
export function Step6ProofExamples({
  formData,
  onChange,
  disabled = false,
  className,
}: WizardStepBaseProps) {
  const proof = formData.proof_elements || DEFAULT_PROOF_ELEMENTS
  const examples = formData.examples_bank || DEFAULT_EXAMPLES_BANK
  const [activeTab, setActiveTab] = useState<'proof' | 'examples'>('proof')

  const updateProof = (updates: Partial<ProofElements>) => {
    onChange({
      proof_elements: {
        ...proof,
        ...updates,
      },
    })
  }

  const updateExamples = (updates: Partial<ExamplesBank>) => {
    onChange({
      examples_bank: {
        ...examples,
        ...updates,
      },
    })
  }

  return (
    <div className={cn('space-y-8', className)}>
      <WizardStepHeader
        title="Proof & Examples"
        description="Add credibility signals and example content. These help AI generate persuasive, on-brand content."
      />

      {/* Tab navigation */}
      <div className="flex border-b border-cream-200">
        <button
          type="button"
          onClick={() => setActiveTab('proof')}
          className={cn(
            'px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'proof'
              ? 'border-primary-500 text-primary-700'
              : 'border-transparent text-warmgray-500 hover:text-warmgray-700'
          )}
        >
          Proof Elements
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('examples')}
          className={cn(
            'px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors',
            activeTab === 'examples'
              ? 'border-primary-500 text-primary-700'
              : 'border-transparent text-warmgray-500 hover:text-warmgray-700'
          )}
        >
          Example Content
        </button>
      </div>

      {/* Proof Elements Tab */}
      {activeTab === 'proof' && (
        <div className="space-y-8">
          {/* Statistics */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <BarChart3 className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-medium text-warmgray-900">
                Statistics & Numbers
              </h3>
            </div>
            <StatisticsList
              statistics={proof.statistics}
              onChange={(v) => updateProof({ statistics: v })}
              disabled={disabled}
            />
          </section>

          {/* Customer Quotes */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <Quote className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-medium text-warmgray-900">
                Customer Quotes
              </h3>
            </div>
            <QuotesList
              quotes={proof.customer_quotes}
              onChange={(v) => updateProof({ customer_quotes: v })}
              disabled={disabled}
            />
          </section>

          {/* Credentials & Certifications */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <Award className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-medium text-warmgray-900">
                Credentials & Certifications
              </h3>
            </div>
            <div className="space-y-4">
              <ChipInput
                label="Credentials"
                values={proof.credentials}
                onChange={(v) => updateProof({ credentials: v })}
                placeholder="Add credential (e.g., Industry Leader, Founded 2010)"
                disabled={disabled}
                maxChips={10}
              />
              <ChipInput
                label="Certifications"
                values={proof.certifications}
                onChange={(v) => updateProof({ certifications: v })}
                placeholder="Add certification (e.g., ISO 9001, B Corp)"
                disabled={disabled}
                maxChips={10}
              />
            </div>
          </section>

          {/* Guarantees */}
          <section>
            <div className="flex items-center gap-3 mb-4">
              <Shield className="w-5 h-5 text-primary-600" />
              <h3 className="text-lg font-medium text-warmgray-900">
                Guarantees & Promises
              </h3>
            </div>
            <ChipInput
              values={proof.guarantees}
              onChange={(v) => updateProof({ guarantees: v })}
              placeholder="Add guarantee (e.g., 30-day money back, Free shipping)"
              disabled={disabled}
              maxChips={10}
            />
          </section>
        </div>
      )}

      {/* Examples Tab */}
      {activeTab === 'examples' && (
        <div className="space-y-8">
          <ExampleEditor
            label="Headlines"
            examples={examples.headlines}
            onChange={(v) => updateExamples({ headlines: v })}
            goodPlaceholder="Machines Built for All-Day Sessions"
            badPlaceholder="Revolutionary game-changing solutions!"
            disabled={disabled}
            maxExamples={5}
          />

          <ExampleEditor
            label="Product Descriptions"
            examples={examples.product_descriptions}
            onChange={(v) => updateExamples({ product_descriptions: v })}
            goodPlaceholder="Clean lines and thoughtful details..."
            badPlaceholder="The most amazing product ever created..."
            disabled={disabled}
            maxExamples={5}
          />

          <ExampleEditor
            label="Calls to Action"
            examples={examples.ctas}
            onChange={(v) => updateExamples({ ctas: v })}
            goodPlaceholder="See What Sets Us Apart"
            badPlaceholder="BUY NOW!!!"
            disabled={disabled}
            maxExamples={5}
          />

          <ExampleEditor
            label="Email Subject Lines"
            examples={examples.email_subject_lines}
            onChange={(v) => updateExamples({ email_subject_lines: v })}
            goodPlaceholder="Your order is ready"
            badPlaceholder="URGENT: Don't miss this!!!!"
            disabled={disabled}
            maxExamples={5}
          />

          <ExampleEditor
            label="Social Posts"
            examples={examples.social_posts}
            onChange={(v) => updateExamples({ social_posts: v })}
            goodPlaceholder="Behind the scenes at our workshop..."
            badPlaceholder="Follow us for more amazing content!"
            disabled={disabled}
            maxExamples={5}
          />
        </div>
      )}

      {/* Help text */}
      <div className="text-sm text-warmgray-500 bg-warmgray-50 rounded-lg p-4">
        <p className="font-medium text-warmgray-700 mb-2">
          {activeTab === 'proof' ? 'Proof element tips:' : 'Example content tips:'}
        </p>
        <ul className="space-y-1 list-disc list-inside">
          {activeTab === 'proof' ? (
            <>
              <li>Use specific numbers - "93% satisfaction" beats "high satisfaction"</li>
              <li>Include context for statistics to make them meaningful</li>
              <li>Customer quotes should feel authentic, not overly polished</li>
              <li>List certifications that matter to your target audience</li>
            </>
          ) : (
            <>
              <li>Show real examples from your brand or create ideal ones</li>
              <li>Bad examples help AI understand what to avoid</li>
              <li>Explanations help AI understand the "why" behind good examples</li>
              <li>Focus on the types of content you'll generate most often</li>
            </>
          )}
        </ul>
      </div>
    </div>
  )
}

/** Statistics list component */
function StatisticsList({
  statistics,
  onChange,
  disabled,
}: {
  statistics: ProofElements['statistics']
  onChange: (value: ProofElements['statistics']) => void
  disabled?: boolean
}) {
  const addStat = () => {
    onChange([...statistics, { stat: '', context: '', source: '' }])
  }

  const updateStat = (index: number, updates: Partial<ProofElements['statistics'][0]>) => {
    const newStats = [...statistics]
    newStats[index] = { ...newStats[index], ...updates }
    onChange(newStats)
  }

  const removeStat = (index: number) => {
    onChange(statistics.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      {statistics.map((stat, index) => (
        <div key={index} className="flex gap-3 p-4 bg-cream-50 rounded-lg border border-cream-200">
          <div className="flex-1 grid md:grid-cols-3 gap-3">
            <input
              type="text"
              value={stat.stat}
              onChange={(e) => updateStat(index, { stat: e.target.value })}
              placeholder="Statistic (e.g., 10,000+ customers)"
              disabled={disabled}
              className={cn(
                'px-3 py-2 text-sm border border-cream-200 rounded-md',
                'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                disabled && 'bg-cream-100'
              )}
            />
            <input
              type="text"
              value={stat.context || ''}
              onChange={(e) => updateStat(index, { context: e.target.value })}
              placeholder="Context (optional)"
              disabled={disabled}
              className={cn(
                'px-3 py-2 text-sm border border-cream-200 rounded-md',
                'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                disabled && 'bg-cream-100'
              )}
            />
            <input
              type="text"
              value={stat.source || ''}
              onChange={(e) => updateStat(index, { source: e.target.value })}
              placeholder="Source (optional)"
              disabled={disabled}
              className={cn(
                'px-3 py-2 text-sm border border-cream-200 rounded-md',
                'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                disabled && 'bg-cream-100'
              )}
            />
          </div>
          {!disabled && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => removeStat(index)}
              className="shrink-0 text-warmgray-400 hover:text-error-600"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      ))}

      {!disabled && statistics.length < 10 && (
        <Button type="button" variant="outline" onClick={addStat} className="w-full">
          <Plus className="w-4 h-4 mr-2" />
          Add statistic
        </Button>
      )}
    </div>
  )
}

/** Customer quotes list component */
function QuotesList({
  quotes,
  onChange,
  disabled,
}: {
  quotes: ProofElements['customer_quotes']
  onChange: (value: ProofElements['customer_quotes']) => void
  disabled?: boolean
}) {
  const addQuote = () => {
    onChange([...quotes, { quote: '', attribution: '', context: '' }])
  }

  const updateQuote = (index: number, updates: Partial<ProofElements['customer_quotes'][0]>) => {
    const newQuotes = [...quotes]
    newQuotes[index] = { ...newQuotes[index], ...updates }
    onChange(newQuotes)
  }

  const removeQuote = (index: number) => {
    onChange(quotes.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      {quotes.map((quote, index) => (
        <div key={index} className="p-4 bg-cream-50 rounded-lg border border-cream-200">
          <div className="flex gap-3">
            <div className="flex-1 space-y-3">
              <textarea
                value={quote.quote}
                onChange={(e) => updateQuote(index, { quote: e.target.value })}
                placeholder="Customer quote..."
                disabled={disabled}
                rows={2}
                className={cn(
                  'w-full px-3 py-2 text-sm border border-cream-200 rounded-md resize-y',
                  'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                  disabled && 'bg-cream-100'
                )}
              />
              <div className="grid md:grid-cols-2 gap-3">
                <input
                  type="text"
                  value={quote.attribution || ''}
                  onChange={(e) => updateQuote(index, { attribution: e.target.value })}
                  placeholder="Attribution (e.g., John D., CEO)"
                  disabled={disabled}
                  className={cn(
                    'px-3 py-2 text-sm border border-cream-200 rounded-md',
                    'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                    disabled && 'bg-cream-100'
                  )}
                />
                <input
                  type="text"
                  value={quote.context || ''}
                  onChange={(e) => updateQuote(index, { context: e.target.value })}
                  placeholder="Context (optional)"
                  disabled={disabled}
                  className={cn(
                    'px-3 py-2 text-sm border border-cream-200 rounded-md',
                    'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
                    disabled && 'bg-cream-100'
                  )}
                />
              </div>
            </div>
            {!disabled && (
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeQuote(index)}
                className="shrink-0 text-warmgray-400 hover:text-error-600"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      ))}

      {!disabled && quotes.length < 10 && (
        <Button type="button" variant="outline" onClick={addQuote} className="w-full">
          <Plus className="w-4 h-4 mr-2" />
          Add quote
        </Button>
      )}
    </div>
  )
}
