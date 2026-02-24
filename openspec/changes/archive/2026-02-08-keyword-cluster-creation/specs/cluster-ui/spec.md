## ADDED Requirements

### Requirement: Seed keyword input page
The system SHALL provide a page at `/projects/{id}/clusters/new` where users enter a seed keyword to create a new cluster.

#### Scenario: Page displays seed keyword form
- **WHEN** user navigates to `/projects/{id}/clusters/new`
- **THEN** the page displays a form with "Seed Keyword" (required) and "Cluster Name" (optional) fields, a "Cancel" button, and a "Get Suggestions" button

#### Scenario: Submitting seed keyword triggers generation
- **WHEN** user enters "trail running shoes" and clicks "Get Suggestions"
- **THEN** the system calls the create cluster API and shows a loading state with progress steps (Generating suggestions → Checking search volume → Finalizing results)

#### Scenario: Loading state shows estimated time
- **WHEN** the cluster generation is in progress
- **THEN** the UI shows a spinner with progress steps that update as stages complete, indicating ~5-10 seconds expected

#### Scenario: Successful generation navigates to suggestions page
- **WHEN** cluster generation completes successfully
- **THEN** the user is navigated to the cluster detail/suggestions page

#### Scenario: Generation failure shows error
- **WHEN** cluster generation fails (API error or timeout)
- **THEN** the UI displays an error message with a "Try Again" button

#### Scenario: Cancel returns to project
- **WHEN** user clicks "Cancel"
- **THEN** user is navigated back to the project detail page

### Requirement: Cluster suggestions and approval page
The system SHALL provide a page at `/projects/{id}/clusters/{clusterId}` showing cluster suggestions with approval controls.

#### Scenario: Page displays cluster header
- **WHEN** user views the cluster suggestions page
- **THEN** the page shows the cluster name, seed keyword, and a stepper indicating the current phase (Keywords → Content → Review → Export)

#### Scenario: Suggestions are displayed as a list
- **WHEN** the cluster has 10 page suggestions
- **THEN** all 10 are displayed in a list, each showing: keyword, role badge (Parent/Child), search volume, CPC, competition level, composite score, URL slug, expansion strategy tag, and an approve/reject toggle

#### Scenario: Parent page is visually distinguished
- **WHEN** a suggestion has `role="parent"`
- **THEN** it is displayed at the top of the list with a distinct "Parent" badge in palm green

#### Scenario: Approve individual suggestion
- **WHEN** user toggles approval on a suggestion
- **THEN** the system calls PATCH endpoint and the suggestion's approval state updates immediately

#### Scenario: Edit URL slug inline
- **WHEN** user clicks on a suggestion's URL slug
- **THEN** the slug becomes editable, and changes are saved on blur or Enter via PATCH endpoint

#### Scenario: Edit keyword inline
- **WHEN** user clicks on a suggestion's keyword
- **THEN** the keyword becomes editable, and changes are saved on blur or Enter via PATCH endpoint

#### Scenario: Reassign parent role
- **WHEN** user clicks a "Make Parent" action on a child suggestion
- **THEN** the system calls PATCH to reassign the parent role and the UI updates to show the new parent at the top

#### Scenario: Approve All button
- **WHEN** user clicks "Approve All"
- **THEN** all suggestions are approved via individual PATCH calls

#### Scenario: Generate Content button triggers bulk-approve
- **WHEN** user clicks "Generate Content" with at least one approved suggestion
- **THEN** the system calls the bulk-approve endpoint, bridges pages to the content pipeline, and navigates to the content generation progress page

#### Scenario: Generate Content disabled with no approvals
- **WHEN** no suggestions are approved
- **THEN** the "Generate Content" button is disabled with tooltip "Approve at least one page"

#### Scenario: Volume data unavailable warning
- **WHEN** suggestions were generated without DataForSEO data
- **THEN** a warning banner is shown: "Search volume data unavailable. Suggestions are based on AI analysis only."

#### Scenario: Back button returns to project
- **WHEN** user clicks "Back"
- **THEN** user is navigated to the project detail page

### Requirement: Cluster list view on project detail
The system SHALL display a list of clusters in the "New Content" section of the project detail page.

#### Scenario: Cluster cards are displayed
- **WHEN** a project has 3 clusters
- **THEN** the New Content section shows 3 cluster cards, each displaying: cluster name, page count, approval status, and a status indicator

#### Scenario: Cluster card shows status
- **WHEN** a cluster has status "suggestions_ready"
- **THEN** the card shows "Awaiting Approval" with the number of suggestions

#### Scenario: Cluster card shows progress for active clusters
- **WHEN** a cluster has status "content_generating"
- **THEN** the card shows a progress indicator (e.g., "3 of 8 pages generated")

#### Scenario: Clicking a cluster card navigates to cluster detail
- **WHEN** user clicks on a cluster card
- **THEN** user is navigated to `/projects/{id}/clusters/{clusterId}`

#### Scenario: New Cluster button navigates to creation page
- **WHEN** user clicks "+ New Cluster" button
- **THEN** user is navigated to `/projects/{id}/clusters/new`

#### Scenario: Empty state shows prompt
- **WHEN** a project has no clusters
- **THEN** the New Content section shows "No clusters yet" with a prominent "+ New Cluster" button

### Requirement: Frontend API client and hooks for clusters
The system SHALL provide TanStack Query hooks and API client functions for cluster operations.

#### Scenario: useCreateCluster hook
- **WHEN** the create cluster mutation is triggered
- **THEN** it calls POST `/api/v1/projects/{projectId}/clusters` and invalidates the clusters list query on success

#### Scenario: useClusters hook
- **WHEN** the clusters list query is active
- **THEN** it fetches GET `/api/v1/projects/{projectId}/clusters` and provides loading/error/data states

#### Scenario: useCluster hook
- **WHEN** the cluster detail query is active for a specific cluster
- **THEN** it fetches GET `/api/v1/projects/{projectId}/clusters/{clusterId}` with all pages

#### Scenario: useUpdateClusterPage hook
- **WHEN** the update page mutation is triggered
- **THEN** it calls PATCH on the cluster page endpoint and optimistically updates the cluster detail query cache

#### Scenario: useBulkApproveCluster hook
- **WHEN** the bulk-approve mutation is triggered
- **THEN** it calls POST on the bulk-approve endpoint and invalidates both the cluster detail and clusters list queries on success
