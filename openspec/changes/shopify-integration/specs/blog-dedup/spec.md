## ADDED Requirements

### Requirement: Blog deduplication compares generated titles against Shopify articles
The system SHALL compare each generated blog topic title against all existing Shopify blog articles for the same project using normalized Levenshtein similarity.

#### Scenario: Titles are normalized before comparison
- **WHEN** blog deduplication runs
- **THEN** both the generated title and existing article titles are normalized: lowercased, punctuation stripped, whitespace collapsed

#### Scenario: High similarity match is silently filtered
- **WHEN** a generated blog title has >90% Levenshtein similarity ratio to an existing Shopify article title
- **THEN** the generated title is excluded from the results without user notification

#### Scenario: Medium similarity match shows warning
- **WHEN** a generated blog title has 70-90% Levenshtein similarity ratio to an existing Shopify article title
- **THEN** the generated title is included in results but flagged with a warning indicating the similar existing post title

#### Scenario: Low similarity is not flagged
- **WHEN** a generated blog title has <70% Levenshtein similarity ratio to all existing Shopify article titles
- **THEN** the generated title is included in results with no warning

### Requirement: Blog dedup warning includes link to live post
The blog deduplication warning SHALL include a clickable link to the live blog post on the Shopify storefront.

#### Scenario: Warning links to live post
- **WHEN** a generated blog title is flagged with a similarity warning
- **THEN** the warning includes the existing article's title and a link to its `full_url` from the `shopify_pages` table (opens in new tab)

### Requirement: Blog dedup runs during blog topic generation
The blog deduplication check SHALL execute as part of the blog topic generation pipeline, before presenting topics to the user.

#### Scenario: Dedup runs when project has Shopify articles
- **WHEN** blog topics are generated for a project that has Shopify articles in `shopify_pages`
- **THEN** each generated topic is compared against all articles with `page_type = 'article'` and `is_deleted = false`

#### Scenario: Dedup is skipped when project has no Shopify connection
- **WHEN** blog topics are generated for a project with no Shopify connection
- **THEN** deduplication is skipped and all topics are returned without filtering or warnings

### Requirement: Blog dedup similarity calculation
The system SHALL use Levenshtein distance ratio for title similarity, calculated as `1 - (edit_distance / max(len(a), len(b)))`.

#### Scenario: Identical titles produce 1.0 similarity
- **WHEN** two titles are identical after normalization
- **THEN** the similarity ratio is 1.0 and the generated title is silently filtered

#### Scenario: Completely different titles produce low similarity
- **WHEN** two titles share no common substrings after normalization
- **THEN** the similarity ratio is near 0.0 and no warning is shown

#### Scenario: Minor variation produces high similarity
- **WHEN** titles differ by only a word or two (e.g., "Best Running Shoes 2025" vs "Best Running Shoes 2026")
- **THEN** the similarity ratio exceeds 0.90 and the generated title is silently filtered
