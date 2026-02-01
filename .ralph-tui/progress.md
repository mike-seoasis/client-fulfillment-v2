# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### NLP Endpoint Pattern
- NLP endpoints are grouped under `/api/v1/nlp/` in `backend/app/api/v1/endpoints/nlp.py`
- Schemas live in `backend/app/schemas/nlp.py`
- Use `_get_request_id(request)` helper for extracting request_id from state
- All endpoints follow structured error response: `{"error": str, "code": str, "request_id": str}`
- Log DEBUG on request entry, INFO on success, WARNING on 4xx, ERROR on 5xx
- Include `duration_ms` in all response logs

### TF-IDF Analysis Pattern
- Use `get_tfidf_analysis_service()` singleton from `app/services/tfidf_analysis`
- `analyze()` for standard term extraction
- `find_missing_terms()` for content gap analysis (terms missing from user content)
- Results include `TermScore` objects with term, score, doc_frequency, term_frequency

---

## 2026-02-01 - client-onboarding-v2-c3y.95
- What was implemented: `/api/v1/nlp/analyze-competitors` endpoint for TF-IDF competitor analysis
- Files changed:
  - `backend/app/api/v1/endpoints/nlp.py` - Added `analyze_competitors` endpoint
  - `backend/app/schemas/nlp.py` - Added `AnalyzeCompetitorsRequest`, `AnalyzeCompetitorsResponse`, `CompetitorTermItem` schemas
- **Learnings:**
  - NLP endpoints follow a consistent pattern with request_id logging and structured error responses
  - TF-IDF service already exists with both standard analysis and missing terms modes
  - The competitor phase endpoints at `/projects/{project_id}/phases/competitor/` are separate from NLP - they handle competitor CRUD and scraping, while NLP handles content analysis
---

