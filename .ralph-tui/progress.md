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

