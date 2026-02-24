## ADDED Requirements

### Requirement: Promotional approach types
The system SHALL define 10 promotional approach types for comments that mention the brand: Sandwich, Story-Based, Skeptic Converted, Comparison, Quick Tip, Problem-Solution, Before/After, Question-Based, List-Based, Technical Deep-Dive. Each approach type SHALL have a description string that guides the comment style.

#### Scenario: Approach type lookup
- **WHEN** the system selects a promotional approach type
- **THEN** the approach description is available for prompt construction
- **AND** the approach name is stored in the comment's approach_type field

### Requirement: Organic approach types
The system SHALL define 11 organic approach types for non-promotional community engagement: Simple Reaction, Appreciation, Follow-Up Question, Agree + Add, Relate Personal Experience, Helpful Tip, Empathy, Validation, Encouragement, Agree + Nuance, Suggest Alternative Approach. Each approach type SHALL have a description string.

#### Scenario: Organic approach type lookup
- **WHEN** the system selects an organic approach type
- **THEN** the approach description is available for prompt construction
- **AND** is_promotional is set to false on the generated comment

### Requirement: Prompt uses BrandConfig voice data
The system SHALL extract voice characteristics, vocabulary (preferred terms, terms to avoid), and brand foundation from BrandConfig.v2_schema to construct the voice section of the prompt. If fields are missing, the system SHALL use sensible defaults (e.g., "friendly and conversational" tone).

#### Scenario: Full BrandConfig available
- **WHEN** a BrandConfig exists with populated v2_schema
- **THEN** the prompt includes voice tone, preferred vocabulary terms, and terms to avoid extracted from v2_schema

#### Scenario: Missing BrandConfig
- **WHEN** no BrandConfig exists for the project
- **THEN** the prompt uses default voice description ("friendly and conversational")
- **AND** generation still proceeds without error

### Requirement: Prompt includes comment instructions
The system SHALL include the RedditProjectConfig.comment_instructions field in the prompt when present, as special instructions guiding the comment voice and approach.

#### Scenario: Comment instructions present
- **WHEN** RedditProjectConfig has non-empty comment_instructions
- **THEN** the prompt includes those instructions in the voice description section

#### Scenario: No comment instructions
- **WHEN** comment_instructions is null or empty
- **THEN** the prompt omits the special instructions section without error

### Requirement: Prompt includes post context
The system SHALL include the post's subreddit, title, and snippet (truncated to 500 chars) in the prompt. The prompt SHALL instruct Claude to write a top-level reply to the original post, ignoring other comments that may appear in the snippet.

#### Scenario: Post with full context
- **WHEN** a post has subreddit, title, and snippet
- **THEN** all three are included in the prompt's post context section

#### Scenario: Post with no snippet
- **WHEN** a post has no snippet
- **THEN** the prompt shows "No content available" for the context/preview section

### Requirement: Promotional vs organic brand section
The prompt SHALL include a brand mention section for promotional comments (brand name, description, key differentiators) and a "do NOT mention any brands" instruction for organic comments.

#### Scenario: Promotional comment prompt
- **WHEN** is_promotional is true
- **THEN** the prompt includes brand name, description, and key features
- **AND** instructs Claude to mention the brand naturally as part of personal experience

#### Scenario: Organic comment prompt
- **WHEN** is_promotional is false
- **THEN** the prompt explicitly states no brands or products should be mentioned

### Requirement: Comment formatting rules
The prompt SHALL instruct Claude to write 50-150 words, use raw text only (no markdown headers or bold), match the subreddit's culture and tone, and respond to the post title (not other comments).

#### Scenario: Formatting constraints in prompt
- **WHEN** a prompt is constructed
- **THEN** it includes length target (50-150 words), no-markdown rule, subreddit culture matching, and top-level reply instruction
