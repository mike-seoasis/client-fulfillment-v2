## ADDED Requirements

### Requirement: Get brand config for project
The system SHALL allow users to retrieve the complete brand configuration for a project.

#### Scenario: Get brand config when exists
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config`
- **THEN** system returns 200 with complete brand config including version, generated_at, all 9 sections, and ai_prompt_snippet

#### Scenario: Get brand config when not generated
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config` for project without brand config
- **THEN** system returns 404 with error message "Brand config not yet generated"

#### Scenario: Get brand config for non-existent project
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config` with non-existent project ID
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Update brand config sections
The system SHALL allow users to update individual sections of the brand configuration.

#### Scenario: Update single section
- **WHEN** client sends PATCH to `/api/v1/projects/{project_id}/brand-config` with `{"brand_foundation": {...}}`
- **THEN** system updates only the brand_foundation section, preserves other sections, and returns 200 with updated config

#### Scenario: Update multiple sections
- **WHEN** client sends PATCH to `/api/v1/projects/{project_id}/brand-config` with multiple section updates
- **THEN** system updates all specified sections atomically and returns 200 with updated config

#### Scenario: Update with invalid section name
- **WHEN** client sends PATCH to `/api/v1/projects/{project_id}/brand-config` with unknown section key
- **THEN** system returns 400 with error message listing valid section names

#### Scenario: Update brand config that doesn't exist
- **WHEN** client sends PATCH to `/api/v1/projects/{project_id}/brand-config` for project without brand config
- **THEN** system returns 404 with error message "Brand config not yet generated"

### Requirement: Regenerate brand config
The system SHALL allow users to regenerate the entire brand config or specific sections.

#### Scenario: Regenerate entire config
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/regenerate` without section parameter
- **THEN** system starts full regeneration using current uploaded files and project URL, returns 202 Accepted

#### Scenario: Regenerate specific section
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/regenerate` with `{"section": "voice_dimensions"}`
- **THEN** system regenerates only that section using stored research context, returns 202 Accepted

#### Scenario: Regenerate multiple sections
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/regenerate` with `{"sections": ["vocabulary", "examples_bank"]}`
- **THEN** system regenerates specified sections, returns 202 Accepted

#### Scenario: Regenerate non-existent section
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/regenerate` with invalid section name
- **THEN** system returns 400 with error message listing valid section names

### Requirement: Brand config v2_schema structure
The system SHALL store brand config in a structured v2_schema format with 9 sections plus metadata.

#### Scenario: v2_schema contains all required fields
- **WHEN** brand config is retrieved
- **THEN** v2_schema contains: `version`, `generated_at`, `source_documents`, `additional_info`, `brand_foundation`, `target_audience`, `voice_dimensions`, `voice_characteristics`, `writing_style`, `vocabulary`, `trust_elements`, `examples_bank`, `competitor_context`, `ai_prompt_snippet`

#### Scenario: brand_foundation section structure
- **WHEN** brand_foundation section is retrieved
- **THEN** it contains: company_overview (name, founded, location, industry, business_model), what_they_sell (primary, secondary, price_point, channels), brand_positioning (tagline, one_sentence, category_position), mission_values (mission, core_values, brand_promise), differentiators (primary_usp, supporting, what_theyre_not)

#### Scenario: target_audience section structure
- **WHEN** target_audience section is retrieved
- **THEN** it contains array of personas, each with: name, percentage, demographics, psychographics, behavioral_insights, communication_preferences, summary

#### Scenario: voice_dimensions section structure
- **WHEN** voice_dimensions section is retrieved
- **THEN** it contains: formality (scale 1-10, description, example), humor (scale, description, example), reverence (scale, description, example), enthusiasm (scale, description, example), voice_summary

#### Scenario: voice_characteristics section structure
- **WHEN** voice_characteristics section is retrieved
- **THEN** it contains: we_are (array of traits with do/dont examples), we_are_not (array of anti-traits)

#### Scenario: writing_style section structure
- **WHEN** writing_style section is retrieved
- **THEN** it contains: sentence_structure, capitalization, punctuation, numbers_formatting, formatting rules

#### Scenario: vocabulary section structure
- **WHEN** vocabulary section is retrieved
- **THEN** it contains: power_words, word_substitutions (instead_of/we_say pairs), banned_words, industry_terms, signature_phrases

#### Scenario: trust_elements section structure
- **WHEN** trust_elements section is retrieved
- **THEN** it contains: hard_numbers, credentials_certifications, media_press, endorsements, guarantees_policies, customer_quotes

#### Scenario: examples_bank section structure
- **WHEN** examples_bank section is retrieved
- **THEN** it contains: headlines_that_work, product_description_examples, email_subject_lines, social_media_posts, ctas_that_work, what_not_to_write

#### Scenario: competitor_context section structure
- **WHEN** competitor_context section is retrieved
- **THEN** it contains: direct_competitors (array with name, positioning, our_difference), competitive_advantages, positioning_statements

### Requirement: Brand config tracks source documents
The system SHALL track which uploaded documents were used to generate the brand config.

#### Scenario: source_documents contains file IDs
- **WHEN** brand config is generated with uploaded documents
- **THEN** v2_schema.source_documents contains array of ProjectFile UUIDs used in generation

#### Scenario: source_documents empty when no docs uploaded
- **WHEN** brand config is generated without uploaded documents
- **THEN** v2_schema.source_documents is empty array
