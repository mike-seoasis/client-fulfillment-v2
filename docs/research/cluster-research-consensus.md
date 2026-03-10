# Keyword Cluster Creation: Consensus Report

## From 3 Research Approaches to 1 Recommended Architecture

---

## 1. Comparative Analysis

### Approach Comparison Table

| Dimension | POP-First | LLM-First | Hybrid |
|-----------|-----------|-----------|--------|
| **Quality of suggestions** | Medium -- SERP-grounded but narrow (~10 variations per call, LSI terms are content-level not page-level) | High -- brand-aware, structured expansion across 7 modifier strategies, 10-15 collection-level keywords | Highest -- combines LLM semantic breadth (30-50 candidates) with real volume data filtering |
| **API cost per cluster** | ~21 POP credits + ~$0.05 DataForSEO = expensive | ~$0.01 total (Claude Haiku + DataForSEO) = negligible | ~$0.07 for Stages 1-3 (Claude Sonnet + DataForSEO) = very cheap |
| **Speed** | 10-20 minutes (serial POP calls, 30-60s each) | 3-5 seconds (1 LLM call + 1 DataForSEO batch) | 5-10 seconds (2 LLM calls + 1 DataForSEO batch) |
| **Implementation complexity** | High -- chaining POP calls, constructing candidates from LSI terms, managing async polling | Low -- 1 new service, ~200 lines, straightforward prompt + validation | Medium -- ~300-400 lines, but mostly composes existing services |
| **Code reuse from existing codebase** | High for POP client, but needs significant new orchestration logic for chaining | Medium -- reuses DataForSEO client and Claude client; similar patterns to PrimaryKeywordService | Highest -- explicitly reuses `enrich_with_volume()`, `calculate_score()`, `filter_to_specific()` patterns, `fetch_content_brief()` |
| **User experience** | Poor -- 10-20 min wait for cluster suggestions is unacceptable for interactive use | Excellent -- suggestions in ~3s, immediate feedback | Excellent -- suggestions in ~5-10s, richer data (volume included in results) |
| **Reliability** | Fragile -- depends on chaining multiple async POP calls; any failure breaks the chain | Robust -- 2 independent API calls, graceful fallback if DataForSEO fails | Most robust -- multiple fallback paths, graceful degradation at every stage |
| **Risk** | HIGH -- POP is being used against its design intent; no keyword discovery API; LSI-as-keywords is a category error | LOW -- main risk is zero-volume hallucination, mitigated by DataForSEO gate | LOWEST -- LLM expansion catches semantic gaps, DataForSEO catches hallucinations, LLM filtering catches cannibalization |

---

## 2. What Each Approach Gets Right

### POP-First: SERP-Grounded Validation

The POP-first report makes a crucial insight that the other two undervalue: **POP's variation overlap analysis can detect keyword cannibalization**. If two proposed cluster keywords return highly overlapping `variations` from `get-terms`, Google likely treats them as the same query. This is a signal you cannot get from LLM reasoning or DataForSEO volume data alone.

**Best element to keep:** POP as an *optional validation step* for detecting cannibalization between proposed cluster pages. Not as the primary driver, but as a quality gate.

The POP-first report also honestly concludes that POP should NOT be the primary driver -- this self-awareness makes its validation-role recommendation more credible.

### LLM-First: Brand-Aware Structured Expansion

The LLM-first report nails the **prompt engineering strategy**. Its multi-strategy prompt (demographic, attribute, price, use-case, comparison, seasonal, material modifiers) is more structured and comprehensive than the hybrid report's simpler prompt. The explicit strategy labels also provide transparency to the user about *why* each suggestion was made.

**Best elements to keep:**
- The 7-strategy expansion prompt (more structured than the hybrid's simpler prompt)
- Brand config injection (`build_brand_context_for_clustering()`) -- makes suggestions relevant to the actual brand
- Using Haiku for the generation step (cheaper, sufficient for structured expansion)
- The over-generate-and-filter strategy (generate 12-15, validate, return top 5-10)

### Hybrid: Pipeline Architecture + Code Reuse Map

The hybrid report provides the most detailed **implementation blueprint**. Its stage-by-stage pipeline with clear inputs/outputs at each stage, its explicit code reuse map (showing which existing functions to call), and its cost-efficient funnel shape (cheap expansion at the top, expensive POP only on approved keywords) represent the best architectural thinking.

**Best elements to keep:**
- 5-stage funnel architecture (expand -> enrich -> filter -> approve -> optimize)
- Explicit code reuse map with reuse levels (direct/adapt/new)
- Two-LLM-call design (one for expansion, one for filtering with volume data)
- Parent/child role assignment in Stage 3
- Clear separation: POP is Stage 5 (post-approval), not Stages 1-3

---

## 3. FINAL Recommended Architecture

### Pipeline Overview

```
User enters seed keyword
         |
  [Stage 1: LLM Candidate Generation]     Claude Haiku ~$0.004, ~0.5s
         |  15-20 candidates
         v
  [Stage 2: DataForSEO Volume Enrichment]  ~$0.05, ~2s
         |  Candidates + volume/CPC/competition
         v
  [Stage 3: LLM Filtering + Clustering]    Claude Haiku ~$0.004, ~1s
         |  8-12 scored cluster pages with parent/child roles
         v
  [Stage 4: User Approval]                 Interactive UI
         |  5-10 approved keywords
         v
  [Stage 5: POP Content Briefs]            Existing pipeline, POP credits
         |  Full content optimization data
         v
  [Existing Content Pipeline]              Brief -> Write -> Check
```

### Stage-by-Stage Specification

#### Stage 1: LLM Candidate Generation

- **Service:** `ClusterKeywordService._generate_candidates()`
- **API:** Claude Haiku 4.5 (sufficient for structured expansion; cheaper than Sonnet)
- **Input:** Seed keyword + brand config context (from `BrandConfig.v2_schema`)
- **Prompt:** Use the LLM-first report's 7-strategy prompt (demographic, attribute, price, use-case, comparison, seasonal, material modifiers) with brand context injection
- **Output:** 15-20 candidate keywords as structured JSON (keyword, expansion_strategy, rationale, estimated_intent)
- **Existing code to reuse:**
  - `BrandConfigService` for loading brand context
  - `ClaudeClient.complete()` for the LLM call
  - JSON parsing patterns from `brand_config.py`
- **New code needed:** Cluster-specific prompt template, `build_brand_context_for_clustering()` helper, response parser

#### Stage 2: DataForSEO Volume Enrichment

- **Service:** `ClusterKeywordService._enrich_with_volume()`
- **API:** DataForSEO Google Ads Search Volume (batch)
- **Input:** 15-20 keyword strings from Stage 1
- **Output:** Same keywords enriched with: `search_volume`, `cpc`, `competition`, `competition_level`, `monthly_searches`
- **Existing code to reuse (DIRECT -- no changes):**
  - `DataForSEOClient.get_keyword_volume_batch()` from `backend/app/integrations/dataforseo.py`
  - `PrimaryKeywordService.enrich_with_volume()` pattern from `backend/app/services/primary_keyword.py`
- **New code needed:** None for the enrichment itself. Just wire it in.
- **Optional enhancement:** Also call `DataForSEOClient.get_keyword_suggestions()` on the seed keyword to discover candidates the LLM missed. Adds ~$0.01, can be toggled via config.

#### Stage 3: LLM Filtering + Clustering

- **Service:** `ClusterKeywordService._filter_and_assign_roles()`
- **API:** Claude Haiku 4.5
- **Input:** Enriched keyword list (keyword + volume + CPC + competition data)
- **Output:** 8-12 keywords with:
  - `role`: "parent" or "child"
  - `keyword`: The collection page keyword
  - `search_volume`, `cpc`, `competition`: From Stage 2
  - `composite_score`: Volume * 0.6 + relevance * 0.4
  - `url_slug`: Auto-generated from keyword
  - `reasoning`: 1-sentence explanation
- **Existing code to reuse:**
  - `PrimaryKeywordService.filter_to_specific()` pattern (adapt prompt)
  - `PrimaryKeywordService.calculate_score()` logic (direct reuse)
- **New code needed:** Cluster-specific filtering prompt, parent/child assignment logic, URL slug generation

#### Stage 4: User Approval (Frontend)

- **UI:** Adapted from existing keyword approval screen (onboarding Step 4.4)
- **Shows:** Keyword, role (parent/child), search volume, CPC, competition, composite score, URL slug, reasoning
- **Actions:** Approve/reject each suggestion, edit URL slug, reassign parent, add custom keyword
- **Existing code to reuse:** Keyword approval components from onboarding flow
- **New code needed:** Parent/child visual indicators, cluster-specific layout, URL slug editor

#### Stage 5: POP Content Briefs (Post-Approval)

- **Service:** Existing `fetch_content_brief()` from `backend/app/services/pop_content_brief.py`
- **API:** POP `get-terms` + `create-report` + `get-custom-recommendations` (existing 3-step flow)
- **Input:** Each approved keyword (with `page_not_built_yet=True`)
- **Output:** Full `ContentBrief` records (LSI terms, competitor data, heading targets, word count targets)
- **Existing code to reuse (DIRECT -- no changes):**
  - `POPClient` from `backend/app/integrations/pop.py`
  - `fetch_content_brief()` from `backend/app/services/pop_content_brief.py`
  - `ContentBrief` model from `backend/app/models/content_brief.py`
- **New code needed:** None. Existing pipeline handles everything.

### Data Model

```python
# backend/app/models/keyword_cluster.py (NEW)

class KeywordCluster(Base):
    __tablename__ = "keyword_clusters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    seed_keyword: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)  # Display name, defaults to seed keyword
    status: Mapped[str] = mapped_column(default="draft")
    # Statuses: "draft" -> "approved" -> "generating" -> "complete"
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="clusters")
    pages: Mapped[list["ClusterPage"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")


class ClusterPage(Base):
    __tablename__ = "cluster_pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("keyword_clusters.id"), nullable=False)
    keyword: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)  # "parent" or "child"
    url_slug: Mapped[str] = mapped_column(nullable=False)
    expansion_strategy: Mapped[str | None] = mapped_column(nullable=True)  # Which modifier strategy generated this
    reasoning: Mapped[str | None] = mapped_column(nullable=True)

    # Volume data from DataForSEO
    search_volume: Mapped[int | None] = mapped_column(nullable=True)
    cpc: Mapped[float | None] = mapped_column(nullable=True)
    competition: Mapped[float | None] = mapped_column(nullable=True)
    competition_level: Mapped[str | None] = mapped_column(nullable=True)
    composite_score: Mapped[float | None] = mapped_column(nullable=True)

    # Approval
    is_approved: Mapped[bool] = mapped_column(default=False)

    # Link to CrawledPage once approved and page is created
    crawled_page_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crawled_pages.id"), nullable=True)

    # Relationships
    cluster: Mapped["KeywordCluster"] = relationship(back_populates="pages")
    crawled_page: Mapped["CrawledPage | None"] = relationship()
```

### API Endpoints

```
POST   /api/v1/projects/{project_id}/clusters
       Body: { "seed_keyword": "trail running shoes" }
       Response: { cluster_id, seed_keyword, suggestions: [ClusterPage...] }
       Triggers: Stages 1-3 (returns in ~5-10 seconds)

GET    /api/v1/projects/{project_id}/clusters
       Response: List of all clusters for the project

GET    /api/v1/projects/{project_id}/clusters/{cluster_id}
       Response: Full cluster with all pages

PATCH  /api/v1/projects/{project_id}/clusters/{cluster_id}/pages/{page_id}
       Body: { "is_approved": true, "url_slug": "custom-slug" }
       Approves/rejects individual cluster pages

POST   /api/v1/projects/{project_id}/clusters/{cluster_id}/approve
       Bulk-approves all pages and triggers Stage 5 (POP briefs + content pipeline)
       Creates CrawledPage + PageKeywords records for each approved page

DELETE /api/v1/projects/{project_id}/clusters/{cluster_id}
       Deletes a cluster and all its pages (if not yet approved)
```

### Frontend Pages/Components

| Component | Type | Description |
|-----------|------|-------------|
| `ClusterCreationPage` | Page | Entry point -- seed keyword input, triggers generation |
| `ClusterSuggestionsPanel` | Component | Displays Stage 1-3 results with loading state |
| `ClusterPageCard` | Component | Individual suggestion card: keyword, role badge, volume, score, approve/reject toggle |
| `ClusterParentBadge` | Component | Visual indicator for parent vs child pages |
| `ClusterApprovalToolbar` | Component | Bulk approve, URL slug editor, add custom keyword |
| `ClusterListView` | Component | Dashboard showing all clusters for a project |

### Estimated Cost Per Cluster

| Stage | API | Cost |
|-------|-----|------|
| Stage 1: LLM Candidates | Claude Haiku 4.5 | ~$0.004 |
| Stage 2: Volume Enrichment | DataForSEO batch | ~$0.05 |
| Stage 2b: Extra Suggestions (optional) | DataForSEO suggestions | ~$0.01 |
| Stage 3: LLM Filtering | Claude Haiku 4.5 | ~$0.004 |
| **Stages 1-3 total** | | **~$0.06-0.07** |
| Stage 5: POP Briefs (per approved page) | POP get-terms + create-report | 2 credits/page |
| Stage 5: Content Writing (per approved page) | Claude Sonnet | ~$0.02/page |
| **Full cluster (10 pages)** | | **~$0.27 + 20 POP credits** |

The critical takeaway: Stages 1-3 (the *cluster creation* part) cost only ~$0.07 and take ~5-10 seconds. The expensive part (POP briefs + content writing) only runs *after* user approval -- so you never waste credits on rejected suggestions.

---

## 4. Key Decisions for Mike

### Decision 1: Use Haiku or Sonnet for cluster generation?

- **Haiku** (~$0.004/cluster): Cheaper, sufficient for structured expansion with a well-crafted prompt. The LLM-first report recommends this.
- **Sonnet** (~$0.01/cluster): More nuanced reasoning, better at avoiding cannibalization in Stage 3 filtering. The hybrid report uses this.
- **Recommendation:** Start with **Haiku for Stage 1** (structured expansion is formulaic) and **Sonnet for Stage 3** (filtering + role assignment needs more judgment). Total ~$0.007/cluster. If Haiku produces good enough filtering results, switch Stage 3 to Haiku too.
- **This is a low-stakes decision** -- the cost difference is fractions of a cent. Easy to test both and compare quality.

### Decision 2: Include DataForSEO keyword suggestions as a supplementary source?

- **Yes** (+$0.01/cluster): Call `get_keyword_suggestions()` on the seed keyword to catch long-tail variations the LLM might miss. Merge into the candidate pool before Stage 2 enrichment.
- **No** (save $0.01): Rely solely on LLM expansion. Simpler pipeline.
- **Recommendation:** **Yes, include it.** The marginal cost is negligible and it provides a real-data safety net for the LLM's blind spots. But make it toggleable so it can be disabled if DataForSEO costs become a concern.

### Decision 3: Include optional POP cannibalization check?

- **Yes** (+5-10 POP credits, +2-5 min): After Stage 3, run `get-terms` on the top 5-10 cluster keywords and compare variation overlap. Flag pairs with >70% overlap as cannibalization risks.
- **No** (save credits + time): Trust the LLM's judgment on cannibalization in Stage 3.
- **Recommendation:** **Skip for v1.** The LLM is reasonably good at detecting "women's trail running shoes" vs "trail running shoes for women" as duplicates. POP validation adds real value but also adds significant latency. Revisit if users report cannibalization issues.

### Decision 4: Minimum volume threshold for suggestions?

- **10** (LLM-first recommendation): Very permissive, includes ultra-niche terms.
- **50**: Reasonable minimum for a collection page worth building.
- **100** (hybrid recommendation): More conservative, ensures meaningful traffic potential.
- **Recommendation:** Default to **50**, make it configurable per-project. Some niche brands might want 10, mass-market brands might want 100+.

### Decision 5: Maximum pages per cluster?

- **5-8**: Focused, easier to manage.
- **10-15**: Comprehensive coverage of the topic.
- **Recommendation:** Default to **10** (1 parent + 9 children). Show all suggestions but default-approve only the top 10 by composite score. User can approve more if desired.

### Decision 6: Skip DataForSEO entirely for an even simpler v1?

- Some users may not care about volume data and just want LLM-generated suggestions they can approve quickly.
- **Not recommended** for v1. Volume data is the single most important quality signal. Without it, you're publishing based on vibes. The DataForSEO call costs $0.05 and takes 2 seconds -- the ROI is enormous.

---

## 5. Implementation Order

### Phase A: Core Pipeline (Stages 1-3) -- Build First

1. **Create `KeywordCluster` and `ClusterPage` database models** + migration
   - New file: `backend/app/models/keyword_cluster.py`
   - Add to `backend/app/models/__init__.py`
   - Create Alembic migration

2. **Create `ClusterKeywordService`** with Stages 1-3
   - New file: `backend/app/services/cluster_keyword.py`
   - `_generate_candidates()` -- Stage 1 (LLM expansion with 7-strategy prompt)
   - `_enrich_with_volume()` -- Stage 2 (reuses DataForSEO batch)
   - `_filter_and_assign_roles()` -- Stage 3 (LLM filtering + parent/child)
   - `generate_cluster()` -- Orchestrator that calls Stages 1-3

3. **Create API endpoints** for cluster CRUD
   - New file: `backend/app/api/v1/clusters.py`
   - POST create, GET list, GET detail, PATCH approve/reject, POST bulk-approve, DELETE

4. **Write tests** for ClusterKeywordService
   - Mock Claude and DataForSEO responses
   - Test the full pipeline with fixtures
   - Test edge cases (no volume data, LLM returns no results, etc.)

### Phase B: Frontend UI -- Build Second

5. **Create cluster creation page**
   - Seed keyword input
   - Loading state (5-10s) with progress indicator
   - Suggestions display with approve/reject

6. **Create cluster list view**
   - Dashboard showing all clusters for a project
   - Status indicators (draft, approved, generating, complete)

### Phase C: Integration with Existing Pipeline -- Build Third

7. **Wire approved clusters into existing content pipeline**
   - On bulk-approve: create `CrawledPage` + `PageKeywords` records
   - Trigger `fetch_content_brief()` for each approved page
   - Feed into existing `run_content_pipeline()`

8. **Add cluster context to content generation prompts**
   - Pass parent/child relationships to content writers
   - Ensure internal linking follows cluster hierarchy (parent links to children and vice versa)

### Phase D: Enhancements -- Build Later

9. **POP cannibalization check** (optional Stage 3.5)
10. **DataForSEO keyword suggestions** as supplementary source
11. **Cluster analytics** (total volume, estimated traffic, content coverage %)
12. **Re-cluster**: Allow users to re-run Stages 1-3 with different seed keyword or parameters

---

## 6. Summary

All three reports converge on the same fundamental insight: **LLM for candidate generation, DataForSEO for volume validation, POP for downstream content optimization.** The only real disagreement was about POP's role -- and even the POP-first report concluded POP should not be the primary driver.

The recommended architecture takes:
- **From POP-first:** The idea that POP variation overlap can detect cannibalization (saved for a future enhancement)
- **From LLM-first:** The 7-strategy structured prompt, brand config injection, Haiku for cheap expansion, and the over-generate-and-filter pattern
- **From Hybrid:** The 5-stage funnel architecture, explicit code reuse map, parent/child role assignment, and the principle that expensive APIs (POP) should only run on user-approved keywords

The result is a pipeline that generates high-quality, brand-aware, volume-validated cluster suggestions in ~5-10 seconds for ~$0.07, with the existing content pipeline handling everything downstream.
