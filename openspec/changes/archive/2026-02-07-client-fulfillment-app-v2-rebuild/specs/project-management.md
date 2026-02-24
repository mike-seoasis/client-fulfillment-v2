# Spec: project-management

## Overview

CRUD operations for client projects with status tracking across all pipeline phases. Projects are the top-level entity containing all crawled pages, keywords, content, and configuration.

## Data Model

### Project Entity

```
Project:
  id: UUID (primary key)
  name: string (required, e.g., "Acme Coffee Co")
  website_url: string (required, validated URL)
  created_at: datetime
  updated_at: datetime
  phase_status: JSON object tracking each phase
  settings: JSON object for project-specific config
```

### Phase Status Structure

Each phase tracks:
```
{
  "status": "pending" | "in_progress" | "completed" | "failed",
  "started_at": datetime | null,
  "completed_at": datetime | null,
  "progress": 0-100,
  "message": string,
  "error": string | null
}
```

## Behaviors

### WHEN creating a project
- THEN validate website_url is a valid URL format
- AND initialize all phase statuses to "pending"
- AND set created_at and updated_at to current timestamp
- AND return the created project with generated UUID

### WHEN listing projects
- THEN return all projects ordered by updated_at descending
- AND include phase_status summary for each project
- AND support optional filtering by status (active, completed, all)

### WHEN getting a single project
- THEN return full project details including all phase statuses
- AND return 404 if project not found

### WHEN updating a project
- THEN only allow updating name, website_url, and settings
- AND update updated_at timestamp
- AND preserve all phase statuses and data
- AND return 404 if project not found

### WHEN deleting a project
- THEN soft delete by marking as inactive (preserve data)
- AND cascade status to all related entities
- AND return 204 on success, 404 if not found

### WHEN a phase status changes
- THEN update the specific phase in phase_status
- AND update project updated_at timestamp
- AND broadcast status change via WebSocket if connected

## API Endpoints

```
GET    /api/v1/projects              - List all projects
POST   /api/v1/projects              - Create project
GET    /api/v1/projects/{id}         - Get project by ID
PUT    /api/v1/projects/{id}         - Update project
DELETE /api/v1/projects/{id}         - Delete project
GET    /api/v1/projects/{id}/status  - Get all phase statuses
```

## Validation Rules

- name: 1-200 characters, required
- website_url: valid URL format, must include protocol (https://)
- settings: optional JSON object, validated against schema

## Error Handling

- Invalid URL format: 400 with message "Invalid website URL format"
- Duplicate website_url: 400 with message "Project with this URL already exists"
- Project not found: 404 with message "Project not found"
- Validation errors: 400 with field-specific error messages

## Database Schema

```sql
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(200) NOT NULL,
  website_url VARCHAR(500) NOT NULL UNIQUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  phase_status JSONB DEFAULT '{}',
  settings JSONB DEFAULT '{}',
  is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_projects_updated_at ON projects(updated_at DESC);
CREATE INDEX idx_projects_is_active ON projects(is_active);
```
