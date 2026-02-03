'use client';

import { SectionCard, TagList, EmptySection } from './SectionCard';
import { type VocabularyData, type BaseSectionProps } from './types';

interface VocabularySectionProps extends BaseSectionProps {
  data?: VocabularyData;
}

/**
 * Displays the Vocabulary Guide section.
 * Shows power words, substitutions, banned words, industry terms, and signature phrases.
 */
export function VocabularySection({ data }: VocabularySectionProps) {
  if (!data) {
    return <EmptySection message="Vocabulary data not available" />;
  }

  const { power_words, word_substitutions, banned_words, industry_terms, signature_phrases } = data;

  const hasContent =
    (power_words && power_words.length > 0) ||
    (word_substitutions && word_substitutions.length > 0) ||
    (banned_words && banned_words.length > 0) ||
    (industry_terms && industry_terms.length > 0) ||
    (signature_phrases && signature_phrases.length > 0);

  if (!hasContent) {
    return <EmptySection message="Vocabulary guide not configured" />;
  }

  return (
    <div>
      {/* Power Words */}
      {power_words && power_words.length > 0 && (
        <SectionCard title="Power Words (Use These)">
          <TagList items={power_words} variant="success" />
        </SectionCard>
      )}

      {/* Word Substitutions */}
      {word_substitutions && word_substitutions.length > 0 && (
        <SectionCard title="Word Substitutions">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-300">
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Instead of...</th>
                  <th className="text-left py-2 text-warm-gray-500 font-medium">We say...</th>
                </tr>
              </thead>
              <tbody>
                {word_substitutions.map((sub, index) => (
                  <tr key={index} className="border-b border-cream-200 last:border-b-0">
                    <td className="py-2 text-warm-gray-500 line-through">{sub.instead_of}</td>
                    <td className="py-2 text-palm-700 font-medium">{sub.we_say}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Banned Words */}
      {banned_words && banned_words.length > 0 && (
        <SectionCard title="Banned Words (Never Use)">
          <TagList items={banned_words} variant="danger" />
        </SectionCard>
      )}

      {/* Industry Terms */}
      {industry_terms && industry_terms.length > 0 && (
        <SectionCard title="Industry Terms (Use Correctly)">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-300">
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Term</th>
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Usage</th>
                </tr>
              </thead>
              <tbody>
                {industry_terms.map((term, index) => (
                  <tr key={index} className="border-b border-cream-200 last:border-b-0">
                    <td className="py-2 text-warm-gray-800 font-medium">{term.term}</td>
                    <td className="py-2 text-warm-gray-600">{term.usage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Signature Phrases */}
      {signature_phrases && signature_phrases.length > 0 && (
        <SectionCard title="Signature Phrases">
          <ul className="space-y-2">
            {signature_phrases.map((phrase, index) => (
              <li key={index} className="flex items-start text-sm">
                <span className="text-palm-500 mr-2 flex-shrink-0">&ldquo;</span>
                <span className="text-warm-gray-700 italic">{phrase}</span>
                <span className="text-palm-500 ml-1">&rdquo;</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
