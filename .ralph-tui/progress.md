# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### SQLAlchemy Model Pattern
- All models inherit from `app.core.database.Base`
- UUID primary keys use `UUID(as_uuid=False)` with `str(uuid4())` default
- Server defaults: `text("gen_random_uuid()")` for UUIDs, `text("now()")` for timestamps
- Foreign keys with cascade: `ForeignKey("table.id", ondelete="CASCADE")`
- Timestamps use `DateTime(timezone=True)` with `datetime.now(UTC)`
- New models must be added to `app/models/__init__.py` (import + `__all__` list)

### Service Pattern
- Services coordinate between integrations (S3, etc.), utilities, and database
- Take dependencies via constructor injection (e.g., `__init__(self, s3_client: S3Client)`)
- Methods take `db: AsyncSession` as first param for database operations
- Raise `HTTPException` for client-facing errors (404, 500)
- New services must be added to `app/services/__init__.py` (import + `__all__` list)

### API Test Pattern
- Use `async_client` fixture for standard API tests
- For tests needing S3, create `async_client_with_s3` fixture that overrides `get_s3` dependency
- Create mock clients (e.g., `MockS3Client`) with same interface as real integration
- Override dependencies via `app.dependency_overrides[dependency_func] = lambda: mock_instance`
- Use `files={"file": ("name.ext", content_bytes, "content/type")}` for multipart uploads
- Test classes follow: `TestUploadFile`, `TestListFiles`, `TestDeleteFile` pattern

---

## 2026-02-03 - S2-001
- **What was implemented:** ProjectFile model for storing uploaded brand documents
- **Files changed:**
  - `backend/app/models/project_file.py` (created)
  - `backend/app/models/__init__.py` (added import/export)
- **Learnings:**
  - Pattern: Use `BigInteger` for file_size to handle large files (>2GB)
  - Pattern: `s3_key` should be unique to prevent duplicate storage references
  - Gotcha: Must use `uv run` prefix for python/mypy/ruff commands in this project
---

## 2026-02-03 - S2-002
- **What was implemented:** Alembic migration for project_files table
- **Files changed:**
  - `backend/alembic/versions/0017_create_project_files_table.py` (created)
- **Learnings:**
  - Pattern: Migrations follow format `0NNN_description.py` with sequential numbering
  - Pattern: Use `sa.ForeignKeyConstraint` with `name` param for explicit FK naming (e.g., `fk_table_column`)
  - Pattern: Use `sa.UniqueConstraint` with `name` param for explicit constraint naming (e.g., `uq_table_column`)
  - Pattern: Index naming convention uses `ix_table_column` via `op.f()` helper
  - Verified: Both upgrade and downgrade paths work correctly
---

## 2026-02-03 - S2-003
- **What was implemented:** Added additional_info column to Project model for user notes during project creation
- **Files changed:**
  - `backend/app/models/project.py` (added additional_info field with Text type, nullable)
  - `backend/alembic/versions/0018_add_additional_info_to_projects.py` (created)
- **Learnings:**
  - Pattern: Use `Text` (not `String`) for unbounded text fields like notes/descriptions
  - Pattern: Simple column additions don't need indexes unless they'll be queried directly
  - Verified: Both upgrade and downgrade paths work correctly
---

## 2026-02-03 - S2-004
- **What was implemented:** S3 integration client with circuit breaker pattern for file storage
- **Files changed:**
  - `backend/app/core/config.py` (added S3 settings: s3_bucket, s3_endpoint_url, s3_access_key, s3_secret_key, s3_region, s3_timeout, s3_max_retries, s3_retry_delay, circuit breaker settings)
  - `backend/app/integrations/s3.py` (created - S3Client class with upload_file, get_file, delete_file, file_exists, get_file_metadata)
  - `backend/app/integrations/__init__.py` (added S3 exports)
- **Learnings:**
  - Pattern: Use `boto3.client` for S3 operations; boto3 clients are thread-safe but operations are sync, so wrap with `run_in_executor` for async
  - Pattern: Use `endpoint_url` parameter for LocalStack/S3-compatible services
  - Pattern: S3NotFoundError (404/NoSuchKey) should NOT trigger circuit breaker - it's expected behavior
  - Pattern: Import `Callable` from `collections.abc` not `typing` (ruff UP035)
  - Pattern: botocore modules need `# type: ignore[import-not-found]` - stubs not available
  - Gotcha: Type ignores must match the exact error code (e.g., `no-any-return` not `return-value`)
---

## 2026-02-03 - S2-005
- **What was implemented:** LocalStack service for local S3 development
- **Files changed:**
  - `docker-compose.yml` (added localstack service with S3, health check, auto-bucket init; added S3 env vars to backend; added localstack_data volume)
  - `backend/.env.example` (added S3 configuration section with S3_BUCKET, S3_ENDPOINT_URL, S3_ACCESS_KEY, S3_SECRET_KEY, S3_REGION)
  - `scripts/localstack-init.sh` (created - auto-creates onboarding-files bucket on startup)
- **Learnings:**
  - Pattern: LocalStack uses `/etc/localstack/init/ready.d/` for init scripts that run after services are ready
  - Pattern: Use `awslocal` CLI in LocalStack init scripts (pre-configured AWS CLI wrapper)
  - Pattern: LocalStack S3 endpoint is `http://localhost:4566` for local access, `http://localstack:4566` for container-to-container
  - Pattern: LocalStack accepts any credentials for local dev (use "test" for simplicity)
  - Pattern: Add `EAGER_SERVICE_LOADING=1` to ensure S3 is ready before health check passes
---

## 2026-02-03 - S2-006
- **What was implemented:** Text extraction utilities for processing uploaded documents (PDF, DOCX, TXT)
- **Files changed:**
  - `backend/app/utils/__init__.py` (created - module init with exports)
  - `backend/app/utils/text_extraction.py` (created - extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt, extract_text dispatcher)
- **Learnings:**
  - Pattern: Use `pypdf` (not PyPDF2) for PDF text extraction - PyPDF2 is deprecated
  - Pattern: Use `python-docx` and import as `docx` (e.g., `from docx import Document`)
  - Pattern: For text files, try UTF-8 first then fall back to latin-1 which accepts any byte sequence
  - Pattern: Normalize content_type by stripping parameters (e.g., `text/plain; charset=utf-8` → `text/plain`)
  - Pattern: Use `io.BytesIO` to wrap file bytes for libraries expecting file-like objects
---

## 2026-02-03 - S2-007
- **What was implemented:** Pydantic schemas for ProjectFile API responses
- **Files changed:**
  - `backend/app/schemas/project_file.py` (created - ProjectFileResponse, ProjectFileList)
  - `backend/app/schemas/__init__.py` (added imports and exports)
- **Learnings:**
  - Pattern: Response schemas use `ConfigDict(from_attributes=True)` for ORM model serialization
  - Pattern: Don't expose internal fields (s3_key, extracted_text) in API responses - keep them internal
  - Pattern: File upload APIs use multipart/form-data, so no Create schema needed for the JSON body
  - Pattern: List schemas follow `items` + `total` convention (may omit `limit`/`offset` for simpler cases)
---

## 2026-02-03 - S2-008
- **What was implemented:** FileService for coordinating file operations (S3 storage + text extraction + DB)
- **Files changed:**
  - `backend/app/services/file.py` (created - FileService class with upload_file, list_files, delete_file)
  - `backend/app/services/__init__.py` (added FileService import and export)
- **Learnings:**
  - Pattern: Services take dependencies (like S3Client) via constructor injection for testability
  - Pattern: Text extraction is best-effort on upload - don't fail the upload if extraction fails
  - Pattern: S3 key format `projects/{project_id}/files/{file_id}/{filename}` provides clean organization
  - Pattern: On delete, handle S3NotFoundError gracefully (file already gone) but still delete DB record
  - Pattern: Use `isinstance(file, bytes)` check rather than `hasattr(file, "read")` for cleaner type handling
---

## 2026-02-03 - S2-009
- **What was implemented:** File upload API endpoints for project file management
- **Files changed:**
  - `backend/app/api/v1/files.py` (created - router with POST, GET, DELETE endpoints)
  - `backend/app/api/v1/__init__.py` (registered files router)
- **Learnings:**
  - Pattern: File endpoints nest under projects: `/projects/{project_id}/files`
  - Pattern: Use `UploadFile` from FastAPI for multipart/form-data handling
  - Pattern: Read file content with `await file.read()` before size validation
  - Pattern: Validate project exists first (reuse `ProjectService.get_project` which raises 404)
  - Pattern: File validation constants at module level: `MAX_FILE_SIZE_BYTES`, `ALLOWED_CONTENT_TYPES`
  - Pattern: 413 for size exceeded, 415 for unsupported media type
  - Pattern: Instantiate service in endpoint with injected S3Client: `FileService(s3)`
---

## 2026-02-03 - S2-010
- **What was implemented:** API tests for file upload endpoints
- **Files changed:**
  - `backend/tests/api/test_files.py` (created - 15 tests covering upload, list, delete)
  - `backend/pyproject.toml` (added boto3 to dependencies - was missing)
- **Learnings:**
  - Pattern: Create a `MockS3Client` class with same interface as S3Client for testing
  - Pattern: Override FastAPI dependencies with `app.dependency_overrides[get_s3] = lambda: mock_s3`
  - Pattern: Create fixture `async_client_with_s3` that combines db/redis/s3 mocks
  - Pattern: Use `files={"file": ("name.txt", content, "content/type")}` for multipart uploads in httpx
  - Pattern: Create minimal valid file content for tests (PDF, DOCX as zip, TXT)
  - Pattern: Test file isolation between projects - ensure each project only sees its own files
  - Pattern: Test cross-project access denied - file belonging to project A should 404 when accessed via project B
  - Gotcha: boto3 was missing from pyproject.toml dependencies - added `boto3>=1.34.0`
---

## 2026-02-03 - S2-011
- **What was implemented:** Updated BRAND_RESEARCH_SYSTEM_PROMPT to cover all 9 brand config sections
- **Files changed:**
  - `backend/app/integrations/perplexity.py` (expanded BRAND_RESEARCH_SYSTEM_PROMPT, updated docstring)
- **Learnings:**
  - Pattern: Brand config follows 9 sections: Foundation, Target Audience, Voice Dimensions, Voice Characteristics, Writing Style, Vocabulary, Trust Elements, Examples Bank, Competitor Context
  - Pattern: System prompts for comprehensive research should request structured output with clear headers for each section
  - Pattern: max_tokens=4096 is appropriate for comprehensive brand research responses
  - Reference: skills/brand_guidelines_bible.md contains the authoritative structure for brand guidelines
---

## 2026-02-03 - S2-012
- **What was implemented:** BrandConfigService to orchestrate brand config generation
- **Files changed:**
  - `backend/app/services/brand_config.py` (created - BrandConfigService, GenerationStatus, GenerationStatusValue)
  - `backend/app/services/__init__.py` (added BrandConfigService and GenerationStatus exports)
- **Learnings:**
  - Pattern: Use dataclass for status objects that need both dict serialization (for JSONB) and typed access
  - Pattern: Store generation status under a `generation` key in the JSONB state field to namespace it from other wizard state data
  - Pattern: Use str enum (inheriting from both str and Enum) for values that need to be JSON-serializable
  - Pattern: Return 409 Conflict when trying to start a process that's already in progress
  - Pattern: Include timestamps (started_at, completed_at) in status objects for debugging and UX
---

## 2026-02-03 - S2-013
- **What was implemented:** Research phase for brand config generation - parallel data gathering from 3 sources
- **Files changed:**
  - `backend/app/services/brand_config.py` (added ResearchContext dataclass and _research_phase method)
  - `backend/app/services/__init__.py` (added ResearchContext export)
- **Learnings:**
  - Pattern: Use `asyncio.gather()` for parallel execution of independent async tasks
  - Pattern: Define inner async functions when you need closure access to outer variables (like `errors` list)
  - Pattern: Check `client.available` property before attempting operations that require external services
  - Pattern: Handle both "task returned None" (service unavailable) and "result.success == False" (API error) cases
  - Pattern: Use `result.fetchall()` with list comprehension for retrieving multiple column values from SQLAlchemy
  - Pattern: Return a dataclass with `has_any_data()` helper to check if any research source succeeded
  - Pattern: Log warnings (not errors) for graceful degradation - research phase continues with partial data
---

## 2026-02-03 - S2-014
- **What was implemented:** Synthesis phase for brand config generation - sequential generation of 10 brand sections via Claude
- **Files changed:**
  - `backend/app/services/brand_config.py` (added SECTION_PROMPTS dict with 10 section-specific prompts, added _synthesis_phase method, added SECTION_TIMEOUT_SECONDS constant, updated GENERATION_STEPS to include ai_prompt_snippet)
- **Learnings:**
  - Pattern: Use `asyncio.wait_for(coro, timeout=N)` for per-call timeouts on async operations
  - Pattern: Catch `TimeoutError` (not `asyncio.TimeoutError`) - ruff UP041 prefers builtin exception
  - Pattern: For sequential LLM generation, accumulate previous sections in prompts to maintain coherence
  - Pattern: Use temperature=0.3 for brand voice generation (slight creativity, but mostly consistent)
  - Pattern: Handle markdown code blocks in LLM JSON responses by stripping fence lines
  - Pattern: Static methods don't need db parameter if they don't use it - pass only what's needed
  - Pattern: Store errors in result dict under `_errors` key for downstream handling
  - Pattern: Use max_tokens=2048 for comprehensive brand section generation
---

## 2026-02-03 - S2-015
- **What was implemented:** Store brand config result method - saves synthesis output to BrandConfig.v2_schema
- **Files changed:**
  - `backend/app/services/brand_config.py` (added `store_brand_config` method, added `get_source_file_ids` helper, imported BrandConfig model)
- **Learnings:**
  - Pattern: Use `dict.pop("_errors", None)` to extract and remove error metadata before storing
  - Pattern: v2_schema structure includes metadata (version, generated_at, source_documents) alongside the 9 generated sections + ai_prompt_snippet
  - Pattern: Use "create or update" pattern - check if record exists with `select().where()`, then update existing or create new
  - Pattern: Store partial success with `_generation_warnings` key when some non-critical sections failed but core sections succeeded
  - Pattern: Mark generation complete even with warnings, but fail if required sections (brand_foundation) are missing
---

## 2026-02-03 - S2-016
- **What was implemented:** API endpoints for triggering and monitoring brand config generation
- **Files changed:**
  - `backend/app/api/v1/brand_config.py` (created - router with POST /generate and GET /status endpoints)
  - `backend/app/schemas/brand_config_generation.py` (created - GenerationStatusResponse schema)
  - `backend/app/api/v1/__init__.py` (registered brand_config router)
  - `backend/app/schemas/__init__.py` (added GenerationStatusResponse export)
- **Learnings:**
  - Pattern: Use `status_code=status.HTTP_202_ACCEPTED` for async operations that start background tasks
  - Pattern: Inject FastAPI `BackgroundTasks` for long-running operations that should return immediately
  - Pattern: Background task receives all dependencies (db, clients) as parameters captured from endpoint scope
  - Pattern: Response schemas for API should be separate from service dataclasses - convert in endpoint
  - Pattern: Routers nested under projects use prefix like `/projects/{project_id}/brand-config`
  - Pattern: Document expected HTTP error responses using FastAPI `responses` parameter in decorator
  - Pattern: Alphabetical import order in `__init__.py` files to pass ruff linting (brand_config before categorize)
---

## 2026-02-03 - S2-017
- **What was implemented:** Pydantic schemas for brand config API - SectionUpdate and RegenerateRequest
- **Files changed:**
  - `backend/app/schemas/brand_config.py` (added SectionUpdate, RegenerateRequest, VALID_SECTION_NAMES)
  - `backend/app/schemas/__init__.py` (added new schema exports including BrandConfigResponse)
- **Learnings:**
  - Pattern: Define valid field values as module-level constants (e.g., `VALID_SECTION_NAMES`) for reuse in validators
  - Pattern: Use `model_config = ConfigDict(json_schema_extra={"examples": [...]})` for complex example structures with multiple variations
  - Pattern: Add helper methods to request schemas (e.g., `get_sections_to_regenerate()`) to centralize business logic
  - Pattern: Mutually exclusive fields (section vs sections) are easier to handle with a helper method than model validators
  - Note: `BrandConfigResponse` already existed but wasn't exported in `__init__.py`
---

## 2026-02-03 - S2-018
- **What was implemented:** Brand config management endpoints for get, update, and regenerate operations
- **Files changed:**
  - `backend/app/api/v1/brand_config.py` (added GET, PATCH, and POST /regenerate endpoints)
  - `backend/app/services/brand_config.py` (added `get_brand_config`, `update_sections`, `regenerate_sections` methods)
  - `backend/tests/api/test_brand_config.py` (created - 12 tests for new endpoints)
- **Learnings:**
  - Pattern: GET endpoint for single resource returns the object directly, 404 if not found
  - Pattern: PATCH endpoint for partial updates - merge sections into existing v2_schema rather than replace
  - Pattern: Regeneration reuses research phase to get fresh context before re-generating sections
  - Pattern: Mock integration clients in tests by overriding FastAPI dependencies with `app.dependency_overrides`
  - Pattern: For regeneration, pass existing sections as context to Claude for coherence
  - Pattern: Service methods raise HTTPException for client-facing errors (404 if brand config doesn't exist yet)
---

## 2026-02-03 - S2-019
- **What was implemented:** Added API tests for brand config generation (start + status) endpoints
- **Files changed:**
  - `backend/tests/api/test_brand_config.py` (added TestStartGeneration and TestGetGenerationStatus test classes, 8 new tests)
- **Learnings:**
  - Pattern: Test 409 Conflict by pre-setting `brand_wizard_state.generation.status = "generating"` on the Project model
  - Pattern: Test generation status transitions (pending, generating, complete, failed) by setting appropriate JSONB state on fixture projects
  - Pattern: Use `async_client_with_mocks` fixture for tests that trigger background tasks (mocks integration clients)
  - Pattern: Use `async_client` fixture for tests that just read state (no external services needed)
  - Pattern: Tests should cover all status states: pending (no state), generating, complete, failed
  - Pattern: Group tests by endpoint into separate test classes for clarity
---

## 2026-02-03 - S2-020
- **What was implemented:** Updated Project schemas to include additional_info and computed brand/file fields
- **Files changed:**
  - `backend/app/schemas/project.py` (added additional_info to ProjectCreate; added brand_config_status, has_brand_config, uploaded_files_count to ProjectResponse)
  - `backend/app/services/project.py` (added to_response and to_response_list methods for computed fields; updated create_project to include additional_info)
  - `backend/app/api/v1/projects.py` (updated all endpoints to use ProjectService.to_response instead of model_validate)
- **Learnings:**
  - Pattern: For computed fields that require DB queries (counts, existence checks), add a `to_response` method in the Service that builds the response schema
  - Pattern: Use `select(func.count()).where(...)` for efficient existence/count checks instead of loading full records
  - Pattern: Extract JSONB nested values safely with `.get("key", {}).get("nested_key")` pattern with defaults
  - Pattern: `to_response_list` helper simplifies list endpoints that need computed fields
---

## 2026-02-03 - S2-021
- **What was implemented:** Updated Project API for new fields and cascade S3 deletion
- **Files changed:**
  - `backend/app/services/project.py` (updated delete_project to accept optional S3Client and delete files from S3 before project deletion)
  - `backend/app/api/v1/projects.py` (added S3Client dependency to delete endpoint, passes S3 client to service)
  - `backend/tests/api/test_projects.py` (added MockS3Client, async_client_with_s3_for_projects fixture, and 3 tests for cascade delete behavior)
- **Learnings:**
  - Pattern: When cascade-deleting related entities that have external storage (S3), delete from external storage BEFORE DB delete since DB cascade happens automatically
  - Pattern: S3 delete errors should be logged but not fail the main operation - the DB cascade will clean up records anyway
  - Pattern: Handle S3NotFoundError gracefully (file may already be deleted) during cascade delete
  - Pattern: Pass optional S3Client to service methods to allow cascade delete while maintaining backward compatibility
  - Pattern: Test fixtures can return tuples like `tuple[AsyncClient, MockS3Client]` to give tests access to mocks for verification
---

## 2026-02-03 - S2-022
- **What was implemented:** Updated project API tests for new response fields (additional_info, brand_config_status, has_brand_config, uploaded_files_count)
- **Files changed:**
  - `backend/tests/api/test_projects.py` (added 7 new tests in TestCreateProject and new TestProjectResponseFields class)
- **Learnings:**
  - Pattern: Test computed response fields by creating projects in specific states and verifying the computed values (e.g., files_count=0 for new project, files_count=2 after uploads)
  - Pattern: Group computed field tests in a dedicated test class (e.g., TestProjectResponseFields) to keep them organized
  - Pattern: Reuse existing fixtures like `async_client_with_s3_for_projects` to test cross-cutting concerns (file uploads affecting project response)
  - Note: Cascade delete tests (files deleted when project deleted) were already implemented in S2-021
---

## 2026-02-03 - S2-023
- **What was implemented:** FileUpload React component with drag-and-drop support
- **Files changed:**
  - `frontend/src/components/FileUpload.tsx` (created - full file upload component)
- **Learnings:**
  - Pattern: Use native drag-drop API instead of react-dropzone to avoid adding dependencies; use `dragCounter` ref to handle nested element drag events correctly
  - Pattern: Validate files by both MIME type and extension as fallback (MIME types can be unreliable across browsers/OS)
  - Pattern: Export validation constants (`MAX_FILE_SIZE_BYTES`, `ALLOWED_EXTENSIONS`, `ALLOWED_MIME_TYPES`) so consumers can access them for consistent validation messaging
  - Pattern: Component accepts `uploadedFiles` prop for controlled file list, allowing parent to manage upload state and progress
  - Pattern: Use `UploadedFile` interface with `status: 'pending' | 'uploading' | 'complete' | 'error'` for flexible progress tracking
  - Pattern: Tropical oasis styling: `palm-*` colors for success states, `coral-*` for errors, `cream-*` for neutral backgrounds
  - Pattern: Reset file input value after selection (`fileInputRef.current.value = ''`) to allow re-selecting the same file
---

## 2026-02-03 - S2-024
- **What was implemented:** useProjectFiles hook with TanStack Query for file operations
- **Files changed:**
  - `frontend/src/hooks/useProjectFiles.ts` (created - useProjectFiles, useUploadFile, useDeleteFile hooks)
- **Learnings:**
  - Pattern: File upload mutations use native `fetch` with `FormData` (not the JSON apiClient) since multipart/form-data requires browser to set Content-Type with boundary
  - Pattern: Query keys for nested resources follow `['parent', parentId, 'child']` convention (e.g., `['projects', projectId, 'files']`)
  - Pattern: Hook factory functions like `useUploadFile(projectId)` take parent ID as param so mutations can invalidate the correct query key
  - Pattern: Don't set Content-Type header for FormData uploads - browser handles it automatically with correct boundary
---

## 2026-02-03 - S2-025
- **What was implemented:** Multi-step wizard for project creation with file upload and brand config generation
- **Files changed:**
  - `frontend/src/components/ui/Textarea.tsx` (created - Textarea component matching Input pattern)
  - `frontend/src/components/ui/index.ts` (added Textarea export)
  - `frontend/src/components/ProjectForm.tsx` (added additional_info field, file upload integration, formId prop)
  - `frontend/src/hooks/useBrandConfigGeneration.ts` (created - hooks for brand config generation status and polling)
  - `frontend/src/hooks/useProjectFiles.ts` (added uploadFileToProject standalone function)
  - `frontend/src/app/projects/new/page.tsx` (converted to 2-step wizard: project details → generation progress)
- **Learnings:**
  - Pattern: Use `formId` prop + HTML `form` attribute on external buttons to submit forms from outside their DOM hierarchy
  - Pattern: For wizard flows with file uploads, use standalone upload functions instead of hooks when the parent ID changes mid-flow (hooks have stale closures)
  - Pattern: TanStack Query's refetchInterval can be a function that returns `false` to stop polling or a number to continue
  - Pattern: Use `&ldquo;` and `&rdquo;` for curly quotes in JSX to satisfy react/no-unescaped-entities rule
  - Pattern: Generation progress checklist uses steps_completed vs array index to determine isComplete, isCurrent states
---

## 2026-02-03 - S2-026
- **What was implemented:** GenerationProgress component extracted from page with all 13 generation steps
- **Files changed:**
  - `frontend/src/components/GenerationProgress.tsx` (created - reusable generation progress component)
  - `frontend/src/app/projects/new/page.tsx` (refactored to use GenerationProgress component)
- **Learnings:**
  - Pattern: Backend only tracks synthesis steps (10 steps), but UI shows all 13 steps (3 research + 10 synthesis)
  - Pattern: Research phase steps (perplexity_research, crawling, processing_docs) are inferred from generation state before synthesis begins
  - Pattern: Extract complex UI logic into dedicated components for reusability (GenerationProgress can be reused elsewhere)
  - Pattern: Use callback props (onComplete, onBack, onGoToProject) to let parent control navigation while component handles display
  - Pattern: useEffect with dependency on generation.isComplete triggers onComplete callback for navigation
---

## 2026-02-03 - S2-027
- **What was implemented:** Added retry functionality to generation completion screen for handling generation failures
- **Files changed:**
  - `frontend/src/components/GenerationProgress.tsx` (added onRetry prop and Retry button in failure state)
  - `frontend/src/app/projects/new/page.tsx` (added handleRetry function and passed onRetry prop)
- **Learnings:**
  - Pattern: For retry functionality, pass an async callback prop (onRetry) from parent rather than calling the hook directly in the component
  - Pattern: Use local state (isRetrying) to manage button loading state while async retry is in progress
  - Pattern: Existing implementation already met most acceptance criteria - generation completion screen had checkmark, message, and navigation
---

## 2026-02-03 - S2-028
- **What was implemented:** useBrandConfig hook for brand config operations (fetch, update, regenerate)
- **Files changed:**
  - `frontend/src/hooks/useBrandConfig.ts` (created - useBrandConfig, useUpdateBrandConfig, useRegenerateBrandConfig, useBrandConfigWithStatus hooks)
- **Learnings:**
  - Pattern: Separate config fetch hooks from generation/status hooks for cleaner organization (useBrandConfig.ts vs useBrandConfigGeneration.ts)
  - Pattern: Re-export related hooks for consumer convenience (`export { useBrandConfigStatus } from './useBrandConfigGeneration'`)
  - Pattern: For mutations with optional input, use `RegenerateInput | undefined` not `RegenerateInput | void` to avoid TypeScript issues with void vs undefined
  - Pattern: Combine query keys factory from related hook files to coordinate cache invalidation across concerns
  - Pattern: Add `useBrandConfigWithStatus()` helper that combines query + mutations for components that need both
---

## 2026-02-03 - S2-029
- **What was implemented:** BrandConfigView page - container page for viewing and editing brand configuration
- **Files changed:**
  - `frontend/src/app/projects/[id]/brand-config/page.tsx` (created - brand config view page with header, back link, regenerate button)
- **Learnings:**
  - Pattern: Next.js App Router dynamic routes use `[id]` folders and `useParams()` hook to access params
  - Pattern: Container pages can be simple shells that establish layout and header - content sections added in subsequent stories
  - Pattern: Reuse loading skeleton and not-found state patterns from project detail page for consistency
  - Pattern: Route is automatically available via folder structure - no manual route registration needed in App Router
  - Pattern: Handle both project-not-found and brand-config-not-found states with informative messages
---

