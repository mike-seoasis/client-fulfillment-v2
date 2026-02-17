## MODIFIED Requirements

### Requirement: Project data model includes reddit_config relationship
The Project model SHALL include a 1:1 relationship to RedditProjectConfig with cascade delete.

#### Scenario: Project has reddit_config relationship
- **WHEN** a project is queried with eager loading
- **THEN** the associated `reddit_config` (RedditProjectConfig or None) is accessible via `project.reddit_config`

#### Scenario: Deleting project cascades to reddit config
- **WHEN** a project with an associated reddit_project_config is deleted
- **THEN** the reddit_project_config is also deleted via cascade
