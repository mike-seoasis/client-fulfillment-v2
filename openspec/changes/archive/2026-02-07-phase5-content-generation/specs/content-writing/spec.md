# Content Writing

Service that generates SEO-optimized collection page content using Claude, guided by POP content brief data and brand configuration.

## ADDED Requirements

### Requirement: Generate 4 content fields per page in a single Claude call
The system SHALL generate page_title, meta_description, top_description, and bottom_description for a crawled page using a single Claude API call.

#### Scenario: Successful content generation
- **WHEN** `generate_content()` is called for a page with keyword "mens trail running shoes", a ContentBrief with LSI terms, and brand config
- **THEN** system calls Claude with a structured prompt and parses the JSON response into a PageContent record with all 4 fields populated

#### Scenario: Claude returns invalid JSON
- **WHEN** Claude's response cannot be parsed as valid JSON
- **THEN** system retries once with a stricter prompt, and if still invalid, marks PageContent status as "failed" with error details

#### Scenario: Claude API unavailable
- **WHEN** Claude API returns an error or circuit breaker is open
- **THEN** system marks PageContent status as "failed" with error details and moves to the next page

### Requirement: Construct structured prompts from brief + brand config + page context
The system SHALL build content writing prompts with clearly labeled sections combining POP brief data, brand configuration, and crawled page context.

#### Scenario: Full prompt construction with POP brief
- **WHEN** a page has a ContentBrief with LSI terms, variations, and word count targets
- **THEN** system constructs a prompt with sections: Task, Page Context (URL, current title, current meta, product count, labels), SEO Targets (LSI terms with weights, variations, word count target), Brand Voice (ai_prompt_snippet, banned words), and Output Format

#### Scenario: Prompt construction without POP brief (fallback)
- **WHEN** a page has no ContentBrief (POP fetch failed or mock mode)
- **THEN** system constructs a prompt using default word count target (300-400 words for bottom_description), page context, and brand config, omitting the SEO Targets section's LSI terms

#### Scenario: Brand config injection
- **WHEN** project has brand config with ai_prompt_snippet and vocabulary (banned words)
- **THEN** system injects ai_prompt_snippet as the system prompt and includes banned words list in the user prompt's Brand Voice section

### Requirement: Store generated content in PageContent model
The system SHALL store all generated content in a single PageContent row per page with status tracking.

#### Scenario: Successful storage
- **WHEN** Claude returns valid content JSON
- **THEN** system creates/updates PageContent with page_title, meta_description, top_description (plain text, 1-2 sentences), bottom_description (HTML with headings/FAQ), word_count, and status="complete"

#### Scenario: Status progression
- **WHEN** content generation pipeline runs for a page
- **THEN** PageContent.status progresses through: pending → generating_brief → writing → checking → complete (or failed at any step)

#### Scenario: Timestamps tracking
- **WHEN** content generation starts and completes
- **THEN** system records generation_started_at and generation_completed_at timestamps

### Requirement: Log all prompts to PromptLog table
The system SHALL persist every prompt sent to Claude and its response in the PromptLog table.

#### Scenario: Prompt logging on generation
- **WHEN** Claude is called for content writing
- **THEN** system creates a PromptLog record with: page_content_id, step="content_writing", role="system" (with system prompt text), role="user" (with user prompt text), and after completion: response_text, model, input_tokens, output_tokens, duration_ms

#### Scenario: Prompt log includes token usage
- **WHEN** Claude responds to a content writing call
- **THEN** PromptLog records input_tokens, output_tokens, and duration_ms from the API response

### Requirement: Use Claude Sonnet for content generation
The system SHALL use claude-sonnet-4-5 for all content generation calls.

#### Scenario: Model selection
- **WHEN** content writing service calls Claude
- **THEN** system uses model "claude-sonnet-4-5-20250929" (Claude Sonnet 4.5)

### Requirement: Content format specifications
The system SHALL generate content matching specific format requirements for each field.

#### Scenario: Top description format
- **WHEN** content is generated
- **THEN** top_description is plain text, 1-2 sentences describing the collection page, no HTML

#### Scenario: Bottom description format
- **WHEN** content is generated
- **THEN** bottom_description is HTML with headings and FAQ section, targeting POP brief word count (or 300-400 words fallback)

#### Scenario: Page title format
- **WHEN** content is generated
- **THEN** page_title is optimized for SEO, includes the primary keyword, and is under 60 characters

#### Scenario: Meta description format
- **WHEN** content is generated
- **THEN** meta_description is optimized for click-through, includes the primary keyword, and is under 160 characters
