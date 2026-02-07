# Ralph Loop: POP API Integration

## Your Mission

Implement the PageOptimizer Pro (POP) API integration for content scoring. Work through the user stories in `prd.json` sequentially, marking each as complete when done.

## Context

- **Branch:** `feature/replace-content-scoring-api`
- **Change directory:** `openspec/changes/replace-content-scoring-api/`
- **Task tracker:** `prd.json` (Ralph TUI format)
- **Design docs:** Read `proposal.md`, `design.md`, and `specs/` for full context

## Instructions

1. **Read prd.json** to find the next story where `passes: false`
2. **Implement that user story** following the acceptance criteria
3. **Verify all acceptance criteria are met**
4. **Update prd.json** to set `passes: true` for the completed story
5. **Commit your work** with message: `feat(pop): US-XXX - <title>`
6. **Move to the next story**

## Patterns to Follow

- **Integration client:** Follow `app/integrations/dataforseo.py` pattern (httpx async, circuit breaker, retry logic)
- **Services:** Follow `app/services/paa_enrichment.py` pattern (dataclasses, logging, error handling)
- **Config:** Add settings to `app/core/config.py` using pydantic Field()
- **Logging:** Include ERROR LOGGING REQUIREMENTS docstring in all new services
- **Models:** Follow existing patterns in `app/models/`
- **Schemas:** Follow existing patterns in `app/schemas/`

## Key Files

- POP API docs: `/Users/mike/Downloads/PageOptimizer_Pro_API_Documentation.md`
- Existing integration example: `backend/app/integrations/dataforseo.py`
- Existing service example: `backend/app/services/content_score.py`
- Design decisions: `openspec/changes/replace-content-scoring-api/design.md`
- Specs: `openspec/changes/replace-content-scoring-api/specs/`

## Completion Criteria

When ALL user stories in `prd.json` have `passes: true`, output:

```
<promise>POP INTEGRATION COMPLETE</promise>
```

## Rules

- Only work on ONE user story per iteration
- Always verify ALL acceptance criteria before marking passes: true
- Always commit after completing a story
- Follow existing code patterns in the codebase
- Include comprehensive logging per project requirements
- Write tests as specified in acceptance criteria
- If blocked, add a note to the story and move to next unblocked story
