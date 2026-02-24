## ADDED Requirements

### Requirement: E-commerce focused research
The Perplexity research prompt SHALL focus on e-commerce and DTC business models, emphasizing website copy, email marketing, social media, and online sales channels.

#### Scenario: Research for e-commerce brand
- **WHEN** system generates research for a brand
- **THEN** research focuses on online presence, digital marketing, website copy, and e-commerce metrics (not catalog, direct mail, or offline channels)

### Requirement: Rich target audience generation
The target_audience prompt SHALL generate detailed personas with demographics, psychographics, behavioral data, and communication preferences.

#### Scenario: Generate personas
- **WHEN** system generates target audience section
- **THEN** output includes at least 2 detailed personas with age, location, income, values, pain points, and buying behavior

### Requirement: Correct voice characteristics format
The voice_characteristics prompt SHALL return `we_are_not` as an array of strings (not objects).

#### Scenario: Generate voice characteristics
- **WHEN** system generates voice characteristics section
- **THEN** `we_are_not` field contains array of simple strings like ["corporate", "stuffy", "salesy"]

### Requirement: Em dash prohibition
The writing_style prompt SHALL always include "never use em dashes" as a punctuation rule.

#### Scenario: Generate writing style
- **WHEN** system generates writing style section
- **THEN** punctuation rules include explicit prohibition of em dashes

### Requirement: Extended vocabulary generation
The vocabulary prompt SHALL generate at least 20 power words and 15 banned words.

#### Scenario: Generate vocabulary
- **WHEN** system generates vocabulary section
- **THEN** output includes 20+ power words and 15+ banned words

### Requirement: Trust elements with store rating
The trust_elements prompt SHALL include average store rating when available.

#### Scenario: Generate trust elements
- **WHEN** system generates trust elements section
- **THEN** hard numbers include average_store_rating field if rating data is available

### Requirement: Extended competitor analysis
The competitor_context prompt SHALL generate at least 5 competitors.

#### Scenario: Generate competitor context
- **WHEN** system generates competitor context section
- **THEN** output includes at least 5 direct competitors with positioning and differentiation

### Requirement: Complete examples bank generation
The examples_bank prompt SHALL generate content for all example categories.

#### Scenario: Generate examples bank
- **WHEN** system generates examples bank section
- **THEN** output includes at least 10 headlines, 3 product descriptions, 10 email subjects, social media examples, and 10 CTAs

### Requirement: Complete AI prompt snippet
The ai_prompt_snippet prompt SHALL generate a complete, usable prompt snippet.

#### Scenario: Generate AI prompt
- **WHEN** system generates AI prompt section
- **THEN** output includes a 100-200 word prompt snippet, voice descriptors, audience summary, and key differentiators

### Requirement: Section regeneration
The system SHALL support regenerating individual sections or all sections on demand.

#### Scenario: Regenerate single section
- **WHEN** user requests regeneration of a specific section
- **THEN** system re-runs research and synthesis for that section only, preserving other sections

#### Scenario: Regenerate all sections
- **WHEN** user requests regeneration of all sections
- **THEN** system re-runs full research and synthesis pipeline
