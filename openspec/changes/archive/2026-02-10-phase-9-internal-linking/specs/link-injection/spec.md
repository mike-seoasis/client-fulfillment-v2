## ADDED Requirements

### Requirement: Rule-based link injection via keyword scanning
The system SHALL inject links into `PageContent.bottom_description` HTML by scanning paragraph text for the selected anchor text (or close variation).

Process for each planned link:
1. Parse bottom_description with BeautifulSoup
2. Iterate paragraphs (`<p>` tags) in order
3. Search for the anchor text as a case-insensitive substring in the paragraph's text content
4. If found and density limits allow: wrap the first occurrence in `<a href="target_url">anchor text</a>`
5. Mark the InternalLink as placement_method="rule_based"

The system SHALL NOT inject links inside existing `<a>` tags, headings (`<h2>`, `<h3>`), or list items (`<li>`).

#### Scenario: Anchor text found in paragraph
- **WHEN** the anchor "trail running shoes" appears in paragraph 3's text and no density limits are exceeded
- **THEN** the first occurrence SHALL be wrapped in an `<a>` tag pointing to the target URL

#### Scenario: Anchor text not found anywhere
- **WHEN** the anchor text does not appear in any paragraph of bottom_description
- **THEN** the link SHALL be escalated to LLM fallback injection

#### Scenario: Anchor text inside existing link
- **WHEN** the anchor text appears only inside an existing `<a>` tag
- **THEN** the system SHALL treat it as "not found" and escalate to LLM fallback

#### Scenario: Case-insensitive matching
- **WHEN** the anchor is "Running Shoes" and the content contains "running shoes"
- **THEN** the match SHALL succeed and the original casing in the content SHALL be preserved in the anchor tag

### Requirement: LLM fallback injection for unplaceable links
When rule-based injection cannot place a link (no keyword match found), the system SHALL use Claude Haiku to rewrite a single paragraph to include the link naturally.

Paragraph selection: Choose the paragraph with the fewest existing links AND the most topical relevance to the target page (measured by keyword overlap between paragraph text and target's primary keyword).

The LLM SHALL receive:
- The paragraph HTML
- The target URL
- The anchor text
- Instruction to keep meaning identical and only modify 1-2 sentences

The system SHALL mark these links as placement_method="llm_fallback".

#### Scenario: LLM rewrites paragraph to include link
- **WHEN** rule-based injection fails for anchor "lightweight trail shoes" targeting /collections/lightweight-trail
- **THEN** the system SHALL select the best paragraph, send it to Haiku for rewriting, and replace the paragraph in bottom_description

#### Scenario: LLM fallback preserves meaning
- **WHEN** a paragraph is rewritten by the LLM
- **THEN** the rewritten paragraph SHALL contain exactly one `<a>` tag for the target link and the semantic meaning SHALL remain unchanged

#### Scenario: LLM fails to produce valid output
- **WHEN** the LLM response does not contain a valid `<a>` tag or is malformed
- **THEN** the link SHALL be marked as status="planned" (not injected) and a warning SHALL be recorded

### Requirement: Mandatory parent link positioning for clusters
For cluster child pages, the mandatory parent link SHALL be placed in the first 2 paragraphs of bottom_description.

If rule-based injection finds the anchor text in paragraph 1 or 2, it SHALL be placed there. If the anchor text is not in paragraphs 1-2, LLM fallback SHALL target paragraph 1 or 2 specifically (not the "best" paragraph).

#### Scenario: Parent keyword in first paragraph
- **WHEN** a child page's first paragraph contains the parent's primary keyword "running shoes"
- **THEN** the mandatory parent link SHALL be placed in paragraph 1 via rule-based injection

#### Scenario: Parent keyword not in first 2 paragraphs
- **WHEN** a child page's first 2 paragraphs do not contain the parent's keyword or any variation
- **THEN** LLM fallback SHALL rewrite paragraph 1 to include the parent link

### Requirement: Density limits enforcement
The system SHALL enforce the following density limits during injection:
- Maximum 2 internal links per paragraph
- Minimum 50 words between consecutive links within the same paragraph

If a paragraph already has 2 links, no additional links SHALL be placed in that paragraph. The system SHALL try the next eligible paragraph instead.

#### Scenario: Paragraph already has 2 links
- **WHEN** paragraph 4 already contains 2 injected links and a third link's anchor is found there
- **THEN** the system SHALL skip paragraph 4 and try subsequent paragraphs

#### Scenario: Links too close together
- **WHEN** two links would be placed with only 20 words between them in the same paragraph
- **THEN** the second link SHALL be moved to the next eligible paragraph or escalated to LLM fallback

### Requirement: Link stripping for re-planning
The system SHALL provide a function to strip all internal links from bottom_description, restoring it to a pre-injection state.

The stripping process SHALL:
1. Parse bottom_description with BeautifulSoup
2. Find all `<a>` tags where href matches an internal URL pattern (relative path or same-domain)
3. Replace each `<a>` tag with its text content (unwrap)
4. Preserve external links (absolute URLs to other domains)
5. Save the cleaned HTML back to PageContent.bottom_description

#### Scenario: Strip internal links only
- **WHEN** bottom_description contains 3 internal links (`<a href="/collections/...">`) and 1 external link (`<a href="https://other.com">`)
- **THEN** the 3 internal links SHALL be unwrapped to plain text and the external link SHALL remain unchanged

#### Scenario: Strip preserves content structure
- **WHEN** links are stripped from a page
- **THEN** all heading structure, paragraph breaks, and non-link HTML SHALL remain identical

### Requirement: Link validation rules
After injection, the system SHALL validate all links for a scope and report pass/fail per rule:

1. **Budget check**: Each page has 3-5 outbound links (warn if outside range, not fail)
2. **Silo integrity**: All link targets are within the same scope (onboarding pages link only to onboarding, cluster pages only to same cluster)
3. **No self-links**: No page links to itself
4. **No duplicate links**: No page links to the same target more than once
5. **Density check**: Max 2 links per paragraph, min 50 words between links
6. **Anchor diversity**: No anchor text used for the same target more than 3 times across the project
7. **First-link rule (cluster only)**: The first `<a>` tag in bottom_description SHALL point to the parent page URL
8. **Direction rules (cluster only)**: Parent links only to children, children link to parent + siblings

Each link SHALL be marked status="verified" if all rules pass, or flagged with the failing rule names.

#### Scenario: All validations pass
- **WHEN** a cluster with 8 pages completes injection with all rules satisfied
- **THEN** all InternalLink rows SHALL have status="verified" and the validation report SHALL show 100% pass rate

#### Scenario: First-link rule violation
- **WHEN** a child page's first `<a>` tag points to a sibling instead of the parent
- **THEN** validation SHALL fail for that page with rule="first_link_rule" and status SHALL remain "injected" (not "verified")

#### Scenario: Silo integrity violation
- **WHEN** a link's target_page_id belongs to a different cluster or has source="onboarding" in a cluster scope
- **THEN** validation SHALL fail with rule="silo_integrity"

#### Scenario: Budget under minimum (warning only)
- **WHEN** a page only has 2 outbound links (below minimum of 3)
- **THEN** validation SHALL log a warning but NOT fail — the page is still marked "verified"
