# brand-wizard Specification

## Purpose

7-step guided wizard for comprehensive brand configuration, with auto-fill from Perplexity research and manual editing capabilities. Replaces the current simple document-upload flow with a structured approach following the Brand Guidelines Bible framework.

## ADDED Requirements

### Requirement: V3 schema structure

The system SHALL store brand configuration in a V3 schema with 11 sections following the Brand Guidelines Bible framework.

#### Scenario: V3 schema created

- **WHEN** user completes brand wizard
- **THEN** system MUST generate a V3 schema with `_version: "3.0"` marker
- **AND** schema MUST include all 11 sections: foundation, personas, voice_dimensions, voice_characteristics, writing_rules, vocabulary, proof_elements, examples_bank, competitor_context, ai_prompts, quick_reference
- **AND** schema MUST include `_generated_at` timestamp and `_sources_used` array

#### Scenario: V2 schema backward compatibility

- **WHEN** system loads an existing V2 brand config (no `_version` or `_version: "2.0"`)
- **THEN** system MUST display V2 data in legacy format
- **AND** system MUST NOT auto-upgrade to V3
- **AND** system MUST offer "Upgrade to V3" action that launches wizard with V2 data pre-filled

### Requirement: 7-step wizard flow

The system SHALL provide a 7-step wizard for brand configuration with the following steps.

#### Scenario: Step 1 - Brand Setup

- **WHEN** user enters Step 1
- **THEN** system MUST display inputs for: brand name (required), domain URL (optional)
- **AND** system MUST show "Research Brand" button when domain is provided
- **AND** clicking "Research Brand" MUST trigger Perplexity research and auto-fill subsequent steps

#### Scenario: Step 2 - Foundation

- **WHEN** user enters Step 2
- **THEN** system MUST display editable fields for: company overview, industry, business model, positioning statement, mission statement, core values, key differentiators, products/services
- **AND** fields MUST be pre-filled from research if available

#### Scenario: Step 3 - Audience

- **WHEN** user enters Step 3
- **THEN** system MUST display persona cards (add/edit/remove)
- **AND** each persona MUST include: name, demographics, psychographics, pain points, motivations, buying triggers
- **AND** user MUST be able to mark one persona as primary

#### Scenario: Step 4 - Voice

- **WHEN** user enters Step 4
- **THEN** system MUST display 4 voice dimension sliders (1-10 scale): formality, humor, reverence, enthusiasm
- **AND** each slider MUST show example text at low/high ends
- **AND** system MUST display voice characteristics editor (we are / we are not) with trait, description, example fields

#### Scenario: Step 5 - Writing Rules

- **WHEN** user enters Step 5
- **THEN** system MUST display toggles and inputs for: sentence length range, paragraph length range, contractions allowed, oxford comma, exclamation limit, capitalization rules
- **AND** system MUST display vocabulary editor with: power words (chips), banned words (chips), preferred terms (key-value pairs), industry terms

#### Scenario: Step 6 - Proof & Examples

- **WHEN** user enters Step 6
- **THEN** system MUST display editors for: statistics, credentials, customer quotes, guarantees
- **AND** system MUST display examples bank with good/bad examples for: headlines, product descriptions, CTAs

#### Scenario: Step 7 - Review & Generate

- **WHEN** user enters Step 7
- **THEN** system MUST display summary of all sections with edit links
- **AND** system MUST display Quick Reference section editor (voice in 3 words, one-sentence summary, primary audience, key CTA, avoid list)
- **AND** system MUST show "Generate Brand Config" button
- **AND** clicking generate MUST save V3 schema and redirect to project detail page

### Requirement: Wizard state persistence

The system SHALL auto-save wizard state after each step to prevent data loss.

#### Scenario: Auto-save on step change

- **WHEN** user navigates away from a wizard step
- **THEN** system MUST save current step data to `brand_wizard_state` JSONB column
- **AND** system MUST save current step number

#### Scenario: Resume wizard

- **WHEN** user returns to wizard after leaving
- **THEN** system MUST restore wizard to last saved step
- **AND** system MUST restore all previously entered data

#### Scenario: Complete wizard clears state

- **WHEN** user completes wizard (Step 7 generate)
- **THEN** system MUST clear `brand_wizard_state` column
- **AND** system MUST save final V3 schema to brand_config

### Requirement: Wizard navigation

The system SHALL allow flexible navigation between wizard steps after Step 1.

#### Scenario: Step 1 required first

- **WHEN** user has not completed Step 1 (brand name)
- **THEN** system MUST NOT allow navigation to other steps
- **AND** system MUST display message explaining brand name is required

#### Scenario: Jump to any step after Step 1

- **WHEN** user has completed Step 1
- **THEN** system MUST allow clicking on any step in progress indicator to jump to that step
- **AND** system MUST preserve data entered in all steps

### Requirement: WebSocket indicator visibility

The system SHALL hide the WebSocket connection indicator by default to avoid confusing users.

#### Scenario: Connected state hidden

- **WHEN** WebSocket is connected
- **THEN** system MUST NOT display any connection indicator

#### Scenario: Reconnecting state hidden initially

- **WHEN** WebSocket enters reconnecting state
- **THEN** system MUST NOT display indicator for first 3 reconnection attempts
- **AND** system MUST continue using polling fallback silently

#### Scenario: Error state shown

- **WHEN** WebSocket fails to connect after 3 attempts
- **THEN** system MUST display subtle "Updates may be delayed" indicator
- **AND** indicator MUST NOT use alarming colors or spinning animation

### Requirement: Phase name display

The system SHALL display user-friendly phase names instead of technical names.

#### Scenario: Phase labels in UI

- **WHEN** displaying project phases in any UI component
- **THEN** system MUST use display labels: "Brand Setup", "Site Analysis", "Content Generation", "Review & Edit", "Export"
- **AND** system MUST map internal names: brand_setup, site_analysis, content_generation, review_edit, export

### Requirement: Phase name migration

The system SHALL migrate existing project phase names in database.

#### Scenario: Migration updates existing records

- **WHEN** database migration runs
- **THEN** system MUST rename phase keys in all existing project records
- **AND** discovery → brand_setup, requirements → site_analysis, implementation → content_generation, review → review_edit, launch → export
