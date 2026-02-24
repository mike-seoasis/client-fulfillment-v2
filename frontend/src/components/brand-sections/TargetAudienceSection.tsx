'use client';

import { SectionCard, EmptySection } from './SectionCard';
import { type TargetAudienceData, type PersonaData, type BaseSectionProps } from './types';

interface TargetAudienceSectionProps extends BaseSectionProps {
  data?: TargetAudienceData;
}

interface PersonaCardProps {
  persona: PersonaData;
  isPrimary?: boolean;
}

/**
 * Individual persona card with expandable sections.
 */
function PersonaCard({ persona, isPrimary = false }: PersonaCardProps) {
  const { demographics, psychographics, behavioral, communication, summary } = persona;

  return (
    <div className="bg-cream-50 border border-cream-300 rounded-sm overflow-hidden mb-4">
      {/* Persona Header */}
      <div className={`px-4 py-3 border-b border-cream-300 ${isPrimary ? 'bg-palm-50' : 'bg-cream-100'}`}>
        <div className="flex items-center justify-between">
          <h4 className={`font-semibold ${isPrimary ? 'text-palm-800' : 'text-warm-gray-800'}`}>
            {persona.name}
          </h4>
          {persona.percentage && (
            <span className={`text-sm ${isPrimary ? 'text-palm-600' : 'text-warm-gray-500'}`}>
              ({persona.percentage})
            </span>
          )}
        </div>
        {isPrimary && (
          <span className="inline-flex items-center mt-1 text-xs text-palm-600 font-medium">
            Primary Persona
          </span>
        )}
      </div>

      {/* Persona Content */}
      <div className="p-4 space-y-4">
        {/* Demographics */}
        {demographics && (
          <div>
            <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
              Demographics
            </h5>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {demographics.age_range && (
                <div>
                  <span className="text-warm-gray-400">Age:</span>{' '}
                  <span className="text-warm-gray-700">{demographics.age_range}</span>
                </div>
              )}
              {demographics.income_level && (
                <div>
                  <span className="text-warm-gray-400">Income:</span>{' '}
                  <span className="text-warm-gray-700">{demographics.income_level}</span>
                </div>
              )}
              {demographics.location && (
                <div>
                  <span className="text-warm-gray-400">Location:</span>{' '}
                  <span className="text-warm-gray-700">{demographics.location}</span>
                </div>
              )}
              {demographics.profession && (
                <div>
                  <span className="text-warm-gray-400">Profession:</span>{' '}
                  <span className="text-warm-gray-700">{demographics.profession}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Psychographics */}
        {psychographics && (
          <div>
            <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
              Psychographics
            </h5>
            <div className="space-y-2">
              {psychographics.values && psychographics.values.length > 0 && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Values:</span>{' '}
                  <span className="text-warm-gray-700">{psychographics.values.join(', ')}</span>
                </div>
              )}
              {psychographics.fears && psychographics.fears.length > 0 && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Fears:</span>{' '}
                  <span className="text-warm-gray-700">{psychographics.fears.join(', ')}</span>
                </div>
              )}
              {psychographics.frustrations && psychographics.frustrations.length > 0 && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Frustrations:</span>{' '}
                  <span className="text-warm-gray-700">{psychographics.frustrations.join(', ')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Behavioral */}
        {behavioral && (
          <div>
            <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
              Behavior
            </h5>
            <div className="space-y-2">
              {behavioral.research_behavior && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Research:</span>{' '}
                  <span className="text-warm-gray-700">{behavioral.research_behavior}</span>
                </div>
              )}
              {behavioral.decision_factors && behavioral.decision_factors.length > 0 && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Decision Factors:</span>{' '}
                  <span className="text-warm-gray-700">{behavioral.decision_factors.join(', ')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Communication */}
        {communication && (
          <div>
            <h5 className="text-xs font-semibold text-warm-gray-500 uppercase tracking-wider mb-2">
              Communication
            </h5>
            <div className="space-y-2">
              {communication.tone_preference && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Responds to:</span>{' '}
                  <span className="text-warm-gray-700">{communication.tone_preference}</span>
                </div>
              )}
              {communication.language_style && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Language:</span>{' '}
                  <span className="text-warm-gray-700">{communication.language_style}</span>
                </div>
              )}
              {communication.content_consumed && communication.content_consumed.length > 0 && (
                <div className="text-sm">
                  <span className="text-warm-gray-400">Consumes:</span>{' '}
                  <span className="text-warm-gray-700">{communication.content_consumed.join(', ')}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Summary */}
        {summary && (
          <div className="pt-3 border-t border-cream-200">
            <p className="text-sm text-warm-gray-600 italic">{summary}</p>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Displays the Target Audience section with persona cards.
 * Shows audience overview and detailed persona information.
 */
export function TargetAudienceSection({ data }: TargetAudienceSectionProps) {
  if (!data) {
    return <EmptySection message="Target audience data not available" />;
  }

  const { personas, audience_overview } = data;

  // Identify primary persona by name or position
  const primaryPersonaName = audience_overview?.primary_persona;

  return (
    <div>
      {/* Audience Overview */}
      {audience_overview && (
        <SectionCard title="Audience Overview">
          <div className="space-y-1">
            {audience_overview.primary_persona && (
              <div className="text-sm">
                <span className="text-palm-600 font-medium">Primary:</span>{' '}
                <span className="text-warm-gray-700">{audience_overview.primary_persona}</span>
              </div>
            )}
            {audience_overview.secondary_persona && (
              <div className="text-sm">
                <span className="text-warm-gray-500">Secondary:</span>{' '}
                <span className="text-warm-gray-700">{audience_overview.secondary_persona}</span>
              </div>
            )}
            {audience_overview.tertiary_persona && (
              <div className="text-sm">
                <span className="text-warm-gray-500">Tertiary:</span>{' '}
                <span className="text-warm-gray-700">{audience_overview.tertiary_persona}</span>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* Persona Cards */}
      {personas && personas.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold text-warm-gray-700 mb-3">Customer Personas</h3>
          {personas.map((persona, index) => (
            <PersonaCard
              key={index}
              persona={persona}
              isPrimary={index === 0 || Boolean(primaryPersonaName && persona.name.includes(primaryPersonaName.split(' ')[0]))}
            />
          ))}
        </div>
      ) : (
        !audience_overview && <EmptySection message="No personas defined" />
      )}
    </div>
  );
}
