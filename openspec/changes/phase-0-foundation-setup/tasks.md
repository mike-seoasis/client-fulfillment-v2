## 1. Branch Setup

- [ ] 1.1 Create v2-rebuild branch from main
- [ ] 1.2 Push branch to origin

## 2. Backend Cleanup

- [ ] 2.1 Delete `backend/app/services/` directory
- [ ] 2.2 Delete `backend/app/api/v1/endpoints/` directory
- [ ] 2.3 Delete `backend/app/repositories/` directory
- [ ] 2.4 Delete `backend/app/utils/` directory
- [ ] 2.5 Delete `backend/app/clients/` directory
- [ ] 2.6 Update `backend/app/main.py` to remove deleted router imports
- [ ] 2.7 Delete or update tests that reference deleted code

## 3. CircuitBreaker Extraction

- [ ] 3.1 Create `backend/app/core/circuit_breaker.py` with CircuitState, CircuitBreakerConfig, and CircuitBreaker
- [ ] 3.2 Add `name` parameter to CircuitBreaker for logging context
- [ ] 3.3 Update `backend/app/core/redis.py` to use shared CircuitBreaker
- [ ] 3.4 Update `backend/app/integrations/dataforseo.py` to use shared CircuitBreaker
- [ ] 3.5 Update `backend/app/integrations/pop.py` to use shared CircuitBreaker
- [ ] 3.6 Update `backend/app/integrations/claude.py` to use shared CircuitBreaker
- [ ] 3.7 Update `backend/app/integrations/perplexity.py` to use shared CircuitBreaker
- [ ] 3.8 Update `backend/app/integrations/google_nlp.py` to use shared CircuitBreaker
- [ ] 3.9 Update `backend/app/integrations/keywords_everywhere.py` to use shared CircuitBreaker
- [ ] 3.10 Update `backend/app/integrations/crawl4ai.py` to use shared CircuitBreaker
- [ ] 3.11 Update `backend/app/integrations/email.py` to use shared CircuitBreaker
- [ ] 3.12 Update `backend/app/integrations/webhook.py` to use shared CircuitBreaker
- [ ] 3.13 Create `backend/tests/core/test_circuit_breaker.py` with unit tests

## 4. uv Migration

- [ ] 4.1 Install uv if not present
- [ ] 4.2 Run `uv lock` in backend directory to create uv.lock
- [ ] 4.3 Update pyproject.toml build system for uv compatibility
- [ ] 4.4 Verify `uv run pytest` works

## 5. Backend Dockerfile

- [ ] 5.1 Create `backend/Dockerfile` with multi-stage build
- [ ] 5.2 Use python:3.11-slim base image
- [ ] 5.3 Install dependencies with uv
- [ ] 5.4 Configure non-root user
- [ ] 5.5 Set up PORT environment variable for Railway
- [ ] 5.6 Verify Docker build succeeds

## 6. Frontend Replacement

- [ ] 6.1 Delete existing `frontend/` directory
- [ ] 6.2 Create new Next.js 14 project with `create-next-app`
- [ ] 6.3 Install TanStack Query v5
- [ ] 6.4 Install Zustand
- [ ] 6.5 Configure Tailwind with warm color palette
- [ ] 6.6 Install and configure Vitest
- [ ] 6.7 Install and configure Playwright
- [ ] 6.8 Verify `npm run build` succeeds

## 7. Docker Compose

- [ ] 7.1 Create `docker-compose.yml` at project root
- [ ] 7.2 Add PostgreSQL 15 service with health check
- [ ] 7.3 Add Redis 7 service with health check
- [ ] 7.4 Add backend service with database dependencies
- [ ] 7.5 Add frontend service (optional, can be commented)
- [ ] 7.6 Configure named volumes for data persistence
- [ ] 7.7 Verify `docker-compose up -d` starts all services

## 8. CI/CD Updates

- [ ] 8.1 Update `.github/workflows/ci.yml` to trigger on v2-rebuild branch
- [ ] 8.2 Update CI to use uv for Python dependency installation
- [ ] 8.3 Update CI frontend commands for Next.js
- [ ] 8.4 Add Docker build verification step to CI

## 9. Verification

- [ ] 9.1 Run `uv run ruff check app` — passes
- [ ] 9.2 Run `uv run ruff format --check app` — passes
- [ ] 9.3 Run `uv run mypy app` — passes
- [ ] 9.4 Run `uv run pytest tests/core/ tests/models/` — passes
- [ ] 9.5 Run `docker build -t backend-test ./backend` — succeeds
- [ ] 9.6 Run `docker-compose up -d` — all services healthy
- [ ] 9.7 Verify `/health` endpoint responds with 200
- [ ] 9.8 Run `pre-commit run --all-files` — passes

## 10. Documentation

- [ ] 10.1 Update V2_REBUILD_PLAN.md — mark Phase 0 complete
- [ ] 10.2 Add session log entry with completion date
- [ ] 10.3 Commit all changes with `feat(phase-0): Foundation setup complete`
- [ ] 10.4 Push v2-rebuild branch to origin
