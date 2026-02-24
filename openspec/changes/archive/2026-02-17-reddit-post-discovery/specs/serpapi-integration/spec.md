## ADDED Requirements

### Requirement: SerpAPI client searches Google for Reddit posts
The system SHALL provide an async SerpAPI client at `backend/app/integrations/serpapi.py` that searches Google with `site:reddit.com` queries and returns structured post results.

#### Scenario: Search with keyword only
- **WHEN** a search is triggered with keyword "cbd for dogs" and no target subreddits
- **THEN** the client sends a GET request to `https://serpapi.com/search` with query `site:reddit.com "cbd for dogs"`, engine `google`, and the configured time range
- **AND** returns only results whose URL contains `/comments/` (actual Reddit posts)

#### Scenario: Search with keyword and target subreddits
- **WHEN** a search is triggered with keyword "cbd for dogs" and target subreddits ["dogs", "pets"]
- **THEN** the client sends separate queries for `site:reddit.com/r/dogs "cbd for dogs"` and `site:reddit.com/r/pets "cbd for dogs"`
- **AND** returns combined results from both searches

#### Scenario: Time range filtering
- **WHEN** a search is triggered with time_range "7d"
- **THEN** the client includes `tbs=qdr:w` in the request parameters
- **AND** maps "24h" to "qdr:d", "7d" to "qdr:w", "30d" to "qdr:m"

#### Scenario: Rate limiting between requests
- **WHEN** multiple search requests are made in sequence
- **THEN** the client SHALL wait at least 1 second between consecutive SerpAPI calls

#### Scenario: Subreddit extraction from URL
- **WHEN** a result URL is `https://www.reddit.com/r/SkincareAddiction/comments/abc123/post_title/`
- **THEN** the client extracts subreddit as "SkincareAddiction"

### Requirement: SerpAPI client follows integration pattern
The SerpAPI client SHALL follow the same patterns as `backend/app/integrations/claude.py` — httpx.AsyncClient, CircuitBreaker, structured logging, retry with exponential backoff.

#### Scenario: Circuit breaker trips on repeated failures
- **WHEN** SerpAPI returns 5 consecutive errors (500, timeout, etc.)
- **THEN** the circuit breaker opens and subsequent calls fail fast without hitting the API

#### Scenario: API key configuration
- **WHEN** the SerpAPI client is initialized
- **THEN** it reads `SERPAPI_KEY` from the application settings (already added in Phase 14a)

#### Scenario: Structured result format
- **WHEN** SerpAPI returns search results
- **THEN** the client returns a list of dataclass objects with fields: url, title, snippet, subreddit, discovered_at
