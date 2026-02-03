'use client';

import { SectionCard, EmptySection } from './SectionCard';
import { type ExamplesBankData, type BaseSectionProps } from './types';

interface ExamplesBankSectionProps extends BaseSectionProps {
  data?: ExamplesBankData;
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

/**
 * Displays the Examples Bank section.
 * Shows headlines, product descriptions, CTAs, and off-brand examples.
 */
export function ExamplesBankSection({ data }: ExamplesBankSectionProps) {
  if (!data) {
    return <EmptySection message="Examples bank data not available" />;
  }

  const { headlines, product_description_example, email_subject_lines, social_media_examples, ctas, off_brand_examples } = data;

  const hasContent =
    (headlines && headlines.length > 0) ||
    product_description_example ||
    (email_subject_lines && email_subject_lines.length > 0) ||
    (social_media_examples && social_media_examples.length > 0) ||
    (ctas && ctas.length > 0) ||
    (off_brand_examples && off_brand_examples.length > 0);

  if (!hasContent) {
    return <EmptySection message="Examples bank not configured" />;
  }

  return (
    <div>
      {/* Headlines That Work */}
      {headlines && headlines.length > 0 && (
        <SectionCard title="Headlines That Work">
          <ul className="space-y-2">
            {headlines.map((headline, index) => (
              <li key={index} className="flex items-start text-sm">
                <CheckIcon className="w-4 h-4 text-palm-500 mr-2 flex-shrink-0 mt-0.5" />
                <span className="text-warm-gray-700">&ldquo;{headline}&rdquo;</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/* Product Description Example */}
      {product_description_example && (
        <SectionCard title="Product Description Example">
          <div className="bg-white border border-cream-200 rounded-sm p-4">
            <p className="text-sm text-warm-gray-700 whitespace-pre-line">
              {product_description_example}
            </p>
          </div>
        </SectionCard>
      )}

      {/* Email Subject Lines */}
      {email_subject_lines && email_subject_lines.length > 0 && (
        <SectionCard title="Email Subject Lines">
          <ul className="space-y-1.5">
            {email_subject_lines.map((subject, index) => (
              <li key={index} className="text-sm text-warm-gray-700">
                <span className="text-warm-gray-400 mr-2">{index + 1}.</span>
                &ldquo;{subject}&rdquo;
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {/* Social Media Examples */}
      {social_media_examples && social_media_examples.length > 0 && (
        <SectionCard title="Social Media Posts">
          <div className="space-y-3">
            {social_media_examples.map((example, index) => (
              <div key={index} className="bg-white border border-cream-200 rounded-sm p-3">
                {example.platform && (
                  <span className="text-xs font-semibold text-palm-600 uppercase tracking-wider">
                    {example.platform}
                  </span>
                )}
                {example.content && (
                  <p className="text-sm text-warm-gray-700 mt-1">&ldquo;{example.content}&rdquo;</p>
                )}
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* CTAs That Work */}
      {ctas && ctas.length > 0 && (
        <SectionCard title="CTAs That Work">
          <div className="flex flex-wrap gap-2">
            {ctas.map((cta, index) => (
              <span
                key={index}
                className="inline-flex items-center px-3 py-1.5 text-sm bg-palm-50 text-palm-700 border border-palm-200 rounded-sm"
              >
                &ldquo;{cta}&rdquo;
              </span>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Off-Brand Examples (What NOT to Write) */}
      {off_brand_examples && off_brand_examples.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-warm-gray-700 mb-3">What NOT to Write (Off-Brand)</h3>
          <div className="space-y-3">
            {off_brand_examples.map((item, index) => (
              <div
                key={index}
                className="bg-coral-50 border border-coral-200 rounded-sm p-4"
              >
                <div className="flex items-start gap-2">
                  <XIcon className="w-4 h-4 text-coral-500 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-warm-gray-700 italic">
                      &ldquo;{item.example}&rdquo;
                    </p>
                    {item.reason && (
                      <p className="text-xs text-coral-600 mt-1">
                        ({item.reason})
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
