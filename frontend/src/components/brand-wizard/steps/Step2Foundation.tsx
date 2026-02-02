/**
 * Step 2: Foundation
 *
 * Company info, positioning, mission/values, and differentiators.
 *
 * Features:
 * - Company overview section
 * - Products/services section
 * - Brand positioning section
 * - Mission & values section
 * - Differentiators section
 */

import { cn } from '@/lib/utils'
import { WizardStepHeader } from '../WizardContainer'
import { ChipInput } from '../ChipInput'
import type { WizardStepBaseProps } from '../types'

/**
 * Step2Foundation - foundation step for company details
 */
export function Step2Foundation({
  formData,
  onChange,
  disabled = false,
  className,
}: WizardStepBaseProps) {
  const foundation = formData.foundation || {}

  const updateFoundation = (section: string, field: string, value: unknown) => {
    onChange({
      foundation: {
        ...foundation,
        [section]: {
          ...(foundation[section as keyof typeof foundation] as object || {}),
          [field]: value,
        },
      },
    })
  }

  return (
    <div className={cn('space-y-10', className)}>
      <WizardStepHeader
        title="Brand Foundation"
        description="Define the core facts about your company - who you are, what you do, and what makes you different."
      />

      {/* Company Overview */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Company Overview
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <InputField
            label="Company Name"
            value={foundation.company_overview?.name}
            onChange={(v) => updateFoundation('company_overview', 'name', v)}
            placeholder="Legal company name"
            disabled={disabled}
          />
          <InputField
            label="Founded"
            value={foundation.company_overview?.founded}
            onChange={(v) => updateFoundation('company_overview', 'founded', v)}
            placeholder="e.g., 2015"
            disabled={disabled}
          />
          <InputField
            label="Location"
            value={foundation.company_overview?.location}
            onChange={(v) => updateFoundation('company_overview', 'location', v)}
            placeholder="HQ and relevant locations"
            disabled={disabled}
          />
          <InputField
            label="Industry"
            value={foundation.company_overview?.industry}
            onChange={(v) => updateFoundation('company_overview', 'industry', v)}
            placeholder="Primary industry/category"
            disabled={disabled}
          />
          <div className="md:col-span-2">
            <InputField
              label="Business Model"
              value={foundation.company_overview?.business_model}
              onChange={(v) => updateFoundation('company_overview', 'business_model', v)}
              placeholder="B2B, B2C, DTC, Marketplace, etc."
              disabled={disabled}
            />
          </div>
        </div>
      </section>

      {/* Products & Services */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Products & Services
        </h3>
        <div className="space-y-4">
          <ChipInput
            label="Primary Products/Services"
            values={foundation.products_services?.primary || []}
            onChange={(v) => updateFoundation('products_services', 'primary', v)}
            placeholder="Add primary offering..."
            disabled={disabled}
          />
          <ChipInput
            label="Secondary Offerings"
            values={foundation.products_services?.secondary || []}
            onChange={(v) => updateFoundation('products_services', 'secondary', v)}
            placeholder="Add supporting offering..."
            disabled={disabled}
          />
          <div className="grid md:grid-cols-2 gap-4">
            <SelectField
              label="Price Point"
              value={foundation.products_services?.price_point}
              onChange={(v) => updateFoundation('products_services', 'price_point', v)}
              options={[
                { value: '', label: 'Select price positioning...' },
                { value: 'budget', label: 'Budget' },
                { value: 'mid-range', label: 'Mid-range' },
                { value: 'premium', label: 'Premium' },
                { value: 'luxury', label: 'Luxury' },
              ]}
              disabled={disabled}
            />
            <div />
          </div>
          <ChipInput
            label="Sales Channels"
            values={foundation.products_services?.sales_channels || []}
            onChange={(v) => updateFoundation('products_services', 'sales_channels', v)}
            placeholder="Add channel (Online, Retail, Wholesale...)"
            disabled={disabled}
          />
        </div>
      </section>

      {/* Brand Positioning */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Brand Positioning
        </h3>
        <div className="space-y-4">
          <InputField
            label="Tagline"
            value={foundation.positioning?.tagline}
            onChange={(v) => updateFoundation('positioning', 'tagline', v)}
            placeholder="Your brand tagline or slogan"
            disabled={disabled}
          />
          <TextAreaField
            label="One-Sentence Description"
            value={foundation.positioning?.one_sentence}
            onChange={(v) => updateFoundation('positioning', 'one_sentence', v)}
            placeholder="A single sentence that captures what your company does"
            disabled={disabled}
          />
          <SelectField
            label="Category Position"
            value={foundation.positioning?.category_position}
            onChange={(v) => updateFoundation('positioning', 'category_position', v)}
            options={[
              { value: '', label: 'Select position...' },
              { value: 'leader', label: 'Market Leader' },
              { value: 'challenger', label: 'Challenger' },
              { value: 'specialist', label: 'Specialist/Niche' },
              { value: 'disruptor', label: 'Disruptor' },
            ]}
            disabled={disabled}
          />
        </div>
      </section>

      {/* Mission & Values */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Mission & Values
        </h3>
        <div className="space-y-4">
          <TextAreaField
            label="Mission Statement"
            value={foundation.mission_values?.mission_statement}
            onChange={(v) => updateFoundation('mission_values', 'mission_statement', v)}
            placeholder="Why does your company exist?"
            disabled={disabled}
          />
          <ChipInput
            label="Core Values"
            values={foundation.mission_values?.core_values || []}
            onChange={(v) => updateFoundation('mission_values', 'core_values', v)}
            placeholder="Add core value (3-5 guiding principles)"
            maxChips={5}
            disabled={disabled}
          />
          <TextAreaField
            label="Brand Promise"
            value={foundation.mission_values?.brand_promise}
            onChange={(v) => updateFoundation('mission_values', 'brand_promise', v)}
            placeholder="What can customers always expect from you?"
            disabled={disabled}
          />
        </div>
      </section>

      {/* Differentiators */}
      <section>
        <h3 className="text-lg font-medium text-warmgray-900 mb-4">
          Differentiators
        </h3>
        <div className="space-y-4">
          <TextAreaField
            label="Primary USP"
            value={foundation.differentiators?.primary_usp}
            onChange={(v) => updateFoundation('differentiators', 'primary_usp', v)}
            placeholder="The #1 thing that makes you different"
            disabled={disabled}
          />
          <ChipInput
            label="Supporting Differentiators"
            values={foundation.differentiators?.supporting || []}
            onChange={(v) => updateFoundation('differentiators', 'supporting', v)}
            placeholder="Add supporting unique factor"
            maxChips={5}
            disabled={disabled}
          />
          <ChipInput
            label="What We Are NOT"
            values={foundation.differentiators?.what_we_are_not || []}
            onChange={(v) => updateFoundation('differentiators', 'what_we_are_not', v)}
            placeholder="Add positioning you reject"
            disabled={disabled}
          />
        </div>
      </section>
    </div>
  )
}

/** Simple input field helper */
function InputField({
  label,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string
  value?: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-warmgray-700 mb-1.5">
        {label}
      </label>
      <input
        type="text"
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          'w-full px-3 py-2 text-sm border border-cream-200 rounded-lg',
          'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
          'placeholder:text-warmgray-400',
          disabled && 'bg-cream-50 cursor-not-allowed'
        )}
      />
    </div>
  )
}

/** Textarea field helper */
function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  label: string
  value?: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-warmgray-700 mb-1.5">
        {label}
      </label>
      <textarea
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        rows={3}
        className={cn(
          'w-full px-3 py-2 text-sm border border-cream-200 rounded-lg resize-y',
          'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
          'placeholder:text-warmgray-400',
          disabled && 'bg-cream-50 cursor-not-allowed'
        )}
      />
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
