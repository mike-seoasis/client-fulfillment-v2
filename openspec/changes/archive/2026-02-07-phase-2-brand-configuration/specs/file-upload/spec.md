## ADDED Requirements

### Requirement: Upload file to project
The system SHALL allow users to upload files (brand documents) associated with a project, storing them in S3 and extracting text content.

#### Scenario: Upload PDF file successfully
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with a PDF file (multipart/form-data)
- **THEN** system stores file in S3, extracts text using pypdf, creates ProjectFile record, and returns 201 with file metadata including `id`, `filename`, `content_type`, `file_size`, and `extracted_text` length

#### Scenario: Upload DOCX file successfully
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with a DOCX file
- **THEN** system stores file in S3, extracts text using python-docx, creates ProjectFile record, and returns 201 with file metadata

#### Scenario: Upload TXT file successfully
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with a plain text file
- **THEN** system stores file in S3, reads text directly, creates ProjectFile record, and returns 201 with file metadata

#### Scenario: Upload file to non-existent project
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with a project ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

#### Scenario: Upload file exceeding size limit
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with a file larger than 10MB
- **THEN** system returns 413 with error message "File size exceeds 10MB limit"

#### Scenario: Upload unsupported file type
- **WHEN** client sends POST to `/api/v1/projects/{project_id}/files` with an unsupported file type (e.g., .exe, .zip)
- **THEN** system returns 415 with error message "Unsupported file type. Allowed: PDF, DOCX, TXT"

### Requirement: List files for project
The system SHALL allow users to retrieve all files associated with a project.

#### Scenario: List files when files exist
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/files`
- **THEN** system returns 200 with array of file objects containing `id`, `filename`, `content_type`, `file_size`, `created_at`

#### Scenario: List files when no files exist
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/files` for a project with no uploaded files
- **THEN** system returns 200 with empty array `[]`

#### Scenario: List files for non-existent project
- **WHEN** client sends GET to `/api/v1/projects/{project_id}/files` with a project ID that does not exist
- **THEN** system returns 404 with error message "Project not found"

### Requirement: Delete file from project
The system SHALL allow users to delete an uploaded file, removing it from S3 and the database.

#### Scenario: Delete existing file
- **WHEN** client sends DELETE to `/api/v1/projects/{project_id}/files/{file_id}` with valid IDs
- **THEN** system removes file from S3, deletes ProjectFile record, and returns 204 No Content

#### Scenario: Delete non-existent file
- **WHEN** client sends DELETE to `/api/v1/projects/{project_id}/files/{file_id}` with a file ID that does not exist
- **THEN** system returns 404 with error message "File not found"

### Requirement: ProjectFile data model
The system SHALL store uploaded file metadata in a ProjectFile table with S3 key reference and extracted text.

#### Scenario: ProjectFile record created with all fields
- **WHEN** a file is uploaded successfully
- **THEN** a ProjectFile record is created with `id` (UUID), `project_id` (FK), `filename`, `content_type`, `s3_key`, `extracted_text`, `file_size`, and `created_at`

#### Scenario: ProjectFile cascades on project deletion
- **WHEN** a project is deleted
- **THEN** all associated ProjectFile records are deleted and files are removed from S3

### Requirement: Text extraction truncates large documents
The system SHALL truncate extracted text to 100,000 characters per document to prevent excessive storage and processing.

#### Scenario: Large document text is truncated
- **WHEN** a document with more than 100,000 characters of text is uploaded
- **THEN** system extracts and stores only the first 100,000 characters and logs a warning

#### Scenario: Normal document text is not truncated
- **WHEN** a document with fewer than 100,000 characters of text is uploaded
- **THEN** system extracts and stores the complete text

### Requirement: S3 storage with dev fallback
The system SHALL use S3 for file storage in production and LocalStack (S3-compatible) for local development.

#### Scenario: File stored in S3 with unique key
- **WHEN** a file is uploaded
- **THEN** system stores it in S3 with key format `projects/{project_id}/files/{file_id}/{filename}`

#### Scenario: S3 unavailable returns error
- **WHEN** S3 is unavailable during upload (circuit breaker open)
- **THEN** system returns 503 with error message "File storage temporarily unavailable"
