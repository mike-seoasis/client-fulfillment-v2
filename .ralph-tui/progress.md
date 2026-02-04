# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Defensive Data Format Handling
When frontend types differ from backend schema (e.g., `string[]` vs `object[]`), handle both formats defensively:
```tsx
// Display: handle both string and object formats
const displayText = typeof item === 'string'
  ? item
  : (item as { trait_name?: string })?.trait_name || JSON.stringify(item);

// Editor: normalize to expected format on init
const normalizedItems = data?.items?.map((item) =>
  typeof item === 'string'
    ? item
    : (item as { trait_name?: string })?.trait_name || ''
) ?? [];
```

### BulletListEditor Usage
The `BulletListEditor` component displays items as `<span>` text, not `<input>` elements. In tests:
- Use `screen.getByText('item')` not `screen.getByDisplayValue('item')`
- Items are displayed with bullet markers (`•`) and reorder/delete controls

---

## 2026-02-04 - BC-032
- Verified VoiceCharacteristics crash fix for `we_are_not` data format mismatch
- Added comprehensive unit tests for VoiceCharacteristicsSection and VoiceCharacteristicsEditor
- **Files changed:**
  - `frontend/src/components/brand-sections/__tests__/VoiceCharacteristicsSection.test.tsx` (created)
  - `frontend/src/components/brand-sections/__tests__/VoiceCharacteristicsEditor.test.tsx` (created)
- **Learnings:**
  - Backend schema defines `we_are_not` as `list[VoiceCharacteristicSchema]` (objects with `trait` field)
  - Frontend type defines `we_are_not` as `string[]`
  - The fix handles both formats defensively in display and editor components
  - CSS `uppercase` class doesn't change DOM text content (test with actual value, not visual)
  - Pre-existing test failures in page.test.tsx for edit/save functionality (unrelated)
---

