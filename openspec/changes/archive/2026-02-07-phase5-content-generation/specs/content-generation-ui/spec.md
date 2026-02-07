# Content Generation UI

Frontend content generation progress page and prompt inspector panel for QA.

## ADDED Requirements

### Requirement: Content generation progress page at step 4 of onboarding
The system SHALL provide a content generation page at `/projects/[id]/onboarding/content/` showing per-page pipeline progress.

#### Scenario: Initial state before generation
- **WHEN** user navigates to the content generation page and no generation has been triggered
- **THEN** page shows a summary of approved pages (count, list) and a "Generate Content" button to start the pipeline

#### Scenario: Generation in progress
- **WHEN** content generation is running
- **THEN** page shows a table/list of all pages with columns: URL (or page title), keyword, status (pending/generating_brief/writing/checking/complete/failed), and polls every 3 seconds using TanStack Query refetch

#### Scenario: Status display per page
- **WHEN** a page's status updates during generation
- **THEN** the UI shows a visual pipeline indicator (Brief → Write → Check → Done) with the current step highlighted

#### Scenario: Generation complete
- **WHEN** all pages have finished generation
- **THEN** polling stops, page shows completion summary (X pages complete, Y failed), and each completed page has a link/button to view its content

#### Scenario: Generation with failures
- **WHEN** some pages fail during generation
- **THEN** failed pages show error status with a brief error description, and a "Retry" option for individual failed pages

### Requirement: Prompt Inspector side panel
The system SHALL provide a collapsible side panel that displays prompts sent to Claude for a selected page.

#### Scenario: Open prompt inspector
- **WHEN** user clicks on a page's prompt inspector button/icon during or after generation
- **THEN** a side panel opens showing all PromptLog entries for that page, organized by step (content_writing)

#### Scenario: Prompt display format
- **WHEN** prompt inspector is open for a page
- **THEN** each prompt entry shows: step label, system prompt (collapsible), user prompt (collapsible), Claude's response (collapsible), token usage (input/output), and duration

#### Scenario: Copy prompt to clipboard
- **WHEN** user clicks copy button on a prompt entry
- **THEN** the full prompt text (system + user) is copied to clipboard with a success toast notification

#### Scenario: Expand/collapse prompt sections
- **WHEN** user clicks on a prompt section header (system/user/response)
- **THEN** that section toggles between expanded (full text visible) and collapsed (truncated preview)

#### Scenario: Real-time prompt updates
- **WHEN** content generation is in progress for the selected page
- **THEN** prompt inspector shows prompts as they are created (polling updates include new PromptLog entries)

### Requirement: Navigation integration with onboarding flow
The system SHALL integrate the content generation page into the existing onboarding step progression.

#### Scenario: Step navigation from keywords
- **WHEN** user completes keyword approval (step 3) and clicks continue
- **THEN** user is navigated to the content generation page (step 4)

#### Scenario: Onboarding progress indicator
- **WHEN** user is on the content generation page
- **THEN** the onboarding progress bar/stepper shows step 4 as active (Upload → Crawl → Keywords → Content)
