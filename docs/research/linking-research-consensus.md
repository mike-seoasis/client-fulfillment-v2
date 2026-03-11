# Internal Linking Research: Consensus Report

> Synthesized from 3 independent research agents (Kyle Roof methodology, other SEO methodologies, algorithmic approaches). 2026-02-08.

---

## Your Hard Rules vs. Research Consensus

### Rule 1: First link on every sub-page = parent/silo hub
**Verdict: STRONGLY SUPPORTED. Keep as-is.**

- Kyle Roof: "Link to Target Page at the top of body content"
- Zyppy study (23M links): First link carries extra weight for anchor text signals
- Matt Diggity: Same — first link goes to money page
- Every methodology agrees on this

**Implementation note:** Enforce at both generation-time (prompt instruction) AND post-processing (validation that first `<a>` tag points to parent URL).

---

### Rule 2: No cross-silo linking
**Verdict: SUPPORTED as default. Consider configurable override for future.**

- Kyle Roof: Strict no cross-silo — "if you interlink out to different target pages, you've broken the silo"
- Semrush: Argues against strict silos, says cross-linking is beneficial
- Modern consensus: Trending toward "keep topical clarity but allow contextual cross-links"

**Recommendation:** Hard rule for MVP. The tool only generates intra-silo links. No need to build cross-silo support now. If it becomes a need later, it's additive — the data model supports it.

---

### Rule 3: Every SEO page must belong to a silo
**Verdict: UNIVERSALLY SUPPORTED. Keep as-is.**

- Every methodology agrees
- Zyppy: 53% of URLs have 3 or fewer incoming links — silo membership prevents this
- Kyle Roof: Pages exist "solely to support one target page"

---

### Rule 4: Anchor text = primary keyword or close variation, cycled
**Verdict: CORRECT DIRECTION, but needs tuning.**

Your instinct is right — cycle through keyword variations. But the research strongly says **variety** is the single most important factor:

- Zyppy (23M links): Anchor text variety correlates with traffic MORE than link count
- High-diversity sites: avg rank position 1.3 vs 3.5 for low-diversity
- Kyle Roof: Never repeat the same anchor text for the same target, keep under 5 words
- Optimal average anchor length: ~4.85 words

**Recommended distribution:**
- ~50-60% partial match / long-tail variations (what POP gives us)
- ~10% exact match primary keyword
- ~20-30% natural language / contextual anchors
- ~10% generic but descriptive

**Implementation:** POP's keyword variations are the primary source. The AnchorTextSelector algorithm scores by diversity (least-used variation wins), context fit (does the keyword appear naturally in the paragraph?), and a small primary-keyword bonus. Track usage globally to prevent repetition.

---

### Rule 5: Links only flow DOWN the funnel
**Verdict: NEEDS REFINEMENT. Core intent is correct, edge cases need clarification.**

Your core intent — collection pages should never link to blog posts — is well-supported:
- Kyle Roof: Target Page links to only ONE supporting page (and even that's debatable)
- Matt Diggity: Priority silo concentrates authority on money pages
- Funnel logic: Don't dilute commercial page authority to informational content

**But the research reveals a nuance:** "Down the funnel" should mean content-type transitions, not hierarchical position:

| Link Direction | Verdict | Why |
|---|---|---|
| Blog → Collection page | ALWAYS OK | Sending authority to money pages |
| Blog → Blog (same silo) | OK | Sibling cross-linking, Kyle Roof allows 1-2 |
| Sub-collection → Parent collection | OK | This IS "down the funnel" (child → parent) |
| Collection → Sub-collection | DEBATABLE | Kyle Roof allows TP → one SP. Your rule says no. |
| Collection → Blog | NEVER | Your rule. Strongly supported. |
| Parent collection → other collections | NEVER in body content | Nav links fine, body content no |

**Recommendation for MVP:**
- Blog → any collection in same silo: YES
- Blog → blog in same silo: YES (1-2 sibling links, per Kyle Roof)
- Sub-collection → parent collection: YES (mandatory first link)
- Sub-collection → sibling sub-collection: YES
- Parent collection outbound body links: NONE (zero outbound internal links in body)

---

## Key Numbers (Research Consensus)

| Metric | Value | Source |
|---|---|---|
| Links per page | 1 per 250 words, clamped 2-15 | Multiple sources |
| Target incoming links | 7-10 per important page (sweet spot) | Kevin Indig, Zyppy |
| Max incoming before decline | 45-50 | Zyppy |
| Anchor text length | 2-5 words (avg 4.85) | Multiple |
| Max same anchor for same target | 2-3 times across site | Kyle Roof, Zyppy |
| Blog links to collections | 2-5 per blog post | E-commerce consensus |
| Kyle Roof supporting page total links | 2-3 (1 to parent + 1-2 siblings) | Kyle Roof |

---

## Architecture Decision: How to Inject Links

**Recommendation: Hybrid approach.**

| Phase | What | How |
|---|---|---|
| 1. Plan | Calculate link budget, select targets, choose anchors | Deterministic algorithm (SiloLinkPlanner) |
| 2. Generate | Parent link included in content generation prompt | LLM writes naturally around it |
| 3. Inject | Remaining links injected via post-processing | BeautifulSoup keyword scanning, LLM fallback for ~30% |
| 4. Validate | Check all rules | First-link rule, silo integrity, density, diversity |
| 5. Persist | Store in edge table | `internal_links` SQL table with rich metadata |

**Why hybrid over pure post-processing:**
- The mandatory parent link needs to read naturally in the opening paragraphs — LLM does this better
- Discretionary links benefit from programmatic control (diversity tracking, density limits)
- Validation catches failures from either approach

**Why hybrid over pure generation-time:**
- Full programmatic control over which pages get linked and how often
- Deterministic anchor text diversity (no hoping the LLM varies its anchors)
- Can update links without regenerating content
- Can apply retroactively to existing content

---

## Data Model

**SQL edge table** (`internal_links`) with:
- source_page_id, target_page_id, cluster_id (FKs)
- anchor_text, anchor_type (exact_match, variation, partial_match, natural)
- position_in_content (paragraph index)
- is_mandatory (boolean for parent-link rule)
- placement_method (generation_time, post_processing, llm_fallback)
- status (planned, injected, verified, removed)

Plus `link_plan_snapshots` table for auditing/rollback.

---

## Open Questions for User

1. **Blog → Blog sibling links:** Kyle Roof allows 1-2 sibling links between supporting pages. Do you want this? Or should blogs only link to collection pages?

2. **Sub-collection → sub-collection links:** Should sibling sub-collections link to each other? (e.g., /organic-puppy-food links to /organic-senior-dog-food)

3. **Parent collection outbound:** Kyle Roof allows the parent/target page to link to ONE supporting page (creates circular authority flow). You said never. Confirm: zero outbound body links from parent collections?

4. **Link budget for collection pages:** If parent collections have zero outbound links, do sub-collections get a budget? (Recommended: yes, sub-collections get 3-5 links — 1 mandatory to parent + 2-4 to siblings/other collections)

5. **When do links get generated?** Two options:
   - **At content generation time** — links are part of the content pipeline, generated when content is written
   - **As a separate step after content** — content is written first, then a "link planning" step runs across the whole silo

   The second option is better because it can see ALL pages in the silo before deciding link distribution. Recommend this.

---

## Full Research Reports

- `.tmp/linking-research-kyle-roof.md` — Kyle Roof's Reverse Content Silo methodology
- `.tmp/linking-research-other-methodologies.md` — Koray Tugberk, Ahrefs/Semrush, Kevin Indig, Zyppy study, Matt Diggity, e-commerce practices
- `.tmp/linking-research-algorithmic-approaches.md` — Algorithms, data models, injection strategies, anchor text selection, open source tools
