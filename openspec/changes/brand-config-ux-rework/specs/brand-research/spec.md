# brand-research Specification

## Purpose

Perplexity-powered automatic brand research from website URL, extracting company information, target audience, brand voice characteristics, differentiators, and proof points to auto-populate the brand configuration wizard.

## ADDED Requirements

### Requirement: Research brand from domain URL

The system SHALL use Perplexity API to research a brand when given a domain URL, extracting structured brand information.

#### Scenario: Successful brand research

- **WHEN** user provides a valid domain URL (e.g., "acme.com")
- **THEN** system MUST call Perplexity API with research prompt
- **AND** system MUST extract: company name, industry, positioning, target audience, brand voice indicators, differentiators, and proof points
- **AND** system MUST return structured research results within 30 seconds

#### Scenario: Invalid domain URL

- **WHEN** user provides an invalid or unreachable domain
- **THEN** system MUST return an error message explaining the domain could not be researched
- **AND** system MUST allow user to proceed with manual entry

#### Scenario: Perplexity API unavailable

- **WHEN** Perplexity API key is not configured or service is unavailable
- **THEN** system MUST log the error
- **AND** system MUST return graceful fallback allowing manual brand entry
- **AND** system MUST NOT block the wizard flow

### Requirement: Synthesize research into V3 schema

The system SHALL use Claude to synthesize Perplexity research results into the V3 brand configuration schema structure.

#### Scenario: Successful synthesis

- **WHEN** Perplexity returns brand research results
- **THEN** system MUST call Claude with synthesis prompt
- **AND** Claude MUST generate a valid V3 schema with all 11 sections populated where data is available
- **AND** sections without sufficient data MUST have sensible defaults or null values

#### Scenario: Partial research results

- **WHEN** Perplexity returns incomplete brand information
- **THEN** system MUST synthesize available data into corresponding V3 sections
- **AND** system MUST mark incomplete sections for user review in wizard

### Requirement: Cache research results

The system SHALL cache brand research results to avoid redundant API calls.

#### Scenario: Research cache hit

- **WHEN** user requests research for a domain that was researched within the last 24 hours
- **THEN** system MUST return cached results
- **AND** system MUST indicate results are from cache with timestamp

#### Scenario: Force refresh research

- **WHEN** user explicitly requests fresh research (refresh button)
- **THEN** system MUST bypass cache and call Perplexity API
- **AND** system MUST update cache with new results

### Requirement: Rate limit research requests

The system SHALL rate limit Perplexity API calls to control costs.

#### Scenario: Rate limit exceeded

- **WHEN** user attempts more than 5 research requests per hour per project
- **THEN** system MUST return rate limit error with retry time
- **AND** system MUST allow user to proceed with manual entry

### Requirement: Perplexity client configuration

The system SHALL require PERPLEXITY_API_KEY environment variable for brand research functionality.

#### Scenario: API key configured

- **WHEN** PERPLEXITY_API_KEY environment variable is set
- **THEN** brand research endpoints MUST be available
- **AND** system MUST use the configured API key for all Perplexity calls

#### Scenario: API key not configured

- **WHEN** PERPLEXITY_API_KEY environment variable is not set
- **THEN** brand research endpoints MUST return 503 Service Unavailable
- **AND** wizard MUST skip auto-research step and proceed to manual entry
