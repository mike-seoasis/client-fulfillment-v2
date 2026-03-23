## ADDED Requirements

### Requirement: Content mode environment variable
The system SHALL support a `CONTENT_MODE` environment variable with values `real` (default) or `lorem` that controls how body content is generated.

#### Scenario: Default mode is real
- **WHEN** `CONTENT_MODE` is not set
- **THEN** the system SHALL generate content using real, natural copy (existing behavior)

#### Scenario: Lorem mode is set
- **WHEN** `CONTENT_MODE=lorem` is set in the environment
- **THEN** the system SHALL generate content where body paragraph text is lorem ipsum and target keywords appear only in SEO-critical positions

#### Scenario: Startup logging
- **WHEN** the backend starts with `CONTENT_MODE=lorem`
- **THEN** it SHALL log a warning: "Content mode: LOREM IPSUM — body text will be placeholder"

### Requirement: Lorem ipsum content generation for collection pages
When `CONTENT_MODE=lorem`, the content writing service SHALL generate collection page content that places target keywords in SEO-critical elements and uses lorem ipsum for all body paragraph text.

#### Scenario: Keywords in headings
- **WHEN** generating a collection page in lorem mode with primary keyword "crossbody water bottle bag"
- **THEN** all H2 and H3 headings in `bottom_description` SHALL contain the primary keyword or LSI term variants from the POP brief

#### Scenario: Lorem ipsum in body paragraphs
- **WHEN** generating a collection page in lorem mode
- **THEN** all `<p>` tag content in `bottom_description` SHALL be latin lorem ipsum text, except for sentences that contain a required keyword placement

#### Scenario: Title tag contains keyword
- **WHEN** generating a collection page in lorem mode
- **THEN** `page_title` SHALL contain the primary keyword

#### Scenario: Meta description contains keyword
- **WHEN** generating a collection page in lorem mode
- **THEN** `meta_description` SHALL contain the primary keyword and read as natural English (not lorem ipsum)

#### Scenario: Top description contains keyword
- **WHEN** generating a collection page in lorem mode
- **THEN** `top_description` SHALL contain the primary keyword in a natural-sounding sentence, with remaining text as lorem ipsum

#### Scenario: POP brief keyword targets are hit
- **WHEN** generating a collection page in lorem mode with POP brief specifying LSI terms and target counts
- **THEN** the generated content SHALL include each LSI term at least the minimum target count specified in the brief

#### Scenario: POP brief heading structure is followed
- **WHEN** generating a collection page in lorem mode with POP brief specifying heading tag targets (e.g., 3 H2s, 5 H3s)
- **THEN** the generated content SHALL match or exceed the heading tag counts from the brief

#### Scenario: Related questions appear as headings
- **WHEN** generating a collection page in lorem mode with POP brief containing related questions (PAA)
- **THEN** at least 2 related questions SHALL appear as H2 or H3 headings in `bottom_description`

### Requirement: Lorem ipsum content generation for blog posts
When `CONTENT_MODE=lorem`, the blog content generation service SHALL generate blog post content with keywords in SEO-critical elements and lorem ipsum body text.

#### Scenario: Blog headings contain keywords
- **WHEN** generating a blog post in lorem mode with primary keyword "best crossbody water bottle bag for hiking"
- **THEN** all H2 and H3 headings in `content` SHALL contain the primary keyword or relevant LSI terms

#### Scenario: Blog body is lorem ipsum
- **WHEN** generating a blog post in lorem mode
- **THEN** all `<p>` tag content in `content` SHALL be latin lorem ipsum text, except for the lead paragraph and sentences containing required keyword placements

#### Scenario: Blog lead paragraph format
- **WHEN** generating a blog post in lorem mode
- **THEN** the first paragraph SHALL use the styled lead class (`text-xl font-medium ... italic`) and contain the primary keyword in a natural sentence with remaining text as lorem ipsum

#### Scenario: Blog meta description is real
- **WHEN** generating a blog post in lorem mode
- **THEN** `meta_description` SHALL contain the primary keyword and read as natural English

### Requirement: Lorem ipsum outline generation
When `CONTENT_MODE=lorem` and outline-first mode is used, the outline generation SHALL produce heading structures that follow POP brief targets, with section purposes noting lorem ipsum body intent.

#### Scenario: Outline headings use real keywords
- **WHEN** generating an outline in lorem mode
- **THEN** all `headline` values in `page_progression` and `section_details` SHALL contain the primary keyword or LSI terms

#### Scenario: Outline section purposes note lorem mode
- **WHEN** generating an outline in lorem mode
- **THEN** each section's `purpose` field SHALL note that body content will be lorem ipsum with keyword placements

### Requirement: Real content mode is unchanged
When `CONTENT_MODE=real` (default), all content generation SHALL behave identically to the existing system.

#### Scenario: No behavioral change in real mode
- **WHEN** `CONTENT_MODE=real` or unset
- **THEN** `_build_task_section()` SHALL produce the same prompt as before this change
