## 1. Database Models + Migration

- [ ] 1.1 Create `KeywordCluster` model in `backend/app/models/keyword_cluster.py` (id, project_id FK, seed_keyword, name, status, generation_metadata JSONB, created_at, updated_at)
- [ ] 1.2 Create `ClusterPage` model in same file (id, cluster_id FK cascade, keyword, role, url_slug, expansion_strategy, reasoning, search_volume, cpc, competition, competition_level, composite_score, is_approved, crawled_page_id FK nullable, created_at, updated_at)
- [ ] 1.3 Add `source` column to `CrawledPage` model (String, default='onboarding', nullable=False)
- [ ] 1.4 Register new models in `backend/app/models/__init__.py`
- [ ] 1.5 Create Alembic migration for keyword_clusters table, cluster_pages table, and crawled_pages.source column (backfill existing rows with 'onboarding')
- [ ] 1.6 Create Pydantic v2 schemas in `backend/app/schemas/cluster.py` (ClusterCreate, ClusterResponse, ClusterListResponse, ClusterPageResponse, ClusterPageUpdate)

## 2. Cluster Keyword Service (Stages 1-3)

- [ ] 2.1 Create `backend/app/services/cluster_keyword.py` with `ClusterKeywordService` class skeleton (init with ClaudeClient, DataForSEOClient)
- [ ] 2.2 Implement `_build_brand_context()` helper — extract brand foundation, target audience, competitor context from brand config for prompt injection
- [ ] 2.3 Implement Stage 1 `_generate_candidates()` — 11-strategy expansion prompt with brand context, Claude Haiku call, JSON response parsing, returns 15-20 candidates
- [ ] 2.4 Implement Stage 2 `_enrich_with_volume()` — call DataForSEOClient.get_keyword_volume_batch(), merge volume/CPC/competition into candidates, handle DataForSEO unavailability gracefully
- [ ] 2.5 Implement Stage 3 `_filter_and_assign_roles()` — Claude Haiku call with volume data, filter to 8-12 candidates, assign parent/child roles, generate URL slugs, calculate composite scores
- [ ] 2.6 Implement `generate_cluster()` orchestrator — runs Stages 1→2→3 sequentially, creates KeywordCluster + ClusterPage DB records, returns result with generation_metadata (timings, costs, counts)
- [ ] 2.7 Implement `bulk_approve_cluster()` — creates CrawledPage (source='cluster', status='completed', category='collection') + PageKeywords (is_approved=True, is_priority for parent) for each approved ClusterPage, sets crawled_page_id back-reference, updates cluster status to 'approved'

## 3. API Endpoints

- [ ] 3.1 Create `backend/app/api/v1/clusters.py` router with project_id path prefix
- [ ] 3.2 Implement POST `/projects/{project_id}/clusters` — validate project exists, call generate_cluster(), return cluster with suggestions (synchronous, ~5-10s)
- [ ] 3.3 Implement GET `/projects/{project_id}/clusters` — list all clusters for project with page counts and status
- [ ] 3.4 Implement GET `/projects/{project_id}/clusters/{cluster_id}` — get cluster detail with all ClusterPage records
- [ ] 3.5 Implement PATCH `/projects/{project_id}/clusters/{cluster_id}/pages/{page_id}` — update approval, keyword, url_slug, role (handle parent reassignment)
- [ ] 3.6 Implement POST `/projects/{project_id}/clusters/{cluster_id}/approve` — bulk-approve, call bulk_approve_cluster(), return bridged page count
- [ ] 3.7 Implement DELETE `/projects/{project_id}/clusters/{cluster_id}` — block deletion if status >= approved, cascade delete otherwise
- [ ] 3.8 Register clusters router in `backend/app/api/v1/__init__.py`

## 4. Backend Tests

- [ ] 4.1 Unit tests for ClusterKeywordService._generate_candidates() with mocked Claude responses
- [ ] 4.2 Unit tests for ClusterKeywordService._enrich_with_volume() with mocked DataForSEO responses (success + failure cases)
- [ ] 4.3 Unit tests for ClusterKeywordService._filter_and_assign_roles() with mocked Claude responses
- [ ] 4.4 Unit tests for generate_cluster() orchestrator (full pipeline with mocks, partial failure scenarios)
- [ ] 4.5 Unit tests for bulk_approve_cluster() (CrawledPage/PageKeywords creation, parent priority, crawled_page_id backref)
- [ ] 4.6 Integration tests for all 6 API endpoints (success cases, 404s, 422s, 409s)
- [ ] 4.7 Test URL slug generation edge cases (special chars, long keywords, duplicates)

## 5. Frontend API Client + Hooks

- [ ] 5.1 Add TypeScript types for Cluster, ClusterPage, ClusterCreate in `frontend/src/lib/types.ts`
- [ ] 5.2 Add cluster API client functions in `frontend/src/lib/api.ts` (createCluster, getClusters, getCluster, updateClusterPage, bulkApproveCluster, deleteCluster)
- [ ] 5.3 Create TanStack Query hooks in `frontend/src/hooks/useClusters.ts` (useCreateCluster, useClusters, useCluster, useUpdateClusterPage, useBulkApproveCluster, useDeleteCluster)

## 6. Seed Keyword Input Page

- [ ] 6.1 Create page at `frontend/src/app/projects/[id]/clusters/new/page.tsx` with seed keyword input form (required), cluster name input (optional), Cancel and Get Suggestions buttons
- [ ] 6.2 Add loading state with 3-step progress indicator (Generating suggestions → Checking search volume → Finalizing results)
- [ ] 6.3 Handle success (navigate to cluster detail) and error (show error with retry button)

## 7. Cluster Suggestions + Approval Page

- [ ] 7.1 Create page at `frontend/src/app/projects/[id]/clusters/[clusterId]/page.tsx` with cluster header (name, seed keyword, stepper)
- [ ] 7.2 Build suggestion list component — each row shows: keyword (editable), role badge (Parent green / Child neutral), search volume, CPC, competition, score, URL slug (editable), expansion strategy tag, approve/reject toggle
- [ ] 7.3 Implement parent page visual distinction (top of list, palm green Parent badge)
- [ ] 7.4 Implement inline editing for keyword and URL slug (save on blur/Enter via PATCH)
- [ ] 7.5 Implement "Make Parent" action on child rows (PATCH role reassignment)
- [ ] 7.6 Implement "Approve All" button (batch approve all suggestions)
- [ ] 7.7 Implement "Generate Content" button — calls bulk-approve, navigates to content generation progress page. Disabled when no pages approved.
- [ ] 7.8 Add volume data unavailable warning banner (when DataForSEO was unavailable)
- [ ] 7.9 Add Back button navigation to project detail

## 8. Project Detail View — Clusters Section

- [ ] 8.1 Update project detail page New Content section — replace disabled placeholder with live cluster list (fetch via useClusters hook)
- [ ] 8.2 Build cluster card component (name, page count, status indicator, click to navigate)
- [ ] 8.3 Implement "+ New Cluster" button (navigates to `/projects/{id}/clusters/new`)
- [ ] 8.4 Implement empty state ("No clusters yet" with prominent create button)

## 9. Frontend Tests

- [ ] 9.1 Component tests for seed keyword input page (form validation, loading state, navigation)
- [ ] 9.2 Component tests for cluster suggestions page (rendering, approval toggling, inline editing, bulk actions)
- [ ] 9.3 Component tests for cluster card and list on project detail

## 10. Verification + Status Update

- [ ] 10.1 Manual end-to-end verification: create cluster → review suggestions → approve → verify CrawledPage/PageKeywords records created → content generation triggers successfully
- [ ] 10.2 Update V2_REBUILD_PLAN.md — mark Phase 8 checkboxes complete, update Current Status, add session log entry
