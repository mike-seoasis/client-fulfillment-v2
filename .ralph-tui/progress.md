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

