## MODIFIED Requirements

### Requirement: Project detail view has New Content section
The project detail view SHALL display a New Content (Clusters) section showing existing clusters and a button to create new ones.

#### Scenario: New Content section shows cluster list
- **WHEN** user views a project detail page with existing clusters
- **THEN** the New Content section displays cluster cards showing name, page count, status, and click-to-navigate

#### Scenario: New Content section shows empty state
- **WHEN** user views a project detail page with no clusters
- **THEN** the New Content section shows "No clusters yet" with a prominent "+ New Cluster" button

#### Scenario: New Cluster button navigates to creation
- **WHEN** user clicks "+ New Cluster" in the New Content section
- **THEN** user is navigated to `/projects/{id}/clusters/new`

#### Scenario: Cluster card click navigates to detail
- **WHEN** user clicks on a cluster card
- **THEN** user is navigated to `/projects/{id}/clusters/{clusterId}`
