## Context

The brand configuration feature generates 10 sections of brand voice and style documentation from research data. Currently:
- Generation produces sparse content that doesn't meet user needs
- Several display components crash or show incorrect data
- Editing shows raw JSON instead of user-friendly inline fields
- Regeneration is broken for some sections

The system uses:
- Backend: FastAPI + Claude for section generation, Perplexity for research
- Frontend: Next.js + React with section-specific display components
- Data: v2_schema JSONB field on BrandConfig model

## Goals / Non-Goals

**Goals:**
- Fix all crash bugs (VoiceCharacteristics, VoiceDimensions)
- Make regeneration work for all sections
- Enhance prompts to produce richer, more detailed content
- Add e-commerce focus to research
- Replace JSON editing with inline editable fields for all 10 sections

**Non-Goals:**
- Changing the underlying data model or v2_schema structure
- Adding new sections beyond the existing 10
- Real-time collaborative editing
- Version history or undo functionality

## Decisions

### 1. VoiceCharacteristics Crash Fix
**Decision:** Add defensive rendering to handle both object and string formats for `we_are_not` array.

**Rationale:** The backend prompt may return objects instead of strings. Rather than only fixing the prompt (which affects new generations), defensive rendering ensures existing data also works. Fix both sides: prompt for correctness, frontend for resilience.

**Alternative considered:** Only fix the prompt - rejected because existing data would still crash.

### 2. VoiceDimensions Slider Fix
**Decision:** Check if `scale.position` exists and is a valid number before calculating percentage. Default to 5 (middle) if missing.

**Rationale:** The slider calculation `((position - 1) / 9) * 100` fails if position is undefined or not a number, defaulting to 0 visually.

### 3. Inline Editors Architecture
**Decision:** Create one editor component per section type in `frontend/src/components/brand-sections/editors/`. Each editor:
- Receives typed data and onChange callback
- Renders appropriate input controls (text, slider, tags, table)
- Maintains local state during editing
- Validates before calling onSave

**Rationale:** Section data structures vary significantly (arrays vs objects, nested data, different field types). Generic form generation would be complex and hard to maintain. Dedicated editors allow optimal UX per section.

**Alternative considered:**
- Schema-driven form generation - rejected due to complexity and loss of UX control
- Keep JSON editing with syntax highlighting - rejected per user feedback

### 4. Editor Component Mapping
| Section | Primary Controls |
|---------|-----------------|
| BrandFoundation | Text inputs, bullet lists |
| TargetAudience | Persona cards with nested fields |
| VoiceDimensions | Range sliders (1-10) with labels |
| VoiceCharacteristics | Trait cards with add/remove |
| WritingStyle | Categorized text inputs |
| Vocabulary | Tag inputs, substitution table |
| TrustElements | Structured inputs per proof type |
| ExamplesBank | Textarea per example category |
| CompetitorContext | Editable table for competitors |
| AIPrompt | Large textarea |

### 5. Prompt Enhancement Strategy
**Decision:** Update each of the 10 prompts in `brand_config.py` to:
- Require more items (e.g., 5+ competitors, 20+ power words)
- Add explicit format requirements (e.g., `we_are_not` must be array of strings)
- Include e-commerce focus in context
- Always include "never use em dashes" for writing style

**Rationale:** More specific prompts produce better structured output. E-commerce focus ensures relevance. Format requirements prevent data type issues.

### 6. Perplexity Research Focus
**Decision:** Update `BRAND_RESEARCH_SYSTEM_PROMPT` to emphasize:
- E-commerce / DTC business model
- Website copy, email marketing, social media
- Online sales channels
- Remove/deprioritize catalog, direct mail references

**Rationale:** User feedback indicated irrelevant content like "direct mail catalog expertise" was being included.

## Risks / Trade-offs

**Risk:** Existing brand configs may not work with new editors if data shape differs.
→ **Mitigation:** Editors handle missing/malformed data gracefully with defaults and optional fields.

**Risk:** Prompt changes may produce different output structure breaking existing code.
→ **Mitigation:** Keep output JSON schema unchanged, only add content depth and format strictness.

**Risk:** 10 new editor components add significant code surface.
→ **Mitigation:** Share common patterns via utility components (TagInput, EditableTable, etc.). Use TypeScript for type safety.

**Trade-off:** Dedicated editors require more code than JSON editing but provide much better UX.
→ **Accepted:** User explicitly requested inline editing over JSON.
