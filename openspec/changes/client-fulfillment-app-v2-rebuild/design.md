# Design: Client Fulfillment App V2 Rebuild

## Context

The existing Client Fulfillment App is a 7-phase SEO content generation pipeline deployed on Railway. It works but has accumulated significant technical debt:

- **Monolithic backend**: 3,217-line main.py with all 40+ endpoints
- **No separation of concerns**: API routes, business logic, and data access mixed together
- **Template-based frontend**: 11 HTML files with Tailwind, no component reuse
- **Zero test coverage**: Manual testing only
- **No NLP optimization**: Content generated without competitor analysis or scoring

The rebuild creates a maintainable, testable, and more capable platform while preserving all existing functionality.

**Stakeholders**: Internal ops team using the tool daily for client onboarding.

**Constraints**:
- Must maintain Railway deployment compatibility
- Must support existing API integrations (Anthropic, Keywords Everywhere, AlsoAsked)
- Budget-conscious: prefer open-source or low-cost solutions

## Goals / Non-Goals

**Goals:**
- Modular, testable architecture with clear separation of concerns
- NLP-powered content optimization with scoring and recommendations
- Modern React frontend with consistent design system
- 80%+ unit test coverage on services
- Real-time progress updates via WebSocket
- Comprehensive API documentation via OpenAPI

**Non-Goals:**
- User authentication / multi-tenant support (single-user tool)
- Mobile app or native clients
- Real-time collaboration features
- Custom CMS or page builder
- Shopify app store listing

## Decisions

### Decision 1: Layered Backend Architecture

**Choice**: API → Services → Repositories → Database

**Rationale**: The monolithic main.py mixes concerns. A layered architecture:
- Makes each layer independently testable
- Allows swapping implementations (e.g., different database)
- Follows FastAPI best practices

**Alternatives Considered**:
- **Keep monolithic, just refactor**: Rejected. Still hard to test, doesn't solve growth issues.
- **Microservices**: Rejected. Overkill for single-user tool, adds operational complexity.

**Structure**:
```
app/
├── api/v1/           # FastAPI routers (HTTP handling only)
├── services/         # Business logic (all computation here)
├── repositories/     # Data access (SQLAlchemy queries)
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic validation schemas
├── integrations/     # External API clients
└── workers/          # Background task processors
```

### Decision 2: React + TypeScript Frontend

**Choice**: React 18 with TypeScript, Vite build, Tailwind CSS

**Rationale**:
- Component-based architecture enables reuse across phases
- TypeScript catches errors at compile time
- Vite provides fast HMR for development
- Tailwind already familiar from existing templates

**Alternatives Considered**:
- **Keep HTML templates, add Alpine.js**: Rejected. Still no component reuse, harder to maintain.
- **Next.js**: Rejected. SSR not needed for internal tool, adds complexity.
- **Vue or Svelte**: Rejected. React has larger ecosystem and more resources.

### Decision 3: DataForSEO for SERP Data

**Choice**: DataForSEO API for competitor SERP scraping

**Rationale**:
- Reliable, structured SERP data
- Includes PAA, featured snippets, organic results
- Cost-effective at $0.002/search
- 24-hour caching reduces API calls

**Alternatives Considered**:
- **SerpAPI**: Similar quality but higher cost.
- **Custom scraping**: Rejected. Unreliable, requires proxy rotation, breaks often.
- **Brightdata/Oxylabs**: Rejected. Expensive, overkill for volume needed.

### Decision 4: Google Cloud NLP for Entity Extraction

**Choice**: Google Cloud Natural Language API

**Rationale**:
- Industry-standard entity recognition
- Identifies entities competitors mention
- Pay-per-use pricing fits variable workload
- Well-documented, reliable

**Alternatives Considered**:
- **spaCy locally**: Rejected. Adds deployment complexity, less accurate for SEO entities.
- **Claude for entity extraction**: Rejected. More expensive, slower, not specialized.
- **AWS Comprehend**: Similar capability, but GCP NLP has better entity linking.

### Decision 5: Redis for Caching

**Choice**: Redis for SERP and keyword volume caching

**Rationale**:
- SERP data is expensive to fetch, changes slowly (24h cache)
- Keyword volumes change rarely (30d cache)
- Redis is simple, fast, Railway-supported

**Cache Strategy**:
```
serp:{keyword}:{location}     → 24h TTL
keyword_volume:{keyword}      → 30d TTL
competitor_analysis:{keyword} → 7d TTL
project_status:{id}           → 5m TTL
```

**Alternatives Considered**:
- **PostgreSQL as cache**: Rejected. Works but slower, less suited for TTL patterns.
- **In-memory dict**: Rejected. Lost on restart, no TTL management.

### Decision 6: WebSocket for Real-Time Progress

**Choice**: FastAPI WebSocket endpoints for phase progress updates

**Rationale**:
- Phases can take minutes; polling is wasteful
- WebSocket provides instant status updates
- FastAPI has built-in WebSocket support

**Pattern**:
```
WS /api/v1/projects/{id}/ws
→ Receives: {"type": "progress", "phase": "crawl", "progress": 45, "message": "..."}
```

**Alternatives Considered**:
- **Server-Sent Events (SSE)**: Simpler but one-directional, WebSocket more flexible.
- **Polling**: Rejected. Wasteful, delays UX.

### Decision 7: Alembic for Database Migrations

**Choice**: Alembic with auto-generation from SQLAlchemy models

**Rationale**:
- Standard tool for SQLAlchemy migrations
- Auto-generates migrations from model changes
- Supports rollback for safe deployments

**Alternatives Considered**:
- **Raw SQL migrations**: Rejected. Error-prone, no auto-generation.
- **Django-style migrations**: Not applicable to FastAPI/SQLAlchemy.

## Risks / Trade-offs

**[Complete rewrite risk]** → Mitigate with parallel deployment. Keep V1 running until V2 is validated. Implement feature flags for gradual rollout.

**[DataForSEO API cost at scale]** → Mitigate with aggressive caching (24h for SERP). Estimate: ~$10/month for typical usage (5000 searches/month).

**[Google Cloud NLP cost uncertainty]** → Mitigate by only extracting entities on-demand (during NLP analysis), not automatically. Estimate: ~$5/month.

**[Redis as single point of failure]** → Mitigate by treating cache as optional. Application should work (slower) if Redis unavailable. Implement circuit breaker pattern.

**[Learning curve for React]** → Frontend is internal tool, UX polish can iterate. Use shadcn/ui components to accelerate development.

**[Data migration complexity]** → Mitigate by designing V2 schema to accept V1 data with minimal transformation. Create one-time migration script.

## Migration Plan

### Phase 1: Parallel Development
1. Create new repository `client-fulfillment-app-v2`
2. Set up CI/CD pipeline with GitHub Actions
3. Deploy V2 to Railway staging environment
4. Keep V1 production running

### Phase 2: Backend First
1. Implement core services (project, crawl, keyword)
2. Write unit tests as services are built
3. Validate API contract matches OpenAPI spec

### Phase 3: Frontend
1. Build React app with mock data
2. Connect to V2 backend on staging
3. Implement all phase UIs

### Phase 4: NLP Integration
1. Integrate DataForSEO client
2. Integrate Google Cloud NLP client
3. Build content optimization UI

### Phase 5: Migration
1. Export V1 production data
2. Run migration script to V2 schema
3. Validate data integrity

### Phase 6: Cutover
1. DNS switch to V2 production
2. Monitor for 48 hours
3. Decommission V1 after validation

### Rollback Strategy
- Keep V1 deployment warm for 2 weeks post-cutover
- Database snapshots before migration
- DNS can revert to V1 within minutes if critical issues

## Open Questions

1. **SERP API selection**: DataForSEO vs SerpAPI final decision pending cost comparison at expected volume.

2. **Entity extraction scope**: Should we extract entities from all competitor pages or just top 3? Cost/quality trade-off.

3. **Content scoring weights**: Initial weights proposed (word count 20%, semantic 20%, readability 15%, etc.) but may need tuning based on real-world results.

4. **Export formats**: Current V1 only exports JSON. Should V2 add CSV and Google Sheets integration?
