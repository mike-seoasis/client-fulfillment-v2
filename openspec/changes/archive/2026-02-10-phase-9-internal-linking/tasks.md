## 1. Data Models & Migration

- [ ] 1.1 Create `InternalLink` model in `backend/app/models/internal_link.py` (id, source_page_id, target_page_id, project_id, cluster_id, scope, anchor_text, anchor_type, position_in_content, is_mandatory, placement_method, status, timestamps)
- [ ] 1.2 Create `LinkPlanSnapshot` model in `backend/app/models/link_plan_snapshot.py` (id, project_id, cluster_id, scope, plan_data JSONB, total_links, created_at)
- [ ] 1.3 Add relationships to CrawledPage model (outbound_links, inbound_links)
- [ ] 1.4 Register new models in `backend/app/models/__init__.py`
- [ ] 1.5 Create Alembic migration `0024_add_internal_links_and_snapshots.py` with indexes
- [ ] 1.6 Run migration and verify tables created

## 2. Pydantic Schemas

- [ ] 2.1 Create `backend/app/schemas/internal_link.py` with request/response schemas (LinkPlanRequest, LinkPlanStatusResponse, LinkMapResponse, PageLinksResponse, AddLinkRequest, EditLinkRequest, AnchorSuggestionsResponse)
- [ ] 2.2 Write unit tests for schema validation

## 3. Link Planning Service — Core Algorithm

- [ ] 3.1 Create `backend/app/services/link_planning.py` with `SiloLinkPlanner` class
- [ ] 3.2 Implement `build_cluster_graph()` — parent/child hierarchy from ClusterPage roles
- [ ] 3.3 Implement `build_onboarding_graph()` — label overlap matrix with 2+ threshold
- [ ] 3.4 Implement `calculate_budget(word_count)` — clamp(word_count/250, 3, 5)
- [ ] 3.5 Implement `select_targets_cluster()` — mandatory parent + siblings by composite_score
- [ ] 3.6 Implement `select_targets_onboarding()` — label overlap + priority bonus + diversity penalty
- [ ] 3.7 Write unit tests for graph construction (cluster + onboarding)
- [ ] 3.8 Write unit tests for budget calculation
- [ ] 3.9 Write unit tests for target selection (both modes, edge cases: small clusters, no eligible targets)

## 4. Anchor Text Selection

- [ ] 4.1 Create `AnchorTextSelector` class in `backend/app/services/link_planning.py`
- [ ] 4.2 Implement candidate gathering (primary keyword, POP variations, LLM-generated natural phrases)
- [ ] 4.3 Implement scoring (diversity bonus, context fit, distribution targets)
- [ ] 4.4 Implement global usage tracking (max 3x same anchor per target)
- [ ] 4.5 Write unit tests for anchor selection and diversity tracking

## 5. Link Injection Service

- [ ] 5.1 Create `backend/app/services/link_injection.py` with `LinkInjector` class
- [ ] 5.2 Implement `inject_rule_based()` — BeautifulSoup keyword scanning in `<p>` tags, case-insensitive match, wrap first occurrence in `<a>` tag
- [ ] 5.3 Implement `inject_llm_fallback()` — select best paragraph, Claude Haiku rewrite, replace paragraph
- [ ] 5.4 Implement density limit enforcement (max 2/paragraph, min 50 words between)
- [ ] 5.5 Implement mandatory parent link positioning (must be in first 2 paragraphs)
- [ ] 5.6 Implement `strip_internal_links()` — unwrap internal `<a>` tags, preserve external links
- [ ] 5.7 Write unit tests for rule-based injection (found, not found, existing link, case insensitive)
- [ ] 5.8 Write unit tests for density limits
- [ ] 5.9 Write unit tests for link stripping

## 6. Link Validation

- [ ] 6.1 Create `LinkValidator` class in `backend/app/services/link_injection.py`
- [ ] 6.2 Implement validation rules: budget check, silo integrity, no self-links, no duplicates, density, anchor diversity
- [ ] 6.3 Implement cluster-specific rules: first-link rule (first `<a>` → parent), direction rules
- [ ] 6.4 Write unit tests for each validation rule

## 7. Pipeline Orchestration

- [ ] 7.1 Create `run_link_planning_pipeline()` in `backend/app/services/link_planning.py` — orchestrate steps 1-4 with progress tracking
- [ ] 7.2 Implement re-plan flow: snapshot → strip → delete → re-run
- [ ] 7.3 Implement progress state tracking (current_step, pages_processed, total_pages)
- [ ] 7.4 Write integration test: full pipeline for a cluster (build graph → select targets → inject → validate)
- [ ] 7.5 Write integration test: full pipeline for onboarding pages

## 8. API Endpoints

- [ ] 8.1 Create `backend/app/api/v1/links.py` with router
- [ ] 8.2 Implement `POST /{project_id}/links/plan` — trigger link planning (background task)
- [ ] 8.3 Implement `GET /{project_id}/links/plan/status` — poll planning progress
- [ ] 8.4 Implement `GET /{project_id}/links` — get link map for scope
- [ ] 8.5 Implement `GET /{project_id}/links/page/{page_id}` — get links for a specific page
- [ ] 8.6 Implement `POST /{project_id}/links` — add manual link
- [ ] 8.7 Implement `DELETE /{project_id}/links/{link_id}` — remove link
- [ ] 8.8 Implement `PUT /{project_id}/links/{link_id}` — edit anchor text
- [ ] 8.9 Implement `GET /{project_id}/links/suggestions/{target_page_id}` — anchor suggestions
- [ ] 8.10 Register router in `backend/app/api/v1/__init__.py`
- [ ] 8.11 Write API tests for all endpoints (happy path + error cases)

## 9. Frontend — API Client & Hooks

- [ ] 9.1 Add link planning types to `frontend/src/types/` (LinkMap, PageLinks, InternalLink, PlanStatus)
- [ ] 9.2 Add API client functions in `frontend/src/lib/api.ts` (planLinks, getPlanStatus, getLinkMap, getPageLinks, addLink, removeLink, editLink, getAnchorSuggestions)
- [ ] 9.3 Create TanStack Query hooks in `frontend/src/hooks/useLinks.ts` (useLinkMap, usePageLinks, usePlanStatus with polling, useLinkMutations)

## 10. Frontend — Link Planning Page

- [ ] 10.1 Create link planning page at `frontend/src/app/projects/[id]/links/page.tsx` (onboarding scope)
- [ ] 10.2 Create link planning page at `frontend/src/app/projects/[id]/clusters/[clusterId]/links/page.tsx` (cluster scope)
- [ ] 10.3 Implement prerequisites checklist component (keywords approved, content complete, QA passed)
- [ ] 10.4 Implement "Plan & Inject Links" button with disabled state
- [ ] 10.5 Implement planning progress indicator (4-step stepper with polling)
- [ ] 10.6 Implement scope-specific link rules display
- [ ] 10.7 Auto-redirect to link map on completion

## 11. Frontend — Link Map Page

- [ ] 11.1 Create link map page at `frontend/src/app/projects/[id]/links/map/page.tsx` (onboarding)
- [ ] 11.2 Create link map page at `frontend/src/app/projects/[id]/clusters/[clusterId]/links/map/page.tsx` (cluster)
- [ ] 11.3 Implement cluster tree visualization component (parent → children with link counts)
- [ ] 11.4 Implement onboarding label-grouped visualization component
- [ ] 11.5 Implement stats sidebar (totals, method breakdown, anchor diversity)
- [ ] 11.6 Implement page table with sorting (page, out/in counts, method, validation status)
- [ ] 11.7 Implement onboarding table filters (label dropdown, priority toggle, search)
- [ ] 11.8 Implement "Re-plan Links" button with confirmation dialog
- [ ] 11.9 Click row → navigate to page link detail

## 12. Frontend — Page Link Detail

- [ ] 12.1 Create page link detail at `frontend/src/app/projects/[id]/links/page/[pageId]/page.tsx`
- [ ] 12.2 Implement outbound links list (ordered by position, mandatory badge, edit/remove/preview buttons)
- [ ] 12.3 Implement inbound links list (read-only)
- [ ] 12.4 Implement anchor diversity section (unique anchors, diversity score)
- [ ] 12.5 Implement Add Link modal (target dropdown sorted by relevance, anchor text input, POP suggestions)
- [ ] 12.6 Implement Edit Anchor modal (current text, suggestions, anchor type radio)
- [ ] 12.7 Implement Remove Link with confirmation

## 13. Frontend — Project Detail Integration

- [ ] 13.1 Add link status indicator to onboarding section ("Not planned" / "Planned (N links)" / "Planning...")
- [ ] 13.2 Add link status indicator to cluster cards
- [ ] 13.3 Add navigation links from status indicators to link planning pages

## 14. Frontend Component Tests

- [ ] 14.1 Write tests for link planning page (prerequisites, button state, progress)
- [ ] 14.2 Write tests for link map page (stats, table, filters)
- [ ] 14.3 Write tests for page link detail (outbound/inbound lists, modals)
- [ ] 14.4 Write tests for project detail link status integration

## 15. Verification & Status Update

- [ ] 15.1 Manual verification: Run full link planning pipeline for a cluster (8 pages) — verify links injected, validation passes, link map displays correctly
- [ ] 15.2 Manual verification: Run full link planning pipeline for onboarding (multiple pages with labels) — verify label-based target selection, priority weighting works
- [ ] 15.3 Manual verification: Edit anchor text, add manual link, remove link — verify content updates
- [ ] 15.4 Manual verification: Re-plan links — verify snapshot created, old links stripped, new plan applied
- [ ] 15.5 Manual verification: Export with links — verify Matrixify CSV contains `<a>` tags in Body HTML
- [ ] 15.6 Update V2_REBUILD_PLAN.md (mark Phase 9 checkboxes, update status, add session log entry)
