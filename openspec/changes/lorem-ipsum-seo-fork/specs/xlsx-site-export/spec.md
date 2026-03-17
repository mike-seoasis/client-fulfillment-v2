## ADDED Requirements

### Requirement: XLSX export endpoint
The system SHALL provide an API endpoint `GET /api/v1/export/sites-xlsx` that generates a multi-site XLSX workbook containing all projects' content data.

#### Scenario: Export all projects
- **WHEN** the endpoint is called without parameters
- **THEN** it SHALL return an XLSX file containing one tab per project plus an INSTRUCTIONS tab

#### Scenario: Export selected projects
- **WHEN** the endpoint is called with `project_ids=uuid1,uuid2` query parameter
- **THEN** it SHALL include only the specified projects as tabs

#### Scenario: File download response
- **WHEN** a valid export request is made
- **THEN** the response SHALL have `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` and `Content-Disposition: attachment; filename="sites-export.xlsx"`

#### Scenario: No projects exist
- **WHEN** the endpoint is called but no projects exist in the database
- **THEN** it SHALL return HTTP 400 with message "No projects available for export"

#### Scenario: No content generated yet
- **WHEN** a project has no generated content (no PageContent or BlogPost records)
- **THEN** that project's tab SHALL be included with only the header row (no data rows)

### Requirement: INSTRUCTIONS tab
The XLSX workbook SHALL include an INSTRUCTIONS tab as the first sheet with static documentation about the file format.

#### Scenario: Instructions content
- **WHEN** the XLSX is generated
- **THEN** the first tab SHALL be named "INSTRUCTIONS" and contain guidance on how the file is structured (each tab = one site, columns = page_type/title/meta/h1/descriptions/blog content)

### Requirement: Project tabs
Each project SHALL be represented as a separate tab in the XLSX workbook.

#### Scenario: Tab naming
- **WHEN** a project has domain "crossbodywaterbottlebag.shop"
- **THEN** the tab SHALL be named "crossbodywaterbottlebag.shop" (or truncated to 31 characters if longer, dropping the TLD suffix first)

#### Scenario: Tab naming without domain
- **WHEN** a project has no domain set but has a name "My Test Site"
- **THEN** the tab SHALL use the project name, sanitized to valid Excel tab characters and truncated to 31 characters

### Requirement: Column structure
Each project tab SHALL have the following columns in order: `page_type`, `title`, `meta_description`, `h1`, `Top description`, `Bottom Description`, `Blog Content`.

#### Scenario: Header row
- **WHEN** a project tab is generated
- **THEN** row 1 SHALL contain the column headers: page_type, title, meta_description, h1, Top description, Bottom Description, Blog Content

### Requirement: Collection page rows
Cluster pages with generated content SHALL be exported as collection rows.

#### Scenario: Collection row mapping
- **WHEN** a CrawledPage has a linked PageContent with status "complete"
- **THEN** it SHALL be exported as a row with page_type=`collection`, title=`PageContent.page_title`, meta_description=`PageContent.meta_description`, h1=`PageContent.page_title`, Top description=`PageContent.top_description`, Bottom Description=`PageContent.bottom_description`, Blog Content=(empty)

#### Scenario: Collection without content
- **WHEN** a CrawledPage has no PageContent or PageContent status is not "complete"
- **THEN** it SHALL NOT be included in the export

### Requirement: Blog post rows
Blog posts with generated content SHALL be exported as blog rows.

#### Scenario: Blog row mapping
- **WHEN** a BlogPost has content_status "complete" or "editing"
- **THEN** it SHALL be exported as a row with page_type=`blog`, title=`BlogPost.title`, meta_description=`BlogPost.meta_description`, h1=`BlogPost.title`, Top description=(empty), Bottom Description=(empty), Blog Content=`BlogPost.content`

#### Scenario: Blog without content
- **WHEN** a BlogPost has no generated content (content is null)
- **THEN** it SHALL NOT be included in the export

### Requirement: Row ordering
Rows within each project tab SHALL be ordered with collection pages first, then blog posts, each group sorted alphabetically by title.

#### Scenario: Mixed content ordering
- **WHEN** a project has 2 collection pages and 3 blog posts
- **THEN** the export SHALL show the 2 collection rows first (alphabetical), then the 3 blog rows (alphabetical)

### Requirement: Dashboard export button
The main dashboard page SHALL display an "Export All Sites" button that triggers the XLSX download.

#### Scenario: Button visibility
- **WHEN** the dashboard loads with at least one project
- **THEN** an "Export All Sites (XLSX)" button SHALL be visible in the dashboard header area

#### Scenario: Button triggers download
- **WHEN** the user clicks "Export All Sites (XLSX)"
- **THEN** the browser SHALL download the XLSX file via the export endpoint

#### Scenario: Loading state
- **WHEN** the export is being generated
- **THEN** the button SHALL show a loading spinner and be disabled until the download completes

#### Scenario: No projects
- **WHEN** the dashboard has no projects
- **THEN** the export button SHALL be hidden or disabled
