# Brand Config & UX Rework - Implementation Tasks

## 1. Setup

- [x] 1.1 Add PERPLEXITY_API_KEY to config and .env.example
- [x] 1.2 Create skills/ directory and move brand_guidelines_bible.md there

## 2. Backend - Perplexity Integration

- [x] 2.1 Create PerplexityClient with research_brand() method
- [x] 2.2 Add caching (24hr TTL) and rate limiting (5/hr/project)

## 3. Backend - V3 Schema

- [x] 3.1 Create V3 Pydantic schemas for all 11 Brand Guidelines Bible sections
- [x] 3.2 Add is_v3_config() / is_v2_config() detection helpers

## 4. Backend - Brand Research Service

- [x] 4.1 Create BrandResearchService with Perplexity→Claude synthesis pipeline
- [x] 4.2 Create Claude prompt for V3 schema synthesis

## 5. Backend - Wizard Endpoints

- [x] 5.1 Add brand_wizard_state column to projects table (migration)
- [x] 5.2 Create wizard API endpoints (GET/PUT state, POST research, POST generate)

## 6. Backend - Phase Migration

- [x] 6.1 Create migration to rename phases (discovery→brand_setup, etc.)
- [x] 6.2 Update PHASE_NAMES constant in project model

## 7. Frontend - Wizard Components

- [x] 7.1 Create wizard layout components (WizardProgress, WizardNavigation, WizardContainer)
- [x] 7.2 Create VoiceDimensionSlider component with 1-10 scale and example text
- [x] 7.3 Create form components (ChipInput, PersonaCard, ExampleEditor)

## 8. Frontend - Wizard Steps

- [x] 8.1 Create Step 1: Brand Setup (name, domain, research button)
- [x] 8.2 Create Step 2: Foundation (company info, positioning, differentiators)
- [x] 8.3 Create Step 3: Audience (persona cards with add/edit/remove)
- [x] 8.4 Create Step 4: Voice (4 dimension sliders + characteristics)
- [x] 8.5 Create Step 5: Writing Rules (toggles, vocabulary editors)
- [x] 8.6 Create Step 6: Proof & Examples (stats, quotes, good/bad examples)
- [x] 8.7 Create Step 7: Review & Generate (summary, quick reference, generate button)

## 9. Frontend - Wizard Page & Integration

- [x] 9.1 Create BrandWizardPage with state management and auto-save
- [x] 9.2 Add route and link from ProjectDetailPage
- [x] 9.3 Update BrandConfigPanel to detect V3 and show "Launch Wizard" button

## 10. Frontend - UX Fixes

- [x] 10.1 Hide WebSocket indicator until 3+ failed reconnection attempts
- [x] 10.2 Update phaseLabels to user-friendly names (Brand Setup, Site Analysis, etc.)

## 11. Testing & Deployment

- [ ] 11.1 Test complete wizard flow end-to-end
- [ ] 11.2 Test V2 backward compatibility and Perplexity fallback
- [ ] 11.3 Add PERPLEXITY_API_KEY to Railway and deploy
