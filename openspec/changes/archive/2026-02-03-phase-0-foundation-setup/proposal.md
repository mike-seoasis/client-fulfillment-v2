## Why

The current codebase was brute-forced in ~1 day using Ralph loop. Services and API routes are tangled and broken in unknown ways. The frontend uses Vite/React but the V2 plan specifies Next.js 14. We need a clean foundation before building vertical slices—keeping only the solid pieces (models, schemas, config, integrations) and replacing everything else.

## What Changes

**Backend:**
- **BREAKING**: Delete all services (`backend/app/services/`)
- **BREAKING**: Delete all API endpoints (`backend/app/api/v1/endpoints/`)
- **BREAKING**: Delete repositories (`backend/app/repositories/`)
- Migrate from pip to uv package manager
- Extract duplicated CircuitBreaker pattern to shared module (`core/circuit_breaker.py`)
- Refactor 11 integration clients to use shared CircuitBreaker
- Create Backend Dockerfile for Railway deployment
- Slim down `main.py` to app setup + health checks only

**Frontend:**
- **BREAKING**: Delete entire Vite/React frontend
- Create new Next.js 14 project with App Router
- Configure TanStack Query v5, Zustand, Tailwind, Vitest, Playwright

**DevOps:**
- Create `docker-compose.yml` for local development (PostgreSQL, Redis, backend, frontend)
- Update GitHub Actions CI for uv and Next.js
- Add v2-rebuild branch triggers

## Capabilities

### New Capabilities
- `circuit-breaker`: Shared fault-tolerance pattern for all external API integrations
- `docker-dev-env`: Local development environment with all services containerized

### Modified Capabilities
- None (this is foundation cleanup, not feature changes)

## Impact

**Code:**
- ~40 service files deleted (rebuild in later phases)
- ~30 endpoint files deleted (rebuild in later phases)
- ~6 repository files deleted
- 11 integration files refactored (CircuitBreaker extraction)
- `main.py` significantly simplified

**APIs:**
- All API endpoints temporarily unavailable (only `/health` remains)
- Will be rebuilt slice-by-slice in Phases 1-9

**Dependencies:**
- pip → uv migration
- Vite → Next.js 14 migration
- New dev dependencies: Playwright, Vitest

**Systems:**
- Railway deployment updated for new Dockerfile
- CI/CD updated for new toolchain
