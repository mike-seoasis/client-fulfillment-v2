'use client';

import { SectionCard, InfoRow, BulletList, EmptySection } from './SectionCard';
import { type BrandFoundationData, type BaseSectionProps } from './types';

interface BrandFoundationSectionProps extends BaseSectionProps {
  data?: BrandFoundationData;
}

/**
 * Displays the Brand Foundation section of the brand configuration.
 * Shows company overview, products, positioning, mission/values, and differentiators.
 */
export function BrandFoundationSection({ data }: BrandFoundationSectionProps) {
  if (!data) {
    return <EmptySection message="Brand foundation data not available" />;
  }

  const { company_overview, what_they_sell, brand_positioning, mission_and_values, differentiators } = data;

  return (
    <div>
      {/* Company Overview */}
      {company_overview && (
        <SectionCard title="Company Overview">
          <InfoRow label="Name" value={company_overview.company_name} />
          <InfoRow label="Founded" value={company_overview.founded} />
          <InfoRow label="Location" value={company_overview.location} />
          <InfoRow label="Industry" value={company_overview.industry} />
          <InfoRow label="Business Model" value={company_overview.business_model} />
        </SectionCard>
      )}

      {/* What They Sell */}
      {what_they_sell && (
        <SectionCard title="What They Sell">
          <InfoRow label="Primary" value={what_they_sell.primary_products} />
          <InfoRow label="Secondary" value={what_they_sell.secondary_offerings} />
          <InfoRow label="Price Point" value={what_they_sell.price_point} />
          <InfoRow label="Sales Channels" value={what_they_sell.sales_channels} />
        </SectionCard>
      )}

      {/* Brand Positioning */}
      {brand_positioning && (
        <SectionCard title="Brand Positioning">
          <InfoRow label="Tagline" value={brand_positioning.tagline} />
          <InfoRow label="One-Sentence" value={brand_positioning.one_sentence_description} />
          <InfoRow label="Position" value={brand_positioning.category_position} />
        </SectionCard>
      )}

      {/* Mission & Values */}
      {mission_and_values && (
        <SectionCard title="Mission & Values">
          {mission_and_values.mission_statement && (
            <div className="mb-4">
              <span className="text-warm-gray-500 text-sm block mb-1">Mission:</span>
              <p className="text-warm-gray-800 text-sm">{mission_and_values.mission_statement}</p>
            </div>
          )}
          {mission_and_values.core_values && mission_and_values.core_values.length > 0 && (
            <div className="mb-4">
              <span className="text-warm-gray-500 text-sm block mb-2">Core Values:</span>
              <BulletList items={mission_and_values.core_values} />
            </div>
          )}
          {mission_and_values.brand_promise && (
            <div>
              <span className="text-warm-gray-500 text-sm block mb-1">Brand Promise:</span>
              <p className="text-warm-gray-800 text-sm">{mission_and_values.brand_promise}</p>
            </div>
          )}
        </SectionCard>
      )}

      {/* Differentiators */}
      {differentiators && (
        <SectionCard title="Differentiators">
          {differentiators.primary_usp && (
            <div className="mb-4">
              <span className="text-warm-gray-500 text-sm block mb-1">Primary USP:</span>
              <p className="text-warm-gray-800 text-sm font-medium">{differentiators.primary_usp}</p>
            </div>
          )}
          {differentiators.supporting_differentiators && differentiators.supporting_differentiators.length > 0 && (
            <div className="mb-4">
              <span className="text-warm-gray-500 text-sm block mb-2">Supporting:</span>
              <BulletList items={differentiators.supporting_differentiators} />
            </div>
          )}
          {differentiators.what_we_are_not && differentiators.what_we_are_not.length > 0 && (
            <div>
              <span className="text-warm-gray-500 text-sm block mb-2">What We&apos;re NOT:</span>
              <BulletList items={differentiators.what_we_are_not} />
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}
