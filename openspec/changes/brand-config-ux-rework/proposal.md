## Why

The current brand configuration is too simplistic (basic colors, fonts, tone dropdown) and doesn't capture the comprehensive brand context needed for AI-generated content. The old system had an 11-part Brand Guidelines Bible framework with Perplexity-powered research that produced much better results. Additionally, the UI shows a broken "Reconnecting" WebSocket indicator and the project phases (Discovery, Requirements, Implementation, Review, Launch) are confusing generic terms that don't map to what users actually do.

## What Changes

### Brand Configuration Overhaul
- **Replace simple V2 schema** with comprehensive 11-part Brand Guidelines Bible framework:
  1. Foundation (company info, positioning, differentiators, mission/values)
  2. Customer Personas (demographics, psychographics, behavioral insights)
  3. Voice Dimensions (4 scales 1-10: formality, humor, reverence, enthusiasm)
  4. Voice Characteristics (we are/we are not with examples)
  5. Writing Rules (sentence structure, capitalization, punctuation, numbers)
  6. Vocabulary (power words, banned words, preferred terms, industry terms)
  7. Proof Elements (statistics, credentials, customer quotes, guarantees)
  8. Examples Bank (good/bad headlines, product descriptions, CTAs)
  9. Competitor Context (positioning statements, differentiation points)
  10. AI Prompts (pre-built prompts for different content types)
  11. Quick Reference (voice in 3 words, one-sentence summary, avoid list)

- **Add Perplexity API integration** for automatic brand research from website URL
- **Add review mining** from Trustpilot/Google Reviews for persona extraction
- **Create guided wizard UI** (7 steps) instead of current document-upload-only flow
- **Maintain backward compatibility** with existing V2 configs via `_legacy` field

### UX Fixes
- **Hide or fix WebSocket "Reconnecting" indicator** - currently shows spinning reconnect status that confuses users
- **BREAKING: Rename project phases** from generic software terms to content-onboarding-specific phases:
  - "Discovery" → "Brand Setup" (configure brand identity)
  - "Requirements" → "Site Analysis" (crawl and analyze website)
  - "Implementation" → "Content Generation" (generate optimized content)
  - "Review" → "Review & Edit" (review and refine content)
  - "Launch" → "Export" (export final content)

### Backend Changes
- Add Perplexity API client for brand research
- Add brand config V3 schema with full 11-part structure
- Add wizard state management endpoints
- Update phase names in database schema

## Capabilities

### New Capabilities
- `brand-research`: Perplexity-powered automatic brand research from website URL, including review mining and social media analysis
- `brand-wizard`: 7-step guided wizard for comprehensive brand configuration with auto-fill from research

### Modified Capabilities
- `directory-structure`: Add `skills/` directory for skill bibles (reference documents like brand_guidelines_bible.md)

## Impact

### Frontend
- `frontend/src/components/BrandConfigPanel.tsx` - Complete rewrite for wizard UI
- `frontend/src/pages/ProjectDetailPage.tsx` - Update phase labels, fix WebSocket indicator
- `frontend/src/lib/phaseUtils.ts` - Rename phases
- New components for wizard steps, voice dimension sliders, vocabulary editors

### Backend
- `backend/app/models/brand_config.py` - V3 schema with 11-part structure
- `backend/app/api/v1/brand_config.py` - Wizard endpoints, Perplexity integration
- `backend/app/models/project.py` - Phase name changes
- New: `backend/app/services/perplexity_client.py`
- New: `backend/app/services/review_miner.py`

### Database
- Migration for phase name changes (update existing records)
- Migration for brand_config V3 schema fields

### Dependencies
- Add Perplexity API key to environment variables
- No new Python packages required (uses existing httpx)

### Breaking Changes
- Phase names change affects any external integrations reading phase status
- Brand config schema version bump (V2 → V3) requires migration path
