## ADDED Requirements

### Requirement: KeywordCluster model stores cluster metadata
The system SHALL have a `keyword_clusters` table that tracks cluster identity, seed keyword, status, and relationship to a project.

#### Scenario: Create a new cluster record
- **WHEN** a cluster is created for a project with seed keyword "trail running shoes"
- **THEN** a `KeywordCluster` record is created with `project_id`, `seed_keyword="trail running shoes"`, `name="trail running shoes"`, `status="generating"`

#### Scenario: Cluster name defaults to seed keyword
- **WHEN** a cluster is created without an explicit name
- **THEN** the `name` field defaults to the `seed_keyword` value

#### Scenario: Cluster status transitions
- **WHEN** a cluster progresses through the workflow
- **THEN** status transitions follow: `generating` → `suggestions_ready` → `approved` → `content_generating` → `complete`

#### Scenario: Cluster stores generation metadata
- **WHEN** Stages 1-3 of the pipeline complete
- **THEN** `generation_metadata` JSONB field stores stage timings, API costs, and candidate counts

#### Scenario: Cluster belongs to a project
- **WHEN** a cluster is queried
- **THEN** it is associated with exactly one project via `project_id` foreign key

#### Scenario: Deleting a cluster cascades to pages
- **WHEN** a `KeywordCluster` is deleted
- **THEN** all associated `ClusterPage` records are deleted via cascade

### Requirement: ClusterPage model stores individual page suggestions
The system SHALL have a `cluster_pages` table that tracks each suggested page within a cluster, including keyword, role, volume data, and approval status.

#### Scenario: Create cluster page with suggestion data
- **WHEN** Stage 3 produces a filtered suggestion
- **THEN** a `ClusterPage` record is created with `keyword`, `role` (parent/child), `url_slug`, `expansion_strategy`, `reasoning`, `composite_score`

#### Scenario: Cluster page stores DataForSEO volume data
- **WHEN** Stage 2 enriches a suggestion with volume data
- **THEN** `search_volume`, `cpc`, `competition`, and `competition_level` fields are populated

#### Scenario: Cluster page tracks approval status
- **WHEN** a user approves a cluster page suggestion
- **THEN** `is_approved` is set to `true`

#### Scenario: Cluster page links to CrawledPage after approval
- **WHEN** a cluster page is bulk-approved and bridged to the content pipeline
- **THEN** `crawled_page_id` is set to the newly created `CrawledPage` record's ID

#### Scenario: Exactly one parent page per cluster
- **WHEN** a cluster's pages are queried
- **THEN** exactly one page has `role="parent"` and all others have `role="child"`

#### Scenario: URL slug is generated from keyword
- **WHEN** a cluster page is created with keyword "waterproof trail running shoes"
- **THEN** `url_slug` is set to `/collections/waterproof-trail-running-shoes`

### Requirement: CrawledPage model has source field
The system SHALL add a `source` column to `crawled_pages` to distinguish between onboarding and cluster pages.

#### Scenario: Existing pages default to onboarding source
- **WHEN** the migration runs on existing data
- **THEN** all existing `crawled_pages` records have `source='onboarding'`

#### Scenario: Cluster pages are created with cluster source
- **WHEN** a cluster page is bridged to a CrawledPage on bulk-approve
- **THEN** the new CrawledPage has `source='cluster'`

### Requirement: Pydantic schemas for cluster API
The system SHALL have Pydantic v2 schemas for cluster creation requests, cluster responses, and cluster page responses.

#### Scenario: Cluster creation request schema
- **WHEN** a POST request creates a cluster
- **THEN** the request body is validated against a schema requiring `seed_keyword` (string, min 2 chars) and optional `name` (string)

#### Scenario: Cluster response schema
- **WHEN** a cluster is returned in an API response
- **THEN** it includes `id`, `project_id`, `seed_keyword`, `name`, `status`, `pages` (list of ClusterPage), `created_at`, `updated_at`

#### Scenario: Cluster page response schema
- **WHEN** a cluster page is returned in an API response
- **THEN** it includes `id`, `keyword`, `role`, `url_slug`, `expansion_strategy`, `reasoning`, `search_volume`, `cpc`, `competition`, `competition_level`, `composite_score`, `is_approved`, `crawled_page_id`
