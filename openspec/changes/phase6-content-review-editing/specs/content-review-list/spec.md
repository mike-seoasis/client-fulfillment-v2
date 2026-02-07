# Content Review List

Frontend content list page showing approval status, QA results, and bulk approve for all pages in a project.

## ADDED Requirements

### Requirement: Content review list page with approval status
The system SHALL update the content list page at `/projects/[id]/onboarding/content/` to show review-oriented columns after generation is complete.

#### Scenario: List view after generation complete
- **WHEN** user navigates to the content list page and content generation is complete for at least one page
- **THEN** the page shows a table with columns: Page URL, Primary Keyword, QA Status (pass/fail icon), Approval Status (approved/pending icon), and a "Review" link that navigates to the editor page

#### Scenario: QA status display
- **WHEN** a page has qa_results
- **THEN** the QA column shows a green checkmark if `qa_results.passed` is true, or a coral warning icon with issue count if false

#### Scenario: Approval status display
- **WHEN** a page has `is_approved=true`
- **THEN** the approval column shows a green "Approved" badge
- **WHEN** a page has `is_approved=false` and status is "complete"
- **THEN** the approval column shows a neutral "Pending" badge

#### Scenario: Approved count summary
- **WHEN** the list page renders
- **THEN** a summary line shows "Approved: N of M" where N is approved pages and M is total complete pages

### Requirement: Bulk approve from list page
The system SHALL provide a bulk approve button on the content list page.

#### Scenario: Bulk approve all passing
- **WHEN** user clicks "Approve All Ready" button
- **THEN** system calls bulk-approve-content endpoint, updates the list with new approval statuses, and shows a toast "N pages approved"

#### Scenario: Button state
- **WHEN** there are no pages eligible for bulk approve (all already approved or all have QA issues)
- **THEN** the "Approve All Ready" button is disabled with a tooltip explaining why

### Requirement: Navigation to export step
The system SHALL allow proceeding to the export step when content is approved.

#### Scenario: Continue to export
- **WHEN** at least one page has `is_approved=true`
- **THEN** a "Continue to Export" button is enabled at the bottom of the list page

#### Scenario: No approved content
- **WHEN** no pages have `is_approved=true`
- **THEN** the "Continue to Export" button is disabled with text "Approve content to continue"
