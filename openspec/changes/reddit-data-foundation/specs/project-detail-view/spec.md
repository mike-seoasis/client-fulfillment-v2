## MODIFIED Requirements

### Requirement: Project detail view has Reddit Marketing section
The project detail view SHALL display a Reddit Marketing section card below the Blogs section, showing Reddit config status and quick stats with a link to the project's Reddit settings page.

#### Scenario: Reddit section visible on project detail
- **WHEN** user views a project detail page
- **THEN** a "Reddit Marketing" section card is displayed after the Blogs section

#### Scenario: Reddit not configured state
- **WHEN** user views a project that has no reddit_project_config
- **THEN** the Reddit section shows "Not configured" status and a "Configure Reddit" CTA button linking to `/projects/[id]/reddit`

#### Scenario: Reddit configured state
- **WHEN** user views a project that has a reddit_project_config
- **THEN** the Reddit section shows "Configured" status and a "Manage Reddit Settings" link to `/projects/[id]/reddit`
