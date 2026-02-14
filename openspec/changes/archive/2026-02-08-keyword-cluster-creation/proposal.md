## Why

The onboarding workflow optimizes existing collection pages, but clients also need to build **new** collection pages around keyword topics they don't yet have. This is the second core workflow (Phase 8). A user enters a seed keyword, the system suggests related collection pages to build as a cluster, and then the existing shared pipeline (content generation, review, export) handles the rest. Without this, the tool only serves half the content strategy — optimization of what exists, not creation of what's missing.

## What Changes

- Add a 5-stage keyword cluster creation pipeline:
  1. **LLM candidate generation** — Claude expands a seed keyword into 15-20 collection page suggestions using an 11-strategy prompt (demographic, attribute, price, use-case, comparison, seasonal, material, experience level, problem/solution, terrain, values/lifestyle) with brand config context
  2. **DataForSEO volume enrichment** — batch lookup validates suggestions with real search volume, CPC, and competition data
  3. **LLM filtering + role assignment** — Claude filters low-quality candidates, assigns parent/child roles, generates URL slugs
  4. **User approval** — review, edit, approve/reject suggestions with volume data visible
  5. **POP content briefs** — approved keywords flow into existing content pipeline (POP briefs → content generation → review → export)
- Add `KeywordCluster` and `ClusterPage` database models with Alembic migration
- Add cluster CRUD API endpoints (create, list, detail, approve/reject pages, bulk-approve, delete)
- Add seed keyword input page, cluster suggestions/approval page, and cluster list view on project dashboard
- Wire approved cluster pages into existing `CrawledPage` + `PageKeywords` records so the downstream content pipeline works unchanged

## Capabilities

### New Capabilities
- `cluster-keyword-service`: Backend service implementing Stages 1-3 of the cluster pipeline (LLM expansion, DataForSEO enrichment, LLM filtering/role assignment). New `ClusterKeywordService` with `generate_cluster()` orchestrator.
- `cluster-data-model`: `KeywordCluster` and `ClusterPage` SQLAlchemy models, Alembic migration, Pydantic schemas for API request/response.
- `cluster-api`: REST endpoints for cluster CRUD — create cluster (triggers Stages 1-3), list/detail, approve/reject individual pages, bulk-approve (triggers Stage 5 integration), delete.
- `cluster-ui`: Frontend pages — seed keyword input, cluster suggestions with approval controls (parent/child badges, volume data, URL slug editing), cluster list view on project detail page.

### Modified Capabilities
- `project-detail-view`: New Content (Clusters) section changes from disabled placeholder to functional cluster list with "+ New Cluster" button and cluster cards showing status/page counts.

## Impact

- **New backend files:** `models/keyword_cluster.py`, `services/cluster_keyword.py`, `api/v1/clusters.py`, `schemas/cluster.py`, plus Alembic migration
- **Modified backend files:** `models/__init__.py` (register new models), `api/v1/__init__.py` (register cluster router)
- **New frontend files:** Cluster creation page, cluster detail/approval page, API client hooks, cluster components
- **Modified frontend files:** Project detail page (activate clusters section)
- **APIs:** Claude Haiku (Stages 1+3, ~$0.008/cluster), DataForSEO batch volume (~$0.05/cluster), POP (Stage 5, existing usage, only on approved keywords)
- **Database:** New `keyword_clusters` and `cluster_pages` tables
- **No changes to:** existing `PrimaryKeywordService`, content generation pipeline, content review, export — all reused as-is via `CrawledPage`/`PageKeywords` integration point
