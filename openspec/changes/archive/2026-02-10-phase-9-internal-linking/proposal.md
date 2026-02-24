## Why

Content generation produces isolated pages with no internal links. Without internal linking, the generated content has zero SEO topical authority signals — Kyle Roof's research shows 2 internal links with silo structure beat 1 external DA-100 link, while the Zyppy 23M link study shows anchor text diversity is the #1 ranking factor for internal links. Both onboarding pages and cluster pages need structured internal links injected into their content before export.

## What Changes

- New `InternalLink` model (SQL edge table) tracking source page, target page, anchor text, placement method, and status
- New `LinkPlanSnapshot` model for auditing and re-planning
- New `SiloLinkPlanner` service with two target selection modes:
  - **Cluster mode**: Hierarchical parent/child linking with mandatory first-link-to-parent rule
  - **Onboarding mode**: Flat label-based relatedness with priority page weighting
- New `AnchorTextSelector` with global diversity tracking (50-60% partial, ~10% exact, ~30% natural)
- New hybrid link injection pipeline:
  - Rule-based: BeautifulSoup keyword scanning to wrap existing text in `<a>` tags
  - LLM fallback: Claude rewrites paragraphs to naturally include links (~30% of placements)
- New link validation layer enforcing: budget (3-5/page), silo integrity, density limits (max 2/paragraph, min 50 words between), anchor diversity, first-link rule (clusters), direction rules
- New API endpoints: trigger link planning, get link plan per page, get link map per silo/project, manual link add/remove/edit
- New frontend link map UI with two variants:
  - Cluster: tree hierarchy visualization (parent → children → siblings)
  - Onboarding: label-grouped flat view with relatedness connections
- New per-page link detail view with outbound/inbound lists, anchor editing, and manual add/remove
- Link planning integrated as a step AFTER content generation, BEFORE content review

## Capabilities

### New Capabilities

- `link-planning`: Core link planning algorithm — graph construction, budget calculation, target selection (cluster hierarchical + onboarding label-based), anchor text selection with diversity tracking
- `link-injection`: Hybrid link injection into existing content — BeautifulSoup rule-based placement + LLM fallback paragraph rewriting + validation layer
- `link-management-api`: API endpoints for triggering link planning, retrieving link maps, and manual link adjustments (add/remove/edit anchor text)
- `link-map-ui`: Frontend link map visualization (cluster tree + onboarding label-grouped), per-page link detail view, manual editing controls, planning progress indicator

### Modified Capabilities

- `matrixify-export`: Export must include injected internal links in the HTML content (links are already in `bottom_description` HTML after injection, so this should work automatically — verify only)

## Impact

- **New models**: `InternalLink`, `LinkPlanSnapshot` + Alembic migration
- **New services**: `SiloLinkPlanner`, `AnchorTextSelector`, `LinkInjector`, `LinkValidator`
- **Modified services**: Content generation pipeline gains a new post-generation step; `content_writing.py` already accepts `related_links`/`priority_links` params (currently unused)
- **New API routes**: `backend/app/api/v1/links.py` (6-8 endpoints)
- **New frontend pages**: Link planning trigger, link map overview, per-page link detail
- **Dependencies**: BeautifulSoup4 (likely already installed), Claude API (for LLM fallback injection)
- **Database**: New migration for `internal_links` + `link_plan_snapshots` tables
- **Schemas**: New Pydantic v2 schemas for link planning requests/responses (existing `InternalLinkItem` and `LinkValidationRequest` schemas in `content_writer.py` and `link_validator.py` provide partial scaffolding)
