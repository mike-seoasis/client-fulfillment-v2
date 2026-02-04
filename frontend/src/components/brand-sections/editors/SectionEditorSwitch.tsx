'use client';

import { BrandFoundationEditor } from './BrandFoundationEditor';
import { TargetAudienceEditor } from './TargetAudienceEditor';
import { VoiceDimensionsEditor } from './VoiceDimensionsEditor';
import { VoiceCharacteristicsEditor } from './VoiceCharacteristicsEditor';
import { WritingStyleEditor } from './WritingStyleEditor';
import { VocabularyEditor } from './VocabularyEditor';
import { TrustElementsEditor } from './TrustElementsEditor';
import { ExamplesBankEditor } from './ExamplesBankEditor';
import { CompetitorContextEditor } from './CompetitorContextEditor';
import { AIPromptEditor } from './AIPromptEditor';
import type {
  BrandFoundationData,
  TargetAudienceData,
  VoiceDimensionsData,
  VoiceCharacteristicsData,
  WritingStyleData,
  VocabularyData,
  TrustElementsData,
  ExamplesBankData,
  CompetitorContextData,
  AIPromptSnippetData,
} from '../types';

/**
 * Valid section keys for brand configuration editors.
 */
export type SectionKey =
  | 'brand_foundation'
  | 'target_audience'
  | 'voice_dimensions'
  | 'voice_characteristics'
  | 'writing_style'
  | 'vocabulary'
  | 'trust_elements'
  | 'examples_bank'
  | 'competitor_context'
  | 'ai_prompt_snippet';

/**
 * Union type of all section data types.
 */
export type SectionData =
  | BrandFoundationData
  | TargetAudienceData
  | VoiceDimensionsData
  | VoiceCharacteristicsData
  | WritingStyleData
  | VocabularyData
  | TrustElementsData
  | ExamplesBankData
  | CompetitorContextData
  | AIPromptSnippetData;

export interface SectionEditorSwitchProps {
  /** The section key identifying which editor to render */
  sectionKey: SectionKey;
  /** The section data to edit (type depends on sectionKey) */
  data: SectionData | undefined;
  /** Whether the save operation is in progress */
  isSaving?: boolean;
  /** Called when the user saves their changes */
  onSave: (data: SectionData) => void;
  /** Called when the user cancels editing */
  onCancel: () => void;
}

/**
 * Router component that selects the correct editor based on section key.
 * Passes data, onSave, and onCancel props to the selected editor component.
 */
export function SectionEditorSwitch({
  sectionKey,
  data,
  isSaving = false,
  onSave,
  onCancel,
}: SectionEditorSwitchProps) {
  switch (sectionKey) {
    case 'brand_foundation':
      return (
        <BrandFoundationEditor
          data={data as BrandFoundationData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'target_audience':
      return (
        <TargetAudienceEditor
          data={data as TargetAudienceData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'voice_dimensions':
      return (
        <VoiceDimensionsEditor
          data={data as VoiceDimensionsData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'voice_characteristics':
      return (
        <VoiceCharacteristicsEditor
          data={data as VoiceCharacteristicsData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'writing_style':
      return (
        <WritingStyleEditor
          data={data as WritingStyleData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'vocabulary':
      return (
        <VocabularyEditor
          data={data as VocabularyData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'trust_elements':
      return (
        <TrustElementsEditor
          data={data as TrustElementsData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'examples_bank':
      return (
        <ExamplesBankEditor
          data={data as ExamplesBankData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'competitor_context':
      return (
        <CompetitorContextEditor
          data={data as CompetitorContextData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    case 'ai_prompt_snippet':
      return (
        <AIPromptEditor
          data={data as AIPromptSnippetData | undefined}
          isSaving={isSaving}
          onSave={onSave}
          onCancel={onCancel}
        />
      );

    default: {
      // TypeScript exhaustiveness check - this should never happen
      const _exhaustiveCheck: never = sectionKey;
      return (
        <div className="p-4 text-warm-gray-500">
          Unknown section: {_exhaustiveCheck}
        </div>
      );
    }
  }
}
