## ADDED Requirements

### Requirement: Stage 1 generates keyword candidates via LLM
The system SHALL use Claude Haiku with an 11-strategy expansion prompt to generate 15-20 collection page keyword candidates from a seed keyword.

#### Scenario: Successful candidate generation
- **WHEN** `ClusterKeywordService.generate_cluster()` is called with seed keyword "trail running shoes" and a brand config
- **THEN** Stage 1 returns 15-20 candidate keywords as structured JSON, each with `keyword`, `expansion_strategy`, `rationale`, and `estimated_intent`

#### Scenario: Brand config context is injected into prompt
- **WHEN** Stage 1 builds the LLM prompt
- **THEN** brand foundation (company name, products, price point), target audience (primary persona), and competitor context are included in the prompt

#### Scenario: 11 expansion strategies are used
- **WHEN** Stage 1 generates candidates
- **THEN** the prompt instructs Claude to expand across: demographic, attribute, price/value, use-case, comparison/intent, seasonal/occasion, material/type, experience level, problem/solution, terrain/environment, and values/lifestyle strategies

#### Scenario: Seed keyword is included as parent candidate
- **WHEN** Stage 1 generates candidates
- **THEN** the seed keyword itself is always included as a candidate with role hint "parent"

#### Scenario: LLM call fails gracefully
- **WHEN** Claude API returns an error during Stage 1
- **THEN** the service returns a failure result with error message, and no cluster is created

### Requirement: Stage 2 enriches candidates with DataForSEO volume data
The system SHALL call DataForSEO batch volume API to add search volume, CPC, and competition data to all candidates.

#### Scenario: Successful volume enrichment
- **WHEN** Stage 2 receives 15-20 candidate keywords
- **THEN** a single batch call to `DataForSEOClient.get_keyword_volume_batch()` enriches each candidate with `search_volume`, `cpc`, `competition`, `competition_level`

#### Scenario: Candidates below volume threshold are flagged
- **WHEN** a candidate has `search_volume < 50`
- **THEN** it is flagged for filtering in Stage 3 (not removed yet — Stage 3 makes the final decision)

#### Scenario: DataForSEO unavailable
- **WHEN** DataForSEO API is unavailable or returns an error
- **THEN** candidates proceed to Stage 3 without volume data, and the final response includes a warning that volume data is unavailable

### Requirement: Stage 3 filters candidates and assigns roles via LLM
The system SHALL use Claude Haiku to filter candidates to the best 8-12, assign parent/child roles, and generate URL slugs.

#### Scenario: Successful filtering and role assignment
- **WHEN** Stage 3 receives enriched candidates with volume data
- **THEN** Claude filters to 8-12 keywords, assigns exactly one as `role="parent"` (the seed keyword) and the rest as `role="child"`, and generates a `/collections/` URL slug for each

#### Scenario: Near-duplicate keywords are filtered
- **WHEN** candidates include "women's trail running shoes" and "trail running shoes for women"
- **THEN** Stage 3 keeps only one (the higher-volume variant) and filters the other as a cannibalization risk

#### Scenario: Low-volume candidates are filtered
- **WHEN** candidates have `search_volume < 50` (or null)
- **THEN** Stage 3 filters them out unless fewer than 5 candidates would remain (in which case the threshold is relaxed)

#### Scenario: URL slug generation
- **WHEN** a candidate keyword is "waterproof trail running shoes"
- **THEN** the generated URL slug is `/collections/waterproof-trail-running-shoes` (lowercase, hyphens, no special chars, max 60 chars)

#### Scenario: Composite score is calculated
- **WHEN** Stage 3 produces filtered candidates
- **THEN** each candidate gets a `composite_score` using the existing `calculate_score()` formula (50% volume, 35% relevance, 15% competition)

### Requirement: generate_cluster orchestrates Stages 1-3
The system SHALL have a `generate_cluster()` method that runs Stages 1-3 sequentially and returns the complete cluster result.

#### Scenario: Successful cluster generation
- **WHEN** `generate_cluster(seed_keyword, brand_config)` is called
- **THEN** it runs Stage 1 → Stage 2 → Stage 3 in sequence and returns a result with `cluster_id`, `suggestions` (list of scored/filtered candidates), `generation_metadata` (timings, costs, counts)

#### Scenario: Generation completes within timeout
- **WHEN** all three stages complete normally
- **THEN** total wall time is under 15 seconds

#### Scenario: Partial failure returns best-effort result
- **WHEN** Stage 2 (DataForSEO) fails but Stage 1 and Stage 3 succeed
- **THEN** suggestions are returned without volume data, with a warning in the response

### Requirement: Bulk-approve bridges cluster pages to content pipeline
The system SHALL create `CrawledPage` and `PageKeywords` records for each approved cluster page when the user bulk-approves.

#### Scenario: CrawledPage records are created for approved pages
- **WHEN** a cluster is bulk-approved with 8 approved pages
- **THEN** 8 new `CrawledPage` records are created with `source='cluster'`, `status='completed'`, `category='collection'`, `normalized_url` from the cluster page's URL slug, and `project_id` from the cluster's project

#### Scenario: PageKeywords records are created for approved pages
- **WHEN** a cluster is bulk-approved
- **THEN** each new CrawledPage gets a `PageKeywords` record with `primary_keyword` from the cluster page keyword, `is_approved=True`, `is_priority` set to `True` for the parent page, `search_volume` and `composite_score` from the cluster page data

#### Scenario: ClusterPage.crawled_page_id is set
- **WHEN** CrawledPage records are created during bulk-approve
- **THEN** each `ClusterPage.crawled_page_id` is updated to reference the new CrawledPage

#### Scenario: Cluster status updates to approved
- **WHEN** bulk-approve completes successfully
- **THEN** the cluster's status changes to `approved`
