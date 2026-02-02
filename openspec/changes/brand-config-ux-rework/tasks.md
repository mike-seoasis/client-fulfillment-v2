# Brand Config & UX Rework - Implementation Tasks

## 1. Setup & Infrastructure

- [ ] 1.1 Add PERPLEXITY_API_KEY to .env.example with documentation
- [ ] 1.2 Add PERPLEXITY_API_KEY to backend/app/core/config.py settings
- [ ] 1.3 Create skills/ directory at project root
- [ ] 1.4 Create skills/README.md explaining purpose and format
- [ ] 1.5 Move brand_guidelines_bible.md to skills/ directory

## 2. Backend - Perplexity Client

- [ ] 2.1 Create backend/app/integrations/perplexity.py with PerplexityClient class
- [ ] 2.2 Implement PerplexityClient.research_brand(domain: str) method
- [ ] 2.3 Add Perplexity API error handling (rate limits, auth errors, timeouts)
- [ ] 2.4 Add research result caching with 24-hour TTL in Redis
- [ ] 2.5 Add rate limiting: 5 requests/hour/project using Redis
- [ ] 2.6 Write unit tests for PerplexityClient

## 3. Backend - V3 Schema & Models

- [ ] 3.1 Create backend/app/schemas/brand_config_v3.py with Pydantic models for all 11 sections
- [ ] 3.2 Add V3FoundationSchema model (company_name, industry, positioning, mission, values, differentiators)
- [ ] 3.3 Add V3PersonaSchema model (name, demographics, psychographics, pain_points, motivations)
- [ ] 3.4 Add V3VoiceDimensionsSchema model (formality, humor, reverence, enthusiasm - each with score 1-10)
- [ ] 3.5 Add V3VoiceCharacteristicsSchema model (we_are, we_are_not lists with trait/description/example)
- [ ] 3.6 Add V3WritingRulesSchema model (sentence_length, paragraph_length, contractions, oxford_comma, etc.)
- [ ] 3.7 Add V3VocabularySchema model (power_words, banned_words, preferred_terms, industry_terms)
- [ ] 3.8 Add V3ProofElementsSchema model (statistics, credentials, customer_quotes, guarantees)
- [ ] 3.9 Add V3ExamplesBankSchema model (headlines, product_descriptions, ctas - each with good/bad)
- [ ] 3.10 Add V3CompetitorContextSchema model (competitors list, positioning_statements)
- [ ] 3.11 Add V3AIPromptsSchema model (collection_description, product_description, email_copy)
- [ ] 3.12 Add V3QuickReferenceSchema model (voice_in_three_words, one_sentence_summary, avoid_list)
- [ ] 3.13 Add V3BrandConfigSchema root model combining all sections with _version, _generated_at, _sources_used
- [ ] 3.14 Add is_v3_config() and is_v2_config() detection helpers
- [ ] 3.15 Write unit tests for V3 schema validation

## 4. Backend - Brand Research Service

- [ ] 4.1 Create backend/app/services/brand_research.py with BrandResearchService class
- [ ] 4.2 Implement research_brand(project_id, domain) method calling Perplexity
- [ ] 4.3 Implement synthesize_to_v3(research_results) method calling Claude
- [ ] 4.4 Create Claude prompt for V3 schema synthesis (reference brand_guidelines_bible.md)
- [ ] 4.5 Add research_and_synthesize(project_id, domain) combined method
- [ ] 4.6 Handle partial research results (populate available sections, mark others for review)
- [ ] 4.7 Write unit tests for BrandResearchService

## 5. Backend - Wizard State & Endpoints

- [ ] 5.1 Create Alembic migration: add brand_wizard_state JSONB column to projects table
- [ ] 5.2 Update backend/app/models/project.py with brand_wizard_state field
- [ ] 5.3 Create backend/app/schemas/brand_wizard.py with WizardStateSchema
- [ ] 5.4 Create backend/app/api/v1/brand_wizard.py router
- [ ] 5.5 Add GET /api/v1/projects/{id}/brand-wizard endpoint (get wizard state)
- [ ] 5.6 Add PUT /api/v1/projects/{id}/brand-wizard endpoint (save wizard step)
- [ ] 5.7 Add POST /api/v1/projects/{id}/brand-wizard/research endpoint (trigger Perplexity research)
- [ ] 5.8 Add POST /api/v1/projects/{id}/brand-wizard/generate endpoint (generate final V3 config)
- [ ] 5.9 Register brand_wizard router in backend/app/api/v1/__init__.py
- [ ] 5.10 Write integration tests for wizard endpoints

## 6. Backend - Phase Migration

- [ ] 6.1 Create Alembic migration for phase name updates
- [ ] 6.2 Write SQL to rename phase keys: discovery→brand_setup, requirements→site_analysis, implementation→content_generation, review→review_edit, launch→export
- [ ] 6.3 Update backend/app/models/project.py PHASE_NAMES constant
- [ ] 6.4 Update any backend code referencing old phase names
- [ ] 6.5 Test migration on local database with existing projects
- [ ] 6.6 Add rollback SQL to migration

## 7. Frontend - Wizard Components

- [ ] 7.1 Create frontend/src/components/brand-wizard/WizardProgress.tsx (step indicator)
- [ ] 7.2 Create frontend/src/components/brand-wizard/WizardNavigation.tsx (prev/next buttons)
- [ ] 7.3 Create frontend/src/components/brand-wizard/WizardContainer.tsx (layout wrapper)
- [ ] 7.4 Create frontend/src/components/brand-wizard/PersonaCard.tsx (persona display/edit)
- [ ] 7.5 Create frontend/src/components/brand-wizard/VoiceCharacteristicRow.tsx (we are/are not row)
- [ ] 7.6 Create frontend/src/components/brand-wizard/ChipInput.tsx (for power_words, banned_words)
- [ ] 7.7 Create frontend/src/components/brand-wizard/KeyValueEditor.tsx (for preferred_terms)
- [ ] 7.8 Create frontend/src/components/brand-wizard/ExampleEditor.tsx (good/bad examples)
- [ ] 7.9 Create frontend/src/components/brand-wizard/index.ts barrel export

## 8. Frontend - Voice Dimension Sliders

- [ ] 8.1 Create frontend/src/components/brand-wizard/VoiceDimensionSlider.tsx component
- [ ] 8.2 Implement slider with 1-10 scale and value display
- [ ] 8.3 Add example text display for low end (1) of slider
- [ ] 8.4 Add example text display for high end (10) of slider
- [ ] 8.5 Add formality slider examples ("Hey!" vs "Dear Valued Customer")
- [ ] 8.6 Add humor slider examples ("Oops, we goofed" vs "We apologize for the error")
- [ ] 8.7 Add reverence slider examples ("The boring competitors" vs "Other solutions in the market")
- [ ] 8.8 Add enthusiasm slider examples ("We're SO excited!" vs "Now available.")
- [ ] 8.9 Style slider with brand colors and smooth transitions

## 9. Frontend - Wizard Steps Implementation

- [ ] 9.1 Create frontend/src/components/brand-wizard/steps/Step1BrandSetup.tsx
- [ ] 9.2 Implement brand name input (required), domain input (optional), Research button
- [ ] 9.3 Create frontend/src/components/brand-wizard/steps/Step2Foundation.tsx
- [ ] 9.4 Implement foundation fields (company overview, industry, positioning, mission, values, differentiators)
- [ ] 9.5 Create frontend/src/components/brand-wizard/steps/Step3Audience.tsx
- [ ] 9.6 Implement persona list with add/edit/remove, primary persona toggle
- [ ] 9.7 Create frontend/src/components/brand-wizard/steps/Step4Voice.tsx
- [ ] 9.8 Implement 4 voice dimension sliders and voice characteristics editor
- [ ] 9.9 Create frontend/src/components/brand-wizard/steps/Step5WritingRules.tsx
- [ ] 9.10 Implement writing rules toggles/inputs and vocabulary editors
- [ ] 9.11 Create frontend/src/components/brand-wizard/steps/Step6ProofExamples.tsx
- [ ] 9.12 Implement proof elements and examples bank editors
- [ ] 9.13 Create frontend/src/components/brand-wizard/steps/Step7Review.tsx
- [ ] 9.14 Implement summary view with edit links and quick reference editor
- [ ] 9.15 Add Generate Brand Config button with loading state

## 10. Frontend - Wizard Main Page

- [ ] 10.1 Create frontend/src/pages/BrandWizardPage.tsx
- [ ] 10.2 Implement wizard state management with useState/useReducer
- [ ] 10.3 Add useApiQuery hook for loading existing wizard state
- [ ] 10.4 Add auto-save on step change using mutation
- [ ] 10.5 Implement step navigation logic (block steps 2-7 until step 1 complete)
- [ ] 10.6 Add route for wizard page in App.tsx: /projects/:projectId/brand-wizard
- [ ] 10.7 Add "Configure Brand" button to ProjectDetailPage linking to wizard
- [ ] 10.8 Handle wizard completion: save V3 config, clear state, redirect to project

## 11. Frontend - WebSocket Indicator Fix

- [ ] 11.1 Update frontend/src/lib/hooks/useWebSocket.ts to track reconnection attempt count
- [ ] 11.2 Add shouldShowIndicator state (false until 3+ failed attempts)
- [ ] 11.3 Update frontend/src/pages/ProjectDetailPage.tsx connection indicator JSX
- [ ] 11.4 Hide indicator when connected or reconnecting (< 3 attempts)
- [ ] 11.5 Show subtle "Updates may be delayed" text after 3+ failed attempts
- [ ] 11.6 Remove spinning animation, use static muted icon
- [ ] 11.7 Test indicator behavior with network disconnection

## 12. Frontend - Phase Labels

- [ ] 12.1 Update frontend/src/lib/phaseUtils.ts PHASE_ORDER array with new names
- [ ] 12.2 Update frontend/src/lib/phaseUtils.ts phaseLabels mapping
- [ ] 12.3 Update phase labels: brand_setup→"Brand Setup", site_analysis→"Site Analysis", content_generation→"Content Generation", review_edit→"Review & Edit", export→"Export"
- [ ] 12.4 Search codebase for old phase name references and update
- [ ] 12.5 Test phase display in ProjectDetailPage and ProjectCard

## 13. Frontend - Update BrandConfigPanel

- [ ] 13.1 Update BrandConfigPanel to detect V3 vs V2 configs
- [ ] 13.2 Add "Launch Brand Wizard" button for projects without V3 config
- [ ] 13.3 Add "Upgrade to V3" button for projects with V2 config
- [ ] 13.4 Display V3 quick reference summary when V3 config exists
- [ ] 13.5 Keep existing V2 display for backward compatibility
- [ ] 13.6 Remove or simplify document upload section (wizard handles this now)

## 14. Testing & Verification

- [ ] 14.1 Run existing backend tests, fix any failures from phase name changes
- [ ] 14.2 Run existing frontend tests, fix any failures
- [ ] 14.3 Test complete wizard flow: new project → research → wizard → generate
- [ ] 14.4 Test wizard resume: leave mid-wizard, return, verify state restored
- [ ] 14.5 Test V2 backward compatibility: load existing V2 config, verify display
- [ ] 14.6 Test V2→V3 upgrade flow via wizard
- [ ] 14.7 Test Perplexity unavailable fallback (remove API key, verify manual entry works)
- [ ] 14.8 Test WebSocket indicator with simulated connection issues
- [ ] 14.9 Verify phase names updated in existing project records after migration

## 15. Deployment & Cleanup

- [ ] 15.1 Add PERPLEXITY_API_KEY to Railway environment variables
- [ ] 15.2 Run database migrations on staging
- [ ] 15.3 Verify staging deployment works end-to-end
- [ ] 15.4 Update CLAUDE.md with new brand wizard documentation
- [ ] 15.5 Remove deprecated BrandConfigPanel document upload code (if fully replaced)
- [ ] 15.6 Archive this change with /opsx:archive
