## ADDED Requirements

### Requirement: Export service generates Matrixify-compatible CSV
The system SHALL generate a CSV file with the following columns in this order:
1. `Handle` — the collection handle extracted from the page URL (e.g., `running-shoes` from `/collections/running-shoes`)
2. `Title` — the generated `page_title` from PageContent
3. `Body (HTML)` — the `bottom_description` from PageContent (HTML content for below-the-fold)
4. `SEO Description` — the `meta_description` from PageContent
5. `Metafield: custom.top_description [single_line_text_field]` — the `top_description` from PageContent

The CSV SHALL use RFC 4180 compliant formatting (comma-delimited, proper quoting/escaping).

#### Scenario: Standard collection URL export
- **WHEN** a page has URL `https://store.com/collections/running-shoes` and approved content with all 4 fields populated
- **THEN** the CSV row SHALL have Handle `running-shoes`, and all content fields mapped to their respective columns

#### Scenario: URL without /collections/ prefix
- **WHEN** a page URL does not contain `/collections/` (e.g., `https://store.com/shoes/hiking`)
- **THEN** the system SHALL use the last path segment as the Handle (e.g., `hiking`)

#### Scenario: Empty content fields
- **WHEN** a page has approved content but some fields are null (e.g., top_description is null)
- **THEN** the CSV SHALL include an empty string for that column, not the literal "None"

### Requirement: Export endpoint accepts page selection
The system SHALL provide an API endpoint `GET /api/v1/projects/{project_id}/export` that accepts an optional query parameter `page_ids` (comma-separated UUIDs) to specify which pages to include.

#### Scenario: Export specific pages
- **WHEN** the endpoint is called with `page_ids=uuid1,uuid2,uuid3`
- **THEN** only those pages SHALL be included in the CSV, provided they have approved content

#### Scenario: Export all approved pages (no page_ids)
- **WHEN** the endpoint is called without `page_ids`
- **THEN** all pages in the project with `is_approved=True` and `status=complete` SHALL be included

#### Scenario: Non-approved page in page_ids
- **WHEN** a page_id in the request does not have approved content
- **THEN** that page SHALL be silently skipped (not included in CSV, no error)

#### Scenario: No exportable pages
- **WHEN** no pages match the criteria (all filtered out or none approved)
- **THEN** the endpoint SHALL return HTTP 400 with message "No approved pages available for export"

### Requirement: Export returns a file download
The endpoint SHALL return the CSV as a file download with:
- `Content-Type: text/csv; charset=utf-8`
- `Content-Disposition: attachment; filename="{project_name}-matrixify-export.csv"`
- UTF-8 BOM prefix for Excel compatibility

#### Scenario: Successful download
- **WHEN** a valid export request is made with at least one exportable page
- **THEN** the response SHALL be a CSV file download with the project name in the filename

#### Scenario: Filename sanitization
- **WHEN** the project name contains special characters (e.g., "Acme's Store!")
- **THEN** the filename SHALL be sanitized to alphanumeric + hyphens (e.g., `acmes-store-matrixify-export.csv`)

### Requirement: Handle extraction from URLs
The system SHALL extract the Shopify collection handle from page URLs using the following logic:
1. Parse the URL path
2. If path contains `/collections/`, use the segment immediately after it
3. Otherwise, use the last non-empty path segment
4. Strip any trailing slashes or query parameters

#### Scenario: Standard Shopify collection URL
- **WHEN** URL is `https://store.com/collections/running-shoes`
- **THEN** Handle SHALL be `running-shoes`

#### Scenario: Nested collection URL
- **WHEN** URL is `https://store.com/collections/mens/running-shoes`
- **THEN** Handle SHALL be `mens/running-shoes` (preserve sub-path after /collections/)

#### Scenario: URL with query parameters
- **WHEN** URL is `https://store.com/collections/sandals?sort=price`
- **THEN** Handle SHALL be `sandals` (query params stripped)

#### Scenario: URL with trailing slash
- **WHEN** URL is `https://store.com/collections/boots/`
- **THEN** Handle SHALL be `boots` (trailing slash stripped)
