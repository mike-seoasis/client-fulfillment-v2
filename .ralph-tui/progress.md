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

