# Content Quality Checks

Service that runs deterministic AI trope detection on generated content to flag common quality issues without API costs.

## ADDED Requirements

### Requirement: Detect banned words from brand config
The system SHALL check generated content against the project's banned words list from brand config vocabulary.

#### Scenario: Banned word detected
- **WHEN** content contains a word from the brand config's banned_words list (e.g., "cheap" when banned)
- **THEN** system flags the content with a "banned_word" issue, listing each occurrence with the word and its location (which field: page_title, meta_description, top_description, or bottom_description)

#### Scenario: No banned words
- **WHEN** content does not contain any banned words
- **THEN** banned_word check passes with no issues

### Requirement: Detect em dashes
The system SHALL flag any use of em dashes in generated content (brand standard: never use).

#### Scenario: Em dash detected
- **WHEN** content contains an em dash character (—) in any field
- **THEN** system flags the content with an "em_dash" issue, listing each occurrence with its field and surrounding context

#### Scenario: En dashes and hyphens are allowed
- **WHEN** content contains regular hyphens (-) or en dashes (–) but no em dashes
- **THEN** em_dash check passes with no issues

### Requirement: Detect common AI writing patterns
The system SHALL flag content containing common AI-generated writing patterns.

#### Scenario: AI opener patterns detected
- **WHEN** content contains phrases like "In today's...", "Whether you're...", "Look no further", "In the world of...", "When it comes to..."
- **THEN** system flags the content with an "ai_pattern" issue for each detected pattern, listing the phrase and field

#### Scenario: Excessive triplet lists detected
- **WHEN** content contains more than 2 instances of triplet list patterns ("X, Y, and Z" constructions)
- **THEN** system flags the content with a "triplet_excess" issue with count and examples

#### Scenario: Excessive rhetorical questions detected
- **WHEN** content contains more than 1 rhetorical question (questions not in FAQ section)
- **THEN** system flags the content with a "rhetorical_excess" issue with count and examples

### Requirement: Return structured quality results
The system SHALL return quality check results as a structured object stored in PageContent.

#### Scenario: Quality results structure
- **WHEN** quality checks complete for a page
- **THEN** system stores results in PageContent.qa_results as JSON with: passed (boolean), issues (array of {type, field, description, context}), checked_at (timestamp)

#### Scenario: All checks pass
- **WHEN** no quality issues are detected
- **THEN** qa_results.passed is true and qa_results.issues is an empty array

#### Scenario: Some checks fail
- **WHEN** one or more quality issues are detected
- **THEN** qa_results.passed is false and qa_results.issues contains all detected issues (content is NOT regenerated — issues are informational for user review)
