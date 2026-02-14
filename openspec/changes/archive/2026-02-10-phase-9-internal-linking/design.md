## Context

Content generation (Phase 5) produces 4 fields per page: page_title, meta_description, top_description, bottom_description. These fields currently contain zero internal links. The content_writing service already accepts `related_links` and `priority_links` parameters (via `InternalLinkItem` schema) but they are never populated.

Internal linking must work for two distinct page topologies:
- **Onboarding pages**: Flat set of crawled collection pages. Relatedness determined by label overlap. Could be 20-50+ pages per project.
- **Cluster pages**: Hierarchical parent/child structure. Parent page (seed keyword) with 5-10 child pages. Explicit silo with mandatory first-link-to-parent rule.

Both topologies share the same injection, validation, and UI infrastructure. Only the target selection algorithm differs.

Links are injected into `bottom_description` HTML (the only field with enough content to support natural link placement). Links are a separate step triggered by the user AFTER all content is generated.

### Current state

| Component | Status |
|---|---|
| `CrawledPage.source` column | Exists ("onboarding" or "cluster") |
| `CrawledPage.labels` JSONB | Exists (label overlap is the basis for onboarding linking) |
| `ClusterPage.role` | Exists ("parent" or "child") |
| `ClusterPage.crawled_page_id` FK | Exists (bridges cluster pages to crawled pages) |
| `PageKeywords.is_priority` | Exists (priority pages get more inbound links) |
| `InternalLinkItem` schema | Exists (url, anchor_text, link_type) |
| `ContentWriterRequest.related_links/priority_links` | Exists but unused |
| `LinkValidationRequest/Response` schemas | Exist but unused |
| BeautifulSoup4 | Already installed (used in content extraction) |
| Latest migration | 0023 |

## Goals / Non-Goals

**Goals:**
- Deterministic link planning algorithm that produces consistent, auditable link maps
- Two target selection modes (label-based for onboarding, hierarchical for clusters) behind a unified interface
- Hybrid injection that places ~70% of links via rule-based keyword matching and ~30% via LLM paragraph rewriting
- Validation layer enforcing all hard rules (budget, silo integrity, density, diversity, first-link)
- API for triggering planning, viewing link maps, and manual adjustments
- Frontend link map visualization with per-page drill-down and editing

**Non-Goals:**
- Cross-silo linking (onboarding ↔ cluster pages) — hard boundary, not configurable
- Real-time link updates during content editing — links are planned as a batch step
- Link scoring / SEO value estimation — we enforce rules, not predictions
- Blog linking — deferred to Phase 10 (will reuse this infrastructure)
- Automatic re-planning when content changes — user triggers manually

## Decisions

### D1: Single CrawledPage-centric model (not PageRegistry)

**Decision:** InternalLink references `crawled_pages` directly. No separate PageRegistry model.

**Rationale:** The FEATURE_SPEC proposed a PageRegistry, but CrawledPage already serves this purpose. Every page (onboarding or cluster) has a CrawledPage row. The `source` column distinguishes them. Adding a registry would duplicate data and create sync issues.

**Alternative considered:** Separate `page_registry` table as proposed in FEATURE_SPEC. Rejected because CrawledPage + source column + labels + keywords already provides everything the registry would.

### D2: Scope field on InternalLink instead of nullable cluster_id

**Decision:** InternalLink has `scope` ("onboarding" | "cluster") and nullable `cluster_id`. For onboarding, cluster_id is null and scope defines the silo boundary (all onboarding pages in the project). For clusters, cluster_id defines the silo.

**Rationale:** Clean silo boundary enforcement. Query for all links in a silo: `WHERE project_id = X AND scope = 'onboarding'` or `WHERE cluster_id = Y`.

### D3: Anchor text sources — POP keyword variations + LLM generation

**Decision:** Anchor text candidates come from 3 sources:
1. Target page's primary keyword (exact match)
2. POP content brief `keyword_variations` field (partial matches) — already stored in content_briefs table
3. LLM-generated natural phrases (2-3 per target, generated once during planning, cached in link plan)

**Rationale:** POP variations are high quality (SERP-derived) and already available. LLM generation fills the "natural" bucket cheaply (Haiku, ~$0.001 per batch).

**Alternative considered:** Only POP variations. Rejected because we need ~30% natural anchors for diversity, and POP doesn't provide those.

### D4: Injection modifies bottom_description in place

**Decision:** Link injection directly modifies `PageContent.bottom_description` HTML. The original (pre-injection) content is preserved in the `LinkPlanSnapshot.plan_data` JSONB as a rollback point.

**Rationale:** Keeping links in the actual content field means:
- Content editor shows links immediately (no merge step)
- Export includes links automatically (no special handling)
- Content review shows the final version

**Trade-off:** If user edits content after link injection, manual link edits could be lost on re-plan. Mitigated by: re-plan wipes and rebuilds all links (clean slate), and the snapshot preserves history.

### D5: LLM fallback uses Claude Haiku for cost efficiency

**Decision:** When rule-based injection can't place a link (no keyword match in content), use Claude Haiku to rewrite a single paragraph to include the link naturally.

**Prompt pattern:**
```
Rewrite this paragraph to naturally include a hyperlink to [URL] using
the anchor text "[anchor]". Keep the meaning identical. Only modify
1-2 sentences. Return only the rewritten paragraph HTML.
```

**Cost:** ~$0.0005 per paragraph rewrite. For a 24-page project with 30% fallback rate (budget 4 links × 24 pages × 30% = ~29 rewrites): ~$0.015 total.

**Alternative considered:** Skip unplaceable links entirely. Rejected because this would leave some pages under-linked and create uneven distribution.

### D6: Planning runs as a background task with polling

**Decision:** Link planning is triggered via POST endpoint, runs as a FastAPI BackgroundTask, and progress is polled via GET endpoint. Same pattern as content generation.

**Stages polled:**
1. Building link graph (instant)
2. Selecting targets & anchor text (per-page progress)
3. Injecting links into content (per-page progress)
4. Validating link rules (instant)

**Rationale:** Consistent with existing patterns. LLM fallback injection makes this non-trivial time (~30s for 24 pages).

### D7: Label overlap threshold = 2, configurable

**Decision:** Two pages are "related" (eligible to link) if they share 2+ labels. Stored as a constant, easily adjustable.

**Rationale:** 1 shared label is too loose (most pages would qualify). 3 is too strict (many pages would have zero eligible targets). Start at 2, adjust based on real data.

### D8: Priority page bonus = +2 in target scoring

**Decision:** When scoring target candidates for onboarding mode, priority pages get +2 added to their label overlap score. Effect: priority pages win tiebreakers and get roughly 2x the inbound links.

**Formula:** `score = label_overlap_count + (2 if target.is_priority else 0) - diversity_penalty`

Where `diversity_penalty` increases as a target accumulates more inbound links (prevents one page from hogging all links).

### D9: Re-planning is destructive (clean slate)

**Decision:** When "Re-plan Links" is triggered:
1. Snapshot current plan to `link_plan_snapshots`
2. Strip all `<a>` tags from `bottom_description` (restore to pre-injection state)
3. Delete all `internal_links` rows for this scope
4. Run full planning pipeline from scratch

**Rationale:** Incremental updates are fragile (what if content changed? what if a page was added?). Clean slate is simpler and more reliable. The snapshot provides history.

**Alternative considered:** Incremental re-planning (only re-plan changed pages). Rejected for MVP — complexity not justified for a batch operation that takes ~30s.

## Risks / Trade-offs

**[Risk] LLM fallback changes content meaning** → Mitigation: Haiku prompt is tightly constrained ("keep meaning identical, only modify 1-2 sentences"). User reviews all content after injection in the content editor. Validation step flags any issues.

**[Risk] Label data quality affects onboarding link quality** → Mitigation: Labels were generated in Phase 3 and are editable. If labels are too generic, users can refine them before running link planning. The 2-label threshold prevents spurious connections.

**[Risk] Re-planning after content edits loses manual link adjustments** → Mitigation: Re-plan is an explicit user action (not automatic). Snapshot preserves previous state. UI warns "This will replace all current links."

**[Risk] Paragraph density limits reduce achievable link count** → Mitigation: Budget is 3-5 links, and bottom_description typically has 6-12 paragraphs. Even with max 2 per paragraph and 50-word spacing, there's ample room.

**[Trade-off] Links only in bottom_description** → top_description is too short (1-2 sentences) for natural link placement. This is acceptable because bottom_description is where the SEO content lives.

**[Trade-off] No cross-silo linking** → Limits linking options but ensures clean topical authority. Can be added later as an opt-in feature if needed.

## Migration Plan

1. Create migration `0024_add_internal_links_and_snapshots.py`:
   - `internal_links` table with indexes on (source_page_id, target_page_id), (project_id, scope), (cluster_id)
   - `link_plan_snapshots` table with index on (project_id, scope)
   - No data migration needed (new tables only)

2. Deploy backend first (new tables + endpoints), then frontend.

3. Rollback: Drop tables. No existing data affected.

## Open Questions

None — all questions resolved in pre-design discussion with user.
