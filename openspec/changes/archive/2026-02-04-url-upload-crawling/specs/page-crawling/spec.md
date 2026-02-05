## ADDED Requirements

### Requirement: Crawl initiation creates page records
The system SHALL create CrawledPage records for each submitted URL with pending status.

#### Scenario: Page records created on URL submission
- **WHEN** URLs are submitted via POST `/api/v1/projects/{id}/urls`
- **THEN** a CrawledPage record is created for each URL with status "pending"

#### Scenario: Duplicate URLs are skipped
- **WHEN** a URL already exists as a CrawledPage for this project
- **THEN** that URL is skipped and existing record is preserved

### Requirement: Parallel crawling with concurrency limit
The system SHALL crawl pages in parallel with a configurable concurrency limit.

#### Scenario: Multiple pages crawl concurrently
- **WHEN** crawl task starts with 10 URLs and concurrency limit of 5
- **THEN** up to 5 pages are crawled simultaneously

#### Scenario: Concurrency is configurable
- **WHEN** CRAWL_CONCURRENCY environment variable is set to 10
- **THEN** up to 10 pages are crawled simultaneously

#### Scenario: Default concurrency is 5
- **WHEN** CRAWL_CONCURRENCY is not set
- **THEN** system uses default concurrency of 5

### Requirement: Page status tracking
The system SHALL update page status as crawling progresses.

#### Scenario: Status changes to crawling
- **WHEN** a page crawl begins
- **THEN** page status changes from "pending" to "crawling"

#### Scenario: Status changes to completed on success
- **WHEN** a page crawl succeeds
- **THEN** page status changes to "completed" and last_crawled_at is set

#### Scenario: Status changes to failed on error
- **WHEN** a page crawl fails
- **THEN** page status changes to "failed" and crawl_error contains the error message

### Requirement: Content extraction from crawled pages
The system SHALL extract structured data from successfully crawled pages.

#### Scenario: Page title extracted
- **WHEN** page is successfully crawled
- **THEN** title field is populated from the `<title>` tag

#### Scenario: Meta description extracted
- **WHEN** page is successfully crawled
- **THEN** meta_description field is populated from `<meta name="description">`

#### Scenario: Headings extracted
- **WHEN** page is successfully crawled
- **THEN** headings field contains JSONB with h1, h2, h3 arrays

#### Scenario: Body content extracted
- **WHEN** page is successfully crawled
- **THEN** body_content field contains cleaned markdown text from Crawl4AI

#### Scenario: Word count calculated
- **WHEN** page is successfully crawled
- **THEN** word_count field contains count of words in body_content

#### Scenario: Large content truncated
- **WHEN** body_content exceeds 50KB
- **THEN** content is truncated to 50KB and word_count reflects original length

### Requirement: Product count extraction for Shopify collections
The system SHALL attempt to extract product count from Shopify collection pages.

#### Scenario: Product count from collection JSON
- **WHEN** page contains Shopify collection JSON data
- **THEN** product_count is extracted from the collection product array length

#### Scenario: Product count from grid elements
- **WHEN** page contains product grid without JSON but with product card elements
- **THEN** product_count is estimated from counting product card elements

#### Scenario: Product count null for non-collection pages
- **WHEN** page is not a recognizable collection page
- **THEN** product_count is null

### Requirement: Crawl error handling
The system SHALL handle crawl failures gracefully without blocking other pages.

#### Scenario: Failed page does not block others
- **WHEN** one page fails to crawl
- **THEN** other pages continue crawling normally

#### Scenario: Network timeout recorded
- **WHEN** crawl times out
- **THEN** page status is "failed" and crawl_error is "Request timed out"

#### Scenario: HTTP error recorded
- **WHEN** page returns 4xx or 5xx status
- **THEN** page status is "failed" and crawl_error contains the HTTP status code

### Requirement: Crawl triggers taxonomy generation
The system SHALL automatically trigger taxonomy generation when all pages finish crawling.

#### Scenario: Taxonomy generation starts after crawl completion
- **WHEN** all pages have status "completed" or "failed"
- **THEN** system triggers label taxonomy generation for completed pages

#### Scenario: Project status updated to labeling
- **WHEN** taxonomy generation starts
- **THEN** project phase_status.onboarding.status changes to "labeling"
