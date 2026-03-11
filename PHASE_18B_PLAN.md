# Phase 18b: Bible Pipeline Integration — Implementation Plan

## Overview

Wire vertical knowledge bibles (from 18a) into the content generation pipeline at two integration points:

1. **Prompt Injection** — Matched bible `content_md` injected as `## Domain Knowledge` in the LLM prompt so Claude writes domain-accurate content from the start
2. **QA Checks** — Bible `qa_rules` drive 4 new deterministic checks (checks 14-17) that catch domain-specific errors the generic 13 checks can't

Both apply to **all three pipelines**: onboarding pages, blog posts, and recheck endpoints.

---

## Team Structure

We'll use a **4-agent team** working in parallel:

| Agent | Role | Worktree | Focus |
|-------|------|----------|-------|
| **backend-dev** | Backend implementation | Yes (isolated) | All Python service changes: QA checks, prompt injection, pipeline wiring |
| **frontend-dev** | Frontend updates | Yes (isolated) | N/A for 18b (no frontend changes — that's 18d) |
| **test-writer** | Test implementation | Yes (isolated) | All test files: unit tests for 4 check functions, integration tests, prompt tests |
| **code-reviewer** | Quality & review | No (reads worktrees) | Reviews PRs from other agents, catches issues, ensures consistency |

> **Note:** 18b is purely backend — there are no frontend changes in this phase. The frontend-dev agent will not be needed. The team reduces to 3 agents: backend-dev, test-writer, and code-reviewer.

---

## Task Breakdown

### Wave 1: Core QA Engine (backend-dev + test-writer in parallel)

These are the foundation — everything else depends on them.

#### Task 1: Add `_split_sentences` helper to `content_quality.py`
**Agent:** backend-dev
**File:** `backend/app/services/content_quality.py`
- Add after `_extract_context` (~line 222)
- Strips HTML, splits on `(?<=[.!?])\s+`
- ~15 lines

#### Task 2: Add `bibles_matched` field to `QualityResult` dataclass
**Agent:** backend-dev
**File:** `backend/app/services/content_quality.py`
- Add `bibles_matched: list[str] = field(default_factory=list)` to dataclass
- Update `to_dict()` to conditionally include it
- ~10 lines

#### Task 3: Implement 4 bible QA check functions
**Agent:** backend-dev
**File:** `backend/app/services/content_quality.py`
- `_check_bible_preferred_terms` (Check 14) — ~30 lines
- `_check_bible_banned_claims` (Check 15) — ~45 lines
- `_check_bible_wrong_attribution` (Check 16) — ~40 lines
- `_check_bible_term_context` (Check 17) — ~40 lines
- All follow existing `_check_*` pattern: accept `fields`, return `list[QualityIssue]`
- Add after existing check functions (after ~line 470)

#### Task 4: Wire bible checks into `run_quality_checks`
**Agent:** backend-dev
**File:** `backend/app/services/content_quality.py`
- Add `matched_bibles: list[Any] | None = None` parameter
- Loop over matched bibles, run checks 14-17, accumulate issues
- Set `result.bibles_matched`
- Store in `content.qa_results`

#### Task 5: Wire bible checks into `run_blog_quality_checks`
**Agent:** backend-dev
**File:** `backend/app/services/content_quality.py`
- Same pattern as Task 4 but for blog quality function
- Runs standard checks (1-9) + blog checks (10-13) + bible checks (14-17)

#### Task 6: Write unit tests for `_split_sentences`
**Agent:** test-writer (can start immediately)
**File:** `backend/tests/services/test_content_quality.py`
- `TestSplitSentences`: basic split, HTML stripping, exclamation/question marks, empty string

#### Task 7: Write unit tests for 4 bible check functions
**Agent:** test-writer (can start after Task 3 signatures are known — but spec has them)
**File:** `backend/tests/services/test_content_quality.py`
- `_FakeBible` helper class
- `TestCheckBiblePreferredTerms`: 6 tests (detect, pass, case-insensitive, word-boundary, empty rules, malformed)
- `TestCheckBibleBannedClaims`: 4 tests (with context, no flag when context absent, without context requirement, empty)
- `TestCheckBibleWrongAttribution`: 3 tests (detect, pass correct, different sentences)
- `TestCheckBibleTermContext`: 4 tests (detect, pass correct, different sentences, empty)

#### Task 8: Write integration tests for `run_quality_checks` with bibles
**Agent:** test-writer
**File:** `backend/tests/services/test_content_quality.py`
- `TestRunQualityChecksWithBibles`: backward compat, bible issues cause failure, multiple bibles accumulate
- `TestRunBlogQualityChecksWithBibles`: backward compat, bible checks run alongside blog checks

---

### Wave 2: Prompt Injection (backend-dev, blocked on Wave 1)

#### Task 9: Add `_build_domain_knowledge_section` function
**Agent:** backend-dev
**File:** `backend/app/services/content_writing.py`
- Add `BIBLE_PROMPT_MAX_CHARS = 8000` constant
- Add function after `_build_brand_voice_section` (~line 988)
- Concatenates `content_md` from matched bibles, caps at 8000 chars
- Returns `"## Domain Knowledge\n..."` or `None`
- ~40 lines

#### Task 10: Thread `matched_bibles` through prompt building
**Agent:** backend-dev
**File:** `backend/app/services/content_writing.py`
- Add `matched_bibles` param to: `build_content_prompt`, `build_blog_content_prompt`, `_build_user_prompt`, `_build_blog_user_prompt`, `generate_content`
- Inject `## Domain Knowledge` between `## SEO Targets` and `## Brand Voice` (collection)
- Inject `## Domain Knowledge` between `## SEO Targets` and `## Recent Trends` (blog)
- All params default to `None` for backward compatibility

#### Task 11: Thread `matched_bibles` through `content_outline.py`
**Agent:** backend-dev
**File:** `backend/app/services/content_outline.py`
- Add `matched_bibles` param to `generate_outline` and `generate_content_from_outline`
- Pass through to prompt building
- ~10 lines

#### Task 12: Write tests for `_build_domain_knowledge_section`
**Agent:** test-writer
**File:** `backend/tests/services/test_content_writing.py`
- `TestBuildDomainKnowledgeSection`: returns None no bibles, single bible, truncation, empty content, multiple bibles concatenated
- 5 tests

---

### Wave 3: Pipeline Wiring (backend-dev, blocked on Wave 2)

#### Task 13: Add `_load_project_bibles` and `_match_bibles_for_keyword` to `content_generation.py`
**Agent:** backend-dev
**File:** `backend/app/services/content_generation.py`
- Add `import re` at top
- `_load_project_bibles(db, project_id)` — loads all active bibles, graceful degradation
- `_match_bibles_for_keyword(project_bibles, keyword)` — word-boundary trigger matching
- ~50 lines total

#### Task 14: Wire bibles into `run_content_pipeline`
**Agent:** backend-dev
**File:** `backend/app/services/content_generation.py`
- Load bibles alongside brand_config in read-only session
- Pass `project_bibles` to `_process_single_page`
- In `_process_single_page`: match per-page keyword, pass to outline/content gen + quality checks
- ~15 lines of wiring

#### Task 15: Wire bibles into `run_generate_from_outline`
**Agent:** backend-dev
**File:** `backend/app/services/content_generation.py`
- Load + match bibles after brand_config
- Pass to `generate_content_from_outline` and `run_quality_checks`
- ~10 lines

#### Task 16: Wire bibles into blog pipeline
**Agent:** backend-dev
**File:** `backend/app/services/blog_content_generation.py`
- Add `_load_project_bibles_for_campaign(db, campaign_id)` — joins BlogCampaign to get project_id
- Load bibles in `run_blog_content_pipeline`
- Pass through `_process_single_post` → `_generate_blog_content` → prompt builder
- Pass through `_process_single_post` → `_run_blog_quality_checks` → quality checker
- ~45 lines

#### Task 17: Wire bibles into recheck endpoints
**Agent:** backend-dev
- **File 1:** `backend/app/api/v1/content_generation.py` — `recheck_content` loads bibles, matches keyword, passes to `run_quality_checks` (~20 lines)
- **File 2:** `backend/app/api/v1/blogs.py` — `recheck_blog_post_content` loads bibles, matches keyword, passes to `_run_blog_quality_checks` (~15 lines)

---

### Wave 4: Review & Verification (code-reviewer, after each wave)

#### Task 18: Code review after Wave 1
**Agent:** code-reviewer
- Verify check functions match spec exactly
- Verify `QualityResult` backward compat
- Verify test coverage completeness
- Check for missed edge cases

#### Task 19: Code review after Wave 2
**Agent:** code-reviewer
- Verify prompt injection placement is correct
- Verify all signature changes have backward-compatible defaults
- Verify truncation logic

#### Task 20: Code review after Wave 3
**Agent:** code-reviewer
- Verify all pipeline paths wired correctly
- Verify graceful degradation (table doesn't exist, no bibles, etc.)
- Run full test suite, verify all pass
- Check no regressions in existing tests

#### Task 21: Final integration verification
**Agent:** code-reviewer
- All existing tests pass unchanged
- All new tests pass
- Backward compat verified: every new param defaults to `None`
- No import cycles
- Pipeline degrades gracefully when no bibles exist

---

## Files Modified (Summary)

| File | Changes | Est. Lines |
|------|---------|-----------|
| `backend/app/services/content_quality.py` | `QualityResult` update, `_split_sentences`, 4 check functions, wire into `run_quality_checks` + `run_blog_quality_checks` | +200 |
| `backend/app/services/content_writing.py` | `_build_domain_knowledge_section`, thread `matched_bibles` through 5 functions | +80 |
| `backend/app/services/content_generation.py` | `_load_project_bibles`, `_match_bibles_for_keyword`, wire 3 pipeline paths | +65 |
| `backend/app/services/blog_content_generation.py` | `_load_project_bibles_for_campaign`, wire blog pipeline | +45 |
| `backend/app/services/content_outline.py` | Thread `matched_bibles` through 2 functions | +10 |
| `backend/app/api/v1/content_generation.py` | Wire recheck endpoint | +20 |
| `backend/app/api/v1/blogs.py` | Wire blog recheck endpoint | +15 |
| `backend/tests/services/test_content_quality.py` | `_FakeBible`, 7 test classes, ~30 tests | +280 |
| `backend/tests/services/test_content_writing.py` | `TestBuildDomainKnowledgeSection`, 5 tests | +50 |
| **Total** | | **+765** |

---

## Execution Strategy

```
Time ──────────────────────────────────────────────────►

Wave 1 (parallel):
  backend-dev:  Tasks 1-5 (QA engine)
  test-writer:  Tasks 6-8 (QA tests, using spec signatures)
  code-reviewer: Reviews as PRs land

Wave 2 (parallel after Wave 1):
  backend-dev:  Tasks 9-11 (prompt injection)
  test-writer:  Task 12 (prompt tests)
  code-reviewer: Task 18 (Wave 1 review)

Wave 3 (parallel after Wave 2):
  backend-dev:  Tasks 13-17 (pipeline wiring)
  code-reviewer: Task 19 (Wave 2 review)

Wave 4 (after Wave 3):
  code-reviewer: Tasks 20-21 (final review + verification)
```

## Key Design Decisions (from spec)

1. **8,000 char max** for bible prompt injection (~$0.006 per page, negligible)
2. **All bible checks are errors** (confidence 1.0, cause `passed=false`) — operators created the rules intentionally
3. **Sentence-level co-occurrence** for banned claims, wrong attribution, term context — strip HTML, split on `(?<=[.!?])\s+`
4. **Word boundary matching** with `re.escape()` — no ReDoS risk
5. **Graceful degradation** — if VerticalBible table doesn't exist, pipeline runs normally
6. **Bibles loaded once per pipeline run**, matched per-page by keyword

## Dependencies

- **Prerequisite:** Phase 18a complete (VerticalBible model, service, API) ✅
- **No frontend changes** in 18b (that's Phase 18d: Quality Panel UI)
- **No migration needed** (18a already created the table)
