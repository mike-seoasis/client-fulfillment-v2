# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Content Scoring Service Pattern
Location: `backend/app/services/content_score.py`

The `ContentScoreService` provides comprehensive content quality analysis using a 5-component weighted scoring system:
1. **Word Count** (15%): Sentence/paragraph counts, target word ranges
2. **Semantic** (25%): TF-IDF-like term analysis, diversity, depth
3. **Readability** (20%): Flesch-Kincaid Reading Ease and Grade Level
4. **Keyword Density** (25%): Primary/secondary keyword frequency targeting 0.5-2.5%
5. **Entity Coverage** (15%): Named entity extraction (money, locations, dates, etc.)

Key patterns:
- Singleton via `get_content_score_service()`
- Async methods with comprehensive DEBUG/INFO logging
- Dataclasses with `to_dict()` for serialization
- Exception hierarchy: `ContentScoreServiceError` → `ContentScoreValidationError`
- Slow operation warnings (>1000ms)

### Frontend Panel Component Pattern
Location: `frontend/src/components/KeywordResearchPanel.tsx`, `frontend/src/components/PAAEnrichmentPanel.tsx`

Standard panel components follow this structure:
1. **Types section**: Define interfaces for API responses, form state, pending items
2. **Constants section**: Default form state, select options, status colors
3. **Sub-components**: Reusable pieces (ProgressBar, StatsCard, Checkbox, ApprovalCard/ReviewCard)
4. **Main component**: Manages state, API queries, mutations, WebSocket subscriptions

Key patterns:
- Use `useApiQuery` for fetching stats from `/api/v1/projects/{id}/phases/{phase}/stats`
- Use `useToastMutation` for approve/reject actions with success toast feedback
- Use `useProjectSubscription` for real-time WebSocket updates during processing
- Collapsible sections via state (`showConfig`, `showReviews`)
- Status colors defined as objects: `{ bg: '...', text: '...', border: '...' }`
- Intent-based filtering for question review workflows
- Consistent card styling with `card` class and rounded-xl borders

Error logging:
- `addBreadcrumb()` for user actions and WebSocket events
- Console.debug for WebSocket updates
- All mutations wrapped in useToastMutation for error display

---

## 2026-02-01 - client-onboarding-v2-c3y.92
- **What was implemented**: Flesch-Kincaid readability calculation - ALREADY COMPLETE
- **Files changed**: None (verification only)
- **Status**: Implementation was already complete in `backend/app/services/content_score.py` (lines 656-746)
- **Verification**:
  - All 62 unit tests pass in `backend/tests/services/test_content_score.py`
  - Ruff linting passes
  - Python syntax valid
- **Learnings:**
  - Flesch-Kincaid was implemented as part of commit 74dc072 (content scoring algorithm)
  - The implementation includes both Flesch Reading Ease (0-100 scale) and Flesch-Kincaid Grade Level
  - Target readability range is 30-70 on Flesch scale (fairly easy to standard reading level)
  - Syllable counting uses vowel group detection with adjustments for silent 'e' and common patterns
  - Error logging requirements are fully met: DEBUG level entry/exit, exception handling with stack traces, entity IDs, validation failure logging, timing logs for slow operations
---

## 2026-02-01 - client-onboarding-v2-c3y.128
- **What was implemented**: PAAEnrichmentPanel with question review workflow
- **Files changed**:
  - `frontend/src/components/PAAEnrichmentPanel.tsx` (new file, ~650 lines)
- **Features**:
  - Statistics overview with keywords enriched, questions found, cache hit rate
  - Intent breakdown chart showing distribution of buying/usage/care/comparison/unknown questions
  - Question review queue with expandable cards showing answer snippets, source URLs, parent questions
  - Intent-based filtering for review queue
  - Configuration form with location/language, fan-out options, fallback settings
  - Real-time progress during enrichment via WebSocket polling
  - Bulk approve/reject actions
- **Learnings:**
  - PAA backend schemas are in `backend/app/schemas/paa_enrichment.py` with rich metadata (intent, source_url, answer_snippet, is_nested, parent_question)
  - Backend endpoints at `/api/v1/projects/{id}/phases/paa_enrichment/[enrich|batch|stats]`
  - Intent categorization includes: buying, usage, care, comparison, unknown
  - Panel components should follow KeywordResearchPanel's structure for consistency
  - Always check for unused imports before committing (TypeScript strict mode catches these)
---

