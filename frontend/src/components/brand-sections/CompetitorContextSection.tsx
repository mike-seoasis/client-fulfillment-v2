'use client';

import { SectionCard, BulletList, EmptySection } from './SectionCard';
import { type CompetitorContextData, type BaseSectionProps } from './types';

interface CompetitorContextSectionProps extends BaseSectionProps {
  data?: CompetitorContextData;
}

/**
 * Displays the Competitor Context section.
 * Shows competitive landscape, advantages, positioning statements, and rules.
 */
export function CompetitorContextSection({ data }: CompetitorContextSectionProps) {
  if (!data) {
    return <EmptySection message="Competitor context data not available" />;
  }

  const { direct_competitors, competitive_advantages, positioning_statements, rules } = data;

  const hasContent =
    (direct_competitors && direct_competitors.length > 0) ||
    (competitive_advantages && competitive_advantages.length > 0) ||
    (positioning_statements && positioning_statements.length > 0) ||
    (rules && rules.length > 0);

  if (!hasContent) {
    return <EmptySection message="Competitor context not configured" />;
  }

  return (
    <div>
      {/* Direct Competitors Table */}
      {direct_competitors && direct_competitors.length > 0 && (
        <SectionCard title="Direct Competitors">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-300">
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Competitor</th>
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Their Position</th>
                  <th className="text-left py-2 text-warm-gray-500 font-medium">Our Difference</th>
                </tr>
              </thead>
              <tbody>
                {direct_competitors.map((competitor, index) => (
                  <tr key={index} className="border-b border-cream-200 last:border-b-0">
                    <td className="py-2 text-warm-gray-800 font-medium">{competitor.name}</td>
                    <td className="py-2 text-warm-gray-600">{competitor.positioning || '—'}</td>
                    <td className="py-2 text-palm-700">{competitor.our_difference || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Competitive Advantages */}
      {competitive_advantages && competitive_advantages.length > 0 && (
        <SectionCard title="Our Competitive Advantages">
          <BulletList items={competitive_advantages} />
        </SectionCard>
      )}

      {/* Positioning Statements */}
      {positioning_statements && positioning_statements.length > 0 && (
        <SectionCard title="Positioning Statements">
          <div className="space-y-3">
            {positioning_statements.map((item, index) => (
              <div key={index} className="bg-white border border-cream-200 rounded-sm p-3">
                {item.context && (
                  <span className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider">
                    {item.context}:
                  </span>
                )}
                <p className="text-sm text-warm-gray-700 mt-1 italic">
                  &ldquo;{item.statement}&rdquo;
                </p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Rules */}
      {rules && rules.length > 0 && (
        <SectionCard title="Rules">
          <ul className="space-y-2">
            {rules.map((rule, index) => (
              <li key={index} className="flex items-start text-sm text-warm-gray-700">
                <span className="text-coral-500 mr-2 flex-shrink-0">•</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}
    </div>
  );
}
