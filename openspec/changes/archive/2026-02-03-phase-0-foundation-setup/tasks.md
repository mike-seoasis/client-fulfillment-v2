## 1. Branch Setup

- [x] 1.1 Create v2-rebuild branch from main
- [x] 1.2 Push branch to origin

## 2. Backend Cleanup

- [x] 2.1 Delete `backend/app/services/` directory
- [x] 2.2 Delete `backend/app/api/v1/endpoints/` directory
- [x] 2.3 Delete `backend/app/repositories/` directory
- [x] 2.4 Delete `backend/app/utils/` directory
- [x] 2.5 Delete `backend/app/clients/` directory
- [x] 2.6 Update `backend/app/main.py` to remove deleted router imports
- [x] 2.7 Delete or update tests that reference deleted code

## 3. CircuitBreaker Extraction

- [x] 3.1 Create `backend/app/core/circuit_breaker.py` with CircuitState, CircuitBreakerConfig, and CircuitBreaker
- [x] 3.2 Add `name` parameter to CircuitBreaker for logging context
- [x] 3.3 Update `backend/app/core/redis.py` to use shared CircuitBreaker
- [x] 3.4 Update `backend/app/integrations/dataforseo.py` to use shared CircuitBreaker
- [x] 3.5 Update `backend/app/integrations/pop.py` to use shared CircuitBreaker
- [x] 3.6 Update `backend/app/integrations/claude.py` to use shared CircuitBreaker
- [x] 3.7 Update `backend/app/integrations/perplexity.py` to use shared CircuitBreaker
- [x] 3.8 Update `backend/app/integrations/google_nlp.py` to use shared CircuitBreaker
- [x] 3.9 Update `backend/app/integrations/keywords_everywhere.py` to use shared CircuitBreaker
- [x] 3.10 Update `backend/app/integrations/crawl4ai.py` to use shared CircuitBreaker
- [x] 3.11 Update `backend/app/integrations/email.py` to use shared CircuitBreaker
- [x] 3.12 Update `backend/app/integrations/webhook.py` to use shared CircuitBreaker
- [x] 3.13 Create `backend/tests/core/test_circuit_breaker.py` with unit tests

## 4. uv Migration

- [x] 4.1 Install uv if not present
- [x] 4.2 Run `uv lock` in backend directory to create uv.lock
- [x] 4.3 Update pyproject.toml build system for uv compatibility
- [x] 4.4 Verify `uv run pytest` works

## 5. Backend Dockerfile

- [x] 5.1 Create `backend/Dockerfile` with multi-stage build
- [x] 5.2 Use python:3.11-slim base image
- [x] 5.3 Install dependencies with uv
- [x] 5.4 Configure non-root user
- [x] 5.5 Set up PORT environment variable for Railway
- [x] 5.6 Verify Docker build succeeds

## 6. Frontend Replacement

- [x] 6.1 Delete existing `frontend/` directory
- [x] 6.2 Create new Next.js 14 project with `create-next-app`
- [x] 6.3 Install TanStack Query v5
- [x] 6.4 Install Zustand
- [x] 6.5 Configure Tailwind with warm color palette
- [x] 6.6 Install and configure Vitest
- [x] 6.7 Install and configure Playwright
- [x] 6.8 Verify `npm run build` succeeds

## 7. Docker Compose

- [x] 7.1 Create `docker-compose.yml` at project root
- [x] 7.2 Add PostgreSQL 15 service with health check
- [x] 7.3 Add Redis 7 service with health check
- [x] 7.4 Add backend service with database dependencies
- [x] 7.5 Add frontend service (optional, can be commented)
- [x] 7.6 Configure named volumes for data persistence
- [x] 7.7 Verify `docker-compose up -d` starts all services

## 8. CI/CD Updates

- [x] 8.1 Update `.github/workflows/ci.yml` to trigger on v2-rebuild branch
- [x] 8.2 Update CI to use uv for Python dependency installation
- [x] 8.3 Update CI frontend commands for Next.js
- [x] 8.4 Add Docker build verification step to CI

## 9. Verification

- [x] 9.1 Run `uv run ruff check app` — passes
- [x] 9.2 Run `uv run ruff format --check app` — passes
- [x] 9.3 Run `uv run mypy app` — passes
- [x] 9.4 Run `uv run pytest tests/core/ tests/models/` — passes
- [x] 9.5 Run `docker build -t backend-test ./backend` — succeeds
- [x] 9.6 Run `docker-compose up -d` — all services healthy
- [x] 9.7 Verify `/health` endpoint responds with 200
- [x] 9.8 Run `pre-commit run --all-files` — passes

## 10. Documentation

- [x] 10.1 Update V2_REBUILD_PLAN.md — mark Phase 0 complete
- [x] 10.2 Add session log entry with completion date
- [x] 10.3 Commit all changes with `feat(phase-0): Foundation setup complete`
- [x] 10.4 Push v2-rebuild branch to origin
