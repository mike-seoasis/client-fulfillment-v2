## ADDED Requirements

### Requirement: InternalLink data model
The system SHALL store internal links in an `internal_links` table with the following columns:
- `id` (UUID, PK)
- `source_page_id` (UUID, FK → crawled_pages, NOT NULL)
- `target_page_id` (UUID, FK → crawled_pages, NOT NULL)
- `project_id` (UUID, FK → projects, NOT NULL)
- `cluster_id` (UUID, FK → keyword_clusters, nullable — null for onboarding scope)
- `scope` (String: "onboarding" | "cluster", NOT NULL)
- `anchor_text` (Text, NOT NULL)
- `anchor_type` (String: "exact_match" | "partial_match" | "natural", NOT NULL)
- `position_in_content` (Integer — paragraph index where link was placed)
- `is_mandatory` (Boolean — true for cluster parent links)
- `placement_method` (String: "rule_based" | "llm_fallback", NOT NULL)
- `status` (String: "planned" | "injected" | "verified" | "removed", NOT NULL)
- `created_at`, `updated_at` (timestamps)

Indexes SHALL be created on: (source_page_id), (target_page_id), (project_id, scope), (cluster_id).

#### Scenario: Create internal link record for cluster child → parent
- **WHEN** the planner creates a mandatory parent link from a child page to the parent page in a cluster
- **THEN** the record SHALL have scope="cluster", cluster_id set, is_mandatory=true, status="planned"

#### Scenario: Create internal link record for onboarding page
- **WHEN** the planner creates a link between two onboarding pages based on label overlap
- **THEN** the record SHALL have scope="onboarding", cluster_id=null, is_mandatory=false, status="planned"

### Requirement: LinkPlanSnapshot data model
The system SHALL store link plan snapshots in a `link_plan_snapshots` table with:
- `id` (UUID, PK)
- `project_id` (UUID, FK → projects, NOT NULL)
- `cluster_id` (UUID, FK → keyword_clusters, nullable)
- `scope` (String: "onboarding" | "cluster", NOT NULL)
- `plan_data` (JSONB — full snapshot including pre-injection content and link plan)
- `total_links` (Integer)
- `created_at` (timestamp)

#### Scenario: Snapshot created on re-plan
- **WHEN** a user triggers "Re-plan Links" for a scope that already has links
- **THEN** the system SHALL create a new snapshot with the current plan_data before deleting existing links

#### Scenario: Snapshot preserves pre-injection content
- **WHEN** a snapshot is created
- **THEN** plan_data SHALL include the `bottom_description` HTML for each page BEFORE link injection, enabling rollback

### Requirement: Link graph construction
The system SHALL build a link graph representing eligible link targets for a given scope.

For **cluster scope**: The graph SHALL model the parent/child hierarchy from `ClusterPage.role`. Parent page connects bidirectionally with all children. Children connect with siblings.

For **onboarding scope**: The graph SHALL compute label overlap between all pairs of crawled pages where `source='onboarding'`. Two pages are eligible to link if they share 2 or more labels (configurable threshold). Edge weight equals the label overlap count.

#### Scenario: Cluster graph with parent and 5 children
- **WHEN** a cluster has 1 parent page and 5 child pages, all with approved content
- **THEN** the graph SHALL have edges from parent to each child and between all sibling pairs

#### Scenario: Onboarding graph with label overlap
- **WHEN** Page A has labels ["running", "women", "trail"] and Page B has labels ["running", "women", "road"]
- **THEN** the graph SHALL have an edge between A and B with weight 2 (shared: "running", "women")

#### Scenario: Onboarding pages below overlap threshold
- **WHEN** Page A has labels ["running", "shoes"] and Page B has labels ["shoes", "boots"]
- **THEN** the graph SHALL have an edge with weight 1, which is below the threshold of 2, so B is NOT an eligible target for A

#### Scenario: Only pages with completed content are included
- **WHEN** a page has `PageContent.status != 'complete'`
- **THEN** that page SHALL be excluded from the link graph entirely

### Requirement: Link budget calculation
The system SHALL calculate a link budget per page using: `budget = clamp(word_count / 250, min=3, max=5)`.

For cluster child pages, 1 budget slot is reserved for the mandatory parent link.

#### Scenario: Page with 1000 words
- **WHEN** a page's bottom_description has 1000 words
- **THEN** the budget SHALL be 4 links (1000 / 250 = 4)

#### Scenario: Page with 200 words (below minimum)
- **WHEN** a page's bottom_description has 200 words
- **THEN** the budget SHALL be 3 links (minimum)

#### Scenario: Page with 2000 words (above maximum)
- **WHEN** a page's bottom_description has 2000 words
- **THEN** the budget SHALL be 5 links (maximum)

#### Scenario: Cluster child budget includes mandatory parent
- **WHEN** a cluster child page has a budget of 4
- **THEN** slot 1 SHALL be the mandatory parent link, leaving 3 slots for siblings

### Requirement: Target selection — cluster mode
For each page in a cluster, the system SHALL select link targets as follows:

**Parent page:** Link to child pages, ranked by `ClusterPage.composite_score` descending. Select up to budget count.

**Child page:** Slot 1 is always the parent page (mandatory). Remaining slots filled with sibling child pages ranked by composite_score, then by least-linked-to (balance distribution).

#### Scenario: Child page selects parent + siblings
- **WHEN** a child page has budget 4 in a cluster with 1 parent and 6 siblings
- **THEN** the plan SHALL assign: link 1 = parent (mandatory), links 2-4 = top 3 siblings by composite_score

#### Scenario: Parent page links to children
- **WHEN** the parent page has budget 5 and the cluster has 7 children
- **THEN** the plan SHALL assign the top 5 children by composite_score as targets

#### Scenario: Small cluster (fewer children than budget)
- **WHEN** a parent page has budget 5 but the cluster only has 3 children
- **THEN** the plan SHALL assign all 3 children as targets (budget partially unfilled is acceptable)

### Requirement: Target selection — onboarding mode
For each onboarding page, the system SHALL select link targets by scoring all eligible pages (2+ shared labels):

`score = label_overlap_count + (2 if target.is_priority else 0) - diversity_penalty`

Where `diversity_penalty` increases by 0.5 for each inbound link the target has already received (across all pages processed so far), preventing any single page from accumulating too many inbound links.

Pages SHALL be processed in arbitrary order. After each page's targets are selected, the inbound counts are updated before processing the next page.

#### Scenario: Priority page wins tiebreaker
- **WHEN** Page A can link to Page B (overlap 3, not priority) or Page C (overlap 3, is priority)
- **THEN** Page C SHALL be selected first (score 5 vs 3)

#### Scenario: Diversity penalty prevents hogging
- **WHEN** Page X already has 6 inbound links and Page Y has 1 inbound link, and both have overlap 3 with the source
- **THEN** Page Y SHALL score higher (3 - 0.5 = 2.5 vs 3 - 3.0 = 0) and be preferred

#### Scenario: No eligible targets (all below threshold)
- **WHEN** a page has no other pages with 2+ shared labels
- **THEN** the page SHALL have 0 links (budget unfilled, no error)

### Requirement: Anchor text selection with diversity tracking
The system SHALL select anchor text for each link using a global usage tracker per target page.

Candidate sources:
1. Target page's primary keyword (from PageKeywords) — tagged as "exact_match"
2. POP keyword variations from the target's content brief — tagged as "partial_match"
3. LLM-generated natural phrases (2-3 per target, Haiku, generated once per planning run) — tagged as "natural"

Selection scoring:
- Diversity bonus: candidates used fewer times globally for this target score higher
- Context fit bonus: candidates that appear as text in the source page's content score higher (enables rule-based injection)
- Distribution target: ~50-60% partial_match, ~10% exact_match, ~30% natural across the project

Constraint: The same anchor text for the same target page SHALL NOT be used more than 3 times across the entire project.

#### Scenario: First link to a target uses exact match
- **WHEN** a target has never been linked to before and its primary keyword appears in the source content
- **THEN** the anchor SHALL be the primary keyword (exact_match) since it has 0 prior uses and context fit

#### Scenario: Third exact match triggers variation
- **WHEN** a target's primary keyword has been used 3 times already as anchor text
- **THEN** the system SHALL select a partial_match or natural variation instead

#### Scenario: Context fit prefers rule-based placeable anchors
- **WHEN** candidate "trail running shoes" appears in the source content but "shoes for trail running" does not
- **THEN** "trail running shoes" SHALL score higher due to context fit bonus

### Requirement: Full planning pipeline orchestration
The system SHALL orchestrate the planning pipeline in 4 sequential steps:
1. Build link graph (scope-appropriate)
2. Select targets and anchor text for all pages
3. Inject links into content (see link-injection spec)
4. Validate all rules (see link-injection spec)

Progress SHALL be tracked with: current step (1-4), pages processed in step 2 and 3.

The pipeline SHALL run as a background task. If any step fails, the pipeline SHALL stop and report the error without partial state changes (existing links remain untouched).

#### Scenario: Successful planning run for cluster
- **WHEN** a cluster with 8 pages (all content complete) triggers link planning
- **THEN** the pipeline SHALL complete all 4 steps and create InternalLink rows with status="verified"

#### Scenario: Planning fails during injection
- **WHEN** an LLM fallback call fails during step 3
- **THEN** the pipeline SHALL stop, no InternalLink rows SHALL be persisted, and the error SHALL be reported

#### Scenario: Re-plan with existing links
- **WHEN** link planning is triggered for a scope that already has links
- **THEN** the system SHALL snapshot the current plan, strip all `<a>` tags from bottom_description, delete existing InternalLink rows, then run the full pipeline fresh
