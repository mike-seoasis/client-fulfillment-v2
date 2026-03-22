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

## Research Notes: Multi-Step Wizard UX

> Six AI agents explored wizard improvements from three expert perspectives, each with a champion (proposing ideas) and a devil's advocate (stress-testing them). Below is the synthesis.

### The Core Tension

**Champion thesis (Maya):** "This isn't a wizard problem, it's a pipeline problem. The wizard was fighting the reality that pages move through stages independently."

**Devil's advocate thesis (Maya):** "The linear structure is a feature, not a bug. The steps have causal dependencies — labels feed keywords feed briefs feed content feed QA. The wizard protects those dependencies."

**Resolution (Derek):** "Speed comes from reducing *unnecessary* friction. Quality comes from preserving *intentional* friction. The art is knowing which is which."

---

### Proposals Evaluated (Champion → Devil's Advocate Verdict)

#### 1. Replace Wizard with Kanban Pipeline Board
- **Champion case:** Pages as cards, moving through columns independently. Instant visibility, drag-to-reorder, auto-advance on completion.
- **DA rebuttal:** Most transitions are *automated*, not human-driven. You'd end up with 80 cards sitting in "Content Generation" with spinners. It's "a dashboard cosplaying as a workspace." You still need dedicated step UIs for actual work (editing content, reviewing keywords), so you maintain both the kanban AND the step views.
- **Verdict: NO as primary UI. YES as a read-only overview component.** Use kanban-style visualization as a status bar/header, not the workspace. Click through to purpose-built step views.

#### 2. Let Pages Progress Independently (Streaming Gates)
- **Champion case (Derek):** The backend already supports per-URL processing. The gate is purely a frontend constraint. Approved items should flow forward immediately. "Converts a blocking operation into a non-blocking one."
- **DA rebuttal (Maya):** Cross-page operations (cannibalization detection, internal linking, site-wide keyword strategy) need a stable set of pages at each stage. Fully independent progression creates "an eventually-consistent distributed system" — bad for content deliverables.
- **Verdict: YES, with cohort boundaries.** Let operators define batches manually. Within a batch, items progress independently. Cross-page operations run within complete batches. Stragglers get a "Hold" state, not a blocker.

#### 3. Dashboard Overview of All Pages
- **Champion case:** Persistent progress strip showing aggregate pipeline stats — segmented bar sized by pages-per-stage. Click to filter.
- **DA rebuttal:** "A dashboard is only as good as the actions it enables." If it just links to step views, it's a fancy nav menu. If it tries to do inline editing, you rebuild every step as a widget. "The dashboard trap" — 3 sprints to build, 6 sprints trying to make it do things.
- **Verdict: YES, ruthlessly scoped.** Progress visualization bar (read-only) + "needs attention" list with one-click navigation. No inline editing. 5-second orientation, then go to the real workspace.

#### 4. Non-Linear Navigation (Jump to Any Step)
- **Champion case:** Let operators jump back to fix labels, keywords, etc. without losing their place.
- **DA rebuttal:** Changing a label at step 2 invalidates keywords (step 3) which invalidates content (step 4). "Non-linear access without robust state management creates a system where users can accidentally destroy hours of work." Manual keyword edits lost on re-generation.
- **Verdict: YES for viewing, NO for casual editing.** Allow viewing any step anytime. Gate editing behind an explicit "revise" action that communicates downstream impact: "Changing this label will require regenerating keywords and content for this page. Your manual keyword edits will be lost. Continue?"

#### 5. Inline Editing Everywhere (Unified Table)
- **Champion case:** One powerful table view — URL, label, keywords, content status — all editable inline.
- **DA rebuttal:** Content review needs a rich text editor with QA sidebar. That's not a table cell. "You build a mediocre version of every step, crammed into a table." Edits in one column invalidate data in others. State management nightmare.
- **Verdict: YES as read-only triage/status table. NO as the editing surface.** Table for scanning, sorting, filtering, navigation. Click a row to enter the purpose-built step view. Simple fields (labels, keyword approve/reject) can be inline; complex ones cannot.

#### 6. Full End-to-End Automation
- **DA verdict:** "Quality failures that are invisible until they reach the client." Garbage crawl data → nonsensical keywords → plausible-looking wrong content → shipped.
- **Verdict: NO for full auto. YES for happy-path segments.** Crawl-to-keywords can auto-run. Pause before content generation with a lightweight checkpoint: "52 pages look good. 8 have issues. Review flagged pages before proceeding?"

#### 7. Keyboard Shortcuts for Everything
- **Champion case (Derek):** `Space-A` to approve keyword, tab to next. 5x speed on repetitive steps.
- **DA rebuttal:** "When you make approval frictionless, you make rubber-stamping frictionless." At Stripe, keyboard shortcuts dropped review time from 45s to 8s — and approval rates went from 74% to 96%. The reviews got worse, not the cases.
- **Verdict: YES for navigation, CAREFUL for approval.** Keyboard nav (J/K/Tab/arrows) — absolutely. Single-key approval — only with guardrails. Require a two-key deliberate action for approvals. Keep "getting to the decision" fast without making the decision automatic.

#### 8. Batch Operations Everywhere
- **DA verdict:** Batch delete = low risk. Batch regenerate = cost risk (API tokens). Batch approve = quality risk.
- **Verdict: YES, tiered by risk.** Batch delete/re-crawl: freely available. Batch regenerate: with cost estimate. Batch approve: only for items already individually viewed/reviewed. Track a "viewed" state per page.

#### 9. Smart Triage Queue
- **Champion case (Priya):** Sort by attention score — QA failures first, low confidence next, clean pages last.
- **DA rebuttal:** Creates two-tier attention. Top items get careful review, bottom items get rubber-stamped. "Items at the bottom get 'I've been reviewing for an hour and I just want to finish' attention."
- **Verdict: YES for surfacing problems, with randomization.** Priority-sorted overview for choosing which *section* to tackle. Within a section, review in logical order (by URL structure, by content type). Randomize within confidence tiers. Add "random deep review" checks to prevent fatigue-driven rubber-stamping.

---

### AI-Specific Proposals Evaluated

#### 10. Confidence Scores on Keywords/Content
- **Champion case (Priya):** Green/amber/red zones. Batch-approve green, focus on amber/red.
- **DA rebuttal:** "LLM confidence measures how linguistically predictable the token was, not how factually correct or brand-appropriate the output is." A supplement keyword like "clinically proven weight loss" gets 94% confidence because it's statistically common — not because it's true for this client.
- **Verdict: INTERNAL use only.** Never expose raw scores. Use thresholds to drive presentation: "attention flag" vs. default. Never use the word "confidence." Call it "review priority."

#### 11. Prompt-to-Fix (AI Regeneration with Instructions)
- **Champion case:** Highlight text, type "make it warmer," AI regenerates just that section. Diff view shows changes.
- **DA rebuttal:** "Every regeneration is a roll of the dice." The AI might fix the tone while silently changing "ships in 5-7 days" to "fast shipping." The user focuses on evaluating their request, loses vigilance over everything else.
- **Verdict: YES, with mandatory diff view and scoped regeneration.** Constrain regeneration to the selected section only (leave rest byte-identical). Show full diff with additions/deletions. Require user to acknowledge changes outside their requested scope. Implement version history for rollback.

#### 12. QA Auto-Fix with Human Confirmation
- **Champion case:** Each QA issue (banned word, em-dash) shows proposed fix inline. "Apply Fix" or "Ignore" per issue. "Apply All Fixes" for bulk.
- **DA rebuttal:** Minimal — this is the safest proposal since fixes are shown before applying.
- **Verdict: STRONG YES.** Lowest risk, highest mechanical time savings. Show before/after per issue. Re-run QA after applying to confirm no new issues introduced. Start with deterministic fixes (banned word swaps, em-dash replacement), expand to pattern rewrites later.

#### 13. AI Reasoning/Explanations Sidebar
- **Champion case:** Show why the AI chose a keyword, what brief guided generation, what source material was used.
- **DA rebuttal:** "LLM reasoning is post-hoc rationalization." The AI generates a plausible explanation for a decision made through statistical prediction. Creates "false authority effect" — users stop applying judgment because the AI's rationale sounds sophisticated.
- **Verdict: Show INPUTS, not REASONING.** Show crawled page excerpts, the brief, source URLs. Let users draw their own conclusions. Do NOT show AI-generated explanations of its choices. Show what the AI had to work with, not what the AI thinks about its own work.

---

### Recommended Build Order

Based on impact, risk, and implementation effort:

| Priority | Change | Type | Effort | Impact |
|----------|--------|------|--------|--------|
| **P0** | Pre-submit URL validation/preview | Data Import | Low | Prevents upload-then-delete loop entirely |
| **P0** | QA auto-fix with human confirmation | AI Workflow | Low | 80-90% time savings on QA fixes |
| **P1** | Progress overview bar (read-only) | Wizard | Medium | Solves "where are all my pages?" |
| **P1** | Streaming gates with cohort boundaries | Wizard | Medium | Eliminates gate-blocking (biggest throughput win) |
| **P1** | Per-page pipeline re-entry with downstream warnings | Data Import | Medium | Solves "redo a page mid-flow" |
| **P2** | Batch review mode (read → approve/flag flow) | Wizard | Medium | 50-60% time savings on content review |
| **P2** | Batch keyword approval with attention flags | AI Workflow | Medium | 70-80% time savings on keyword step |
| **P2** | Prompt-to-fix with scoped regen + diff view | AI Workflow | Medium | Replaces manual editing for AI content |
| **P3** | Keyboard navigation (not approval) | Wizard | Low | Power-user acceleration |
| **P3** | Command palette (Cmd+K) | Wizard | Medium | Power-user acceleration (after other features exist) |
| **P3** | Inputs sidebar (crawl data, brief, sources) | AI Workflow | Low | Trust + review speed |
| **P3** | "Add More URLs" from any step | Data Import | Low | Removes confusion about batches |

### Key Design Principles (From the Debate)

1. **Preserve intentional friction.** Human review of content going on live client websites is not a bottleneck to optimize away — it's the product. Make review *efficient*, not *optional*.

2. **Show inputs, not AI opinions.** Let users see what the AI had to work with (crawl data, briefs, sources). Never show AI-generated explanations of its own choices — that's post-hoc rationalization that creates false authority.

3. **Separate reading from editing.** The overview/triage layer is read-only. Purpose-built step views are for editing. Don't try to make one view do both.

4. **Tier actions by risk.** Delete/retry = free. Regenerate = show cost. Approve = require deliberate action with "viewed" tracking.

5. **Batch by cohort, not by convenience.** Cross-page operations (linking, cannibalization) need a stable set. Let operators define cohorts. Within cohorts, stream items forward independently.

6. **The wizard stays, but breathes.** Keep the sequential structure (it protects causal dependencies). Add persistent progress visibility, quick-view navigation, and per-page re-entry. Make it feel effortless, not removed.
