## Context

The V2 rebuild uses a vertical slice approach—each phase adds a complete feature from database to UI. Phase 0 establishes the foundation before any slices are built.

**Current state:**
- Backend: FastAPI with SQLAlchemy 2.0, 14 models, 25+ schemas, 12 integrations
- Frontend: Vite/React (needs replacement with Next.js 14)
- Tooling: pip, Ruff, mypy, pre-commit hooks, GitHub Actions CI
- Deployment: Railway (production only, no staging)

**Constraints:**
- Must preserve database migrations (15 Alembic versions)
- Integration clients have working API connections (POP, Claude, etc.)
- CircuitBreaker is duplicated ~120 lines across 11 files
- No downtime acceptable for production (but API is internal-only)

## Goals / Non-Goals

**Goals:**
- Clean foundation with only solid, tested code
- uv package manager for faster installs
- Shared CircuitBreaker module (DRY)
- Next.js 14 frontend ready for slice-by-slice development
- Local dev environment via docker-compose
- CI/CD ready for v2-rebuild branch

**Non-Goals:**
- Rebuilding any API endpoints (Phase 1+)
- Rebuilding any services (Phase 1+)
- Frontend UI components (Phase 1+)
- Production deployment (staging first)
- Database schema changes (models unchanged)

## Decisions

### 1. Branch Strategy
**Decision:** Create `v2-rebuild` branch, keep `main` untouched.

**Alternatives considered:**
- Work directly on main → Rejected: Too risky, breaks production
- Create `staging` branch → Rejected: Plan specifies v2-rebuild first

**Rationale:** Isolates destructive changes. Can merge to staging then main when ready.

### 2. Package Manager Migration
**Decision:** Migrate to uv, create `uv.lock`, update CI.

**Alternatives considered:**
- Keep pip → Rejected: Plan explicitly specifies uv
- Use Poetry → Rejected: uv is faster, simpler, plan specifies it

**Rationale:** uv is 10-100x faster than pip. Modern tooling aligns with tech stack decisions.

### 3. CircuitBreaker Extraction
**Decision:** Create `backend/app/core/circuit_breaker.py` with generic implementation. Add `name` parameter for logging context.

**Alternatives considered:**
- Keep duplicated code → Rejected: ~1,320 lines of duplication, maintenance nightmare
- Use third-party library (e.g., pybreaker) → Rejected: Current implementation works, adds dependency

**Rationale:** Single source of truth. Each integration imports and instantiates with its name.

### 4. Frontend Replacement
**Decision:** Delete Vite frontend entirely, scaffold fresh Next.js 14 with `create-next-app`.

**Alternatives considered:**
- Migrate incrementally → Rejected: Vite→Next.js is too different, clean start faster
- Keep Vite, add Next.js later → Rejected: Plan specifies Next.js 14

**Rationale:** Next.js 14 with App Router provides SSR, better structure for slice-based development.

### 5. Backend Dockerfile
**Decision:** Multi-stage build with python:3.11-slim, uv for deps, non-root user.

**Alternatives considered:**
- Single-stage build → Rejected: Larger image, slower deploys
- Alpine base → Rejected: Compatibility issues with some Python packages

**Rationale:** Slim image + multi-stage = fast builds, small images. Non-root for security.

### 6. What to Delete vs Keep

**Keep:**
| Directory | Reason |
|-----------|--------|
| `app/models/` | 14 solid database models |
| `app/schemas/` | 25+ Pydantic schemas |
| `app/core/config.py` | Settings management |
| `app/core/database.py` | Async DB layer |
| `app/core/logging.py` | JSON structured logging |
| `app/core/redis.py` | Redis client (refactor CB) |
| `app/integrations/` | API clients (refactor CB) |
| `alembic/` | 15 migration versions |

**Delete:**
| Directory | Reason |
|-----------|--------|
| `app/services/` | Too tangled, rebuild per slice |
| `app/api/v1/endpoints/` | Too tangled, rebuild per slice |
| `app/repositories/` | Part of tangled layer |
| `app/utils/` | Most tied to deleted code |
| `app/clients/` | WebSocket client, review later |

## Risks / Trade-offs

**[Risk] Deleting working code** → Mitigation: Code stays in git history. Can reference old implementations when rebuilding.

**[Risk] Breaking tests that depend on deleted code** → Mitigation: Only run `tests/core/` and `tests/models/` initially. Delete or skip service/endpoint tests.

**[Risk] uv migration issues** → Mitigation: uv is compatible with pyproject.toml. Fallback to pip if blocking issues.

**[Risk] Next.js 14 learning curve** → Mitigation: App Router is well-documented. Start simple, add complexity per slice.

**[Risk] CircuitBreaker refactor breaks integrations** → Mitigation: Interface stays identical. Only import path changes.

## Migration Plan

1. **Create branch:** `git checkout -b v2-rebuild`
2. **Backend cleanup:** Delete services, endpoints, repositories
3. **CircuitBreaker:** Extract to shared module, update imports
4. **uv migration:** Create lock file, update CI
5. **Backend Dockerfile:** Create and test build
6. **Frontend replacement:** Delete old, scaffold new
7. **docker-compose:** Create for local dev
8. **CI updates:** Add v2-rebuild triggers, uv commands
9. **Verify:** All checks pass, health endpoint works
10. **Push:** `git push -u origin v2-rebuild`

**Rollback:** Branch isolation means main is unaffected. If Phase 0 fails, delete branch and restart.

## Open Questions

1. **Railway staging setup:** Manual process—document steps after completion
2. **Test cleanup:** Which tests to keep vs delete? Need to audit after code deletion
3. **Schemas cleanup:** Some schemas reference deleted services—may need pruning
