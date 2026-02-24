'use client';

import { SectionCard, InfoRow, EmptySection } from './SectionCard';
import { type WritingStyleData, type BaseSectionProps } from './types';

interface WritingStyleSectionProps extends BaseSectionProps {
  data?: WritingStyleData;
}

/**
 * Displays the Writing Style Rules section.
 * Shows sentence structure, capitalization, punctuation, and formatting rules.
 */
export function WritingStyleSection({ data }: WritingStyleSectionProps) {
  if (!data) {
    return <EmptySection message="Writing style data not available" />;
  }

  const { sentence_structure, capitalization, punctuation, numbers_formatting } = data;

  const hasContent = sentence_structure || capitalization || punctuation || numbers_formatting;

  if (!hasContent) {
    return <EmptySection message="Writing style rules not configured" />;
  }

  return (
    <div>
      {/* Sentence Structure */}
      {sentence_structure && (
        <SectionCard title="Sentence Structure">
          <InfoRow label="Avg sentence length" value={sentence_structure.average_sentence_length} />
          <InfoRow label="Paragraph length" value={sentence_structure.paragraph_length} />
          <InfoRow label="Contractions" value={sentence_structure.use_contractions} />
          <InfoRow label="Voice" value={sentence_structure.active_vs_passive} />
        </SectionCard>
      )}

      {/* Capitalization */}
      {capitalization && (
        <SectionCard title="Capitalization">
          <InfoRow label="Headlines" value={capitalization.headlines} />
          <InfoRow label="Product names" value={capitalization.product_names} />
          <InfoRow label="Features" value={capitalization.feature_names} />
        </SectionCard>
      )}

      {/* Punctuation */}
      {punctuation && (
        <SectionCard title="Punctuation">
          <InfoRow label="Serial comma" value={punctuation.serial_comma} />
          <InfoRow label="Em dashes" value={punctuation.em_dashes} />
          <InfoRow label="Exclamation points" value={punctuation.exclamation_points} />
          <InfoRow label="Ellipses" value={punctuation.ellipses} />
        </SectionCard>
      )}

      {/* Numbers & Formatting */}
      {numbers_formatting && (
        <SectionCard title="Numbers & Formatting">
          <InfoRow label="Spell out" value={numbers_formatting.spell_out_rules} />
          <InfoRow label="Currency" value={numbers_formatting.currency} />
          <InfoRow label="Percentages" value={numbers_formatting.percentages} />
          <InfoRow label="Bold" value={numbers_formatting.bold_usage} />
          <InfoRow label="Bullets" value={numbers_formatting.bullet_usage} />
        </SectionCard>
      )}
    </div>
  );
}
