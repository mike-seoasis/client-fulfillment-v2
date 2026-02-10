## ADDED Requirements

### Requirement: Link planning trigger page
The system SHALL provide a link planning page accessible from the project detail view for both onboarding and cluster scopes.

The page SHALL display:
- Prerequisites checklist (all keywords approved, all content generated, quality checks passed) with pass/fail indicators
- "Plan & Inject Links" button, disabled until all prerequisites are met
- Link rules summary (informational, scope-specific)

For cluster scope: accessible at `/projects/{id}/clusters/{clusterId}/links`
For onboarding scope: accessible at `/projects/{id}/links`

#### Scenario: All prerequisites met
- **WHEN** all pages in scope have approved keywords and complete content
- **THEN** the "Plan & Inject Links" button SHALL be enabled

#### Scenario: Prerequisites not met
- **WHEN** 3 pages are missing completed content
- **THEN** the button SHALL be disabled and the prerequisites checklist SHALL show which items fail with counts

#### Scenario: Rules display adapts to scope
- **WHEN** viewing the cluster link planning page
- **THEN** the rules section SHALL mention "First link on every child page → parent collection" and silo constraints
- **WHEN** viewing the onboarding link planning page
- **THEN** the rules section SHALL mention "Pages link to related pages (shared labels)" and priority page weighting

### Requirement: Link planning progress indicator
When link planning is in progress, the page SHALL display a progress indicator showing:
- Overall progress bar
- Current step label (1-4): "Building link graph", "Selecting targets & anchor text", "Injecting links into content", "Validating link rules"
- Page-level progress for steps 2 and 3 (e.g., "5/8 pages")
- Completed steps with checkmarks, current step with spinner, pending steps grayed out

The progress SHALL poll the status endpoint every 2 seconds.

On completion, the page SHALL automatically redirect to the Link Map page.

#### Scenario: Planning in progress at step 2
- **WHEN** the planner is at step 2, processing page 5 of 8
- **THEN** step 1 SHALL show a checkmark, step 2 SHALL show a spinner with "5/8 pages", steps 3-4 SHALL be grayed out

#### Scenario: Planning complete
- **WHEN** the planner finishes all 4 steps
- **THEN** the page SHALL redirect to the link map view after a brief success message

### Requirement: Cluster link map visualization
For cluster scope, the link map page SHALL display:
- A tree diagram with the parent page at the top and child pages below
- Each page node showing: page title (truncated), inbound count (↑N), outbound count (↓N)
- Sibling connection indicators (◄► arrows) between child pages that link to each other
- The parent page marked distinctly (star icon or "parent" label)

#### Scenario: Cluster with parent and 5 children
- **WHEN** viewing the link map for a cluster with 1 parent and 5 children
- **THEN** the tree SHALL show the parent at the top with lines connecting to 5 child nodes below, each with link counts

### Requirement: Onboarding link map visualization
For onboarding scope, the link map page SHALL display:
- Pages grouped by primary label
- Each group shows the label name and the pages within it
- Connections between groups indicate shared labels that create cross-group linking
- Priority pages marked with a star icon (★)

#### Scenario: Onboarding with 24 pages across 6 label groups
- **WHEN** viewing the link map for an onboarding scope with 24 pages
- **THEN** pages SHALL be grouped by their most common label, with connecting indicators between groups that share labels

### Requirement: Link map stats sidebar
The link map page SHALL display a stats sidebar with:
- Total links count
- Total pages count
- Average links per page
- Validation pass rate (percentage)
- Link method breakdown (rule-based vs LLM fallback counts)
- Anchor diversity breakdown (exact_match, partial_match, natural percentages)
- For onboarding: priority page stats (count, avg inbound vs non-priority avg inbound)

#### Scenario: Stats reflect actual link data
- **WHEN** a cluster has 28 links across 8 pages, 14 rule-based and 6 LLM fallback
- **THEN** the sidebar SHALL show: Total 28, Pages 8, Avg 3.5, method breakdown matching

### Requirement: Link map page table
Below the visualization, the link map page SHALL display a sortable table with one row per page:
- Page title/URL
- Role (cluster: parent/child) or Labels (onboarding)
- Outbound link count
- Inbound link count
- Method summary (e.g., "1 gen + 2 rule")
- Validation status (✓, ⚠, ✗)

Clicking a row SHALL navigate to the page link detail view.

For onboarding, the table SHALL include filter controls:
- Label filter dropdown
- Priority-only toggle
- Search by page name

#### Scenario: Click page row
- **WHEN** a user clicks on the "Trail Running Shoes" row
- **THEN** the browser SHALL navigate to the page link detail view for that page

#### Scenario: Filter onboarding table by label
- **WHEN** the user selects label "running" from the filter dropdown
- **THEN** only pages with the "running" label SHALL be shown in the table

### Requirement: Page link detail view
The page link detail view SHALL display at `/projects/{id}/links/page/{pageId}`:

**Outbound Links section:**
- List of links FROM this page, ordered by position in content
- Each link shows: target page title, anchor text, anchor type, placement method, paragraph position
- Mandatory parent link (cluster only) marked with "mandatory" badge and no remove button
- Action buttons per link: [Edit Anchor], [Remove] (except mandatory), [Preview]
- [+ Add] button to add a manual link

**Inbound Links section (read-only):**
- List of links TO this page from other pages
- Each shows: source page title, anchor text, anchor type

**Anchor Diversity section:**
- All unique anchors pointing to this page with usage counts
- Diversity score: "High" (>80% unique), "Medium" (50-80%), "Low" (<50%)

#### Scenario: View cluster child page links
- **WHEN** viewing a child page with 4 outbound links
- **THEN** link 1 SHALL show "mandatory" badge and no [Remove] button; links 2-4 SHALL show [Edit Anchor] and [Remove]

#### Scenario: View onboarding page links
- **WHEN** viewing an onboarding page with 4 outbound links
- **THEN** all 4 links SHALL show [Edit Anchor] and [Remove] (no mandatory links in onboarding)

### Requirement: Add link modal
Clicking [+ Add] SHALL open a modal with:
- Target page dropdown (searchable, scoped to same silo/project)
- Anchor text input field
- Suggested anchors list (from POP variations of the selected target, clickable to fill input)
- [Cancel] and [Add Link] buttons

The dropdown SHALL show page title and URL for each option.

For onboarding, the dropdown SHALL sort pages by label overlap with the current page (most related first).

#### Scenario: Add link with suggested anchor
- **WHEN** the user selects a target page and clicks a suggested anchor "trail running shoes"
- **THEN** the anchor text input SHALL be filled with "trail running shoes"

#### Scenario: Add link validation
- **WHEN** the user tries to add a link to a page that's already linked from this source
- **THEN** the modal SHALL show an inline error "Link already exists to this page"

### Requirement: Edit anchor modal
Clicking [Edit Anchor] SHALL open a modal with:
- Target page name (read-only)
- Current anchor text in an editable input
- Suggested variations list (from POP variations, clickable)
- Anchor type radio buttons (partial match, exact match, natural)
- [Cancel] and [Save Anchor] buttons

#### Scenario: Edit anchor text
- **WHEN** the user changes anchor text from "running shoes" to "best running shoes" and clicks Save
- **THEN** the link's anchor text SHALL update in both the InternalLink row and the HTML content

### Requirement: Re-plan links button
The link map page SHALL include a "Re-plan Links" button that:
1. Shows a confirmation dialog: "This will replace all current links. Previous plan will be saved as a snapshot."
2. On confirm: triggers the planning endpoint (re-plan flow)
3. Shows the planning progress indicator

#### Scenario: Re-plan confirmation
- **WHEN** the user clicks "Re-plan Links"
- **THEN** a confirmation dialog SHALL appear before any action is taken

#### Scenario: Re-plan executes
- **WHEN** the user confirms re-planning
- **THEN** the system SHALL snapshot, strip, delete, and re-run planning with progress shown

### Requirement: Project detail integration
The project detail page SHALL show the link planning status for each scope:

For onboarding section: A "Links" status indicator showing "Not planned" | "Planned (N links)" | "Planning..."
For each cluster card: A link status showing the same states

Clicking the status SHALL navigate to the link planning page for that scope.

#### Scenario: Onboarding links not yet planned
- **WHEN** viewing the project detail page and no onboarding links exist
- **THEN** the onboarding section SHALL show "Links: Not planned" with a link to the planning page

#### Scenario: Cluster with planned links
- **WHEN** a cluster has 28 verified links
- **THEN** the cluster card SHALL show "Links: 28 planned" with a link to the cluster link map
