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
