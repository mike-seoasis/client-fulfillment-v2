## ADDED Requirements

### Requirement: Create cluster endpoint
The system SHALL provide `POST /api/v1/projects/{project_id}/clusters` to create a new cluster and run Stages 1-3.

#### Scenario: Successful cluster creation
- **WHEN** a POST request is sent with `{"seed_keyword": "trail running shoes"}`
- **THEN** the system runs Stages 1-3 synchronously and returns 200 with the cluster ID, seed keyword, name, status, and list of page suggestions with volume data and scores

#### Scenario: Optional cluster name
- **WHEN** a POST request includes `{"seed_keyword": "trail running shoes", "name": "Trail Running"}`
- **THEN** the cluster is created with `name="Trail Running"` instead of defaulting to the seed keyword

#### Scenario: Invalid project ID returns 404
- **WHEN** a POST request targets a non-existent project ID
- **THEN** the system returns 404 with error message

#### Scenario: Empty seed keyword returns 422
- **WHEN** a POST request is sent with `{"seed_keyword": ""}`
- **THEN** the system returns 422 validation error

#### Scenario: Request timeout returns 504
- **WHEN** Stages 1-3 exceed 30 seconds
- **THEN** the system returns 504 with a message suggesting the user retry

### Requirement: List clusters endpoint
The system SHALL provide `GET /api/v1/projects/{project_id}/clusters` to list all clusters for a project.

#### Scenario: List clusters for a project
- **WHEN** a GET request is sent for a project with 3 clusters
- **THEN** the system returns 200 with a list of 3 clusters, each including `id`, `seed_keyword`, `name`, `status`, `page_count` (total), `approved_count`, `created_at`

#### Scenario: Empty cluster list
- **WHEN** a GET request is sent for a project with no clusters
- **THEN** the system returns 200 with an empty list

### Requirement: Get cluster detail endpoint
The system SHALL provide `GET /api/v1/projects/{project_id}/clusters/{cluster_id}` to get a cluster with all its pages.

#### Scenario: Get cluster with pages
- **WHEN** a GET request is sent for a specific cluster
- **THEN** the system returns 200 with the full cluster object including all `ClusterPage` records with their volume data, scores, roles, and approval status

#### Scenario: Cluster not found returns 404
- **WHEN** a GET request targets a non-existent cluster ID
- **THEN** the system returns 404

### Requirement: Update cluster page endpoint
The system SHALL provide `PATCH /api/v1/projects/{project_id}/clusters/{cluster_id}/pages/{page_id}` to approve/reject individual pages and edit URL slugs.

#### Scenario: Approve a single page
- **WHEN** a PATCH request is sent with `{"is_approved": true}`
- **THEN** the cluster page's `is_approved` is set to true and the updated page is returned

#### Scenario: Reject a previously approved page
- **WHEN** a PATCH request is sent with `{"is_approved": false}`
- **THEN** the cluster page's `is_approved` is set to false

#### Scenario: Edit URL slug
- **WHEN** a PATCH request is sent with `{"url_slug": "/collections/custom-slug"}`
- **THEN** the cluster page's `url_slug` is updated

#### Scenario: Edit keyword
- **WHEN** a PATCH request is sent with `{"keyword": "best trail running shoes"}`
- **THEN** the cluster page's `keyword` is updated

#### Scenario: Reassign parent role
- **WHEN** a PATCH request is sent with `{"role": "parent"}` for a child page
- **THEN** the target page becomes the parent, and the previous parent becomes a child

#### Scenario: Page not found returns 404
- **WHEN** a PATCH request targets a non-existent page ID
- **THEN** the system returns 404

### Requirement: Bulk-approve cluster endpoint
The system SHALL provide `POST /api/v1/projects/{project_id}/clusters/{cluster_id}/approve` to approve all selected pages and bridge them into the content pipeline.

#### Scenario: Bulk-approve creates CrawledPage and PageKeywords records
- **WHEN** a POST request is sent to the bulk-approve endpoint
- **THEN** the system creates CrawledPage + PageKeywords records for all approved pages, updates cluster status to `approved`, and returns 200 with the count of pages bridged

#### Scenario: No approved pages returns 400
- **WHEN** bulk-approve is called but no cluster pages have `is_approved=true`
- **THEN** the system returns 400 with error "No approved pages to process"

#### Scenario: Already-approved cluster returns 409
- **WHEN** bulk-approve is called on a cluster with status `approved` or later
- **THEN** the system returns 409 with error "Cluster already approved"

### Requirement: Delete cluster endpoint
The system SHALL provide `DELETE /api/v1/projects/{project_id}/clusters/{cluster_id}` to delete a cluster.

#### Scenario: Delete a draft cluster
- **WHEN** a DELETE request targets a cluster with status `suggestions_ready`
- **THEN** the cluster and all its pages are deleted, returning 204

#### Scenario: Delete an approved cluster is blocked
- **WHEN** a DELETE request targets a cluster with status `approved` or later
- **THEN** the system returns 409 with error "Cannot delete cluster after approval — pages are already in the content pipeline"

#### Scenario: Cluster not found returns 404
- **WHEN** a DELETE request targets a non-existent cluster ID
- **THEN** the system returns 404
