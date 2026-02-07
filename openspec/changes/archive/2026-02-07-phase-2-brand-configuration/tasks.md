## 1. Database & Models

- [ ] 1.1 Create ProjectFile model with fields: id, project_id (FK), filename, content_type, s3_key, extracted_text, file_size, created_at
- [ ] 1.2 Create Alembic migration for project_files table with cascade delete on project
- [ ] 1.3 Add additional_info column to Project model (Text, nullable)
- [ ] 1.4 Create Alembic migration for projects.additional_info column
- [ ] 1.5 Extend BrandConfig.v2_schema with 9-section structure (update docstring with full schema)

## 2. S3 Integration

- [ ] 2.1 Create S3Client integration in backend/app/integrations/s3.py with circuit breaker pattern
- [ ] 2.2 Add S3 config settings (bucket name, endpoint, access key, secret key) to core/config.py
- [ ] 2.3 Implement upload_file, get_file, delete_file methods with proper error handling
- [ ] 2.4 Add LocalStack configuration for docker-compose.yml (local S3)
- [ ] 2.5 Add S3 environment variables to .env.example

## 3. Text Extraction Utilities

- [ ] 3.1 Add pypdf and python-docx dependencies to pyproject.toml
- [ ] 3.2 Create text extraction module at backend/app/utils/text_extraction.py
- [ ] 3.3 Implement extract_text_from_pdf() using pypdf
- [ ] 3.4 Implement extract_text_from_docx() using python-docx
- [ ] 3.5 Implement extract_text_from_txt() for plain text files
- [ ] 3.6 Add text truncation at 100k characters with warning logging

## 4. File Upload API

- [ ] 4.1 Create ProjectFile Pydantic schemas (Create, Response, List)
- [ ] 4.2 Create FileService in backend/app/services/file.py
- [ ] 4.3 Implement upload endpoint: POST /api/v1/projects/{id}/files
- [ ] 4.4 Implement list endpoint: GET /api/v1/projects/{id}/files
- [ ] 4.5 Implement delete endpoint: DELETE /api/v1/projects/{id}/files/{file_id}
- [ ] 4.6 Add file size validation (max 10MB)
- [ ] 4.7 Add file type validation (PDF, DOCX, TXT only)
- [ ] 4.8 Write API tests for file upload endpoints

## 5. Brand Config Generation Service

- [ ] 5.1 Update PerplexityClient.research_brand() prompt to cover all 9 brand sections
- [ ] 5.2 Create BrandConfigService in backend/app/services/brand_config.py
- [ ] 5.3 Implement research phase: parallel calls to Perplexity, Crawl4AI, and doc text extraction
- [ ] 5.4 Implement synthesis phase: sequential Claude calls for each of 9 sections
- [ ] 5.5 Create generation status tracking with step progress
- [ ] 5.6 Add timeout handling per step (60s) and total (5min)
- [ ] 5.7 Store generation status in project.brand_wizard_state JSONB field

## 6. Brand Config Generation API

- [ ] 6.1 Implement trigger endpoint: POST /api/v1/projects/{id}/brand-config/generate
- [ ] 6.2 Implement status endpoint: GET /api/v1/projects/{id}/brand-config/status
- [ ] 6.3 Wire generation to FastAPI BackgroundTasks
- [ ] 6.4 Add conflict handling for generation already in progress (409)
- [ ] 6.5 Write API tests for generation endpoints

## 7. Brand Config Management API

- [ ] 7.1 Create BrandConfig Pydantic schemas (Response, SectionUpdate, RegenerateRequest)
- [ ] 7.2 Implement get endpoint: GET /api/v1/projects/{id}/brand-config
- [ ] 7.3 Implement update endpoint: PATCH /api/v1/projects/{id}/brand-config
- [ ] 7.4 Implement regenerate endpoint: POST /api/v1/projects/{id}/brand-config/regenerate
- [ ] 7.5 Add section validation for update/regenerate requests
- [ ] 7.6 Write API tests for brand config management endpoints

## 8. Project API Updates

- [ ] 8.1 Update ProjectCreate schema to include additional_info (optional)
- [ ] 8.2 Update ProjectResponse schema to include brand_config_status, has_brand_config, uploaded_files_count
- [ ] 8.3 Update project list endpoint to include new fields
- [ ] 8.4 Update project get endpoint to include new fields
- [ ] 8.5 Update project delete to cascade delete files from S3
- [ ] 8.6 Update existing project API tests for new fields

## 9. Frontend: File Upload Component

- [ ] 9.1 Create FileUpload component with drag-and-drop support
- [ ] 9.2 Add file type and size validation in UI
- [ ] 9.3 Create useProjectFiles hook with TanStack Query (list, upload, delete mutations)
- [ ] 9.4 Add file list display with delete buttons
- [ ] 9.5 Add upload progress indicator

## 10. Frontend: Project Creation Wizard

- [ ] 10.1 Convert CreateProject page to multi-step wizard (Step 1: Details, Step 2: Generation)
- [ ] 10.2 Add FileUpload component to Step 1
- [ ] 10.3 Add additional_info textarea to Step 1
- [ ] 10.4 Create generation progress screen for Step 2
- [ ] 10.5 Implement status polling with 2s interval during generation
- [ ] 10.6 Add step indicators showing generation progress
- [ ] 10.7 Handle generation completion/failure with appropriate UI feedback
- [ ] 10.8 Navigate to project detail on completion

## 11. Frontend: Brand Config Viewer

- [ ] 11.1 Create BrandConfigView page at /projects/{id}/brand-config
- [ ] 11.2 Create vertical tab navigation for 9 sections + AI Prompt
- [ ] 11.3 Create section components for each brand config section
- [ ] 11.4 Create useBrandConfig hook with TanStack Query (get, update mutations)
- [ ] 11.5 Add inline editing for each section
- [ ] 11.6 Add save button per section with optimistic updates
- [ ] 11.7 Add "Regenerate" buttons (all config and per-section)
- [ ] 11.8 Link brand config from project detail page header

## 12. Frontend: Project Detail Updates

- [ ] 12.1 Add brand config status badge to project header
- [ ] 12.2 Add "Edit Brand" button linking to brand config viewer
- [ ] 12.3 Show uploaded files count in project overview
- [ ] 12.4 Add empty state prompting brand config generation if not generated

## 13. Testing & Integration

- [ ] 13.1 Write unit tests for text extraction utilities
- [ ] 13.2 Write unit tests for S3 client
- [ ] 13.3 Write integration tests for brand config generation flow
- [ ] 13.4 Write frontend component tests for FileUpload
- [ ] 13.5 Write frontend component tests for BrandConfigView
- [ ] 13.6 Manual E2E test: Create project with files, generate brand config, edit sections

## 14. Completion Tasks

- [ ] 14.1 All implementation tasks complete
- [ ] 14.2 All tests passing (pytest backend/tests/ && npm test)
- [ ] 14.3 Manual verification: Can upload files, generate brand config, view/edit sections
- [ ] 14.4 Update V2_REBUILD_PLAN.md: Mark Phase 2 checkboxes complete
- [ ] 14.5 Update V2_REBUILD_PLAN.md: Update Current Status table
- [ ] 14.6 Update V2_REBUILD_PLAN.md: Add Session Log entry
- [ ] 14.7 Commit with message: feat(phase-2): Add brand configuration with file upload and AI generation
