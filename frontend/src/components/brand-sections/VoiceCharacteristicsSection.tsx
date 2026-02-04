'use client';

import { SectionCard, EmptySection } from './SectionCard';
import { type VoiceCharacteristicsData, type VoiceTraitExample, type BaseSectionProps } from './types';

interface VoiceCharacteristicsSectionProps extends BaseSectionProps {
  data?: VoiceCharacteristicsData;
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

interface TraitCardProps {
  trait: VoiceTraitExample;
  index: number;
}

/**
 * Card displaying a single voice trait with do/don't examples.
 */
function TraitCard({ trait, index }: TraitCardProps) {
  // Handle both 'trait_name' (new) and 'characteristic' (legacy) field names
  const traitName = trait.trait_name || (trait as unknown as { characteristic?: string }).characteristic || 'Unnamed';

  return (
    <div className="bg-cream-50 border border-cream-300 rounded-sm overflow-hidden mb-4">
      {/* Header */}
      <div className="bg-palm-50 px-4 py-3 border-b border-cream-300">
        <div className="flex items-center gap-2">
          <span className="text-palm-600 font-semibold text-sm">{index + 1}.</span>
          <h4 className="font-semibold text-palm-800 uppercase tracking-wide text-sm">
            {traitName}
          </h4>
        </div>
        {trait.description && (
          <p className="text-sm text-warm-gray-600 mt-1">{trait.description}</p>
        )}
      </div>

      {/* Do/Don't Examples */}
      <div className="p-4 space-y-3">
        {/* DO Example */}
        {trait.do_example && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-palm-100 flex items-center justify-center">
              <CheckIcon className="w-4 h-4 text-palm-600" />
            </div>
            <div className="flex-1">
              <span className="text-xs font-semibold text-palm-600 uppercase tracking-wider">DO:</span>
              <p className="text-sm text-warm-gray-700 mt-0.5">&ldquo;{trait.do_example}&rdquo;</p>
            </div>
          </div>
        )}

        {/* DON'T Example */}
        {trait.dont_example && (
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-6 h-6 rounded-full bg-coral-100 flex items-center justify-center">
              <XIcon className="w-4 h-4 text-coral-600" />
            </div>
            <div className="flex-1">
              <span className="text-xs font-semibold text-coral-600 uppercase tracking-wider">DON&apos;T:</span>
              <p className="text-sm text-warm-gray-700 mt-0.5">&ldquo;{trait.dont_example}&rdquo;</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Displays the Voice Characteristics section with trait cards.
 * Shows "We Are" traits with do/don't examples and "We Are NOT" list.
 */
export function VoiceCharacteristicsSection({ data }: VoiceCharacteristicsSectionProps) {
  if (!data) {
    return <EmptySection message="Voice characteristics data not available" />;
  }

  const { we_are, we_are_not } = data;

  const hasContent = (we_are && we_are.length > 0) || (we_are_not && we_are_not.length > 0);

  if (!hasContent) {
    return <EmptySection message="Voice characteristics not configured" />;
  }

  return (
    <div>
      {/* We Are Section */}
      {we_are && we_are.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-warm-gray-700 mb-3">We Are:</h3>
          {we_are.map((trait, index) => (
            <TraitCard key={index} trait={trait} index={index} />
          ))}
        </div>
      )}

      {/* We Are NOT Section */}
      {we_are_not && we_are_not.length > 0 && (
        <SectionCard title="We Are NOT:">
          <ul className="space-y-2">
            {we_are_not.map((item, index) => {
              // Handle both string items and object items defensively
              const displayText = typeof item === 'string'
                ? item
                : (item as { trait_name?: string })?.trait_name || JSON.stringify(item);
              return (
                <li key={index} className="flex items-start text-sm text-warm-gray-700">
                  <span className="text-coral-500 mr-2 flex-shrink-0">•</span>
                  <span>{displayText}</span>
                </li>
              );
            })}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
