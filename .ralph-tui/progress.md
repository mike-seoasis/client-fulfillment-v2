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

