## ADDED Requirements

### Requirement: Discovery pipeline orchestrates search, classification, and scoring
The system SHALL provide a discovery service at `backend/app/services/reddit_discovery.py` that runs the full pipeline: SERP search → deduplicate → filter → classify intent → score with Claude Sonnet → store results.

#### Scenario: Full discovery pipeline execution
- **WHEN** discovery is triggered for a project with configured search keywords and brand config
- **THEN** the service searches SerpAPI for each keyword, deduplicates results by URL, filters banned/marketing subreddits, classifies intent via keyword matching, scores relevance via Claude Sonnet, and stores results in the database

#### Scenario: Deduplication by URL
- **WHEN** the same Reddit post URL is returned by multiple keyword searches
- **THEN** only one entry is kept (first occurrence wins)

#### Scenario: Banned subreddit filtering
- **WHEN** a discovered post is from a subreddit in the project's `banned_subreddits` list
- **THEN** the post is excluded from further processing

#### Scenario: Marketing subreddit filtering
- **WHEN** a discovered post is from a known marketing subreddit (facebookads, ppc, marketing, entrepreneur, smallbusiness, ecommerce, shopify, business, startup, advertising)
- **THEN** the post is excluded from further processing

### Requirement: Intent classification uses keyword matching
The system SHALL classify post intent using keyword lists ported from the Flask app, without making any API calls.

#### Scenario: Research intent detection
- **WHEN** a post title or snippet contains keywords like "recommend", "best", "looking for", "suggestions", "vs", "compare", "alternative"
- **THEN** the post is classified with intent "research"

#### Scenario: Pain point intent detection
- **WHEN** a post title or snippet contains keywords like "struggling", "problem", "not working", "disappointed", "frustrated"
- **THEN** the post is classified with intent "pain_point"

#### Scenario: Competitor mention detection
- **WHEN** a post title or snippet mentions a brand name from the project's competitors list
- **THEN** the post is classified with intent "competitor"

#### Scenario: Question pattern detection
- **WHEN** a post title or snippet contains patterns like "?", "how do i", "what is", "should i", "does anyone"
- **THEN** the post is classified with intent "question"

#### Scenario: Promotional post exclusion
- **WHEN** a post title or snippet contains promotional keywords like "my brand", "i founded", "check out my", "discount code", "affiliate"
- **THEN** the post is auto-rejected and not sent to Claude for scoring

#### Scenario: Multiple intents
- **WHEN** a post matches multiple intent categories
- **THEN** all matching intents are stored in the post's `intent_categories` JSONB array

### Requirement: Claude Sonnet scores post relevance
The system SHALL use Claude Sonnet (never Haiku) to score each post's relevance to the brand on a 0-10 scale.

#### Scenario: Claude scoring with brand context
- **WHEN** a post is sent to Claude for scoring
- **THEN** the prompt includes the brand name, brand description, and competitors from BrandConfig
- **AND** Claude returns a JSON response with score (0-10), reasoning, and intent assessment

#### Scenario: Low-score auto-rejection
- **WHEN** Claude scores a post below 4
- **THEN** the post's filter_status is automatically set to "irrelevant"

#### Scenario: High-score auto-approval
- **WHEN** Claude scores a post 7 or above
- **THEN** the post's filter_status is set to "relevant"

#### Scenario: Mid-range scores remain pending
- **WHEN** Claude scores a post between 4 and 6 (inclusive)
- **THEN** the post's filter_status remains "pending" for human review

### Requirement: Discovery results are stored with upsert semantics
The system SHALL store discovered posts using upsert (insert or update) based on the UniqueConstraint on (project_id, url).

#### Scenario: New post discovered
- **WHEN** a post URL has not been seen before for this project
- **THEN** a new RedditPost row is created with all discovery data

#### Scenario: Existing post rediscovered
- **WHEN** a post URL already exists for this project
- **THEN** the existing row is updated with fresh snippet, score, and intent data
- **AND** the filter_status is NOT overwritten if it was manually set by a user

### Requirement: Discovery tracks progress for polling
The system SHALL maintain in-memory progress data during discovery for frontend polling.

#### Scenario: Progress during search phase
- **WHEN** discovery is searching SerpAPI for keywords
- **THEN** progress reports status "searching", keywords_searched count, and total_keywords count

#### Scenario: Progress during scoring phase
- **WHEN** discovery is scoring posts with Claude
- **THEN** progress reports status "scoring", posts_scored count, and total_posts_found count

#### Scenario: Progress on completion
- **WHEN** discovery finishes successfully
- **THEN** progress reports status "complete" with total_found, unique, and stored counts

#### Scenario: Progress on failure
- **WHEN** discovery encounters an unrecoverable error
- **THEN** progress reports status "failed" with the error message
