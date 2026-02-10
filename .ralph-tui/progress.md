# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **Model UUID pattern**: `UUID(as_uuid=False)` with `default=lambda: str(uuid4())` and `server_default=text("gen_random_uuid()")`. Python type is `Mapped[str]`, not `Mapped[UUID]`.
- **DateTime pattern**: `DateTime(timezone=True)` with `default=lambda: datetime.now(UTC)` and `server_default=text("now()")`. Add `onupdate=lambda: datetime.now(UTC)` for `updated_at`.
- **Boolean defaults**: Use `server_default=text("false")` (lowercase string), not `server_default=False`.
- **FK pattern**: `ForeignKey("table.id", ondelete="CASCADE")` for required refs, `ondelete="SET NULL"` for optional refs.
- **Composite indexes**: Use `__table_args__` tuple with `Index(name, col1, col2)`. See `notification.py` and `internal_link.py`.
- **Multi-FK relationships**: When a model has multiple FKs to the same table, specify `foreign_keys=[column]` on each relationship to disambiguate.
- **Model registration**: Import in `backend/app/models/__init__.py` and add to `__all__`.
- **Migration numbering**: Sequential `0001`, `0002`, etc. in `backend/alembic/versions/`. Set `down_revision` to previous.
- **Virtual env**: Use `.venv/bin/python` (not `python`) in the backend directory.
- **Test DB verification**: When verifying DB state after an API endpoint commits, use `async_session_factory()` for a fresh session — the test's `db_session` has stale cached objects.

---

## 2026-02-10 - S9-001
- Created `InternalLink` model (`backend/app/models/internal_link.py`) with all fields from acceptance criteria
- Created Alembic migration `0024_create_internal_links_table.py` with table, FKs, and indexes
- Registered model in `backend/app/models/__init__.py`
- **Files changed:**
  - `backend/app/models/internal_link.py` (new)
  - `backend/app/models/__init__.py` (updated import + __all__)
  - `backend/alembic/versions/0024_create_internal_links_table.py` (new)
- **Learnings:**
  - Models with multiple FKs to the same table (e.g., source_page_id and target_page_id both pointing to crawled_pages) require `foreign_keys=[column]` on each relationship to avoid SQLAlchemy ambiguity errors
  - Composite indexes go in `__table_args__` tuple — pattern already used in `notification.py`
  - Enums defined as `str, Enum` for JSON serialization compatibility
  - Virtual env is at `backend/.venv/bin/python`
---

## 2026-02-10 - S9-002
- Created `LinkPlanSnapshot` model in `backend/app/models/internal_link.py` (same file as InternalLink)
- Fields: id (UUID PK), project_id (FK CASCADE), cluster_id (FK SET NULL nullable), scope (String(20)), plan_data (JSONB), total_links (Integer), created_at (DateTime timezone)
- Composite index on (project_id, scope)
- Relationship to Project and KeywordCluster
- Created Alembic migration `0025_create_link_plan_snapshots_table.py`
- Registered `LinkPlanSnapshot` in `backend/app/models/__init__.py`
- **Files changed:**
  - `backend/app/models/internal_link.py` (added LinkPlanSnapshot class, added JSONB import)
  - `backend/app/models/__init__.py` (added LinkPlanSnapshot import + __all__ entry)
  - `backend/alembic/versions/0025_create_link_plan_snapshots_table.py` (new)
- **Learnings:**
  - JSONB column uses `from sqlalchemy.dialects.postgresql import JSONB` alongside `UUID`
  - Python type hint for JSONB column is `Mapped[dict]`
  - Multiple models in the same file sharing FKs to the same tables (e.g. both InternalLink and LinkPlanSnapshot referencing keyword_clusters) works fine without `foreign_keys=` disambiguation since each model only has one FK to that table
---

## 2026-02-10 - S9-003
- Added `outbound_links` and `inbound_links` relationships to `CrawledPage` model
- Added `back_populates` to `InternalLink.source_page` and `InternalLink.target_page` relationships for bidirectional linking
- Added `InternalLink` to `TYPE_CHECKING` imports in `crawled_page.py`
- Models already registered in `__init__.py` from S9-001/S9-002
- **Files changed:**
  - `backend/app/models/crawled_page.py` (added TYPE_CHECKING import + two relationships)
  - `backend/app/models/internal_link.py` (added back_populates to source_page and target_page)
- **Learnings:**
  - When adding reverse relationships on a model with multi-FK ambiguity, use string-form `foreign_keys="[ClassName.column]"` on the parent side and `foreign_keys=[column]` on the child side
  - Both sides need `back_populates` for proper bidirectional behavior
  - `cascade="all, delete-orphan"` on the parent side ensures links are cleaned up when a page is deleted
---

## 2026-02-10 - S9-004
- Migrations already existed from S9-001 and S9-002 (0024 + 0025), so this was a verification task
- Verified `0024_create_internal_links_table.py` creates internal_links with all columns, FKs, and indexes
- Verified `0025_create_link_plan_snapshots_table.py` creates link_plan_snapshots with all columns, FKs, and indexes
- Ran `alembic upgrade head` successfully (0023 → 0024 → 0025)
- Verified reversibility: `alembic downgrade 0023` drops both tables cleanly, then re-upgraded to head
- **Files changed:** None (migrations already existed)
- **Learnings:**
  - When model creation stories (S9-001, S9-002) each create their own migration, the migration story (S9-004) becomes a verification task rather than a creation task
  - Always verify both upgrade AND downgrade paths when validating migrations
---

## 2026-02-10 - S9-005
- Created Pydantic v2 schemas for internal link management API
- 9 schema classes: LinkPlanRequest, LinkPlanStatusResponse, InternalLinkResponse, PageLinksResponse, LinkMapPageSummary, LinkMapResponse, AddLinkRequest, EditLinkRequest, AnchorSuggestionsResponse
- All use `Literal` types for constrained string fields (scope, anchor_type, status)
- `ConfigDict(from_attributes=True)` on InternalLinkResponse for ORM serialization
- Registered all schemas in `backend/app/schemas/__init__.py`
- **Files changed:**
  - `backend/app/schemas/internal_link.py` (new)
  - `backend/app/schemas/__init__.py` (added imports + __all__ entries)
- **Learnings:**
  - Pydantic v2 `Literal` types work well for constrained string enums in request schemas (cleaner than validator)
  - Ruff import sorter (isort) requires `internal_link` to sort alphabetically among other schema imports — placing it before `crawled_page` caused a re-sort
  - Response schemas that join data from relationships (e.g., InternalLinkResponse with target_url/target_title) don't need `from_attributes=True` if they'll be constructed manually rather than from ORM objects — but including it is harmless and future-proofs
---

## 2026-02-10 - S9-006
- Created `SiloLinkPlanner` class in `backend/app/services/link_planning.py`
- `build_cluster_graph(cluster_id, db)`: queries ClusterPage with joinedload on crawled_page, builds parent_child + sibling edges
- `build_onboarding_graph(project_id, db)`: queries CrawledPage joined with PageContent (status='complete') and PageKeywords (is_approved=True), computes pairwise label overlap with LABEL_OVERLAP_THRESHOLD=2
- Edge cases handled: 0-1 cluster pages returns empty edges, no overlapping labels returns pages but no edges
- Registered `SiloLinkPlanner` and `LABEL_OVERLAP_THRESHOLD` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_planning.py` (new)
  - `backend/app/services/__init__.py` (added imports + __all__ entries)
- **Learnings:**
  - `joinedload` with `result.unique().scalars().all()` is needed when using joined eager loading to avoid duplicate rows from the SQL join
  - Import sorting in `__init__.py` is alphabetical by module name — `link_planning` sorts after `label_taxonomy`
  - `itertools.combinations` is the clean way to generate pairwise edges for the overlap graph
---

## 2026-02-10 - S9-007
- Implemented `calculate_budget(word_count)` → `clamp(word_count // 250, 3, 5)`
- Implemented `select_targets_cluster(graph, budgets)` → parent gets children by composite_score; children get mandatory parent + siblings by composite_score then least-linked-to
- Implemented `select_targets_onboarding(graph, budgets)` → scores targets by label_overlap + priority_bonus - diversity_penalty, updates running inbound_counts after each page
- Added `composite_score` field to cluster graph page dicts (needed for target ranking)
- Registered `calculate_budget`, `select_targets_cluster`, `select_targets_onboarding` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_planning.py` (added 3 functions + composite_score to graph pages)
  - `backend/app/services/__init__.py` (added 3 new exports)
- **Learnings:**
  - Target selection functions are pure (no DB calls) — they operate on graph dicts from build_*_graph, making them easy to test
  - The diversity_penalty formula `max(0, (inbound - avg_inbound) * 0.5)` only penalizes pages above average, preventing any single page from hogging all links
  - `replace_all=true` in Edit tool matches literal text — if formatting differs between occurrences, some won't match
---

## 2026-02-10 - S9-008
- Created `AnchorTextSelector` class in `backend/app/services/link_planning.py`
- `gather_candidates(target_page_id, db)`: Returns candidates from 3 sources — primary keyword (exact_match) from PageKeywords, POP keyword_targets variations (partial_match) from ContentBrief, with secondary_keywords fallback when POP data unavailable
- `generate_natural_phrases(keywords)`: Batches all target keywords into a single Claude Haiku call, parses JSON response into natural-type candidates
- `select_anchor(candidates, source_content, target_page_id, usage_tracker)`: Scores by diversity_bonus (3 - use_count), context_fit (+2 if anchor in source), type_weight (1.5 partial, 1.0 natural, 0.3 exact). Rejects anchors used >= 3 times per target.
- Usage tracker is `dict[target_page_id, dict[anchor_text, count]]`, mutated in-place by select_anchor
- Constants: `ANCHOR_LLM_MODEL = "claude-haiku-4-5-20251001"`, `MAX_ANCHOR_REUSE = 3`
- Registered `AnchorTextSelector`, `ANCHOR_LLM_MODEL`, `MAX_ANCHOR_REUSE` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_planning.py` (added AnchorTextSelector class + constants)
  - `backend/app/services/__init__.py` (added 3 new exports)
- **Learnings:**
  - ContentBrief.keyword_targets is a JSONB array of dicts with `keyword` key — useful for POP variations
  - ClaudeClient from `app.integrations.claude` uses httpx directly (no SDK), init with `ClaudeClient(api_key=get_api_key())` for background contexts
  - `select_anchor` type_weights approximate the 50-60% partial / 10% exact / 30% natural distribution via scoring bias rather than hard quotas
  - Must close ClaudeClient instances created outside the global lifecycle (`await client.close()` in finally block)
---

## 2026-02-10 - S9-009
- Created `LinkInjector` class in `backend/app/services/link_injection.py`
- `inject_rule_based(html, anchor_text, target_url)` → parses HTML with BeautifulSoup, scans `<p>` tags for case-insensitive anchor text match, wraps first occurrence in `<a href>` tag. Returns `(modified_html, paragraph_index)` or `(original_html, None)`.
- Does NOT inject inside existing `<a>`, `<h2>`, `<h3>`, or `<li>` elements — walks NavigableString descendants and checks parent chain for forbidden tags
- Case-insensitive matching via `re.compile(re.escape(anchor_text), re.IGNORECASE)` preserves original casing in anchor tag
- Density limits enforced: max 2 links per paragraph (`MAX_LINKS_PER_PARAGRAPH`), min 50 words between links (`MIN_WORDS_BETWEEN_LINKS`)
- If target paragraph is at density limit, automatically tries next paragraph with the match
- Constants `MAX_LINKS_PER_PARAGRAPH` and `MIN_WORDS_BETWEEN_LINKS` exported for reuse
- Registered `LinkInjector`, `MAX_LINKS_PER_PARAGRAPH`, `MIN_WORDS_BETWEEN_LINKS` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_injection.py` (new)
  - `backend/app/services/__init__.py` (added imports + __all__ entries)
- **Learnings:**
  - BeautifulSoup `NavigableString` import requires `# type: ignore[attr-defined]` because `types-beautifulsoup4` stubs don't explicitly export it (works fine at runtime)
  - For inserting before/after a text node: use `text_node.extract()` then `parent.insert(idx, ...)` rather than `replace_with()` + `find(string=...)` — the find approach is fragile when multiple text nodes have identical content
  - `list(parent.children).index(text_node)` gives the correct insertion index for splicing a text node into [before, link, after]
  - Word distance check uses character offsets in the paragraph's full text to calculate word count between proposed link position and existing links
---

## 2026-02-10 - S9-010
- Implemented `inject_llm_fallback(html, anchor_text, target_url, target_keyword, *, mandatory_parent=False)` async method on `LinkInjector`
- Best paragraph selection: scores by `word_overlap(paragraph, target_keyword) - existing_link_count`, skips paragraphs at density limit
- Mandatory parent links target paragraph index 1 or 0 specifically (not best-scored)
- Haiku prompt matches spec exactly: "Rewrite this paragraph to naturally include a hyperlink..."
- Validates LLM response: exactly 1 `<a>` tag with correct `href`; returns `(original_html, None)` on malformed response
- Uses `claude-haiku-4-5-20251001` with `temperature=0.0`, `max_tokens=500`
- Strips markdown code fences from LLM response (same pattern as `generate_natural_phrases`)
- ClaudeClient created with `get_api_key()` and closed in `finally` block (background task pattern)
- Added constants `LLM_FALLBACK_MODEL`, `LLM_FALLBACK_MAX_TOKENS`, `LLM_FALLBACK_TEMPERATURE`
- Registered `LLM_FALLBACK_MODEL` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_injection.py` (added async `inject_llm_fallback` + 4 helper methods + constants + claude import)
  - `backend/app/services/__init__.py` (added `LLM_FALLBACK_MODEL` import + __all__ entry)
- **Learnings:**
  - `inject_llm_fallback` is async (because of Claude API call) while `inject_rule_based` is sync — callers need to await the fallback path
  - `BeautifulSoup.replace_with()` accepts another BeautifulSoup object for swapping entire paragraph HTML
  - Paragraph relevance scoring via simple word overlap (`set.intersection`) is sufficient per spec — no need for TF-IDF or embeddings
---

## 2026-02-10 - S9-011
- Implemented `strip_internal_links(html, site_domain=None)` as a module-level function in `link_injection.py`
- Internal link detection: relative paths (starts with `/`) and same-domain (href netloc contains `site_domain`)
- Uses BeautifulSoup `.unwrap()` to replace `<a>` tags with their text content
- External links (absolute URLs to other domains) left unchanged
- Content structure (headings, paragraphs, lists) fully preserved
- Helper `_is_internal_link(href, site_domain)` uses `urlparse` for robust domain matching
- **Files changed:**
  - `backend/app/services/link_injection.py` (added `strip_internal_links` + `_is_internal_link` + `urlparse` import)
  - `backend/app/services/__init__.py` (added `strip_internal_links` import + `__all__` entry)
- **Learnings:**
  - `a_tag.get("href", "")` returns `str | AttributeValueList` per BS4 type stubs — need `isinstance(href, str)` guard for mypy
  - BeautifulSoup `.unwrap()` is perfect for "replace tag with its text content" — no manual text extraction needed
  - Collecting tags to unwrap in a list first avoids modification-during-iteration issues with `find_all`
---

## 2026-02-10 - S9-012
- Created `LinkValidator` class in `backend/app/services/link_injection.py`
- Implemented `validate_links(links, pages_html, scope, cluster_data)` → returns `{passed: bool, results: [{page_id, rules: [{rule, passed, message}]}]}`
- 8 validation rules implemented:
  1. `budget_check` — 3-5 outbound links per page (WARN only, always passes)
  2. `silo_integrity` — all targets within same scope; cluster links checked against cluster page set
  3. `no_self_links` — source_page_id != target_page_id
  4. `no_duplicate_links` — Counter-based check for same target linked twice from one page
  5. `density` — max 2 links per paragraph + min 50 words between links (reuses existing constants)
  6. `anchor_diversity` — same anchor text for same target max 3x across project
  7. `first_link` (cluster only) — first `<a>` tag in bottom_description points to parent URL
  8. `direction` (cluster only) — parent links to children only, children link to parent + siblings
- Status update: links marked `status='verified'` if all rules pass, `status='failed:rule1,rule2'` if any fail
- Constants added: `BUDGET_MIN=3`, `BUDGET_MAX=5`, `MAX_ANCHOR_REUSE_VALIDATION=3`
- Registered `LinkValidator`, `BUDGET_MIN`, `BUDGET_MAX`, `MAX_ANCHOR_REUSE_VALIDATION` in `backend/app/services/__init__.py`
- **Files changed:**
  - `backend/app/services/link_injection.py` (added LinkValidator class + constants + imports)
  - `backend/app/services/__init__.py` (added 4 new imports + __all__ entries)
- **Learnings:**
  - Ruff E741 rejects `l` as a variable name (ambiguous) — use `lnk` instead in generator expressions
  - `dict.get()` returns `Any` when the dict value type is `Any` — assign to typed local variable to satisfy mypy `no-any-return`
  - `cluster_data` uses `crawled_page_id` as the primary identifier for pages within a cluster (maps to InternalLink's source/target_page_id), with `page_id` as fallback (ClusterPage.id)
  - The `budget_check` rule intentionally always passes (WARN semantics) — it reports outside-range counts but never fails validation
---

## 2026-02-10 - S9-013
- Implemented `run_link_planning_pipeline(project_id, scope, cluster_id, db)` in `backend/app/services/link_planning.py`
- 4-step pipeline: build graph → select targets + anchor text → inject links (rule-based + LLM fallback) → validate all rules
- Module-level `_pipeline_progress` dict keyed by `(project_id, scope, cluster_id)` for frontend polling
- `get_pipeline_progress()` helper function for reading progress state
- Per-page try/except in injection step so one page failing doesn't kill the pipeline
- `_LinkProxy` class mimics InternalLink attributes for validator (avoids DB writes before validation passes)
- InternalLink rows created after successful injection with status='injected' then updated based on validation results
- PageContent.bottom_description updated with injected HTML using separate write session via `db_manager.session_factory()`
- Helper functions: `_extract_page_ids`, `_page_id_for_scope`, `_load_word_counts`, `_load_page_content_text`, `_load_bottom_description`
- **Files changed:**
  - `backend/app/services/link_planning.py` (added pipeline orchestrator + progress dict + helpers)
  - `backend/app/services/__init__.py` (added `run_link_planning_pipeline`, `get_pipeline_progress` imports + __all__ entries)
- **Learnings:**
  - `dict.get()` on `dict[str, Any]` returns `Any` — mypy `no-any-return` requires assigning to a typed local variable before returning
  - The pipeline follows the same background task pattern as `content_generation.py` — module-level dict for progress, `db_manager.session_factory()` for write sessions
  - `_LinkProxy` pattern avoids creating real DB rows before validation, enabling clean rollback (no partial state) if the pipeline fails
  - Cluster graph pages have both `page_id` (ClusterPage.id) and `crawled_page_id` (CrawledPage.id) — always use `crawled_page_id` for PageContent/InternalLink lookups
  - `selectinload` import wasn't needed (pipeline uses separate queries, not eager loading) — ruff caught the unused import
---

## 2026-02-10 - S9-014
- Implemented `replan_links(project_id, scope, cluster_id, db)` async function in `backend/app/services/link_planning.py`
- 4-step re-plan flow: snapshot current state → strip internal links from content → delete InternalLink rows → run full pipeline
- `LinkPlanSnapshot` created BEFORE stripping/deleting — stores all InternalLink rows + pre-strip `bottom_description` per page as rollback point
- Short-circuits to `run_link_planning_pipeline` directly when no existing links found (first-time plan)
- Site domain extracted from `Project.site_url` via `urlparse` for accurate internal link detection in `strip_internal_links`
- Uses `sqlalchemy.delete()` for bulk deletion of InternalLink rows (filtered by project_id + scope + cluster_id)
- Separate `db_manager.session_factory()` write sessions for snapshot, strip, and delete steps (consistent with pipeline pattern)
- **Files changed:**
  - `backend/app/services/link_planning.py` (added `replan_links` function + imports for `delete`, `LinkPlanSnapshot`, `Project`, `strip_internal_links`)
  - `backend/app/services/__init__.py` (added `replan_links` import + `__all__` entry)
- **Learnings:**
  - `Result.rowcount` from async SQLAlchemy `delete()` needs `# type: ignore[attr-defined]` — mypy doesn't see `rowcount` on the generic `Result[Any]` type from async execute
  - Import ordering: `project` sorts after `page_keywords` alphabetically — ruff caught the mis-order and auto-fixed
  - The `urlparse` import can be localized (inside function body) to avoid top-level import of `urllib.parse` when it's only used in one function
---

## 2026-02-10 - S9-021
- Created `backend/app/api/v1/links.py` with APIRouter for link management endpoints
- POST `/api/v1/projects/{project_id}/links/plan` — validates prerequisites (content complete + keywords approved), validates cluster scope (cluster exists, >= 2 approved pages), checks for existing links to trigger re-plan flow, starts pipeline as BackgroundTask, returns 202 with LinkPlanStatusResponse
- GET `/api/v1/projects/{project_id}/links/plan/status` — accepts `scope` and `cluster_id` query params, reads progress from `get_pipeline_progress()` in link_planning.py, returns LinkPlanStatusResponse
- Module-level `_active_plans` set prevents duplicate concurrent runs (keyed by project_id, scope, cluster_id tuple)
- Background task wrapper `_run_link_planning_background` creates its own DB session via `db_manager.session_factory()`, calls `replan_links` or `run_link_planning_pipeline` based on existing links
- Registered router in `backend/app/api/v1/__init__.py`
- **Files changed:**
  - `backend/app/api/v1/links.py` (new)
  - `backend/app/api/v1/__init__.py` (added links router import + include)
- **Learnings:**
  - Deferred imports inside background task functions avoid circular imports and ensure fresh module references — `from app.core.database import db_manager` must come before `from app.services.link_planning import ...` for ruff import sorting
  - `type: ignore[arg-type]` needed on `replan_links`/`run_link_planning_pipeline` calls because the Literal["onboarding", "cluster"] param doesn't match `str` from the request body
  - The `_active_plans` set uses tuples `(project_id, scope, cluster_id)` rather than just project_id (unlike content_generation.py) because link planning can run independently per scope/cluster
---

## 2026-02-10 - S9-022
- Added 3 new GET endpoints to `backend/app/api/v1/links.py` for link map display and per-page details
- GET `/api/v1/projects/{project_id}/links` — accepts `scope` and `cluster_id` query params, returns LinkMapResponse with aggregate stats (total_links, total_pages, avg_links_per_page, validation_pass_rate), method breakdown, anchor diversity percentages, per-page summaries. For cluster scope, includes hierarchy tree with parent at root and children array.
- GET `/api/v1/projects/{project_id}/links/page/{page_id}` — returns PageLinksResponse with outbound links (ordered by position_in_content), inbound links, anchor diversity counts, and diversity_score ('good'/'needs_variation'/'poor')
- GET `/api/v1/projects/{project_id}/links/suggestions/{target_page_id}` — returns AnchorSuggestionsResponse with primary keyword from PageKeywords, POP variations from ContentBrief.keyword_targets, and usage counts from existing InternalLink rows grouped by anchor_text
- All endpoints return 404 for invalid project/page IDs; empty results (not errors) when no links exist
- Helper functions: `_build_link_response`, `_compute_anchor_diversity_percentages`, `_compute_diversity_score`, `_build_hierarchy_tree`
- **Files changed:**
  - `backend/app/api/v1/links.py` (added 3 endpoints, 4 helper functions, expanded imports)
- **Learnings:**
  - Reusing variable name `page` in different loop scopes within the same async function triggers mypy `name-defined` error — use distinct names like `crawled` for the second loop
  - `selectinload` chaining (e.g., `selectinload(InternalLink.target_page).selectinload(CrawledPage.keywords)`) works for multi-hop eager loading and requires `result.unique().scalars().all()` to deduplicate
  - `ContentBrief.page_id` (not `crawled_page_id`) is the FK column name — inconsistent with other models like PageContent/PageKeywords which use `crawled_page_id`
  - `func.count().label("count")` with `.group_by()` returns tuples — access via positional index `row[0]`, `row[1]`
---

## 2026-02-10 - S9-023
- Added 3 manual link management endpoints to `backend/app/api/v1/links.py`:
  - POST `/{project_id}/links` — validates self-links, duplicates, silo integrity (auto-detects scope/cluster from ClusterPage membership), injects link via rule-based or LLM fallback, creates InternalLink with status='verified', returns 201
  - DELETE `/{project_id}/links/{link_id}` — rejects mandatory links (400), uses BeautifulSoup to find and `.unwrap()` the `<a>` tag matching anchor text + href, sets status='removed', returns 204
  - PUT `/{project_id}/links/{link_id}` — finds `<a>` tag by matching current anchor text (disambiguates by href), replaces `.string` with new anchor text, updates InternalLink row, returns updated link
- Added imports: `AddLinkRequest`, `EditLinkRequest`, `BeautifulSoup`, `Tag`, `Response`, `LinkInjector`
- Router now has 8 total routes
- **Files changed:**
  - `backend/app/api/v1/links.py` (added 3 endpoints + imports)
- **Learnings:**
  - `from bs4 import BeautifulSoup, Tag` does NOT need `# type: ignore[attr-defined]` — only `NavigableString` triggers that (mypy flags unused ignore comments)
  - For DELETE endpoints returning 204, use `-> Response` return type with `return Response(status_code=status.HTTP_204_NO_CONTENT)` rather than `None` return
  - Scope auto-detection for manual links: query ClusterPage for both source and target, check for shared cluster_id via set intersection — avoids requiring scope in the request body
  - BeautifulSoup `Tag.string = "new text"` directly replaces the tag's text content, simpler than extract+insert for anchor text edits
  - `db.flush()` after content update + before commit ensures PageContent and InternalLink changes are in the same transaction
---

## 2026-02-10 - S9-024
- Verified links router already registered in `backend/app/api/v1/__init__.py` (done in S9-021)
- Created `backend/tests/test_links_api.py` with 21 integration tests covering all 8 endpoints:
  - POST `/links/plan`: success (202), 400 prerequisites not met, 400 missing cluster_id, 400 not enough pages
  - GET `/links/plan/status`: idle, during planning, complete with total_links
  - GET `/links` (link map): cluster scope with hierarchy, onboarding scope empty
  - GET `/links/page/{page_id}`: outbound + inbound lists, 404 invalid page
  - GET `/links/suggestions/{target_page_id}`: keyword + variations + counts, 404 invalid page
  - POST `/links` (add): success rule-based, 400 self-link, 400 duplicate
  - DELETE `/links/{link_id}`: success discretionary, 400 mandatory, 404 invalid
  - PUT `/links/{link_id}`: success with DB + content verification, 404 invalid
- **Files changed:**
  - `backend/tests/test_links_api.py` (new)
- **Learnings:**
  - When verifying DB state after API endpoint commits (separate session), must use `async_session_factory()` for a fresh session — the test's `db_session` has stale cached objects that don't reflect the API's committed changes
  - Ruff B905 requires `strict=True` on `zip()` calls in test code
  - Testing pipeline progress state: directly inject into module-level `_pipeline_progress` dict, clean up in `finally` block
  - Rule-based link injection works in tests when the anchor text literally appears in the HTML content (case-insensitive match)
  - `_active_plans` module-level set needs cleanup after successful plan tests to avoid 409 conflicts in subsequent tests
---

## 2026-02-10 - S9-025
- Added TypeScript interfaces and API client functions for the internal linking API to `frontend/src/lib/api.ts`
- 8 TypeScript interfaces: InternalLink, LinkMapPage, LinkMap, PageLinks, PlanStatus, AnchorSuggestions, AddLinkRequest, EditLinkRequest
- 8 API client functions: planLinks, getPlanStatus, getLinkMap, getPageLinks, addLink, removeLink, editLink, getAnchorSuggestions
- All functions follow existing apiClient pattern (get/post/put/delete convenience methods)
- Query params built with URLSearchParams for getPlanStatus and getLinkMap (scope + optional cluster_id)
- **Files changed:**
  - `frontend/src/lib/api.ts` (added types + functions section before EXPORT section)
- **Learnings:**
  - Frontend types are simplified versions of backend Pydantic schemas — no need for `Field()` metadata, just plain TS interfaces
  - The codebase puts all types AND API functions in a single `api.ts` file (no separate `types.ts`) — types are co-located with their API functions in feature sections
  - DELETE endpoints returning 204 use `apiClient.delete<void>()` which is handled by the `handleResponse` function's 204 branch returning `undefined as T`
  - URLSearchParams is the clean way to build query strings with optional params — avoids manual `?` and `&` concatenation
---

## 2026-02-10 - S9-026
- Created `frontend/src/hooks/useLinks.ts` with 9 TanStack Query hooks for internal linking
- Query hooks: `usePlanStatus` (2s polling), `useLinkMap`, `usePageLinks`, `useAnchorSuggestions`
- Mutation hooks: `usePlanLinks`, `useAddLink`, `useRemoveLink`, `useEditLink`
- Query keys factory `linkKeys` with `allForProject` prefix for broad invalidation on mutations
- Polling pattern: `refetchInterval` callback checks `data?.status === 'planning'` → returns 2000ms, otherwise `false`
- **Files changed:**
  - `frontend/src/hooks/useLinks.ts` (new)
- **Learnings:**
  - For mutations that affect multiple query keys (e.g., addLink invalidates both link map and page links), use a shared prefix key like `['projects', projectId, 'links']` with `invalidateQueries` — TanStack Query matches all queries whose key starts with the provided prefix
  - The polling pattern for plan status mirrors `useContentGenerationStatus` but with 2s interval (vs 3s for content gen) per the spec
  - Pre-existing TS error in `GenerationProgress.test.tsx:425` (index out of bounds on tuple) — unrelated to links
---

## 2026-02-10 - S9-027
- Created link planning trigger page for onboarding scope at `frontend/src/app/projects/[id]/links/page.tsx`
- Created link planning trigger page for cluster scope at `frontend/src/app/projects/[id]/clusters/[clusterId]/links/page.tsx`
- Both pages share the same structure: prerequisites checklist, Plan & Inject Links button, 4-step progress indicator with polling, auto-redirect to link map on completion, scope-specific link rules
- Prerequisites derived from content generation status: all keywords approved, all content generated (N/N), quality checks passed
- Progress polling uses `usePlanStatus` hook (2s interval) with step icons (check/spinner/circle) and page counts for steps 2-3
- Cluster variant filters content gen pages by `clusterCrawledPageIds` (same pattern as cluster content generation page)
- Auto-redirect after 1.5s delay to `/links/map` (onboarding) or `/clusters/{clusterId}/links/map` (cluster) — link map pages are future stories S9-028/S9-029
- **Files changed:**
  - `frontend/src/app/projects/[id]/links/page.tsx` (new)
  - `frontend/src/app/projects/[id]/clusters/[clusterId]/links/page.tsx` (new)
- **Learnings:**
  - Link map routes are at `/links/map` (onboarding, S9-029) and `/clusters/{clusterId}/links/map` (cluster, S9-028) — separate from the planning trigger pages
  - SVG icon components are duplicated per page (no shared icon library) — consistent with the codebase pattern in content generation pages
  - The `usePlanStatus` hook accepts an `enabled` param — set to `true` to start polling immediately on page load (catches in-progress plans if user navigates away and back)
  - Progress bar calculation: `((currentStep - 1) / 4 * 100) + (pagesProcessed / totalPages * 25)` gives smooth progress across 4 equal-weight steps
---

## 2026-02-10 - S9-028
- Created cluster link map overview page at `frontend/src/app/projects/[id]/clusters/[clusterId]/links/map/page.tsx`
- Stats sidebar: total links, pages, avg per page, validation pass rate, method breakdown (with colored dots), anchor diversity percentages
- Tree visualization: parent node (★ badge) at top → children below with ↑N (inbound) and ↓N (outbound) counts; sibling connection indicators (◄►) between linked children; rows of up to 4 children with connecting lines
- Page table: sortable columns (Page, Role, Out, In, Method, Status) with parent always pinned to top; parent row highlighted with green left border; click row → navigate to page link detail
- Validation status icons: ✓ (verified/pass), ✗ (failed with tooltip showing failed rules), ⚠ (warnings)
- Re-plan Links button with modal confirmation dialog: "This will replace all current links. Previous plan will be saved as a snapshot." — triggers `usePlanLinks` mutation then redirects to planning trigger page for progress
- Empty state when no links exist with "Plan Links" CTA linking to the planning trigger page
- Back button to project detail
- **Files changed:**
  - `frontend/src/app/projects/[id]/clusters/[clusterId]/links/map/page.tsx` (new)
- **Learnings:**
  - The `hierarchy` field in `LinkMap` response is typed as `Record<string, unknown> | null` on the frontend — needs cast to a typed `HierarchyNode` interface matching the backend `_build_hierarchy_tree` output structure (page_id, keyword, role, url, title, outbound_count, inbound_count, children)
  - For sortable tables with a pinned row (parent always at top), sort the array first then splice the parent to index 0 — avoids complex sort comparators
  - `formatMethodSummary` maps backend method keys (`rule_based`, `llm_fallback`, `generation`) to short display labels (`rule`, `LLM`, `gen`) joined by ` + ` — matches wireframe format like "1 gen + 2 rule"
  - Re-plan flow redirects to the planning trigger page (`/clusters/{clusterId}/links`) rather than showing inline progress — reuses the existing progress UI from S9-027
---

## 2026-02-10 - S9-029
- Created onboarding link map overview page at `frontend/src/app/projects/[id]/links/map/page.tsx`
- Stats sidebar: total links, pages, avg per page, validation pass rate, method breakdown, anchor diversity, plus onboarding-specific priority page stats (count, avg inbound vs non-priority avg)
- Label-grouped visualization: pages grouped by primary label (first in labels array), groups sorted by page count descending, connections between adjacent groups showing shared labels
- Page table with 3 filter controls: label dropdown (populated from unique labels across all pages), priority-only toggle checkbox, search-by-page-name input with search icon
- Table columns: page title (with ★ for priority), labels (tag chip with hover tooltip), out count, in count, method summary, validation status icon
- Priority pages float to top of sorted results; table is scrollable with max-height
- Click table row → navigate to `/projects/{id}/links/page/{pageId}` for page link detail
- Re-plan Links button with confirmation dialog → triggers `usePlanLinks` mutation then redirects to `/projects/{id}/links` planning trigger page
- Back button to project detail; breadcrumb navigation: project → Link Map
- Empty state with "Plan Links" CTA when no links exist
- **Files changed:**
  - `frontend/src/app/projects/[id]/links/map/page.tsx` (new)
- **Learnings:**
  - `[...Set]` spread syntax triggers TS2802 when `target` is below ES2015 — use `Array.from(set)` instead for Set-to-Array conversion
  - Onboarding link map has no `hierarchy` field (that's cluster-specific) — uses label grouping visualization instead, built from `LinkMapPage.labels` array
  - For the label groups visualization, grouping by first label (`labels?.[0]`) is a clean primary-label approach; connections between groups are derived from set intersection of all labels across group pages
  - Filter controls above the table (not inside table header) keeps the sortable column headers clean and simple
  - The onboarding variant's page table includes a Labels column (tag chips) instead of the cluster variant's Role column — different metadata is relevant per scope
---
