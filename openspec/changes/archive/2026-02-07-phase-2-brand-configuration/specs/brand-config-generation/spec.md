## ADDED Requirements

### Requirement: Trigger brand config generation
The system SHALL allow users to start brand config generation for a project, which runs as a background task.

#### Scenario: Start generation successfully
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/generate`
- **THEN** system starts background generation task, sets status to "generating", and returns 202 Accepted with initial status

#### Scenario: Start generation for non-existent project
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/generate` with non-existent project ID
- **THEN** system returns 404 with error message "Project not found"

#### Scenario: Start generation while already generating
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/brand-config/generate` while generation is in progress
- **THEN** system returns 409 with error message "Generation already in progress"

### Requirement: Poll generation status
The system SHALL allow users to poll the status of brand config generation.

#### Scenario: Poll status while generating
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config/status` while generation is in progress
- **THEN** system returns 200 with status object containing `status: "generating"`, `current_step`, `steps_completed`, `steps_total`, and `error: null`

#### Scenario: Poll status when complete
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config/status` after generation completes
- **THEN** system returns 200 with status object containing `status: "complete"` and all steps in `steps_completed`

#### Scenario: Poll status when failed
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config/status` after generation fails
- **THEN** system returns 200 with status object containing `status: "failed"` and `error` describing the failure

#### Scenario: Poll status when no generation started
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/brand-config/status` for project with no generation history
- **THEN** system returns 200 with status object containing `status: "pending"` and empty `steps_completed`

### Requirement: Research phase gathers source material
The system SHALL gather research from three sources in parallel during generation: Perplexity web research, website crawl, and uploaded document text.

#### Scenario: Perplexity research completes successfully
- **WHEN** generation reaches the perplexity_research step
- **THEN** system calls Perplexity API with brand research prompt covering all 9 sections, stores result with citations

#### Scenario: Perplexity research fails gracefully
- **WHEN** Perplexity API call fails or times out
- **THEN** system logs warning, continues generation with website crawl and documents only, notes limitation in generated config

#### Scenario: Website crawl extracts content
- **WHEN** generation reaches the crawling step
- **THEN** system uses Crawl4AI to extract markdown from project's site_url, stores extracted content

#### Scenario: Website crawl fails gracefully
- **WHEN** Crawl4AI fails to crawl the website
- **THEN** system logs warning, continues generation with Perplexity research and documents only

#### Scenario: Document text is combined
- **WHEN** generation reaches the processing_docs step
- **THEN** system retrieves extracted_text from all ProjectFile records for the project and combines into single context document

### Requirement: Synthesis phase generates 9 brand config sections
The system SHALL generate each of the 9 brand config sections sequentially using Claude, with each section building on previous context.

#### Scenario: Brand foundation section generated
- **WHEN** generation reaches the brand_foundation step
- **THEN** system calls Claude with combined research context and skill bible template, generates brand_foundation section with company overview, positioning, mission, values, and differentiators

#### Scenario: Target audience section generated
- **WHEN** generation reaches the target_audience step
- **THEN** system calls Claude with research context and previous sections, generates target_audience section with personas including demographics, psychographics, and behavioral insights

#### Scenario: Voice dimensions section generated
- **WHEN** generation reaches the voice_dimensions step
- **THEN** system calls Claude to analyze formality, humor, reverence, and enthusiasm scales (1-10) with examples

#### Scenario: Voice characteristics section generated
- **WHEN** generation reaches the voice_characteristics step
- **THEN** system calls Claude to generate "we are" and "we are not" voice traits with do/don't examples

#### Scenario: Writing style section generated
- **WHEN** generation reaches the writing_style step
- **THEN** system calls Claude to generate sentence structure, capitalization, punctuation, and formatting rules

#### Scenario: Vocabulary section generated
- **WHEN** generation reaches the vocabulary step
- **THEN** system calls Claude to generate power words, word substitutions, banned words, and industry terms

#### Scenario: Trust elements section generated
- **WHEN** generation reaches the trust_elements step
- **THEN** system calls Claude to extract hard numbers, credentials, guarantees, and customer quotes from research

#### Scenario: Examples bank section generated
- **WHEN** generation reaches the examples_bank step
- **THEN** system calls Claude to generate on-brand headline examples, CTAs, and off-brand examples to avoid

#### Scenario: Competitor context section generated
- **WHEN** generation reaches the competitor_context step
- **THEN** system calls Claude to generate competitor analysis and positioning statements

#### Scenario: AI prompt snippet generated last
- **WHEN** generation reaches the ai_prompt_snippet step
- **THEN** system calls Claude to synthesize all sections into a concise AI prompt snippet for content generation

### Requirement: Generation stores result in BrandConfig
The system SHALL store the complete generated brand config in the BrandConfig.v2_schema JSONB field.

#### Scenario: Complete config stored on success
- **WHEN** all generation steps complete successfully
- **THEN** system stores complete v2_schema with version, generated_at timestamp, source_documents, and all 9 sections plus ai_prompt_snippet

#### Scenario: Partial config stored on failure
- **WHEN** generation fails mid-way
- **THEN** system stores partial config with completed sections, sets status to "failed", and preserves error details

### Requirement: Generation respects timeout limits
The system SHALL enforce per-step and total timeout limits to prevent runaway generation.

#### Scenario: Individual step times out
- **WHEN** a single generation step exceeds 60 seconds
- **THEN** system cancels that step, logs timeout, and continues to next step with null for that section

#### Scenario: Total generation times out
- **WHEN** total generation exceeds 5 minutes
- **THEN** system stops generation, stores partial results, sets status to "failed" with timeout error
