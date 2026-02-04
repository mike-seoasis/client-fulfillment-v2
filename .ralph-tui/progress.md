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

