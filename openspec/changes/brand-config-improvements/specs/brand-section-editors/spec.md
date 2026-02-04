## ADDED Requirements

### Requirement: Inline editing for brand config sections
The system SHALL provide inline editing components for all 10 brand config sections, replacing raw JSON editing with user-friendly form controls.

#### Scenario: User edits Brand Foundation section
- **WHEN** user clicks Edit on Brand Foundation section
- **THEN** system displays text inputs for company name, tagline, mission, and bullet list editors for products, values, and differentiators

#### Scenario: User edits Voice Dimensions section
- **WHEN** user clicks Edit on Voice Dimensions section
- **THEN** system displays interactive sliders (1-10 scale) for Formality, Humor, Reverence, and Enthusiasm with live value updates

#### Scenario: User edits Voice Characteristics section
- **WHEN** user clicks Edit on Voice Characteristics section
- **THEN** system displays editable trait cards for "We Are" characteristics with add/remove buttons, and an editable list for "We Are NOT" items

#### Scenario: User edits Target Audience section
- **WHEN** user clicks Edit on Target Audience section
- **THEN** system displays persona cards with editable fields for demographics, psychographics, and communication preferences

#### Scenario: User edits Writing Style section
- **WHEN** user clicks Edit on Writing Style section
- **THEN** system displays categorized inputs for sentence structure, capitalization, punctuation, and formatting rules

#### Scenario: User edits Vocabulary section
- **WHEN** user clicks Edit on Vocabulary section
- **THEN** system displays tag inputs for power words and banned words, and an editable table for word substitutions

#### Scenario: User edits Trust Elements section
- **WHEN** user clicks Edit on Trust Elements section
- **THEN** system displays structured inputs for hard numbers, credentials, customer quotes, and guarantees

#### Scenario: User edits Examples Bank section
- **WHEN** user clicks Edit on Examples Bank section
- **THEN** system displays textareas for headlines, product descriptions, email subjects, social posts, and CTAs

#### Scenario: User edits Competitor Context section
- **WHEN** user clicks Edit on Competitor Context section
- **THEN** system displays an editable table for competitors with columns for name, positioning, and differentiation

#### Scenario: User edits AI Prompt section
- **WHEN** user clicks Edit on AI Prompt section
- **THEN** system displays a large textarea for the prompt snippet and text inputs for supporting metadata

### Requirement: Editor state management
The system SHALL maintain local state during editing and only persist changes when user explicitly saves.

#### Scenario: User cancels editing
- **WHEN** user clicks Cancel while editing a section
- **THEN** system discards all changes and reverts to the previously saved data

#### Scenario: User saves changes
- **WHEN** user clicks Save after editing a section
- **THEN** system validates the data, calls the update API, and displays the updated section in read mode

#### Scenario: Validation error on save
- **WHEN** user attempts to save with invalid data (e.g., empty required field)
- **THEN** system displays inline validation errors and prevents save until corrected

### Requirement: Editor keyboard shortcuts
The system SHALL support keyboard shortcuts for common editing actions.

#### Scenario: Save with keyboard
- **WHEN** user presses Cmd/Ctrl+S while editing
- **THEN** system saves the current changes

#### Scenario: Cancel with keyboard
- **WHEN** user presses Escape while editing
- **THEN** system cancels editing and discards changes
