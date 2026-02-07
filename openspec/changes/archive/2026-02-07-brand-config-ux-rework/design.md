## Context

The current brand configuration system uses a simple V2 schema (colors, typography, voice tone dropdown, social links) synthesized from uploaded documents via Claude. The old system had a comprehensive 11-part Brand Guidelines Bible framework with Perplexity-powered website research that produced higher quality brand context for AI-generated content.

**Current State:**
- `BrandConfigPanel.tsx`: Document upload UI with basic schema display
- `brand_config.py` model: JSONB `v2_schema` field with simple structure
- `BrandConfigService`: Claude-based synthesis from documents only
- WebSocket hook shows "Reconnecting" indicator even when working correctly
- Project phases use generic software terms (Discovery, Requirements, etc.)

**Stakeholders:**
- End users creating content for clients
- Backend services consuming brand config for content generation
- Frontend wizard UI

## Goals / Non-Goals

**Goals:**
- Replace simple brand schema with comprehensive 11-part Brand Guidelines Bible structure
- Add Perplexity API integration for automatic website research
- Create a guided 7-step wizard UI for brand configuration
- Fix confusing "Reconnecting" WebSocket indicator
- Rename phases to match actual content onboarding workflow
- Maintain backward compatibility with existing V2 configs

**Non-Goals:**
- Review mining from Trustpilot/Google (defer to future iteration - complex scraping)
- Social media analysis (defer - requires platform APIs)
- Automated brand guideline PDF generation
- Multi-brand support per project (one brand config per project is sufficient)

## Decisions

### Decision 1: V3 Schema Structure

**Choice:** Implement full 11-part Brand Guidelines Bible as V3 schema, stored in existing `v2_schema` JSONB field with `_version: "3.0"` marker.

**Rationale:**
- JSONB is flexible enough for schema evolution
- No database migration needed for new fields
- Detection via `_version` field allows graceful handling of V2 vs V3

**Alternatives considered:**
- New `v3_schema` column: Rejected - unnecessary complexity, JSONB handles evolution
- Separate tables per section: Rejected - over-normalized, complicates queries

**V3 Schema Structure:**
```json
{
  "_version": "3.0",
  "_generated_at": "ISO timestamp",
  "_sources_used": ["perplexity", "documents"],

  "foundation": {
    "company_name": "string",
    "tagline": "string|null",
    "industry": "string",
    "business_model": "string",
    "positioning_statement": "string",
    "mission_statement": "string|null",
    "core_values": ["string"],
    "key_differentiators": ["string"],
    "products_services": "string"
  },

  "personas": [{
    "name": "string",
    "is_primary": "boolean",
    "demographics": { "age_range", "gender_skew", "income_level", "location" },
    "psychographics": { "values": [], "interests": [], "lifestyle": "string" },
    "pain_points": ["string"],
    "motivations": ["string"],
    "buying_triggers": ["string"]
  }],

  "voice_dimensions": {
    "formality": { "score": 1-10, "description": "string" },
    "humor": { "score": 1-10, "description": "string" },
    "reverence": { "score": 1-10, "description": "string" },
    "enthusiasm": { "score": 1-10, "description": "string" }
  },

  "voice_characteristics": {
    "we_are": [{ "trait": "string", "description": "string", "example": "string" }],
    "we_are_not": [{ "trait": "string", "description": "string", "anti_example": "string" }]
  },

  "writing_rules": {
    "sentence_length": { "min": 10, "max": 25 },
    "paragraph_length": { "min": 2, "max": 4 },
    "contractions_allowed": true,
    "oxford_comma": true,
    "exclamation_limit_per_page": 1,
    "capitalization": { "headlines": "title_case", "subheads": "sentence_case" }
  },

  "vocabulary": {
    "power_words": ["string"],
    "banned_words": ["delve", "unlock", "journey", "game-changer", "revolutionary"],
    "preferred_terms": { "buy": "shop", "cheap": "affordable" },
    "industry_terms": [{ "term": "string", "usage": "string" }]
  },

  "proof_elements": {
    "statistics": [{ "stat": "string", "context": "string" }],
    "credentials": ["string"],
    "customer_quotes": [{ "quote": "string", "attribution": "string" }],
    "guarantees": ["string"]
  },

  "examples_bank": {
    "headlines": { "good": ["string"], "bad": ["string"] },
    "product_descriptions": { "good": ["string"], "bad": ["string"] },
    "ctas": { "good": ["string"], "bad": ["string"] }
  },

  "competitor_context": {
    "competitors": [{ "name": "string", "positioning": "string", "our_difference": "string" }],
    "positioning_statements": ["string"]
  },

  "ai_prompts": {
    "collection_description": "string",
    "product_description": "string",
    "email_copy": "string"
  },

  "quick_reference": {
    "voice_in_three_words": ["string", "string", "string"],
    "one_sentence_summary": "string",
    "primary_audience": "string",
    "key_cta": "string",
    "avoid_at_all_costs": ["string"]
  },

  "_legacy": {
    "colors": {},
    "typography": {},
    "logo": {},
    "voice": {},
    "social": {}
  }
}
```

### Decision 2: Perplexity Integration Architecture

**Choice:** Create new `PerplexityClient` service with dedicated endpoint for brand research. Call Perplexity first, then use Claude to synthesize into V3 schema.

**Rationale:**
- Perplexity excels at web research with citations
- Claude excels at structured synthesis
- Two-stage approach: research → synthesis
- Perplexity API is simple (similar to OpenAI chat API)

**Alternatives considered:**
- Claude-only with web browsing: Rejected - Claude doesn't have real-time web access
- Perplexity-only: Rejected - Claude better at structured schema generation

**Flow:**
1. User provides domain URL
2. Backend calls Perplexity: "Research the brand at {domain}. Extract company info, target audience, brand voice, differentiators, proof points."
3. Perplexity returns research with citations
4. Claude synthesizes research into V3 schema structure
5. User can edit in wizard UI

### Decision 3: Wizard UI Architecture

**Choice:** 7-step wizard with auto-save per step, stored in `brand_wizard_state` JSONB column.

**Steps:**
1. **Brand Setup** - Domain URL, brand name, trigger Perplexity research
2. **Foundation** - Company info, positioning (auto-filled, editable)
3. **Audience** - Personas (auto-generated from research, editable)
4. **Voice** - 4 dimension sliders (1-10), characteristics
5. **Writing Rules** - Toggles and inputs for rules, vocabulary
6. **Proof & Examples** - Stats, quotes, good/bad examples
7. **Review & Generate** - Summary, generate final config

**Rationale:**
- Breaking into steps reduces cognitive load
- Auto-save prevents data loss
- Each step can be revisited

**Alternatives considered:**
- Single long form: Rejected - overwhelming, easy to skip sections
- Accordion sections: Rejected - still shows everything at once, less guided

### Decision 4: WebSocket Indicator Fix

**Choice:** Hide the connection status indicator by default. Only show when there's an actual error after 3 failed reconnection attempts.

**Rationale:**
- Users don't care about technical connection status
- "Reconnecting" is alarming when the app still works (polling fallback exists)
- Only surface errors that actually affect functionality

**Alternatives considered:**
- Fix WebSocket endpoint: Possible but complex - polling fallback already works
- Remove indicator entirely: Rejected - need to show actual errors

### Decision 5: Phase Renaming Strategy

**Choice:** Update phase names in `phaseUtils.ts` and create database migration to update existing records.

**Mapping:**
- `discovery` → `brand_setup`
- `requirements` → `site_analysis`
- `implementation` → `content_generation`
- `review` → `review_edit`
- `launch` → `export`

**Rationale:**
- Clear mapping to actual workflow steps
- Labels in frontend are decoupled (just update `phaseLabels`)
- Migration updates existing project records

**Alternatives considered:**
- Keep internal names, change labels only: Cleaner but confusing in logs/API
- Add new columns: Rejected - unnecessary complexity

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Perplexity API costs | Estimate ~$0.02-0.05 per research call. Cache results. Rate limit to 1 call per project per hour. |
| V3 schema too complex | Wizard UI guides users through sections. Quick Reference provides summary. |
| Breaking existing V2 configs | Detection via `_version` field. V2 configs still work, upgraded on edit. |
| Phase rename breaks integrations | Document in release notes. API returns both internal name and display label. |
| Perplexity research quality varies | Claude synthesis step normalizes output. User can always edit. |

## Migration Plan

### Database Migration
```sql
-- Add wizard state column to projects
ALTER TABLE projects ADD COLUMN brand_wizard_state JSONB DEFAULT '{}';

-- Update phase names in existing records (run as data migration)
UPDATE projects
SET phase_status = jsonb_set(
  jsonb_set(
    jsonb_set(
      jsonb_set(
        jsonb_set(phase_status, '{brand_setup}', phase_status->'discovery'),
        '{site_analysis}', phase_status->'requirements'
      ),
      '{content_generation}', phase_status->'implementation'
    ),
    '{review_edit}', phase_status->'review'
  ),
  '{export}', phase_status->'launch'
) - 'discovery' - 'requirements' - 'implementation' - 'review' - 'launch'
WHERE phase_status ? 'discovery';
```

### Rollback Strategy
1. Phase names: Revert migration by running inverse UPDATE
2. V3 schema: V2 configs still work, no rollback needed
3. Wizard state: Column can remain, frontend ignores if not used

## Open Questions

1. **Perplexity model selection**: Use `sonar` (default) or `sonar-pro` (better quality, higher cost)?
   - *Tentative answer*: Start with `sonar`, upgrade to `sonar-pro` if quality issues

2. **Wizard step validation**: Should steps be strictly sequential or allow jumping?
   - *Tentative answer*: Allow jumping after step 1 (need domain/name first)

3. **Existing brand configs**: Auto-upgrade V2→V3 on view, or only on explicit edit?
   - *Tentative answer*: Only on edit to avoid unintended changes
