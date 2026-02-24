# Plan: Remove Secondary Keywords and PAA Generation

> **Status:** Draft
> **Created:** 2026-02-02
> **Purpose:** Simplify content workflow by leveraging POP API for LSI terms and related questions

---

## Overview

Remove custom secondary keyword selection and PAA (People Also Ask) generation services. These are now redundant because PageOptimizer Pro (POP) provides:

- **LSI Terms** → Replaces secondary keywords (better quality - based on actual SERP competitor analysis)
- **Related Questions** → Replaces PAA generation (direct from Google, no DataForSEO costs)

## Rationale

### Current Flow (Complex)
```
1. Generate primary keyword
2. Generate secondary keywords (custom algorithm)
3. Fetch PAA questions (DataForSEO API)
4. Categorize PAA questions (Claude LLM)
5. Analyze PAA for content angle
6. Human approves keywords + PAA
7. Send to POP for brief
```

### New Flow (Simplified)
```
1. Generate primary keyword
2. Human approves primary keyword
3. Send to POP → Returns everything:
   • LSI terms (replaces secondaries)
   • Related questions (replaces PAA)
   • Word count targets
   • Heading structure targets
   • Competitor analysis
```

### Benefits
- **Fewer API costs** - No DataForSEO PAA calls, no Claude categorization calls
- **Faster workflow** - Fewer async steps, less human approval needed
- **Better data quality** - POP's LSI terms are based on actual ranking competitors
- **Less code to maintain** - ~18 files deleted, ~7 files simplified

---

## Files to Delete

### Core Services (4 files)
| File | Description |
|------|-------------|
| `app/services/secondary_keywords.py` | Selects 3-5 secondary keywords from keyword research |
| `app/services/paa_enrichment.py` | Fetches PAA from DataForSEO + fan-out for nested questions |
| `app/services/paa_categorization.py` | Claude LLM categorizes questions by intent |
| `app/services/paa_analysis.py` | Groups questions, picks priorities, recommends content angle |

### Supporting Services (1 file)
| File | Description |
|------|-------------|
| `app/services/paa_cache.py` | Redis caching layer for PAA enrichment |

### API Endpoints (2 files)
| File | Description |
|------|-------------|
| `app/api/v1/endpoints/paa_enrichment.py` | PAA enrichment REST endpoints |
| `app/api/v1/endpoints/keyword_research.py` | Contains `/secondary` endpoint (may need partial removal) |

### Schemas (4 files)
| File | Description |
|------|-------------|
| `app/schemas/paa_enrichment.py` | PAA enrichment request/response schemas |
| `app/schemas/paa_analysis.py` | PAA analysis schemas |
| `app/schemas/content_plan.py` | Depends on PAA analysis schemas |
| `app/schemas/keyword_research.py` | Contains SecondaryKeywordRequest/Response (may need partial removal) |

### Tests (5 files)
| File | Description |
|------|-------------|
| `tests/services/test_secondary_keywords.py` | Secondary keyword service tests |
| `tests/services/test_paa_enrichment.py` | PAA enrichment tests |
| `tests/services/test_paa_categorization.py` | PAA categorization tests |
| `tests/services/test_paa_analysis.py` | PAA analysis tests |
| `tests/services/test_paa_cache.py` | PAA cache tests |

---

## Files to Modify

### Service Exports
| File | Change |
|------|--------|
| `app/services/__init__.py` | Remove exports for secondary_keywords, paa_* services |

### API Router
| File | Change |
|------|--------|
| `app/api/v1/__init__.py` | Remove router imports for paa_enrichment, keyword_research (if fully removed) |

### Orchestration Services
| File | Change |
|------|--------|
| `app/services/content_plan.py` | Remove PAA imports and integration; update to use POP brief data instead |

### API Endpoints
| File | Change |
|------|--------|
| `app/api/v1/endpoints/content_plan.py` | Remove PAA schema dependencies; update response models |

### E2E Tests
| File | Change |
|------|--------|
| `tests/e2e/test_crawl_to_content_workflow.py` | Remove secondary_keywords references |

---

## Database Considerations

### Tables Potentially Affected
| Table | Migration File | Decision |
|-------|----------------|----------|
| `page_keywords` | `alembic/versions/0003_create_page_keywords_table.py` | **Review** - May store primary keywords too |
| `page_paa` | `alembic/versions/0004_create_page_paa_table.py` | **Deprecate** - POP provides related questions |

### Models to Review
| File | Decision |
|------|----------|
| `app/models/page_paa.py` | Delete if only used by PAA services |
| `app/models/page_keywords.py` | Review - may need to keep for primary keywords |

### Migration Strategy
1. **Phase 1:** Stop writing to `page_paa` table (code removal)
2. **Phase 2:** Create migration to drop `page_paa` table (after confirming no dependencies)
3. **Phase 3:** Review `page_keywords` - keep if storing primary keywords, modify if only secondaries

---

## New Workflow Integration

### Where POP Fits In

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE: Keyword Research                                        │
├─────────────────────────────────────────────────────────────────┤
│  Step 1: Generate primary keyword candidates                    │
│  Step 2: Human approves primary keyword for each page           │
│          (No secondary approval needed)                         │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE: Content Planning (NEW - POP Integration)                │
├─────────────────────────────────────────────────────────────────┤
│  Step 1: Send approved primary keyword + target URL to POP      │
│                                                                 │
│  Step 2: POP returns Content Brief:                             │
│          • lsi_terms (replaces secondary keywords)              │
│          • related_questions (replaces PAA)                     │
│          • word_count_target, word_count_min, word_count_max    │
│          • heading_targets (H1, H2, H3 counts)                  │
│          • keyword_targets (placement recommendations)          │
│          • competitors (top ranking pages analysis)             │
│                                                                 │
│  Step 3: Store Content Brief in database                        │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE: Content Generation                                      │
├─────────────────────────────────────────────────────────────────┤
│  Use Content Brief to guide content creation:                   │
│  • Target word count from brief                                 │
│  • Include LSI terms naturally                                  │
│  • Answer related questions (FAQ section)                       │
│  • Follow heading structure recommendations                     │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE: Content Scoring                                         │
├─────────────────────────────────────────────────────────────────┤
│  Step 1: Send content URL + keyword to POP for scoring          │
│  Step 2: Review page_score and recommendations                  │
│  Step 3: Iterate until score meets threshold (default 70)       │
└─────────────────────────────────────────────────────────────────┘
```

### Data Mapping: Old → New

| Old System | New System (POP) |
|------------|------------------|
| `SecondaryKeywordResult.keywords` | `POPContentBriefResult.lsi_terms` |
| `PAAEnrichmentResult.questions` | `POPContentBriefResult.related_questions` |
| `PAAAnalysisResult.content_angle` | Derived from `lsi_terms` weights or manual |
| `PAAAnalysisResult.priority_questions` | Top N from `related_questions` |

---

## Implementation Steps

### Phase 1: Preparation
- [ ] Verify POP integration tests pass
- [ ] Document current secondary keyword and PAA usage in production
- [ ] Identify any frontend dependencies on removed endpoints

### Phase 2: Add POP-Based Alternatives
- [ ] Update `content_plan.py` to fetch Content Brief from POP instead of PAA services
- [ ] Create new schemas for POP-based content planning (or reuse existing)
- [ ] Update content generation to use `lsi_terms` and `related_questions` from POP

### Phase 3: Remove Old Code
- [ ] Delete service files (secondary_keywords, paa_*)
- [ ] Delete API endpoint files
- [ ] Delete schema files
- [ ] Update `__init__.py` exports
- [ ] Update router registrations

### Phase 4: Clean Up
- [ ] Delete test files
- [ ] Update E2E tests
- [ ] Create database migration to drop `page_paa` table
- [ ] Review and update `page_keywords` table/model

### Phase 5: Verification
- [ ] Run full test suite
- [ ] Test complete workflow end-to-end
- [ ] Verify no broken imports or references

---

## Rollback Plan

If issues arise after deployment:

1. **Code Rollback:** Git revert the removal commits
2. **Database:** No immediate action needed (tables not dropped in Phase 1)
3. **API:** Endpoints restored with code revert

---

## Open Questions

1. **Primary keyword storage:** Does `page_keywords` table store primary keywords, or only secondaries?
   - If only secondaries → can delete table
   - If primaries too → keep table, just stop writing secondaries

2. **Frontend dependencies:** What frontend components call the removed endpoints?
   - `/api/v1/keyword-research/secondary`
   - `/api/v1/paa-enrichment/*`

3. **Content angle:** PAA analysis provided a "content angle" recommendation. Do we need to replicate this logic using POP's LSI term weights, or is it no longer needed?

4. **Historical data:** Should we preserve existing PAA and secondary keyword data, or is it safe to drop?

---

## Estimated Impact

| Metric | Before | After |
|--------|--------|-------|
| Service files | +4 | -4 |
| API endpoints | +2 | -2 |
| Schema files | +4 | -4 |
| Test files | +5 | -5 |
| API calls per keyword | DataForSEO + Claude + POP | POP only |
| Human approval steps | 2 (keywords + PAA) | 1 (primary keyword only) |
