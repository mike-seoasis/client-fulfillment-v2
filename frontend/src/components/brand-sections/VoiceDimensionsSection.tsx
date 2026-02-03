'use client';

import { SectionCard, EmptySection } from './SectionCard';
import { type VoiceDimensionsData, type VoiceDimensionScale, type BaseSectionProps } from './types';

interface VoiceDimensionsSectionProps extends BaseSectionProps {
  data?: VoiceDimensionsData;
}

interface DimensionScaleProps {
  label: string;
  leftLabel: string;
  rightLabel: string;
  scale?: VoiceDimensionScale;
}

/**
 * Visual scale slider showing a voice dimension position.
 * Displays a 1-10 scale with marker and description.
 */
function DimensionScale({ label, leftLabel, rightLabel, scale }: DimensionScaleProps) {
  if (!scale) return null;

  const position = scale.position;
  // Convert 1-10 position to percentage (1 = 0%, 10 = 100%)
  const positionPercent = ((position - 1) / 9) * 100;

  return (
    <div className="bg-cream-50 border border-cream-300 rounded-sm p-4 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-warm-gray-800">{label}</h4>
        <span className="text-sm text-palm-600 font-medium">{position}/10</span>
      </div>

      {/* Scale visualization */}
      <div className="relative mb-3">
        {/* Track */}
        <div className="h-2 bg-cream-200 rounded-full overflow-hidden">
          {/* Filled portion */}
          <div
            className="h-full bg-gradient-to-r from-palm-300 to-palm-500 transition-all duration-300"
            style={{ width: `${positionPercent}%` }}
          />
        </div>

        {/* Position marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 w-4 h-4 bg-palm-500 border-2 border-white rounded-full shadow-sm transition-all duration-300"
          style={{ left: `calc(${positionPercent}% - 8px)` }}
        />

        {/* Labels */}
        <div className="flex justify-between mt-2">
          <span className="text-xs text-warm-gray-500">{leftLabel}</span>
          <span className="text-xs text-warm-gray-500">{rightLabel}</span>
        </div>
      </div>

      {/* Description */}
      {scale.description && (
        <p className="text-sm text-warm-gray-600 mb-2">{scale.description}</p>
      )}

      {/* Example */}
      {scale.example && (
        <div className="bg-white border border-cream-200 rounded-sm p-3 mt-3">
          <span className="text-xs text-warm-gray-400 uppercase tracking-wider">Example:</span>
          <p className="text-sm text-warm-gray-700 italic mt-1">&ldquo;{scale.example}&rdquo;</p>
        </div>
      )}
    </div>
  );
}

/**
 * Displays the Voice Dimensions section with visual scale sliders.
 * Shows the four Nielsen Norman Group voice dimensions.
 */
export function VoiceDimensionsSection({ data }: VoiceDimensionsSectionProps) {
  if (!data) {
    return <EmptySection message="Voice dimensions data not available" />;
  }

  const { formality, humor, reverence, enthusiasm, voice_summary } = data;

  const hasAnyDimension = formality || humor || reverence || enthusiasm;

  if (!hasAnyDimension && !voice_summary) {
    return <EmptySection message="Voice dimensions not configured" />;
  }

  return (
    <div>
      {/* Dimension Scales */}
      <DimensionScale
        label="Formality"
        leftLabel="Casual"
        rightLabel="Formal"
        scale={formality}
      />

      <DimensionScale
        label="Humor"
        leftLabel="Funny"
        rightLabel="Serious"
        scale={humor}
      />

      <DimensionScale
        label="Reverence"
        leftLabel="Irreverent"
        rightLabel="Respectful"
        scale={reverence}
      />

      <DimensionScale
        label="Enthusiasm"
        leftLabel="Enthusiastic"
        rightLabel="Matter-of-Fact"
        scale={enthusiasm}
      />

      {/* Voice Summary */}
      {voice_summary && (
        <SectionCard title="Voice Summary">
          <p className="text-sm text-warm-gray-700">{voice_summary}</p>
        </SectionCard>
      )}
    </div>
  );
}
