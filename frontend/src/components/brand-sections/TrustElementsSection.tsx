'use client';

import { SectionCard, InfoRow, BulletList, EmptySection } from './SectionCard';
import { type TrustElementsData, type BaseSectionProps } from './types';

interface TrustElementsSectionProps extends BaseSectionProps {
  data?: TrustElementsData;
}

function QuoteIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M6 17h3l2-4V7H5v6h3zm8 0h3l2-4V7h-6v6h3z" />
    </svg>
  );
}

/**
 * Displays the Trust & Proof Elements section.
 * Shows hard numbers, credentials, guarantees, and customer quotes.
 */
export function TrustElementsSection({ data }: TrustElementsSectionProps) {
  if (!data) {
    return <EmptySection message="Trust elements data not available" />;
  }

  const { hard_numbers, credentials, media_press, endorsements, guarantees, customer_quotes } = data;

  const hasContent =
    hard_numbers ||
    (credentials && credentials.length > 0) ||
    (media_press && media_press.length > 0) ||
    (endorsements && endorsements.length > 0) ||
    guarantees ||
    (customer_quotes && customer_quotes.length > 0);

  if (!hasContent) {
    return <EmptySection message="Trust elements not configured" />;
  }

  return (
    <div>
      {/* Hard Numbers */}
      {hard_numbers && (
        <SectionCard title="Hard Numbers">
          <InfoRow label="Customers" value={hard_numbers.customer_count} />
          <InfoRow label="Years in business" value={hard_numbers.years_in_business} />
          <InfoRow label="Products sold" value={hard_numbers.products_sold} />
          <InfoRow label="Review average" value={hard_numbers.review_average} />
          <InfoRow label="Review count" value={hard_numbers.review_count} />
        </SectionCard>
      )}

      {/* Credentials & Certifications */}
      {credentials && credentials.length > 0 && (
        <SectionCard title="Credentials & Certifications">
          <BulletList items={credentials} />
        </SectionCard>
      )}

      {/* Media & Press */}
      {media_press && media_press.length > 0 && (
        <SectionCard title="Media & Press">
          <BulletList items={media_press} />
        </SectionCard>
      )}

      {/* Endorsements */}
      {endorsements && endorsements.length > 0 && (
        <SectionCard title="Endorsements">
          <BulletList items={endorsements} />
        </SectionCard>
      )}

      {/* Guarantees & Policies */}
      {guarantees && (
        <SectionCard title="Guarantees & Policies">
          <InfoRow label="Return policy" value={guarantees.return_policy} />
          <InfoRow label="Warranty" value={guarantees.warranty} />
          <InfoRow label="Satisfaction guarantee" value={guarantees.satisfaction_guarantee} />
        </SectionCard>
      )}

      {/* Customer Quotes */}
      {customer_quotes && customer_quotes.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-warm-gray-700 mb-3">Customer Quotes (Approved for Use)</h3>
          <div className="space-y-3">
            {customer_quotes.map((item, index) => (
              <div
                key={index}
                className="bg-cream-50 border border-cream-300 rounded-sm p-4 relative"
              >
                <QuoteIcon className="absolute top-3 left-3 w-5 h-5 text-palm-200" />
                <div className="pl-6">
                  <p className="text-sm text-warm-gray-700 italic mb-2">
                    &ldquo;{item.quote}&rdquo;
                  </p>
                  <p className="text-xs text-warm-gray-500">
                    — {item.attribution}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
