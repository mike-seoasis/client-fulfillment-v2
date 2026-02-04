'use client';

import { useState, useCallback } from 'react';
import { Button, Input, Textarea } from '@/components/ui';
import { BulletListEditor } from './BulletListEditor';
import { type BrandFoundationData } from '../types';

interface BrandFoundationEditorProps {
  /** The brand foundation data to edit */
  data: BrandFoundationData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: BrandFoundationData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

interface ValidationErrors {
  company_name?: string;
  tagline?: string;
  mission_statement?: string;
}

/**
 * Editor component for Brand Foundation section.
 * Provides form-based editing for company info, positioning, values, and differentiators.
 */
export function BrandFoundationEditor({
  data,
  isSaving = false,
  onSave,
  onCancel,
}: BrandFoundationEditorProps) {
  // Initialize form state from data
  const [companyName, setCompanyName] = useState(data?.company_overview?.company_name ?? '');
  const [founded, setFounded] = useState(data?.company_overview?.founded ?? '');
  const [location, setLocation] = useState(data?.company_overview?.location ?? '');
  const [industry, setIndustry] = useState(data?.company_overview?.industry ?? '');
  const [businessModel, setBusinessModel] = useState(data?.company_overview?.business_model ?? '');

  const [primaryProducts, setPrimaryProducts] = useState(data?.what_they_sell?.primary_products ?? '');
  const [secondaryOfferings, setSecondaryOfferings] = useState(data?.what_they_sell?.secondary_offerings ?? '');
  const [pricePoint, setPricePoint] = useState(data?.what_they_sell?.price_point ?? '');
  const [salesChannels, setSalesChannels] = useState(data?.what_they_sell?.sales_channels ?? '');

  const [tagline, setTagline] = useState(data?.brand_positioning?.tagline ?? '');
  const [oneSentence, setOneSentence] = useState(data?.brand_positioning?.one_sentence_description ?? '');
  const [categoryPosition, setCategoryPosition] = useState(data?.brand_positioning?.category_position ?? '');

  const [missionStatement, setMissionStatement] = useState(data?.mission_and_values?.mission_statement ?? '');
  const [coreValues, setCoreValues] = useState<string[]>(data?.mission_and_values?.core_values ?? []);
  const [brandPromise, setBrandPromise] = useState(data?.mission_and_values?.brand_promise ?? '');

  const [primaryUsp, setPrimaryUsp] = useState(data?.differentiators?.primary_usp ?? '');
  const [supportingDifferentiators, setSupportingDifferentiators] = useState<string[]>(
    data?.differentiators?.supporting_differentiators ?? []
  );
  const [whatWeAreNot, setWhatWeAreNot] = useState<string[]>(data?.differentiators?.what_we_are_not ?? []);

  const [errors, setErrors] = useState<ValidationErrors>({});

  const validate = useCallback((): boolean => {
    const newErrors: ValidationErrors = {};

    if (!companyName.trim()) {
      newErrors.company_name = 'Company name is required';
    }

    if (!tagline.trim()) {
      newErrors.tagline = 'Tagline is required';
    }

    if (!missionStatement.trim()) {
      newErrors.mission_statement = 'Mission statement is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [companyName, tagline, missionStatement]);

  const handleSave = useCallback(() => {
    if (!validate()) {
      return;
    }

    const updatedData: BrandFoundationData = {
      company_overview: {
        company_name: companyName.trim(),
        founded: founded.trim() || undefined,
        location: location.trim() || undefined,
        industry: industry.trim() || undefined,
        business_model: businessModel.trim() || undefined,
      },
      what_they_sell: {
        primary_products: primaryProducts.trim() || undefined,
        secondary_offerings: secondaryOfferings.trim() || undefined,
        price_point: pricePoint.trim() || undefined,
        sales_channels: salesChannels.trim() || undefined,
      },
      brand_positioning: {
        tagline: tagline.trim(),
        one_sentence_description: oneSentence.trim() || undefined,
        category_position: categoryPosition.trim() || undefined,
      },
      mission_and_values: {
        mission_statement: missionStatement.trim(),
        core_values: coreValues.length > 0 ? coreValues : undefined,
        brand_promise: brandPromise.trim() || undefined,
      },
      differentiators: {
        primary_usp: primaryUsp.trim() || undefined,
        supporting_differentiators: supportingDifferentiators.length > 0 ? supportingDifferentiators : undefined,
        what_we_are_not: whatWeAreNot.length > 0 ? whatWeAreNot : undefined,
      },
    };

    onSave(updatedData);
  }, [
    validate,
    companyName,
    founded,
    location,
    industry,
    businessModel,
    primaryProducts,
    secondaryOfferings,
    pricePoint,
    salesChannels,
    tagline,
    oneSentence,
    categoryPosition,
    missionStatement,
    coreValues,
    brandPromise,
    primaryUsp,
    supportingDifferentiators,
    whatWeAreNot,
    onSave,
  ]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      // Save on Cmd/Ctrl + S
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      // Cancel on Escape
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
      }
    },
    [handleSave, onCancel]
  );

  return (
    <div className="space-y-6" onKeyDown={handleKeyDown}>
      {/* Instructions */}
      <div className="bg-cream-50 border border-cream-300 rounded-sm p-3">
        <p className="text-sm text-warm-gray-600 mb-1">
          Edit your brand foundation below. Required fields are marked with *.
        </p>
        <p className="text-xs text-warm-gray-500">
          Press <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">⌘S</kbd> to save or{' '}
          <kbd className="px-1 py-0.5 bg-cream-200 rounded text-xs">Esc</kbd> to cancel.
        </p>
      </div>

      {/* Company Overview */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Company Overview
        </h3>
        <div className="space-y-4">
          <Input
            label="Company Name *"
            value={companyName}
            onChange={(e) => {
              setCompanyName(e.target.value);
              if (errors.company_name) setErrors((prev) => ({ ...prev, company_name: undefined }));
            }}
            error={errors.company_name}
            placeholder="Enter company name"
            disabled={isSaving}
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Founded"
              value={founded}
              onChange={(e) => setFounded(e.target.value)}
              placeholder="e.g., 2015"
              disabled={isSaving}
            />
            <Input
              label="Location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., Austin, TX"
              disabled={isSaving}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Industry"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g., Health & Wellness"
              disabled={isSaving}
            />
            <Input
              label="Business Model"
              value={businessModel}
              onChange={(e) => setBusinessModel(e.target.value)}
              placeholder="e.g., DTC E-commerce"
              disabled={isSaving}
            />
          </div>
        </div>
      </section>

      {/* What They Sell */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          What They Sell
        </h3>
        <div className="space-y-4">
          <Textarea
            label="Primary Products"
            value={primaryProducts}
            onChange={(e) => setPrimaryProducts(e.target.value)}
            placeholder="Describe the main products or services"
            disabled={isSaving}
            className="min-h-[80px]"
          />
          <Textarea
            label="Secondary Offerings"
            value={secondaryOfferings}
            onChange={(e) => setSecondaryOfferings(e.target.value)}
            placeholder="Any additional products or services"
            disabled={isSaving}
            className="min-h-[60px]"
          />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Price Point"
              value={pricePoint}
              onChange={(e) => setPricePoint(e.target.value)}
              placeholder="e.g., Premium, Mid-range"
              disabled={isSaving}
            />
            <Input
              label="Sales Channels"
              value={salesChannels}
              onChange={(e) => setSalesChannels(e.target.value)}
              placeholder="e.g., Website, Amazon"
              disabled={isSaving}
            />
          </div>
        </div>
      </section>

      {/* Brand Positioning */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Brand Positioning
        </h3>
        <div className="space-y-4">
          <Input
            label="Tagline *"
            value={tagline}
            onChange={(e) => {
              setTagline(e.target.value);
              if (errors.tagline) setErrors((prev) => ({ ...prev, tagline: undefined }));
            }}
            error={errors.tagline}
            placeholder="Enter brand tagline"
            disabled={isSaving}
          />
          <Textarea
            label="One-Sentence Description"
            value={oneSentence}
            onChange={(e) => setOneSentence(e.target.value)}
            placeholder="A single sentence that captures what the brand does"
            disabled={isSaving}
            className="min-h-[60px]"
          />
          <Input
            label="Category Position"
            value={categoryPosition}
            onChange={(e) => setCategoryPosition(e.target.value)}
            placeholder="e.g., Premium organic skincare"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Mission & Values */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Mission & Values
        </h3>
        <div className="space-y-4">
          <Textarea
            label="Mission Statement *"
            value={missionStatement}
            onChange={(e) => {
              setMissionStatement(e.target.value);
              if (errors.mission_statement) setErrors((prev) => ({ ...prev, mission_statement: undefined }));
            }}
            error={errors.mission_statement}
            placeholder="What is the company's mission?"
            disabled={isSaving}
            className="min-h-[80px]"
          />
          <BulletListEditor
            label="Core Values"
            value={coreValues}
            onChange={setCoreValues}
            placeholder="Add a core value..."
            addButtonText="Add value"
            disabled={isSaving}
          />
          <Textarea
            label="Brand Promise"
            value={brandPromise}
            onChange={(e) => setBrandPromise(e.target.value)}
            placeholder="What does the brand promise to its customers?"
            disabled={isSaving}
            className="min-h-[60px]"
          />
        </div>
      </section>

      {/* Differentiators */}
      <section>
        <h3 className="text-sm font-semibold text-warm-gray-800 mb-3 uppercase tracking-wide">
          Differentiators
        </h3>
        <div className="space-y-4">
          <Textarea
            label="Primary USP"
            value={primaryUsp}
            onChange={(e) => setPrimaryUsp(e.target.value)}
            placeholder="What's the main unique selling proposition?"
            disabled={isSaving}
            className="min-h-[60px]"
          />
          <BulletListEditor
            label="Supporting Differentiators"
            value={supportingDifferentiators}
            onChange={setSupportingDifferentiators}
            placeholder="Add a differentiator..."
            addButtonText="Add differentiator"
            disabled={isSaving}
          />
          <BulletListEditor
            label="What We're NOT"
            value={whatWeAreNot}
            onChange={setWhatWeAreNot}
            placeholder="Add what the brand is not..."
            addButtonText="Add item"
            disabled={isSaving}
          />
        </div>
      </section>

      {/* Action buttons */}
      <div className="flex justify-end gap-3 pt-4 border-t border-cream-200">
        <Button variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}

export type { BrandFoundationEditorProps };
