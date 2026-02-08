# Content Generation UI

Delta spec for modifications to the existing content generation UI capability.

## MODIFIED Requirements

### Requirement: Content generation progress page at step 4 of onboarding
The system SHALL provide a content generation page at `/projects/[id]/onboarding/content/` showing per-page pipeline progress and, after completion, a review-oriented list.

#### Scenario: Generation complete — review mode
- **WHEN** all pages have finished generation (overall_status is "complete")
- **THEN** page transitions to review mode showing a table with: Page URL, Primary Keyword, QA Status (pass/fail), Approval Status (approved/pending), and "Review" link to the editor page for each row

#### Scenario: Link to editor instead of read-only preview
- **WHEN** user clicks "Review" or the page URL on a completed page row
- **THEN** user navigates to `/projects/[id]/onboarding/content/[pageId]` which is now the full editor (not read-only preview)

### Requirement: Navigation integration with onboarding flow
The system SHALL integrate the content review step into the existing onboarding step progression.

#### Scenario: Step navigation from content to export
- **WHEN** user has approved at least one page and clicks "Continue to Export"
- **THEN** user is navigated to the export page (step 5)

#### Scenario: Onboarding progress indicator
- **WHEN** user is on the content generation/review page
- **THEN** the onboarding progress bar shows step 4 as active (Upload → Crawl → Keywords → Content → Export)
