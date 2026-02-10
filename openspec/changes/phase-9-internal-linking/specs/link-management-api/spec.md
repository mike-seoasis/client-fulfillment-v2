## ADDED Requirements

### Requirement: Trigger link planning endpoint
The system SHALL provide `POST /api/v1/projects/{project_id}/links/plan` to trigger the link planning pipeline.

Request body:
- `scope` (required): "onboarding" | "cluster"
- `cluster_id` (required if scope="cluster"): UUID of the cluster

The endpoint SHALL return HTTP 202 Accepted with a task status object. The pipeline runs as a background task.

Prerequisites checked before starting:
- All pages in scope have `PageContent.status = 'complete'`
- All pages in scope have `PageKeywords.is_approved = true`
- If scope="cluster": cluster exists and has at least 2 approved pages

If prerequisites are not met, the endpoint SHALL return HTTP 400 with a message listing which prerequisites failed.

#### Scenario: Trigger planning for a cluster
- **WHEN** POST is called with scope="cluster" and cluster_id, and all 8 cluster pages have complete content
- **THEN** the response SHALL be HTTP 202 with `{"status": "planning", "scope": "cluster", "cluster_id": "..."}`

#### Scenario: Trigger planning for onboarding
- **WHEN** POST is called with scope="onboarding" for a project with 24 onboarding pages, all with complete content
- **THEN** the response SHALL be HTTP 202 with `{"status": "planning", "scope": "onboarding"}`

#### Scenario: Prerequisites not met
- **WHEN** POST is called but 3 pages have status="pending" (content not generated)
- **THEN** the response SHALL be HTTP 400 with `{"error": "3 pages do not have complete content", "missing_pages": [...]}`

#### Scenario: Re-plan with existing links
- **WHEN** POST is called for a scope that already has InternalLink rows
- **THEN** the system SHALL snapshot, strip, delete, and re-run (per design D9)

### Requirement: Link planning status endpoint
The system SHALL provide `GET /api/v1/projects/{project_id}/links/plan/status` with query params `scope` and optional `cluster_id`.

Response:
- `status`: "idle" | "planning" | "complete" | "failed"
- `current_step`: 1-4 (null if idle)
- `step_label`: Human-readable step name
- `pages_processed`: Number of pages processed in current step
- `total_pages`: Total pages in scope
- `total_links`: Total links created (available when complete)
- `error`: Error message (if failed)

#### Scenario: Poll during step 2
- **WHEN** the planner is selecting targets for page 5 of 8
- **THEN** the response SHALL include `status="planning"`, `current_step=2`, `step_label="Selecting targets & anchor text"`, `pages_processed=5`, `total_pages=8`

#### Scenario: Poll when complete
- **WHEN** planning has finished successfully
- **THEN** the response SHALL include `status="complete"`, `total_links=28`

#### Scenario: Poll when idle (no planning in progress)
- **WHEN** no planning has been triggered or the last run completed
- **THEN** the response SHALL include `status="idle"` or `status="complete"` with the results of the last run

### Requirement: Get link map for scope
The system SHALL provide `GET /api/v1/projects/{project_id}/links` with query params `scope` and optional `cluster_id`.

Response:
- `scope`: "onboarding" | "cluster"
- `total_links`: Integer
- `total_pages`: Integer
- `avg_links_per_page`: Float
- `validation_pass_rate`: Float (0-1)
- `method_breakdown`: `{"rule_based": N, "llm_fallback": N}`
- `anchor_diversity`: `{"exact_match": N, "partial_match": N, "natural": N}` (percentages)
- `pages`: Array of page summaries, each with:
  - `page_id`, `url`, `title`, `is_priority` (cluster: `role`)
  - `outbound_count`, `inbound_count`
  - `methods`: `{"rule_based": N, "llm_fallback": N}`
  - `validation_status`: "passed" | "warnings" | "failed"
  - `labels` (onboarding only): array of labels

For cluster scope, the response SHALL also include:
- `hierarchy`: Tree structure with parent and children for visualization

#### Scenario: Get cluster link map
- **WHEN** GET is called with scope="cluster" and cluster_id for a cluster with 8 pages and 28 links
- **THEN** the response SHALL include the hierarchy tree, all 8 page summaries, and aggregate stats

#### Scenario: Get onboarding link map
- **WHEN** GET is called with scope="onboarding" for a project with 24 pages and 84 links
- **THEN** the response SHALL include all 24 page summaries with labels, and aggregate stats (no hierarchy)

#### Scenario: No links planned yet
- **WHEN** GET is called for a scope that has no InternalLink rows
- **THEN** the response SHALL return `total_links=0`, `pages=[]` (empty, not an error)

### Requirement: Get links for a specific page
The system SHALL provide `GET /api/v1/projects/{project_id}/links/page/{page_id}` returning:

- `outbound_links`: Array of links FROM this page, ordered by position_in_content:
  - `id`, `target_page_id`, `target_url`, `target_title`, `target_keyword`
  - `anchor_text`, `anchor_type`, `position_in_content`
  - `is_mandatory`, `placement_method`, `status`
- `inbound_links`: Array of links TO this page from other pages:
  - `id`, `source_page_id`, `source_url`, `source_title`
  - `anchor_text`, `anchor_type`
- `anchor_diversity`: Object showing all unique anchors pointing to this page with usage counts
- `diversity_score`: "high" | "medium" | "low" based on unique anchors / total inbound ratio

#### Scenario: Page with 4 outbound and 3 inbound links
- **WHEN** GET is called for a child page in a cluster
- **THEN** outbound_links SHALL include the mandatory parent link first, followed by 3 sibling links ordered by paragraph position

#### Scenario: Page with no links
- **WHEN** GET is called for a page that was excluded from link planning (e.g., no eligible targets)
- **THEN** outbound_links and inbound_links SHALL be empty arrays

### Requirement: Add manual link
The system SHALL provide `POST /api/v1/projects/{project_id}/links` to manually add a link.

Request body:
- `source_page_id` (UUID, required)
- `target_page_id` (UUID, required)
- `anchor_text` (string, required, max 100 chars)
- `anchor_type` (string: "exact_match" | "partial_match" | "natural", required)

The system SHALL:
1. Validate silo integrity (both pages in same scope)
2. Check for duplicate links (same source → same target)
3. Check no self-links
4. Inject the link into bottom_description using rule-based or LLM fallback
5. Create an InternalLink row with status="verified"

#### Scenario: Add valid manual link
- **WHEN** POST is called with valid source, target, and anchor for pages in the same cluster
- **THEN** the link SHALL be injected into the source page's content and a new InternalLink row SHALL be created

#### Scenario: Add link violating silo integrity
- **WHEN** POST is called with source in cluster A and target in cluster B
- **THEN** the response SHALL be HTTP 400 with `{"error": "Target page is not in the same silo"}`

#### Scenario: Add duplicate link
- **WHEN** POST is called for a source → target pair that already has a link
- **THEN** the response SHALL be HTTP 400 with `{"error": "Link already exists from this source to this target"}`

### Requirement: Remove link
The system SHALL provide `DELETE /api/v1/projects/{project_id}/links/{link_id}` to remove a link.

The system SHALL:
1. Reject removal of mandatory parent links (return HTTP 400)
2. Strip the link's `<a>` tag from bottom_description (unwrap to text)
3. Update the InternalLink row status to "removed"

#### Scenario: Remove discretionary link
- **WHEN** DELETE is called for a non-mandatory link
- **THEN** the `<a>` tag SHALL be unwrapped in the content and the InternalLink status SHALL be set to "removed"

#### Scenario: Attempt to remove mandatory parent link
- **WHEN** DELETE is called for a link where is_mandatory=true
- **THEN** the response SHALL be HTTP 400 with `{"error": "Cannot remove mandatory parent link"}`

### Requirement: Edit link anchor text
The system SHALL provide `PUT /api/v1/projects/{project_id}/links/{link_id}` to update a link's anchor text.

Request body:
- `anchor_text` (string, required, max 100 chars)
- `anchor_type` (string: "exact_match" | "partial_match" | "natural", required)

The system SHALL:
1. Find the existing `<a>` tag in bottom_description by matching the current anchor text
2. Replace the anchor text with the new value
3. Update the InternalLink row

#### Scenario: Edit anchor text
- **WHEN** PUT is called changing anchor from "running shoes" to "best running shoes"
- **THEN** the `<a>` tag's inner text SHALL change to "best running shoes" and the InternalLink row SHALL be updated

### Requirement: Get anchor text suggestions for a target page
The system SHALL provide `GET /api/v1/projects/{project_id}/links/suggestions/{target_page_id}` returning anchor text suggestions.

Response:
- `primary_keyword`: The target page's primary keyword
- `pop_variations`: Array of POP keyword variations from the target's content brief
- `usage_counts`: Object mapping each anchor text to how many times it's been used for this target

#### Scenario: Get suggestions for a page with POP brief
- **WHEN** GET is called for a page that has a content brief with keyword_variations
- **THEN** the response SHALL include the primary keyword and all POP variations with their current usage counts
