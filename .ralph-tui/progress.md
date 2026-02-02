# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### External API Configuration Pattern
When adding a new external API integration to `backend/app/core/config.py`:
1. **API credentials**: `{prefix}_api_key` or `{prefix}_api_login`/`{prefix}_api_password` (str | None, default=None)
2. **Base URL**: `{prefix}_api_url` (str with default value)
3. **Polling/timeout settings**: `{prefix}_task_poll_interval`, `{prefix}_task_timeout` for async task-based APIs
4. **Circuit breaker**: `{prefix}_circuit_failure_threshold` (int, default=5) and `{prefix}_circuit_recovery_timeout` (float, default=60.0)
5. All fields use pydantic `Field()` with `description` parameter

### Alembic Migration Pattern
When creating new database tables in `backend/alembic/versions/`:
1. **File naming**: `{nnnn}_{descriptive_name}.py` where nnnn is zero-padded sequence number
2. **Revision chain**: Set `revision = "{nnnn}"` and `down_revision = "{previous_nnnn}"`
3. **UUID primary keys**: Use `postgresql.UUID(as_uuid=False)` with `server_default=sa.text("gen_random_uuid()")`
4. **JSONB columns**: Use `postgresql.JSONB(astext_type=sa.Text())` with appropriate defaults (`'[]'::jsonb` for arrays, `'{}'::jsonb` for objects)
5. **Timestamps**: `created_at` and `updated_at` with `server_default=sa.text("now()")` and `timezone=True`
6. **Foreign keys**: Use `sa.ForeignKeyConstraint()` with `ondelete="CASCADE"` and named constraints like `fk_{table}_{column}`
7. **Indexes**: Create indexes for foreign keys and commonly queried columns using `op.f("ix_{table}_{column}")`
8. **Verify**: Run `alembic heads` and `alembic history` to verify migration chain

---

## 2026-02-02 - US-001
- Added POP API configuration settings to `backend/app/core/config.py`:
  - `pop_api_key`: API key for PageOptimizer Pro
  - `pop_api_url`: Base URL (default: https://api.pageoptimizer.pro)
  - `pop_task_poll_interval`: Polling interval for async tasks (default: 2.0s)
  - `pop_task_timeout`: Maximum wait time for task completion (default: 300s)
  - `pop_circuit_failure_threshold`: Circuit breaker threshold (default: 5)
  - `pop_circuit_recovery_timeout`: Circuit recovery timeout (default: 60s)
- Created `backend/.env.example` with documented environment variables including POP_API_KEY
- Files changed:
  - `backend/app/core/config.py` - Added POP API settings
  - `backend/.env.example` - New file with all backend env vars documented
- **Learnings:**
  - Backend config lives in `backend/app/core/config.py`, not `app/core/config.py`
  - No `.env.example` existed for backend previously; created one with all documented API keys
  - Pattern: All external APIs follow same structure with circuit breaker settings
  - ruff is available globally but mypy needs to be installed in venv (dev dependency)
---

## 2026-02-02 - US-002
- Created database migrations for POP content data persistence:
  - `0012_create_content_briefs_table.py`: Stores content brief data from POP API
  - `0013_create_content_scores_table.py`: Stores content scoring results from POP API
- **content_briefs table columns**: id, page_id (FK), keyword, pop_task_id, word_count_target/min/max, heading_targets (JSONB), keyword_targets (JSONB), lsi_terms (JSONB), entities (JSONB), related_questions (JSONB), related_searches (JSONB), competitors (JSONB), page_score_target, raw_response (JSONB), created_at, updated_at
- **content_scores table columns**: id, page_id (FK), pop_task_id, page_score, passed, keyword_analysis (JSONB), lsi_coverage (JSONB), word_count_current, heading_analysis (JSONB), recommendations (JSONB), fallback_used, raw_response (JSONB), scored_at, created_at
- Files changed:
  - `backend/alembic/versions/0012_create_content_briefs_table.py` - New migration
  - `backend/alembic/versions/0013_create_content_scores_table.py` - New migration
- **Learnings:**
  - Running `alembic upgrade head` requires DATABASE_URL in environment (no mock/test mode)
  - Can verify migrations without database by: importing Python module, running `alembic heads`, and `alembic history`
  - Use `DATABASE_URL="postgresql://user:pass@localhost:5432/db"` prefix for alembic commands when env var not set
  - Both tables have FK to `crawled_pages.id` with CASCADE delete
---

