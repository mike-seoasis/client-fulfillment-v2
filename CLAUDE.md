# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

---

## V2 Rebuild: Slice-Based Development

This project is being rebuilt using vertical slices. Each slice is a complete feature from database to UI.

### Session Start Protocol

At the start of EVERY session:
1. Read `V2_REBUILD_PLAN.md` — Check current status, where we are
2. Read relevant section of `FEATURE_SPEC.md` — Feature details for current slice
3. Read relevant section of `WIREFRAMES.md` — UI reference for current slice
4. Tell the user: "We're on Phase X, Slice Y. Last session we completed Z. Next up is W."

If user says "Let's continue" — follow this protocol automatically.

### Slice Completion Protocol

When completing ANY slice or significant milestone, you MUST:

1. **Update V2_REBUILD_PLAN.md:**
   - Mark completed checkboxes with `[x]`
   - Update the "Current Status" section at the top
   - Add a row to the Session Log table

2. **Commit with slice reference:**
   - Format: `feat(slice-X): Description`
   - Example: `feat(slice-1): Add project list endpoint and dashboard UI`

3. **Verify before moving on:**
   - All tests passing
   - Manual verification criteria met
   - Status file updated

**DO NOT proceed to next slice without completing these steps.**

### OpenSpec + Ralph Integration

Each slice uses OpenSpec for planning and Ralph TUI for execution:
- `/opsx:new "Slice X: Name"` — Start planning
- Convert tasks to `prd.json` for Ralph execution
- Final tasks always include status file updates
- `/opsx:verify` — Confirm completion before archiving

**IMPORTANT:** When converting tasks to prd.json for Ralph, ALWAYS read `openspec/templates/slice-template.md` first and follow its structure exactly. This ensures:
- Correct task ID format (S{X}-NNN)
- Required final tasks are included (status update + verification)
- Proper prd.json schema for Ralph TUI

### Pre-Flight Checklist (Before Starting Any Slice)

Before writing any code for a new slice, verify:
- [ ] Previous slice is complete and archived
- [ ] V2_REBUILD_PLAN.md status is current
- [ ] You've read the relevant FEATURE_SPEC.md section
- [ ] You've read the relevant WIREFRAMES.md section
- [ ] Branch created: `feature/slice-X-[name]`

### Post-Flight Checklist (After Completing Any Slice)

Before moving to the next slice, verify:
- [ ] All tests passing
- [ ] Manual verification criteria met
- [ ] V2_REBUILD_PLAN.md updated (checkboxes, status, session log)
- [ ] Commit made with `feat(slice-X):` prefix
- [ ] OpenSpec change archived

---

## Design Context

### Users
Internal operations team onboarding new clients. They need efficiency but also an interface that feels premium—something they're proud to work in daily. The tool should make their job feel elevated, not like data entry.

### Brand Personality
**Warm, helpful, human.** The interface should feel like a knowledgeable colleague rather than cold software. Approachable but polished. Friendly without being casual. Premium without being pretentious.

### Aesthetic Direction
- **Visual tone:** Light, airy, tropical oasis. Soft sandy neutrals with lush green accents. Think palm fronds, natural materials, breathing room.
- **Reference:** Airtable's approachable flexibility, but with tropical resort warmth
- **Anti-reference:** Dense enterprise dashboards, cold corporate blues, cluttered interfaces
- **Theme:** Light mode only—supports the airy, sophisticated aesthetic
- **Color palette:** Tropical oasis palette:
  - **palm** (primary accent): Sage/forest greens for buttons, highlights, icons
  - **sand/cream** (backgrounds): Warm sandy neutrals, light and airy
  - **coral** (secondary accent): Soft terracotta for alerts, warnings, tropical warmth
  - **lagoon** (tertiary accent): Teal for links, info states, water element
  - **warm-gray** (text/borders): Natural, earthy neutrals

### Design Principles

1. **Breathe** — Generous whitespace. Let elements float. Never crowd the interface. Sophistication lives in what you leave out.

2. **Warm the details** — Soft shadows over hard edges. Sharp, refined corners (`rounded-sm`). Warm grays over cool. Every micro-decision should add warmth.

3. **Guide gently** — Clear visual hierarchy. Obvious next steps. The interface should feel like a helpful hand, not a demanding form.

4. **Elevate the mundane** — Even routine tasks should feel considered. Thoughtful transitions, pleasant feedback, small moments of polish.

5. **Respect the work** — Clean, scannable, efficient. Premium doesn't mean slow. The team should feel capable and fast, not bogged down by decoration.

### Technical Notes
- Accessibility: Standard best practices (reasonable contrast, keyboard navigation, semantic HTML)
- Typography: Favor readable, friendly typefaces with good weight variety
- Motion: Subtle, purposeful—enhance understanding, never distract
- Border radius: Use `rounded-sm` (0.25rem) as the standard for all UI elements (cards, buttons, inputs). Sharp, refined corners feel more premium than soft/bubbly ones.
- Borders: Use `border-sand-500` (or `border-cream-500`, same values) for card borders to ensure visibility against the background.
- Buttons: Primary buttons use `bg-palm-500` (green). Secondary use `bg-sand-200`. Danger use `bg-coral-500`.
- Focus rings: Use `ring-palm-400` for focus states.
