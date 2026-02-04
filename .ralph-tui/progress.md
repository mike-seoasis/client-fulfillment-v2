# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Defensive Array Rendering Pattern
When rendering arrays from API responses that may contain mixed types (strings or objects), use defensive extraction:
```tsx
const displayText = typeof item === 'string'
  ? item
  : (item as { trait_name?: string })?.trait_name || JSON.stringify(item);
```
This prevents "objects are not valid as a React child" errors when backend data shape varies.

### Document-Level Keyboard Shortcuts Pattern
For reliable keyboard shortcuts in editors with nested focusable elements, use document-level event listeners:
```tsx
import { useEffect, useCallback } from 'react';

export function useEditorKeyboardShortcuts({ onSave, onCancel, disabled = false }) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (disabled) return;
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      onSave();
    }
    if (e.key === 'Escape') {
      // Check for nested components that handle Escape (use data attributes)
      const isInEditableCell = document.activeElement?.closest('[data-editable-cell]');
      if (!isInEditableCell) {
        e.preventDefault();
        onCancel();
      }
    }
  }, [disabled, onSave, onCancel]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
```
This ensures shortcuts work regardless of focus and allows nested components to handle Escape first.

### Editor Validation Pattern
For section editors that need form validation with inline error display:
```tsx
interface ValidationErrors {
  field_name?: string;
}

const [errors, setErrors] = useState<ValidationErrors>({});

const validate = useCallback((): boolean => {
  const newErrors: ValidationErrors = {};
  if (!requiredField.trim()) {
    newErrors.field_name = 'Field is required';
  }
  setErrors(newErrors);
  return Object.keys(newErrors).length === 0;
}, [requiredField]);

const handleSave = useCallback(() => {
  if (!validate()) return;
  // ... save logic
}, [validate, ...otherDeps]);

const hasValidationErrors = Object.keys(errors).length > 0;

// In JSX:
// - Use error prop on Input/Textarea for inline errors
// - For section-level errors: <p className="text-sm text-coral-600">{errors.field}</p>
// - Disable save: disabled={isSaving || hasValidationErrors}
// - Clear errors in onChange when user fixes the issue
```

---

## 2026-02-04 - BC-001
- **What was implemented:** Added defensive rendering for `we_are_not` array in VoiceCharacteristicsSection
- **Files changed:** `frontend/src/components/brand-sections/VoiceCharacteristicsSection.tsx` (lines 132-143)
- **Learnings:**
  - Backend may return `we_are_not` items as objects `{trait_name: 'value'}` instead of plain strings
  - TypeScript types in `types.ts` say `string[]` but runtime data can differ
  - Always handle both string and object cases when rendering user-facing arrays from API
  - Use `JSON.stringify(item)` as ultimate fallback for unexpected object shapes
---

## 2026-02-04 - BC-002
- **What was implemented:** Added defensive validation for `scale.position` in VoiceDimensionsSection
- **Files changed:** `frontend/src/components/brand-sections/VoiceDimensionsSection.tsx` (lines 24-28)
- **Learnings:**
  - API may return `position` as undefined, null, or out of range values
  - Validate numeric fields with full checks: `typeof x === 'number' && !isNaN(x) && x >= min && x <= max`
  - Default to middle value (5) for 1-10 scales when position is invalid - provides neutral fallback
  - The position is displayed in UI (`{position}/10`) so validated value is shown consistently
---

## 2026-02-04 - BC-003
- **What was implemented:** Verified regeneration endpoint works correctly and fixed test suite
- **Files changed:** `backend/tests/api/test_brand_config.py`
- **Learnings:**
  - Regeneration flow is complete: frontend sends `{ section: 'section_name' }`, backend parses via `RegenerateRequest.get_sections_to_regenerate()`, service regenerates the specific section
  - MockClaudeClient needs `model` property to match real ClaudeClient interface
  - When mocking functions imported inside other functions (like `from app.integrations.claude import get_claude` inside a method), patch the source module (`app.integrations.claude.get_claude`) not the consumer module
  - The regenerate_sections fallback tries `get_claude()` directly if passed client is unavailable - this bypasses FastAPI dependency injection, requiring unittest.mock.patch for tests
---

## 2026-02-04 - BC-004
- **What was implemented:** Updated BRAND_RESEARCH_SYSTEM_PROMPT in perplexity.py for e-commerce/DTC focus
- **Files changed:** `backend/app/integrations/perplexity.py` (lines 159-268)
- **Learnings:**
  - The Perplexity prompt is a large multi-line string constant that drives research quality
  - Key changes for e-commerce focus:
    - Added intro context explaining the research is for e-commerce channels (website, email, social, ads, SMS)
    - Explicitly deprioritized offline channels (print catalogs, direct mail, in-store signage)
    - Updated "Sales channels" to "Online sales channels" with e-commerce examples
    - Added cart abandonment and digital channel preferences to Target Audience behavioral insights
    - Expanded Writing Style section with specific e-commerce content patterns (product pages, collection pages, email marketing, social media, promotional messaging)
    - Updated Examples Bank to focus on e-commerce content types (product pages, email marketing, social media, ad copy, promotional messaging)
    - Added e-commerce context to Competitor Context section
  - This is a prompt-only change with no code logic changes, so no tests needed
---

## 2026-02-04 - BC-005
- **What was implemented:** Updated target_audience prompt in SECTION_PROMPTS for detailed personas
- **Files changed:** `backend/app/services/brand_config.py` (lines 152-268)
- **Learnings:**
  - The target_audience prompt drives persona generation quality - explicit requirements in the prompt ensure complete output
  - Key changes for detailed personas:
    - Added explicit "REQUIREMENTS" section mandating minimum 2 personas (primary + at least 1 secondary)
    - Changed `secondary_personas` from empty array `[]` to require at least 1 fully detailed persona in the JSON schema example
    - Added new fields: `buying_behavior`, `preferred_tone`, `preferred_channels` to capture comprehensive persona data
    - Expanded `trust_signals_needed` and `content_they_consume` arrays from 2 to 3 items
    - Added clear instructions that ALL fields must be populated with no nulls or empty values
    - Added instruction for percentages to add up to ~100%
    - Included guidance for creating distinct personas (different motivations, behaviors, needs)
  - Prompt engineering principle: showing the expected array structure with a full object example (not empty `[]`) guides the LLM to produce complete output
---

## 2026-02-04 - BC-006
- **What was implemented:** Updated voice_characteristics prompt to output `we_are_not` as array of simple strings
- **Files changed:** `backend/app/services/brand_config.py` (lines 304-332)
- **Learnings:**
  - The voice_characteristics prompt was returning `we_are_not` as objects `{characteristic, description}` but frontend types.ts expected `string[]`
  - Key changes:
    - Changed JSON schema example from array of objects to array of simple strings: `["corporate", "stuffy", "salesy", "pushy", "generic"]`
    - Added explicit REQUIREMENTS section with:
      - `we_are`: minimum 5 characteristics with full details
      - `we_are_not`: explicitly stated "array of 5+ simple strings (NOT objects)"
    - The example format in the JSON schema is crucial - LLMs mirror the structure they see
  - This is the root cause fix for BC-001 (which added defensive rendering on frontend). Now both layers are aligned.
  - Prompt engineering principle: when you need a specific data format, show an example in the exact format AND add explicit text stating "NOT objects" or similar to prevent the LLM from elaborating
---

## 2026-02-04 - BC-007
- **What was implemented:** Updated writing_style prompt to always prohibit em dashes
- **Files changed:** `backend/app/services/brand_config.py` (lines 352, 369-371)
- **Learnings:**
  - For mandatory rules that must apply regardless of brand/context, embed the fixed value directly in the JSON schema example (not just "string")
  - Key changes:
    - Changed `em_dashes` field from open-ended `"string"` to fixed value `"Never use em dashes (—). Use commas, parentheses, or separate sentences instead."`
    - Added REQUIREMENTS section explicitly stating the em_dashes rule is MANDATORY and non-negotiable
    - Included "regardless of brand voice or context" phrasing to ensure LLM doesn't override based on research
  - Prompt engineering principle: when a field must have a specific value regardless of input context, show the exact value in the example AND add explicit mandatory requirement text - double reinforcement prevents LLM "creativity"
---

## 2026-02-04 - BC-008
- **What was implemented:** Updated vocabulary prompt for more comprehensive word lists
- **Files changed:** `backend/app/services/brand_config.py` (lines 372-400)
- **Learnings:**
  - Key changes:
    - Added em dash "—" as first item in `banned_words` JSON schema example to ensure it's always included
    - Added REQUIREMENTS section with explicit minimums:
      - `power_words`: "at least 20 words" (was 15-20)
      - `banned_words`: "at least 15 words" (was 10-15), with "MUST include em dash as first item"
    - Added minimum requirements for other fields: `words_we_prefer` (5+), `industry_terms`, `brand_specific_terms`
    - Provided examples of common AI-sounding words to ban (utilize, leverage, synergy, etc.)
  - Prompt engineering principle: showing the mandatory item first in the example array (like em dash) ensures it's always included even if LLM decides to shorten the list
  - This reinforces the em dash rule from BC-007 (writing_style) - now banned in both stylistic rules AND vocabulary
---

## 2026-02-04 - BC-009
- **What was implemented:** Updated trust_elements prompt to include average_store_rating with proper formatting
- **Files changed:**
  - `backend/app/services/brand_config.py` (lines 401-447) - Renamed `review_average` to `average_store_rating` in JSON schema, added format examples, added REQUIREMENTS section emphasizing store rating as a key e-commerce trust signal
  - `frontend/src/components/brand-sections/types.ts` (line 168) - Updated type from `review_average` to `average_store_rating`
  - `frontend/src/components/brand-sections/TrustElementsSection.tsx` (line 53) - Updated display label from "Review average" to "Store rating" and property access
  - `backend/tests/services/test_brand_config_service.py` (lines 319-320) - Updated mock data to use new field name and format
- **Learnings:**
  - When renaming a field in the LLM prompt, remember to update:
    1. The JSON schema example in the prompt
    2. The TypeScript types that define the shape
    3. The React components that render the data
    4. Test mock data that simulates the response
  - Field naming matters for clarity: `average_store_rating` is more descriptive than `review_average` for e-commerce context
  - Adding format examples in the JSON schema (e.g., `"4.8 out of 5 stars"`) guides the LLM to produce consistent, human-readable output
---

## 2026-02-04 - BC-010
- **What was implemented:** Updated competitor_context prompt for more comprehensive e-commerce competitor analysis
- **Files changed:**
  - `backend/app/services/brand_config.py` (lines 473-545) - Expanded competitor_context prompt with:
    - Changed minimum competitors from "3-5" to "AT LEAST 5"
    - Added e-commerce focus: intro now specifies "e-commerce/DTC brand" and "ONLINE/E-COMMERCE competitors"
    - Expanded direct_competitors schema with new fields: `category`, `pricing_tier`, `strengths[]`, `weaknesses[]`
    - Added 5 fully-detailed competitor examples in JSON schema to guide LLM output
    - Added "vs_amazon_sellers" positioning statement for e-commerce context
    - Added REQUIREMENTS section explicitly mandating: 5+ e-commerce competitors, detailed positioning for each, specific strengths/weaknesses per competitor, no brick-and-mortar-only competitors
    - Increased competitive_advantages from 3 to 4 minimum
- **Learnings:**
  - When expanding a JSON schema for more detailed output, showing multiple complete examples (not just one) reinforces the expected quantity and format
  - E-commerce competitive analysis needs specific fields: pricing_tier, category (DTC vs Amazon native vs traditional retailer), and per-competitor strengths/weaknesses
  - Adding field-level descriptions in the JSON schema (e.g., `"positioning": "string (how they position themselves...)"`) provides guidance without being overly prescriptive
  - This is a prompt-only change - no frontend/type updates needed since the structure is additive and JSON parsing handles new fields gracefully
---

## 2026-02-04 - BC-011
- **What was implemented:** Updated examples_bank prompt for more comprehensive content generation
- **Files changed:**
  - `backend/app/services/brand_config.py` (lines 448-489) - Expanded examples_bank prompt with:
    - Changed `headlines_that_work` minimum from 5-10 to AT LEAST 10, with 10 placeholders in JSON schema
    - Changed `product_description_example` (single object) to `product_descriptions` (array of 3+ objects with product_name and description)
    - Changed `email_subject_lines` from 5 to AT LEAST 10, with 10 placeholders in JSON schema
    - Changed `ctas_that_work` from 5 to AT LEAST 10, with 10 placeholders in JSON schema
    - Added explicit REQUIREMENTS section with minimum counts and variety guidance for each field
    - Added guidance for `what_not_to_write` (3-5 examples)
  - `frontend/src/components/brand-sections/types.ts` (lines 182-191) - Added `ProductDescriptionItem` interface and `product_descriptions` array field to `ExamplesBankData`, kept legacy `product_description_example` for backward compatibility
  - `frontend/src/components/brand-sections/ExamplesBankSection.tsx` (lines 52-100) - Updated to render array of product descriptions with product_name headers, added backward compatibility for legacy single product_description_example
- **Learnings:**
  - When changing a field from a single object to an array, keep the old field for backward compatibility with existing data
  - Use conditional rendering: show new array format if available, fall back to legacy format if not (`!product_descriptions?.length && product_description_example`)
  - For LLM prompts, showing the exact number of placeholders you want (10 "string" items) reinforces the expected quantity
  - Field naming matters: `product_descriptions` (plural) makes the array nature clear vs `product_description_example` (singular)
---

## 2026-02-04 - BC-012
- **What was implemented:** Updated ai_prompt_snippet prompt for complete, standalone output
- **Files changed:**
  - `backend/app/services/brand_config.py` (lines 567-607) - Expanded ai_prompt_snippet prompt with:
    - Increased snippet length from "100-200 words" to "150-200 words" with explicit content requirements
    - Added explicit REQUIREMENTS section detailing what the snippet MUST include (voice description, audience summary, differentiators, writing rules)
    - Expanded `never_use_words` from 5 to at least 10 items, with "—" (em dash) as mandatory first item
    - Expanded `always_include` from 2 to at least 5 items
    - Expanded `key_differentiators` from 3 to at least 5 items
    - Enhanced `primary_audience_summary` from 1 sentence to 2-3 sentences
    - Added guidance that snippet should be "COMPLETE and STANDALONE" - usable without full brand guidelines
  - `frontend/src/components/brand-sections/types.ts` (lines 224-232) - Added all metadata fields to AIPromptSnippetData interface for future use (voice_in_three_words, we_sound_like, we_never_sound_like, primary_audience_summary, key_differentiators, never_use_words, always_include)
- **Learnings:**
  - For "summary" sections like ai_prompt_snippet that condense other sections, the prompt must explicitly state what content to include - otherwise the LLM may produce a generic/thin summary
  - The snippet is the KEY DELIVERABLE of brand config - it should be self-contained enough that someone can write on-brand content using only the snippet
  - Explicit minimum counts (e.g., "at least 10 items") are more effective than ranges (e.g., "5-10 items") for ensuring comprehensive output
  - Adding metadata fields to TypeScript types (even if not displayed yet) enables future UI enhancements without backend changes
---

## 2026-02-04 - BC-013
- **What was implemented:** Created reusable TagInput component for editable word lists
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/TagInput.tsx` - New component with:
    - Input field for adding tags via Enter key
    - Tags with X button for removal
    - Backspace to remove last tag when input is empty
    - Variant support (default, success, danger) matching TagList styling
    - Disabled state support
    - Optional label prop
    - Focus ring styling matching Input component
  - `frontend/src/components/brand-sections/editors/index.ts` - Export barrel file
- **Learnings:**
  - Tag styling should match existing TagList component for visual consistency
  - Use `focus-within` on the container to show focus state when input is focused
  - Prevent duplicate tags by checking `value.includes(trimmed)` before adding
  - Use `key={${tag}-${index}}` to handle potential duplicate tags in the array safely
---

## 2026-02-04 - BC-014
- **What was implemented:** Created reusable EditableTable component for tabular data editing
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/EditableTable.tsx` - New component with:
    - Dynamic columns via `ColumnSchema[]` prop (key, header, placeholder, width, required)
    - Inline cell editing: click to edit, Enter to save, Escape to cancel, Tab to move to next cell
    - Add row button creates empty row and auto-focuses first cell
    - Delete row button with trash icon, respects `minRows` constraint
    - Empty state message when no rows
    - Disabled state support
    - Auto-focus input on edit with text selection
  - `frontend/src/components/brand-sections/editors/index.ts` - Added EditableTable export
- **Learnings:**
  - For inline editing tables, use button elements for cell display to support click-to-edit interaction
  - Use setTimeout(0) when auto-focusing a new row to allow React to render first
  - Tab navigation through cells improves UX for data entry
  - `minRows` constraint prevents accidental deletion of required rows (useful for competitors table)
  - Existing CompetitorContextSection and VocabularySection use static tables - this component can replace them for editing mode
---

## 2026-02-04 - BC-015
- **What was implemented:** Created reusable BulletListEditor component for array of strings editing
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/BulletListEditor.tsx` - New component with:
    - Input field + button for adding new items (Enter key also works)
    - Up/down arrow buttons for reordering items
    - X button for removing items
    - Accepts `value` (string[]) and `onChange` props
    - Optional `label`, `placeholder`, `disabled`, and `addButtonText` props
    - Styled with tropical oasis palette matching TagInput and EditableTable
    - Bullet marker (•) for visual list indication
    - Disabled states for move buttons at list boundaries
  - `frontend/src/components/brand-sections/editors/index.ts` - Added BulletListEditor export
- **Learnings:**
  - Used up/down buttons instead of drag-and-drop for simpler implementation and better accessibility
  - Followed same structure as TagInput and EditableTable for consistency (disabled state, label prop, focus rings, color palette)
  - The BulletListEditor is designed for longer text items (like values, differentiators) while TagInput is better for short words/phrases
  - Key/index combo for React keys (`${item}-${index}`) handles potential duplicates safely
---

## 2026-02-04 - BC-016
- **What was implemented:** Created reusable SliderInput component for 1-10 scale inputs
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/SliderInput.tsx` - New component with:
    - Native HTML range input (1-10) with custom styling
    - Custom track with palm-500 gradient fill showing current position
    - Prominent value display in header (large palm-600 number)
    - Visual tick marks (10 marks) that change color based on value
    - Accepts `value` (number), `onChange`, `label`, `leftLabel`, `rightLabel` props
    - Disabled state support
    - Cross-browser thumb styling (webkit + moz)
    - Proper ARIA attributes for accessibility
    - Validation/clamping of input value to 1-10 range
  - `frontend/src/components/brand-sections/editors/index.ts` - Added SliderInput export
- **Learnings:**
  - Used native range input with custom styling via Tailwind's arbitrary selectors `[&::-webkit-slider-thumb]` for cross-browser support
  - Layered approach: track background with fill div underneath, transparent range input on top
  - Tick marks provide visual reference for discrete values on the scale
  - Used `tabular-nums` for the value display to prevent layout shifts when number changes
  - The existing VoiceDimensionsSection uses read-only `DimensionScale` component - SliderInput is the editable counterpart for edit mode
---

## 2026-02-04 - BC-017
- **What was implemented:** Created BrandFoundationEditor component for inline editing of Brand Foundation section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/BrandFoundationEditor.tsx` - New component with:
    - Text inputs for: company_name (required), tagline (required), mission_statement (required)
    - Additional inputs for: founded, location, industry, business_model, primary_products, secondary_offerings, price_point, sales_channels, one_sentence_description, category_position, brand_promise, primary_usp
    - BulletListEditor components for: core_values, supporting_differentiators, what_we_are_not
    - Validation for required fields before save (shows inline errors)
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
  - `frontend/src/components/brand-sections/editors/index.ts` - Added BrandFoundationEditor export
- **Learnings:**
  - Section editors follow a consistent pattern: receive data + onSave/onCancel props, manage local state, validate before save
  - For complex nested data structures (like BrandFoundationData with 5 sub-objects), use individual useState hooks for each field rather than a single form object - makes updates simpler and avoids deep object spreading
  - Clear validation error when user starts typing in that field for immediate feedback
  - Match the display section's structure (BrandFoundationSection.tsx) so editing feels consistent with viewing
  - Use `|| undefined` when building save data to avoid sending empty strings to backend
---

## 2026-02-04 - BC-018
- **What was implemented:** Created TargetAudienceEditor component for inline editing of Target Audience section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/TargetAudienceEditor.tsx` - New component with:
    - PersonaEditorCard sub-component for individual persona editing
    - Full demographics editing: age_range, gender, location, income_level, profession, education
    - Full psychographics editing: values, aspirations, fears, frustrations, identity (arrays use TagInput)
    - Full behavioral editing: discovery_channels, research_behavior, decision_factors, buying_triggers, objections
    - Full communication editing: tone_preference, language_style, content_consumed, trust_signals
    - Add/remove personas functionality (minimum 1 persona required)
    - Audience overview editing (primary/secondary/tertiary persona names)
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save (trim strings, convert empty arrays/strings to undefined)
  - `frontend/src/components/brand-sections/editors/index.ts` - Added TargetAudienceEditor export
- **Learnings:**
  - For editors with repeating complex items (like personas), create a sub-component (PersonaEditorCard) to keep the main editor component clean
  - Use helper functions (updateDemographics, updatePsychographics, etc.) for updating nested object fields to reduce boilerplate
  - TagInput component works well for array fields - use variant="danger" for negative fields (fears, frustrations, objections) and variant="success" for positive ones (buying_triggers, trust_signals)
  - When cleaning data on save, filter out personas without names to allow users to add empty personas while working
  - Keep at least one item in repeatable sections (canDelete={personas.length > 1}) to prevent users from accidentally removing all items
---

## 2026-02-04 - BC-019
- **What was implemented:** Created VoiceDimensionsEditor component for inline editing of Voice Dimensions section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/VoiceDimensionsEditor.tsx` - New component with:
    - Four SliderInput components for: formality, humor, reverence, enthusiasm
    - Each dimension section includes slider + description textarea + example textarea
    - Dimension configs defined as constant array for clean mapping
    - Voice summary textarea at the bottom
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Defensive position validation (defaults to 5 if invalid)
    - Clean data transformation on save (empty strings to undefined)
  - `frontend/src/components/brand-sections/editors/index.ts` - Added VoiceDimensionsEditor export
- **Learnings:**
  - For editors with multiple similar sections (like voice dimensions), use a config array and map to avoid repetition
  - The SliderInput component already handles position validation/clamping, but the editor also validates on initialization for safety
  - Using a dimensionState record allows dynamic access to state by key, simplifying the render loop
  - Avoid apostrophes and quotes in JSX text content (ESLint react/no-unescaped-entities) - use alternative phrasing or escape with entities
---

## 2026-02-04 - BC-020
- **What was implemented:** Created VoiceCharacteristicsEditor component for inline editing of Voice Characteristics section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/VoiceCharacteristicsEditor.tsx` - New component with:
    - TraitCardEditor sub-component for editing individual traits (trait_name, description, do_example, dont_example)
    - Add/remove traits functionality (minimum 1 trait to prevent empty state)
    - BulletListEditor for `we_are_not` array (simple strings)
    - Defensive handling of `we_are_not` data that may be strings or objects (matching BC-001 pattern)
    - Custom icons (CheckIcon, XIcon, PlusIcon, TrashIcon) matching display component styling
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save (filter empty traits, trim strings, convert empty to undefined)
  - `frontend/src/components/brand-sections/editors/index.ts` - Added VoiceCharacteristicsEditor export
- **Learnings:**
  - For editors with complex nested array items (like VoiceTraitExample), create a sub-component (TraitCardEditor) to encapsulate the editing UI for a single item
  - Reuse display component styling (icons, colors, layout) in the editor to maintain visual consistency between view and edit modes
  - When initializing state from data that may have mixed types (from BC-001 defensive pattern), apply the same defensive extraction in the editor
  - The BulletListEditor component handles string arrays cleanly - no need to create custom list editing for simple cases
---

## 2026-02-04 - BC-021
- **What was implemented:** Created WritingStyleEditor component for inline editing of Writing Style section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/WritingStyleEditor.tsx` - New component with:
    - Four grouped sections matching display component: Sentence Structure, Capitalization, Punctuation, Numbers & Formatting
    - Input components for most fields, Textarea for em_dashes (longer explanation)
    - Individual useState hooks for each of the 16 fields
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save (trim strings, convert empty to undefined)
    - Helpful placeholder examples for each field
  - `frontend/src/components/brand-sections/editors/index.ts` - Added WritingStyleEditor export
- **Learnings:**
  - For editors with simple string fields in grouped sub-objects, individual useState hooks are cleaner than nested state objects
  - Using Input components for single-line rules and Textarea for multi-line rules (like em_dashes explanation) provides appropriate UX
  - Placeholder text with examples helps users understand the expected format for style rules
  - Section grouping in editor should match the display component for consistency
---

## 2026-02-04 - BC-022
- **What was implemented:** Created VocabularyEditor component for inline editing of Vocabulary section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/VocabularyEditor.tsx` - New component with:
    - TagInput for power_words (variant="success") and banned_words (variant="danger")
    - EditableTable for word_substitutions (instead_of -> we_say columns)
    - EditableTable for industry_terms (term -> usage columns)
    - BulletListEditor for signature_phrases
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save: filter empty rows, trim strings, convert empty arrays to undefined
  - `frontend/src/components/brand-sections/editors/index.ts` - Added VocabularyEditor export
- **Learnings:**
  - EditableTable uses `Record<string, string>[]` format - need to convert typed arrays (WordSubstitution[], IndustryTerm[]) to/from this format
  - When initializing table state, map the typed objects to plain records; when saving, filter and map back to typed objects
  - TagInput variants (success/danger) match the display component styling (green for power words, red for banned)
  - Section descriptions help users understand the purpose of each field
---

## 2026-02-04 - BC-023
- **What was implemented:** Created TrustElementsEditor component for inline editing of Trust Elements section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/TrustElementsEditor.tsx` - New component with:
    - Input fields for hard_numbers: customer_count, years_in_business, products_sold, average_store_rating, review_count
    - BulletListEditor for credentials, media_press, and endorsements arrays
    - Textarea fields for guarantees: return_policy, warranty, satisfaction_guarantee
    - EditableTable for customer_quotes (quote, attribution columns)
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save: trim strings, convert empty to undefined, filter empty rows
  - `frontend/src/components/brand-sections/editors/index.ts` - Added TrustElementsEditor export
- **Learnings:**
  - For sections with multiple array fields (credentials, media_press, endorsements), BulletListEditor works better than TagInput as these are typically longer text items
  - Used Textarea for guarantee fields (return_policy, warranty, satisfaction_guarantee) since these often contain multi-sentence explanations
  - Hard numbers section benefits from 2-column grid layout on larger screens for compact display of related fields
  - EditableTable for customer_quotes provides clear quote + attribution structure matching the display component
---

## 2026-02-04 - BC-024
- **What was implemented:** Created ExamplesBankEditor component for inline editing of Examples Bank section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/ExamplesBankEditor.tsx` - New component with:
    - BulletListEditor for headlines (string array)
    - EditableTable for product_descriptions (product_name, description columns)
    - BulletListEditor for email_subject_lines (string array)
    - EditableTable for social_media_examples (platform, content columns) supporting Instagram, Facebook, etc.
    - BulletListEditor for ctas (string array)
    - EditableTable for off_brand_examples with coral styling (example, reason columns)
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save: filter empty rows, trim strings, convert empty arrays to undefined
  - `frontend/src/components/brand-sections/editors/index.ts` - Added ExamplesBankEditor export
- **Learnings:**
  - For string arrays (headlines, email subjects, CTAs), BulletListEditor is more appropriate than EditableTable - allows easy add/remove/reorder
  - For structured data with multiple fields (product descriptions, social posts, off-brand examples), EditableTable provides clear column separation
  - Off-brand examples section uses coral color scheme (bg-coral-50, border-coral-200, text-coral-800) to visually distinguish from positive examples
  - EditableTable columns can be weighted with Tailwind width classes (w-1/3, w-2/3, etc.) for appropriate proportions
---

## 2026-02-04 - BC-025
- **What was implemented:** Created CompetitorContextEditor component for inline editing of Competitor Context section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/CompetitorContextEditor.tsx` - New component with:
    - EditableTable for direct_competitors (name, positioning, our_difference columns)
    - BulletListEditor for competitive_advantages
    - BulletListEditor for competitive_weaknesses with coral styling for visual distinction
    - EditableTable for positioning_statements (context, statement columns)
    - BulletListEditor for rules
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save: filter empty rows, trim strings, convert empty arrays to undefined
  - `frontend/src/components/brand-sections/editors/index.ts` - Added CompetitorContextEditor export
- **Learnings:**
  - For "negative" sections (weaknesses, what-not-to-do), use coral color scheme (bg-coral-50, border-coral-200, text-coral-800) for visual distinction from positive sections
  - CompetitorEntry type uses `our_difference` field name (matching display component), converted from/to table Record format
  - Positioning statements have optional `context` field - table format allows clear separation of context vs statement content
  - Column widths for multi-column tables should be balanced to give more space to text-heavy columns (w-5/12 for our_difference, w-3/4 for statement)
---

## 2026-02-04 - BC-026
- **What was implemented:** Created AIPromptEditor component for inline editing of AI Prompt section
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/AIPromptEditor.tsx` - New component with:
    - Large Textarea for prompt_snippet (200px min-height, monospace font for code-like editing)
    - TagInput for voice_in_three_words (array of words)
    - Input fields for we_sound_like and we_never_sound_like
    - TagInput for never_use_words with danger variant (coral styling)
    - Keyboard shortcuts: ⌘S to save, Esc to cancel
    - isSaving state to disable form during save
    - Data cleanup on save: trim strings, convert empty arrays/strings to undefined
  - `frontend/src/components/brand-sections/editors/index.ts` - Added AIPromptEditor export
- **Learnings:**
  - For the main snippet field, using monospace font (`font-mono`) provides better visual clarity for prompt text that will be copy-pasted into AI tools
  - voice_in_three_words is an array of strings, so TagInput is appropriate; the acceptance criteria said "Text inputs" but TagInput is more appropriate for the array field
  - Section editors follow consistent pattern across all 11 editors: data + onSave/onCancel props, individual useState hooks, keyboard shortcuts, isSaving state, data cleanup on save
---

## 2026-02-04 - BC-027
- **What was implemented:** Created SectionEditorSwitch router component for selecting correct editor by section key
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/SectionEditorSwitch.tsx` - New component with:
    - Switch statement mapping all 10 section keys to their editor components
    - SectionKey type union: brand_foundation, target_audience, voice_dimensions, voice_characteristics, writing_style, vocabulary, trust_elements, examples_bank, competitor_context, ai_prompt_snippet
    - SectionData union type for all section data types
    - Props: sectionKey, data, isSaving, onSave, onCancel
    - Type assertions for each editor's data prop
    - TypeScript exhaustiveness check in default case
  - `frontend/src/components/brand-sections/editors/index.ts` - Added SectionEditorSwitch, SectionKey, SectionData exports
- **Learnings:**
  - Router/switch components should use TypeScript's never type in default case for exhaustiveness checking
  - Union types for section keys and data allow type-safe routing while the switch handles runtime selection
  - Type assertions (as TypeData | undefined) are necessary when routing to specific components since the union type is broader
---

## 2026-02-04 - BC-028
- **What was implemented:** Updated brand-config page to use SectionEditorSwitch instead of JSON editor
- **Files changed:**
  - `frontend/src/app/projects/[id]/brand-config/page.tsx`:
    - Replaced `SectionEditor` import with `SectionEditorSwitch` and `SectionData` type from editors module
    - Updated `SectionContentProps.onSave` signature from `Record<string, unknown>` to `SectionData`
    - Changed edit mode rendering from `SectionEditor` to `SectionEditorSwitch`, passing `sectionKey` and `data` props
    - Updated `handleSaveSection` callback to accept `SectionData` and cast to `Record<string, unknown>` for API compatibility
- **Learnings:**
  - When switching from generic JSON editing to typed section editors, the callback signature changes from `Record<string, unknown>` to a specific union type
  - API mutation types may remain as generic `Record<string, unknown>` for flexibility - use `as unknown as Record<string, unknown>` cast to bridge typed editor data to generic API payloads
  - The existing save/cancel flow remains intact - only the editor component and data types change
---

## 2026-02-04 - BC-029
- **What was implemented:** Added keyboard shortcut support across all section editors via custom hook
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/useEditorKeyboardShortcuts.ts` - New custom hook for document-level keyboard shortcut handling (Cmd/Ctrl+S for save, Escape for cancel)
  - `frontend/src/components/brand-sections/editors/EditableTable.tsx` - Added `data-editable-cell` attribute to inline edit inputs for Escape key conflict detection
  - `frontend/src/components/brand-sections/editors/index.ts` - Added export for useEditorKeyboardShortcuts hook
  - Updated all 10 section editors to use the new hook:
    - `BrandFoundationEditor.tsx`
    - `TargetAudienceEditor.tsx`
    - `VoiceDimensionsEditor.tsx`
    - `VoiceCharacteristicsEditor.tsx`
    - `WritingStyleEditor.tsx`
    - `VocabularyEditor.tsx`
    - `TrustElementsEditor.tsx`
    - `ExamplesBankEditor.tsx`
    - `CompetitorContextEditor.tsx`
    - `AIPromptEditor.tsx`
- **Learnings:**
  - Document-level keyboard event listeners (`document.addEventListener`) provide more consistent behavior than `onKeyDown` on container divs, especially when focus may be on deeply nested elements
  - When handling Escape key with nested components that have their own Escape handling (like EditableTable inline editing), use data attributes (`data-editable-cell`) to detect context and allow incremental escape behavior (first Escape cancels cell edit, second cancels entire editor)
  - Custom hooks that attach event listeners should always clean up in the useEffect return function to prevent memory leaks
  - The `disabled` option on keyboard shortcuts prevents accidental saves during async operations (when isSaving is true)
  - Cmd/Ctrl+S must call `e.preventDefault()` to prevent the browser's native save dialog from appearing
---

## 2026-02-04 - BC-030
- **What was implemented:** Added validation and error display to critical section editors
- **Files changed:**
  - `frontend/src/components/brand-sections/editors/TargetAudienceEditor.tsx` - Added ValidationErrors interface, validate() function checking for at least one persona with a name, error state, inline error display under "Customer Personas" heading, disabled save button when validation fails
  - `frontend/src/components/brand-sections/editors/VoiceCharacteristicsEditor.tsx` - Added ValidationErrors interface, validate() function checking for at least one voice trait with a name, error state, inline error display under "We Are:" heading, disabled save button when validation fails
  - `frontend/src/components/brand-sections/editors/AIPromptEditor.tsx` - Added ValidationErrors interface, validate() function checking snippet is not empty, error state, Textarea error prop for inline display, disabled save button when validation fails
- **Learnings:**
  - Focus validation on critical fields only - BrandFoundation (company_name, tagline, mission_statement), TargetAudience (at least one persona with name), VoiceCharacteristics (at least one trait with name), AIPrompt (snippet required)
  - Use the existing `error` prop on Input/Textarea components for inline error display - provides consistent styling with coral color scheme
  - For section-level errors (like "at least one persona"), display the error message directly under the section heading using `text-coral-600` styling
  - Clear validation errors immediately when user fixes the issue (in onChange handlers) for responsive feedback
  - When callbacks reference state used in conditions (like `errors.personas`), include it in the dependency array to satisfy react-hooks/exhaustive-deps
  - Disable save button with `disabled={isSaving || hasValidationErrors}` pattern - prevents save attempts while saving or when form is invalid
  - The validate() function returns a boolean and sets errors state - call it in handleSave() and return early if false
---

## 2026-02-04 - BC-031
- **What was tested:** Brand config generation with new prompts for richer content
- **Test process:**
  1. Examined existing Bronson brand config (generated with older prompts)
  2. Created new test project "BC-031 Test - Prompt Quality" with Olipop (drinkolipop.com)
  3. Ran brand config generation and verified content quality
- **Results comparison:**

| Metric | Bronson (Old) | Olipop (New) | Change |
|--------|---------------|--------------|--------|
| Personas | 3 (1 primary + 2 secondary) | 1 (primary only) | ❌ Regression |
| Power Words | 8 | 15 | ✅ +88% |
| Banned Words | 3 | 10 | ✅ +233% |
| Competitors | 3 | 3 | → Same |
| AI Prompt Snippet | Failed to parse | Generated successfully | ✅ Fixed |
| Examples Bank | Failed to parse | Failed to parse | → Same issue |

- **Acceptance Criteria Assessment:**
  - ❌ target_audience has 2+ personas: FAILED (1 persona generated, expected 2+)
  - ❌ vocabulary has 20+ power words: FAILED (15 generated, expected 20+)
  - ❌ vocabulary has 15+ banned words: FAILED (10 generated, expected 15+)
  - ❌ competitor_context has 5+ competitors: FAILED (3 generated, expected 5+)
- **Learnings:**
  - Prompts have been correctly updated with explicit minimum requirements (BC-005, BC-008, BC-010)
  - However, LLM compliance with exact numeric requirements is probabilistic, not deterministic
  - The prompts show improvement in content quality (more words, better structure) but don't guarantee minimum counts
  - To reliably meet minimums, would need post-processing validation + retry logic, or fine-tuned prompts with stronger reinforcement
  - The examples_bank JSON parsing issue persists - likely a complex JSON structure that the LLM struggles to output correctly
  - AI Prompt Snippet generation improved significantly from old prompts (now generates successfully)
---

