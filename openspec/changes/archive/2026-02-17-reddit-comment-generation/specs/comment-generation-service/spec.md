## ADDED Requirements

### Requirement: Single comment generation
The system SHALL generate a single Reddit comment for a given post by loading the project's BrandConfig and RedditProjectConfig, selecting a random approach type, building a prompt via the prompt builder, calling Claude Sonnet with temperature 0.7, and storing the result as a DRAFT RedditComment row with generation_metadata.

#### Scenario: Successful single generation
- **WHEN** generate_comment is called with a valid post and project_id
- **THEN** a new RedditComment row is created with status "draft"
- **AND** body and original_body contain the Claude-generated text
- **AND** generation_metadata includes model name and approach type
- **AND** is_promotional defaults to true
- **AND** approach_type is set to the randomly selected approach name

#### Scenario: Quote wrapping cleanup
- **WHEN** Claude's response starts and ends with double quotes
- **THEN** the service strips the wrapping quotes before storing

#### Scenario: Missing BrandConfig
- **WHEN** no BrandConfig exists for the project
- **THEN** the prompt builder uses default voice characteristics
- **AND** generation still completes without error

### Requirement: Approach selection
The system SHALL randomly select an approach from PROMOTIONAL_APPROACHES (10 types) when is_promotional is true, or from ORGANIC_APPROACHES (11 types) when is_promotional is false. The default is is_promotional=true.

#### Scenario: Promotional approach selection
- **WHEN** is_promotional is true (the default)
- **THEN** a random approach is selected from the 10 promotional approaches

#### Scenario: Organic approach selection
- **WHEN** is_promotional is false
- **THEN** a random approach is selected from the 11 organic approaches

### Requirement: Batch comment generation
The system SHALL generate comments for multiple posts as a background task. It processes posts sequentially (one Claude call per post), tracks progress in an in-memory dict, and commits all results on completion.

#### Scenario: Batch generation for relevant posts
- **WHEN** generate_batch is called with a list of post_ids
- **THEN** each post with filter_status "relevant" gets a generated comment
- **AND** posts that are not relevant are skipped
- **AND** progress is tracked with posts_generated and total_posts counts

#### Scenario: Post already has a draft
- **WHEN** a post in the batch already has a DRAFT comment
- **THEN** a new comment row is created (does not overwrite the existing one)

#### Scenario: Individual post failure in batch
- **WHEN** Claude generation fails for one post in a batch
- **THEN** that post is skipped with an error logged
- **AND** generation continues for remaining posts
- **AND** the batch does not fail entirely

### Requirement: Generation progress tracking
The system SHALL track batch generation progress in an in-memory dict keyed by project_id, following the same pattern as discovery progress. Progress includes status (generating/complete/failed), total_posts, posts_generated, and error fields.

#### Scenario: Progress during generation
- **WHEN** batch generation is in progress
- **THEN** the progress dict shows status "generating" with current counts

#### Scenario: Generation complete
- **WHEN** all posts in a batch have been processed
- **THEN** the progress dict shows status "complete" with final counts

#### Scenario: Generation failed
- **WHEN** the batch generation encounters an unrecoverable error
- **THEN** the progress dict shows status "failed" with error message

### Requirement: Claude client usage
The system SHALL use ClaudeClient (project default Sonnet model) with temperature 0.7 and max_tokens 500 for comment generation. The system SHALL NOT use Haiku.

#### Scenario: Claude call parameters
- **WHEN** the service calls Claude for comment generation
- **THEN** temperature is set to 0.7
- **AND** max_tokens is set to 500
- **AND** the model used is Claude Sonnet (via ClaudeClient default)

### Requirement: Generation metadata storage
The system SHALL store generation metadata as JSONB on the RedditComment row including: model name, approach type, is_promotional flag, and timestamp.

#### Scenario: Metadata contents
- **WHEN** a comment is generated
- **THEN** generation_metadata contains "model", "approach", "is_promotional", and "generated_at" fields
