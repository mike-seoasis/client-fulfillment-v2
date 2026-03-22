# UX Improvement Plan

> Living document tracking UX improvements identified through usage pain points.

---

## Area 1: Data Import Flow

### Pain Points Identified
1. **Upload then delete loop** — No preview/confirmation before URLs commit to the database. Wrong URLs get crawled, then must be manually deleted.
2. **Can't redo a single page mid-flow** — Once a page has gone through keywords/content/links, there's no clean way to re-run just one stage for one page. Only option is reset the entire onboarding.
3. **Adding more pages later is opaque** — Batch system exists but UX doesn't surface it. Unclear what happens to new URLs when existing pages are already further along in the pipeline.

### Proposed Changes

#### 1a. Pre-submit validation + preview step
- After paste/CSV, show URL chips with status indicators (valid/invalid/duplicate/already-exists)
- Users fix issues *before* anything hits the database
- Clear count summary: "12 new URLs, 3 duplicates skipped, 1 invalid"
- Explicit "Start Crawl" action separated from "Add URLs"

#### 1b. Per-page pipeline re-entry
- Per-page status tracking across all pipeline stages (crawl → labels → keywords → content → links)
- Action buttons per page: "Re-crawl", "Re-generate keywords", "Re-generate content"
- Only affects the single page, not the batch
- Downstream stages auto-invalidate when upstream is re-run (re-crawl clears keywords + content)

#### 1c. First-class "Add More URLs" action
- Available from any step in the wizard (not just the upload step)
- Clear messaging: "These 5 new URLs will start from crawling while your existing 47 pages continue in the keywords step"
- New URLs appear in the same page list with a "catching up" indicator
- No disruption to pages already further along in the pipeline

---

## Area 2: Multi-Step Wizard Flow

### Current Flow (6 steps)
1. **Upload** — Paste URLs or CSV
2. **Crawl & Label** — Monitor crawl, auto-label, edit labels
3. **Keywords** — Generate primary keywords, approve/edit each
4. **Content Generation** — 4-phase pipeline (Brief → Write → QA → Links)
5. **Content Review** — Rich editor + QA sidebar, approve per page
6. **Export** — Select pages, download Matrixify CSV

### Known Friction
- Linear wizard forces sequential progression even when some pages could advance independently
- Gate checks (e.g. "all keywords approved") block entire batch for one straggler
- Going back to fix something mid-flow is disorienting — unclear what state you're returning to
- No overview of where all pages are across the pipeline simultaneously
- Batch concept adds complexity without proportional UX benefit

### Exploration Areas (Under Investigation)
- Should the wizard be replaced with a pipeline/kanban view?
- Can pages progress independently through stages?
- How should partial completion and re-entry work?
- What's the right balance between guided flow and flexibility?
- How should the UI handle mixed states (some pages at keywords, others at content)?

*See agent research below for detailed proposals.*

---

## Research Notes

*(To be populated with findings from UX exploration agents)*
