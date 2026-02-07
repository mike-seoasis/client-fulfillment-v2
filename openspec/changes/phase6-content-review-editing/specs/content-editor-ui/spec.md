# Content Editor UI

Frontend content editor page with Lexical rich text editor for bottom description, four-layer keyword highlighting, live stats sidebar, and approval controls.

## ADDED Requirements

### Requirement: Content editor page replaces read-only preview
The system SHALL provide a content editor page at `/projects/[id]/onboarding/content/[pageId]` that replaces the existing read-only preview with a full editing interface.

#### Scenario: Page layout
- **WHEN** user navigates to the content editor page for a page with generated content
- **THEN** page renders a two-column layout: left column (~65%) contains all 4 content fields stacked vertically, right column (~35%) contains a sticky stats/quality sidebar

#### Scenario: Header with page context
- **WHEN** the editor page loads
- **THEN** header shows breadcrumb (Project › Onboarding › Content › Page), the page URL, primary keyword as a badge, and a "Back to content list" link

### Requirement: Page title field with character count
The system SHALL provide an editable text input for the page title with a live character counter.

#### Scenario: Title character count display
- **WHEN** user views or edits the page title field
- **THEN** a character counter shows "{current} / 70" that updates on every keystroke, displayed in palm-600 when under 70 and coral-600 when over

### Requirement: Meta description field with character count
The system SHALL provide an editable textarea for the meta description with a live character counter.

#### Scenario: Meta description character count display
- **WHEN** user views or edits the meta description field
- **THEN** a character counter shows "{current} / 160" that updates on every keystroke, displayed in palm-600 when under 160 and coral-600 when over

### Requirement: Top description field with word count
The system SHALL provide an editable textarea for the top description with a live word counter.

#### Scenario: Top description word count
- **WHEN** user views or edits the top description
- **THEN** a word count displays below the field, updating on change

### Requirement: Bottom description with Lexical rich text editor
The system SHALL provide a Lexical rich text editor for the bottom description field that supports structured HTML editing.

#### Scenario: Rendered view (default)
- **WHEN** the "Rendered" tab is active (default)
- **THEN** the bottom description displays in a Lexical editor with formatted content (headings, paragraphs, lists), keyword highlights visible inline, and the content is directly editable

#### Scenario: HTML source view
- **WHEN** user clicks the "HTML Source" tab
- **THEN** the bottom description shows the raw HTML in a monospace textarea for direct HTML editing

#### Scenario: Toggle between views
- **WHEN** user switches between Rendered and HTML Source tabs
- **THEN** changes made in one view are reflected in the other (Lexical serializes to HTML, HTML parses into Lexical state)

#### Scenario: Word count and heading count
- **WHEN** the bottom description content changes
- **THEN** the footer bar below the editor shows updated word count and heading breakdown (e.g., "4 H2 · 4 H3")

### Requirement: Four-layer keyword highlighting in Lexical editor
The system SHALL highlight four categories of terms inline in the bottom description editor using Lexical decorator nodes.

#### Scenario: Primary keyword exact match highlighting
- **WHEN** the primary keyword (e.g., "best running shoes") appears exactly in the content
- **THEN** each occurrence is highlighted with a solid gold underline highlight

#### Scenario: Primary keyword variation highlighting
- **WHEN** variations of the primary keyword (e.g., "shoes", "runners", "running") appear in the content
- **THEN** each occurrence is highlighted with a lighter gold color and dashed underline, visually distinct from exact matches

#### Scenario: LSI term highlighting
- **WHEN** LSI terms from the POP content brief (e.g., "foam technology", "cushioning") appear in the content
- **THEN** each occurrence is highlighted with a lagoon/teal background tint and bottom border

#### Scenario: AI trope violation highlighting
- **WHEN** a passage is flagged by the quality check system (e.g., AI opener pattern, negation contrast)
- **THEN** the flagged text is highlighted with a coral wavy underline

#### Scenario: Highlight toggle controls
- **WHEN** user clicks the highlight toggle buttons in the page header
- **THEN** each highlight layer can be independently toggled on/off: "Keywords + Vars" controls both exact and variation highlights together, "LSI Terms" controls LSI highlights, "Issues" controls trope violation highlights

### Requirement: Live stats sidebar
The system SHALL display a sticky right sidebar with live content statistics that update as the user edits.

#### Scenario: Quality status card
- **WHEN** sidebar loads with qa_results data
- **THEN** it shows overall status ("Pass" with palm green or "N Issues Found" with coral), and individual check results (banned words, em dashes, AI openers, triplet lists, rhetorical questions, tier 1 AI words, tier 2 AI words, negation contrast) each with pass/fail indicator

#### Scenario: Flagged passages with jump-to
- **WHEN** qa_results contains issues
- **THEN** sidebar shows each violation with a red dot, short description, context quote, and a "Jump to" link that scrolls the editor to the flagged passage and pulses the highlight

#### Scenario: Content stats section
- **WHEN** sidebar renders the content stats
- **THEN** it shows: word count, heading count vs brief targets (e.g., "4 H2 · 4 H3" with "Target: 3–8 H2, 4–12 H3"), primary keyword exact match count with density bar, and primary keyword variation count with the variation words listed

#### Scenario: LSI term checklist
- **WHEN** sidebar renders the LSI term section
- **THEN** it shows each LSI term from the content brief with: a green dot and occurrence count for terms found in the content, the term text in readable warm-600 for terms not found (no strikethrough, no heavy opacity reduction), a summary "N of M terms used" at the top, and found terms are clickable to scroll to first occurrence in the editor

#### Scenario: Heading outline
- **WHEN** sidebar renders the heading outline
- **THEN** it shows a mini table of contents derived from H2/H3 headings in the bottom description, with H3s indented under their parent H2

### Requirement: Auto-save with indicator
The system SHALL auto-save content edits with a visible indicator.

#### Scenario: Auto-save on blur
- **WHEN** user moves focus away from a content field (blur event) and the field value has changed
- **THEN** system calls the PUT content update endpoint and shows "Saving..." in the bottom bar, then "Auto-saved just now" on success

#### Scenario: Auto-save indicator
- **WHEN** auto-save completes
- **THEN** bottom action bar shows a green dot with "Auto-saved {time}" (e.g., "Auto-saved 2 min ago") that updates periodically

#### Scenario: Save failure
- **WHEN** auto-save fails
- **THEN** bottom bar shows a coral warning "Save failed — click to retry" and does not overwrite the user's local edits

### Requirement: Bottom action bar with save, re-check, and approve
The system SHALL display a sticky bottom action bar with content actions.

#### Scenario: Action bar layout
- **WHEN** the editor page loads
- **THEN** the bottom bar shows: left side has auto-save indicator, right side has "Re-run Checks" (secondary), "Save Draft" (secondary), and "Approve" (primary palm-500 green) buttons

#### Scenario: Re-run checks
- **WHEN** user clicks "Re-run Checks"
- **THEN** system calls the recheck-content endpoint, shows a loading spinner on the button, and updates the sidebar quality panel with fresh results on completion

#### Scenario: Save draft
- **WHEN** user clicks "Save Draft"
- **THEN** system calls the PUT content update endpoint with all current field values and shows a success toast

#### Scenario: Approve content
- **WHEN** user clicks "Approve" on content that has status "complete"
- **THEN** system calls the approve-content endpoint, button changes to show a checkmark with "Approved" state, and the content list reflects the updated status

#### Scenario: Unapprove content
- **WHEN** user clicks the "Approved" button on already-approved content
- **THEN** system calls approve-content with value=false, button reverts to "Approve" state
