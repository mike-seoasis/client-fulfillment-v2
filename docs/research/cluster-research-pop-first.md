# POP-First Keyword Cluster Creation: Research Report

## Executive Summary

PageOptimizer Pro's API is designed for **on-page optimization of a single keyword at a time**, not keyword discovery or clustering. The API's primary value lies in its LSI/NLP analysis of SERP competitors for a given keyword -- it tells you *how to optimize* a page, not *what pages to build*. A "POP-first" approach to keyword cluster creation is technically feasible through creative chaining of API calls, but it is slow, expensive in API credits, and produces clustering data as a side effect rather than a core output. POP should be positioned **downstream** in the pipeline (optimizing content for approved keywords) rather than upstream (discovering which keywords/pages to build).

---

## 1. POP API Capabilities Analysis

### Available Endpoints

The POP API exposes 7 endpoints:

| Endpoint | Method | Purpose | Credits |
|----------|--------|---------|---------|
| `/api/google-search-locations/` | GET | List available Google locations | Free |
| `/api/expose/get-terms/` | POST | Get LSI terms + variations for a keyword/URL pair | 1 credit |
| `/api/task/:task_id/results/` | GET | Poll async task results | Free |
| `/api/expose/create-report/` | POST | Create full on-page report (needs prepareId from get-terms) | 1 credit |
| `/api/expose/get-custom-recommendations/` | POST | Get placement recommendations for a report | Free |
| `/api/expose/setup-watchdog` | POST | Monitor ranking changes | Unknown |
| `/api/expose/generate-ai-schema` | POST | Generate schema markup | Unknown |

### What `get-terms` Returns (Key Endpoint for Clustering)

When you call `get-terms` with a keyword + target URL, POP:
1. Scrapes the top ~10 SERP results for that keyword
2. Analyzes all competitor pages using TF-IDF / NLP
3. Returns:

**`lsaPhrases`** (array of ~50-60 terms):
```json
{
  "phrase": "content",
  "weight": 0.277,
  "averageCount": 49,
  "targetCount": 17
}
```
These are LSI/NLP-derived terms that competitors commonly use. Sorted by `weight` (importance). These are **content optimization terms**, not keyword suggestions -- they tell you which words to include in your content, not which pages to create.

**`variations`** (array of ~10 strings):
```json
["off-site seo", "on-page", "off-page seo", "site", "search engine optimization", "page", "on-site", "seo", "on-site seo", "pages"]
```
These are **Google's own keyword variations** extracted from the SERP. These are the closest thing POP provides to "related keyword suggestions" and could serve as cluster candidates.

**`prepareId`**: Needed for step 2 (create-report).

### What `create-report` Returns

After get-terms, you can create a full report which adds:
- **`competitors`**: Top-ranking URLs with h2/h3 texts, page scores, word counts
- **`relatedQuestions`**: People Also Ask questions (with links, snippets)
- **`relatedSearches`**: Google's related searches (queries + links)
- **`secondaryKeywords`**: Keywords POP identifies as secondary targets
- **`variations`** (report-level): Keyword variations with recommendation objects
- **`tagCounts`**: Heading structure recommendations
- **`wordCount`**: Target word count based on competitors
- **`pageScore`**: Optimization score

The `relatedQuestions` and `relatedSearches` from create-report are useful for cluster creation -- they represent what Google considers topically related.

### What `get-custom-recommendations` Returns

Placement-level optimization data (exact keyword in H1, H2, paragraph, etc.). Not useful for clustering -- this is pure on-page optimization guidance.

---

## 2. Can POP Data Drive Keyword Cluster Creation?

### Potential Approach: Chaining get-terms Calls

**Concept**: Call `get-terms` for the seed keyword, extract variations + LSI terms, then call `get-terms` again for each promising variation to build a cluster tree.

**Example Flow**:
```
Seed: "trail running shoes"
  |
  +--> get-terms("trail running shoes", placeholder_url)
  |    Returns variations: ["running shoes", "trail shoes", "best trail running shoes", ...]
  |    Returns LSI phrases: ["waterproof", "grip", "cushioning", "lightweight", ...]
  |
  +--> For each variation, call get-terms again:
       get-terms("best trail running shoes", placeholder_url)
       get-terms("trail shoes", placeholder_url)
       get-terms("waterproof trail running shoes", placeholder_url)  [constructed from LSI + seed]
       ...
```

### Data Available for Clustering from POP

| Data Point | Source | Usefulness for Clustering |
|-----------|--------|--------------------------|
| `variations` (strings) | get-terms step 1 | HIGH -- Google's own related queries |
| `relatedSearches` (queries) | create-report step 2 | HIGH -- Google's related searches |
| `relatedQuestions` (PAA) | create-report step 2 | MEDIUM -- good for content topics, less for page-level clusters |
| `secondaryKeywords` | create-report step 2 | MEDIUM -- POP's secondary keyword suggestions |
| `lsaPhrases` (NLP terms) | get-terms step 1 | LOW for clustering -- these are content optimization terms, not keyword suggestions |
| `competitors.h2Texts/h3Texts` | create-report step 2 | LOW-MEDIUM -- competitor headings reveal subtopics |

### Proposed POP-First Architecture

```
Step 1: Seed Expansion (1 API credit)
  Input:  seed keyword (e.g., "trail running shoes")
  Call:   get-terms(seed, placeholder_url)
  Output: variations[] + lsaPhrases[]

Step 2: Construct Candidate Keywords
  - Take all variations (Google's own related queries)
  - Combine high-weight LSI phrases with seed to form long-tail candidates
    e.g., "waterproof" + "trail running shoes" = "waterproof trail running shoes"
  - Use LLM to filter/refine candidates into page-worthy clusters

Step 3: Validate Candidates via Full Reports (1 credit each)
  For each candidate cluster keyword:
    Call: create-report(prepareId, variations, lsaPhrases)
    Extract: relatedQuestions, relatedSearches, secondaryKeywords, competitors

  Use relatedSearches + secondaryKeywords to confirm/refine clusters

Step 4: Enrich with Volume Data (DataForSEO)
  For all cluster candidates:
    Call: DataForSEO keyword volume batch
    Get: search_volume, competition, CPC

Step 5: Score and Rank Clusters
  Combine POP semantic data + DataForSEO volume data
  Score by: volume * relevance * (1 - competition)
  Present top 5-10 cluster recommendations
```

### Data Flow Diagram

```
                    User Input
                        |
                  [seed keyword]
                        |
                   POP get-terms
                   (1 API credit)
                        |
              +---------+---------+
              |                   |
         variations[]        lsaPhrases[]
         (Google queries)    (NLP terms)
              |                   |
              +----> LLM Merge <--+
                        |
                [candidate keywords]
                   (5-15 terms)
                        |
              POP create-report (per candidate)
              (5-15 API credits)
                        |
              +---------+---------+---------+
              |         |         |         |
         relatedQ  relatedS  secondaryKW  competitors
              |         |         |         |
              +----> LLM Cluster Refinement <+
                        |
                [refined clusters]
                   (5-10 pages)
                        |
              DataForSEO Volume Enrichment
                        |
                [scored & ranked clusters]
                        |
                  User Approval UI
```

---

## 3. Gap Analysis: What POP Cannot Do

### Critical Gaps

1. **No Search Volume Data**: POP provides zero search volume, CPC, or competition data. You cannot assess whether a keyword is worth targeting without DataForSEO (or similar). This is the single biggest gap.

2. **No Keyword Discovery Endpoint**: POP has no dedicated keyword suggestion or discovery endpoint. The `variations` from get-terms are a byproduct of SERP analysis (~10 terms), not a keyword research feature.

3. **No Bulk/Batch Processing**: Each get-terms call processes one keyword. To explore 10 candidate keywords, you need 10 API calls (10 credits, ~30-60 seconds each for real API due to SERP scraping).

4. **No Keyword Strategy Tool in API**: POP's web UI has a "Keyword Strategy Tool" that generates keyword clusters from topics/competitor URLs using AI. This feature is NOT exposed in the API. It is only available through the web interface and requires manual interaction.

5. **Requires a Target URL**: get-terms requires both a `keyword` AND a `targetUrl`. For new pages that don't exist yet, you must provide a placeholder URL. The `targetUrl` affects the analysis since POP compares your page against SERP competitors.

6. **LSI Terms Are Content-Level, Not Page-Level**: LSI phrases like "waterproof", "grip", "cushioning" are words to include IN a page about trail running shoes. They are NOT separate page topics. Using them as cluster seeds would produce low-quality suggestions.

7. **No Intent Classification**: POP does not classify keywords by search intent (informational, commercial, navigational, transactional). Intent is critical for deciding whether a keyword warrants its own page.

### Moderate Gaps

8. **Slow for Real-Time UX**: Each get-terms call takes 30-60 seconds (SERP scraping + NLP analysis). A chained approach with 10+ calls would take 5-10 minutes -- poor for an interactive UX.

9. **Cost Adds Up**: At 1 credit per get-terms call, exploring 10 cluster candidates costs 10 credits + 10 more for create-report. That's 20 credits per cluster generation session.

10. **Variations Are Generic**: The ~10 variations from get-terms are Google's broad related queries, not e-commerce-specific collection page suggestions.

---

## 4. Pros and Cons of POP-First Approach

### Pros

| Pro | Detail |
|-----|--------|
| SERP-grounded data | Variations come directly from Google's SERP, reflecting real search behavior |
| Semantic richness | LSI phrases provide deep topical understanding of the seed keyword's SERP landscape |
| Competitor intelligence | create-report reveals what top-ranking pages look like (headings, word count, structure) |
| Integration exists | We already have a robust POPClient + POPMockClient with circuit breaker, retry logic, polling |
| Related questions/searches | PAA and related searches from create-report are valuable cluster signals |
| Quality over quantity | POP's NLP-filtered terms are higher quality than raw keyword suggestion APIs |

### Cons

| Con | Detail |
|-----|--------|
| No volume data | Must supplement with DataForSEO for any volume/competition data |
| Slow | 30-60s per keyword, chaining 10+ calls = 5-10 minute wait |
| Expensive | 10-20 credits per cluster generation session |
| Wrong abstraction level | POP optimizes pages, it doesn't discover pages to build |
| No dedicated clustering API | Keyword Strategy Tool exists in UI but not in API |
| LSI terms mislead | Using LSI terms as cluster candidates conflates "words to use on a page" with "pages to create" |
| Requires target URL | Awkward for pages that don't exist yet |
| Limited variation count | Only ~10 variations per call -- not enough for comprehensive cluster generation |
| No intent classification | Cannot determine if a keyword should be its own page vs. a section on an existing page |

---

## 5. Honest Assessment & Recommendation

### POP-First Is the Wrong Architecture

POP is an **on-page optimization tool**, not a keyword research tool. Using it as the primary source for cluster creation is like using a spell-checker to write a novel -- it's good at refining what you've already decided to write, but it can't tell you what to write.

The most honest architecture positions POP as follows:

```
[Keyword Discovery]  -->  [Cluster Creation]  -->  [Content Optimization]
   DataForSEO +               LLM                      POP
   LLM ideation          (grouping/intent)        (LSI, recommendations)
```

### Where POP Adds Value in Clustering

Despite not being the primary driver, POP data can **validate and enrich** clusters:

1. **Validation**: Run get-terms on a proposed cluster keyword. If the variations overlap heavily with the seed keyword's variations, they may be too similar for separate pages (cannibalization risk).

2. **Enrichment**: After clusters are defined, run create-report on each cluster keyword to pre-populate content briefs with LSI terms, competitor data, and heading structures.

3. **Differentiation Check**: Compare LSI phrases across cluster keywords. High overlap = pages that will be hard to differentiate. Low overlap = good candidates for separate pages.

### Recommended Role for POP in the Pipeline

```
Phase 1: Cluster Discovery (NOT POP-primary)
  - LLM generates 20-30 candidate keywords from seed
  - DataForSEO provides volume/competition data
  - LLM groups into 5-10 clusters by intent + topic

Phase 2: Cluster Validation (POP supplementary, OPTIONAL)
  - POP get-terms on each cluster keyword
  - Compare variation overlap between clusters
  - Flag potential cannibalization

Phase 3: Content Brief Generation (POP primary -- EXISTING FLOW)
  - POP full 3-step flow on each approved keyword
  - Store as ContentBrief records (existing infrastructure)
  - This is where POP shines and we already have it built
```

---

## 6. Cost & Performance Estimates

### POP-First Approach (NOT recommended as primary)

| Step | API Calls | Credits | Time (real API) |
|------|-----------|---------|-----------------|
| Seed get-terms | 1 | 1 | 30-60s |
| Candidate get-terms (10 keywords) | 10 | 10 | 5-10 min |
| Candidate create-report (10 keywords) | 10 | 10 | 5-10 min |
| DataForSEO volume enrichment | 1 batch | ~$0.05 | 2-3s |
| **Total** | **~21** | **~21 credits** | **~10-20 min** |

### Hybrid Approach (POP as validator only)

| Step | API Calls | Credits | Time (real API) |
|------|-----------|---------|-----------------|
| LLM candidate generation | 1 LLM call | ~$0.02 | 2-5s |
| DataForSEO volume + suggestions | 1-2 batch | ~$0.10 | 3-5s |
| LLM clustering | 1 LLM call | ~$0.02 | 2-5s |
| POP validation (optional, 5-10 keywords) | 5-10 | 5-10 | 2.5-10 min |
| **Total** | **~8-13** | **~5-10 credits + ~$0.14** | **~3-10 min** |

### No-POP Approach (fastest, cheapest)

| Step | API Calls | Credits | Time (real API) |
|------|-----------|---------|-----------------|
| LLM candidate generation | 1 LLM call | ~$0.02 | 2-5s |
| DataForSEO keyword suggestions | 1 | ~$0.05 | 2-3s |
| DataForSEO volume enrichment | 1 batch | ~$0.05 | 2-3s |
| LLM clustering + scoring | 1 LLM call | ~$0.02 | 2-5s |
| **Total** | **4** | **~$0.14** | **~8-16s** |

---

## 7. Existing Code Integration Points

### What We Already Have

1. **POPClient** (`backend/app/integrations/pop.py`):
   - `create_report_task()` -- calls get-terms
   - `poll_for_result()` -- polls async tasks
   - `create_report()` -- creates full report from prepareId
   - `get_custom_recommendations()` -- gets placement recs
   - Full circuit breaker, retry, logging infrastructure
   - Mock client for testing with deterministic fixtures

2. **POP Content Brief Service** (`backend/app/services/pop_content_brief.py`):
   - `fetch_content_brief()` -- full 3-step orchestration
   - All parse helpers for LSI terms, competitors, related questions, etc.
   - Caching via ContentBrief model

3. **DataForSEO Client** (`backend/app/integrations/dataforseo.py`):
   - `get_keyword_volume()` -- volume/CPC/competition
   - `get_keyword_volume_batch()` -- batch processing with concurrency control
   - `get_keyword_suggestions()` -- related keyword ideas from Google Ads
   - `get_serp()` -- SERP results

4. **Primary Keyword Service** (`backend/app/services/primary_keyword.py`):
   - `generate_candidates()` -- LLM-based keyword generation from page content
   - `enrich_with_volume()` -- DataForSEO enrichment
   - `filter_to_specific()` -- LLM specificity filtering
   - `calculate_score()` -- composite scoring (volume + relevance + competition)
   - `select_primary_and_alternatives()` -- deduplication + selection

### Code Reuse Opportunities

For a new `KeywordClusterService`, we can reuse:
- DataForSEO's `get_keyword_suggestions()` for initial keyword expansion
- DataForSEO's `get_keyword_volume_batch()` for volume enrichment
- PrimaryKeywordService's `calculate_score()` logic for cluster keyword scoring
- POPClient for optional validation (get-terms variation overlap analysis)
- LLM integration for candidate generation and intent classification

---

## 8. Conclusion

**POP should NOT be the primary driver of keyword cluster creation.** Its API is designed for single-keyword on-page optimization, not keyword discovery or clustering. The Keyword Strategy Tool that does clustering is only available in the web UI, not the API.

**POP's best role is downstream**: once clusters are defined and approved, POP's 3-step flow generates the content briefs that power content creation. We already have this built and working.

**For cluster creation itself**, the recommended approach is:
1. LLM for creative keyword expansion + intent classification
2. DataForSEO for volume data + keyword suggestions
3. LLM for grouping candidates into coherent clusters
4. Optional: POP get-terms for SERP-grounded validation of cluster differentiation

This keeps cluster creation fast (~10-20 seconds), cheap (~$0.14), and reliable, while preserving POP's value where it truly shines -- content optimization.
