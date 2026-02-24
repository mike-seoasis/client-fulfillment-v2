## 1. Fix Critical Bugs

- [x] 1.1 Fix VoiceCharacteristicsSection crash - add defensive rendering for `we_are_not` array to handle both string and object formats
- [x] 1.2 Fix VoiceDimensionsSection slider - validate `scale.position` exists and is a number, default to 5 if missing
- [x] 1.3 Debug and fix regeneration endpoint - verify API is being called correctly for Target Audience and Examples Bank

## 2. Backend Prompt Enhancements

- [x] 2.1 Update Perplexity `BRAND_RESEARCH_SYSTEM_PROMPT` to focus on e-commerce/DTC, remove catalog/direct mail references
- [x] 2.2 Update `target_audience` prompt to require 2+ detailed personas with all demographic/psychographic fields
- [x] 2.3 Update `voice_characteristics` prompt to explicitly require `we_are_not` as array of strings
- [x] 2.4 Update `writing_style` prompt to always include "never use em dashes" rule
- [x] 2.5 Update `vocabulary` prompt to require 20+ power words and 15+ banned words
- [x] 2.6 Update `trust_elements` prompt to include average_store_rating field
- [x] 2.7 Update `competitor_context` prompt to require 5+ competitors
- [x] 2.8 Update `examples_bank` prompt to require 10+ headlines, 3+ descriptions, 10+ CTAs
- [x] 2.9 Update `ai_prompt_snippet` prompt to ensure complete output with all metadata fields

## 3. Create Shared Editor Components

- [x] 3.1 Create `TagInput` component for editable tag lists (power words, banned words)
- [x] 3.2 Create `EditableTable` component for tabular data (competitors, substitutions)
- [x] 3.3 Create `BulletListEditor` component for editable bullet lists
- [x] 3.4 Create `SliderInput` component for 1-10 range sliders with labels

## 4. Create Section Editors

- [x] 4.1 Create `BrandFoundationEditor` - text inputs for name/tagline/mission, bullet lists for products/values/differentiators
- [x] 4.2 Create `TargetAudienceEditor` - persona cards with editable nested fields
- [x] 4.3 Create `VoiceDimensionsEditor` - interactive sliders for 4 dimensions
- [x] 4.4 Create `VoiceCharacteristicsEditor` - trait cards with add/remove, editable we_are_not list
- [x] 4.5 Create `WritingStyleEditor` - categorized text inputs for sentence/capitalization/punctuation rules
- [x] 4.6 Create `VocabularyEditor` - tag inputs for words, editable table for substitutions
- [x] 4.7 Create `TrustElementsEditor` - structured inputs for numbers, credentials, quotes, guarantees
- [x] 4.8 Create `ExamplesBankEditor` - textareas for headlines, descriptions, emails, social, CTAs
- [x] 4.9 Create `CompetitorContextEditor` - editable table for competitors, text inputs for advantages
- [x] 4.10 Create `AIPromptEditor` - large textarea for snippet, text inputs for metadata

## 5. Integrate Editors

- [x] 5.1 Create `SectionEditorSwitch` component to route to appropriate editor by section key
- [x] 5.2 Update brand-config page to use `SectionEditorSwitch` instead of `SectionEditor` (JSON)
- [x] 5.3 Add keyboard shortcut support (Cmd/Ctrl+S to save, Escape to cancel)
- [x] 5.4 Add validation and error display for each editor

## 6. Testing & Verification

- [x] 6.1 Test brand config generation with new prompts - verify richer content
- [x] 6.2 Test VoiceCharacteristics with both string and object data formats
- [x] 6.3 Test VoiceDimensions slider with various position values including missing/invalid
- [x] 6.4 Test regeneration for all 10 sections
- [x] 6.5 Test inline editing save/cancel for all 10 editors
- [x] 6.6 E2E test: create project, generate brand config, edit sections, regenerate
