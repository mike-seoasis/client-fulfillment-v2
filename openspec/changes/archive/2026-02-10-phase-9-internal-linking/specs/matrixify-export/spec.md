## MODIFIED Requirements

### Requirement: Export service generates Matrixify-compatible CSV
The system SHALL generate a CSV file with the following columns in this order:
1. `Handle` — the collection handle extracted from the page URL (e.g., `running-shoes` from `/collections/running-shoes`)
2. `Title` — the generated `page_title` from PageContent
3. `Body (HTML)` — the `bottom_description` from PageContent (HTML content for below-the-fold, including any injected internal links as `<a>` tags)
4. `SEO Description` — the `meta_description` from PageContent
5. `Metafield: custom.top_description [single_line_text_field]` — the `top_description` from PageContent

The CSV SHALL use RFC 4180 compliant formatting (comma-delimited, proper quoting/escaping).

Internal links injected into `bottom_description` during Phase 9 link planning SHALL be preserved as-is in the exported HTML. No additional processing of link tags is required.

#### Scenario: Standard collection URL export
- **WHEN** a page has URL `https://store.com/collections/running-shoes` and approved content with all 4 fields populated
- **THEN** the CSV row SHALL have Handle `running-shoes`, and all content fields mapped to their respective columns

#### Scenario: URL without /collections/ prefix
- **WHEN** a page URL does not contain `/collections/` (e.g., `https://store.com/shoes/hiking`)
- **THEN** the system SHALL use the last path segment as the Handle (e.g., `hiking`)

#### Scenario: Empty content fields
- **WHEN** a page has approved content but some fields are null (e.g., top_description is null)
- **THEN** the CSV SHALL include an empty string for that column, not the literal "None"

#### Scenario: Content with internal links
- **WHEN** a page's bottom_description contains internal links (e.g., `<a href="/collections/trail-shoes">trail running shoes</a>`)
- **THEN** the exported Body (HTML) SHALL include those `<a>` tags exactly as they appear in bottom_description
