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

