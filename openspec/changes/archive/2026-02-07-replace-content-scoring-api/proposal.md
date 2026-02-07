## Why

Our current content workflow uses multiple services with different data sources: DataForSEO for PAA questions, and a homegrown `ContentScoreService` for quality scoring based on arbitrary thresholds. PageOptimizer Pro (POP) is an established SEO tool that provides SERP-based competitor analysis, giving us real targets derived from what's actually ranking. By integrating POP, we can consolidate data sources and get more accurate, competitor-informed content guidance.

## What Changes

**New workflow with two POP API calls:**

1. **Content Brief Phase (NEW)** — After keywords are approved, call POP API to get:
   - Word count targets (based on competitor analysis)
   - Heading structure targets (H1, H2, H3, H4 counts)
   - Keyword density targets by section (title, headings, paragraphs)
   - LSI/semantic terms with weights and target counts
   - Entity recommendations
   - `relatedQuestions` (PAA data) — potentially replacing DataForSEO PAA fetch
   - `relatedSearches` for additional context
   - Competitor analysis data

2. **Content Scoring Phase** — After content is generated, call POP API again to:
   - Score the generated content against targets
   - Verify keyword density, term usage, structure compliance
   - Get a page score (0-100)

**Impact on existing phases:**

- **PAA Enrichment**: Could be replaced or simplified — POP provides `relatedQuestions` (same PAA data). Intent categorization (LLM step) would still be needed since POP doesn't categorize.
- **Content Scoring**: `ContentScoreService` replaced with POP API scoring
- **Content Quality**: `ContentQualityService` (AI trope detection) **unchanged**

**Breaking changes:**

- **BREAKING**: Insert new "Content Brief" phase after keyword approval, before content generation
- **BREAKING**: Replace `ContentScoreService` with POP-based scoring
- Potential deprecation of DataForSEO PAA fetch (if POP's relatedQuestions is sufficient)

## Capabilities

### New Capabilities
- `pop-content-brief`: Integration with POP API to fetch SERP-based content targets (word count, heading structure, keyword density, LSI terms, entities, PAA questions) after keyword approval
- `pop-content-scoring`: Integration with POP API to score generated content against competitor-derived targets

### Modified Capabilities
- `paa-enrichment`: May be modified to use POP's relatedQuestions instead of DataForSEO, or deprecated entirely (needs investigation)

## Impact

**Code changes:**
- New service: `POPContentBriefService` — fetches content targets from POP API
- New service: `POPContentScoreService` — scores content via POP API
- New phase endpoints for content brief
- Modify content generation to consume POP brief data
- Update or deprecate `paa_enrichment.py` (DataForSEO dependency)
- Config: Add `POP_API_KEY` environment variable

**Workflow changes:**
- New phase inserted: Keywords Approved → **Content Brief (POP)** → Content Generation → Content Scoring (POP) → Content Quality (trope detection)

**Dependencies:**
- New: PageOptimizer Pro API (`app.pageoptimizer.pro`)
- Potentially remove: DataForSEO (if POP PAA data is sufficient)

**API considerations:**
- POP API is async (create task → poll for results) — need background task handling
- Two API calls per content piece (brief + scoring) — cost/rate limit implications
- Rich response data — decide what to persist vs. pass through

**Open questions:**
1. Is POP's `relatedQuestions` sufficient to replace DataForSEO PAA fetch entirely?
2. Should intent categorization (LLM) still run on POP's PAA data?
3. What's the cost/rate limit structure for POP API?
4. Fallback strategy if POP API is unavailable?
