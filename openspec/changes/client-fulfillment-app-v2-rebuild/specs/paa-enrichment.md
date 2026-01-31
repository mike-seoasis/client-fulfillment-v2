# Spec: paa-enrichment

## Overview

Fetches "People Also Ask" questions from SERP data for each keyword and enriches the keyword data with relevant questions and answers. Uses a fan-out strategy to discover nested questions, with semantic filtering to ensure relevance.

## Key Logic from Existing Implementation

The existing PAA enrichment uses sophisticated strategies that MUST be preserved:

1. **Fan-Out Strategy**: Search initial keyword, then search each PAA question to find nested questions
2. **Related Searches Fallback**: If no PAA found, use Related Searches + LLM semantic filter
3. **Parallel Processing**: Async requests with rate limiting
4. **Max 20 Questions**: Cap per keyword to avoid overwhelming content

## Behaviors

### WHEN enriching a keyword with PAA
- THEN search SERP API for the keyword
- AND extract PAA questions from results
- AND for each PAA question, perform secondary search to find nested questions
- AND deduplicate questions across all searches
- AND cap at 20 questions maximum

### WHEN no PAA questions found
- THEN fall back to Related Searches from SERP
- AND use LLM to filter Related Searches to semantically relevant questions
- AND convert relevant searches to question format

### WHEN performing fan-out search
- THEN take top 3-5 initial PAA questions
- AND search each as a query
- AND extract PAA from secondary searches
- AND merge all unique questions

### WHEN filtering for relevance
- THEN invoke LLM with keyword context and question list
- AND ask: "Which questions are relevant to someone researching {keyword}?"
- AND LLM returns filtered list with relevance scores
- AND keep questions with relevance >= 70%

### WHEN processing in parallel
- THEN use async HTTP client (aiohttp)
- AND max 5 concurrent SERP API calls
- AND respect rate limits (10 requests/second typical)
- AND implement exponential backoff on 429 responses

## SERP API Integration

**Primary Option**: DataForSEO (decision from design.md)
**Fallback**: SerpAPI (if DataForSEO unavailable)

**DataForSEO Request**:
```json
{
  "keyword": "airtight coffee containers",
  "location_code": 2840,
  "language_code": "en",
  "device": "desktop",
  "os": "windows"
}
```

**Response fields used**:
- `items[].people_also_ask`: Array of PAA questions
- `items[].related_searches`: Array of related search terms

## Fan-Out Algorithm

```python
async def fetch_paa_with_fanout(keyword: str, max_questions: int = 20):
    # Initial search
    initial_results = await serp_search(keyword)
    initial_paa = extract_paa(initial_results)

    all_questions = set(initial_paa)

    # Fan-out: search each initial PAA question
    fanout_queries = initial_paa[:5]  # Top 5 for secondary search

    tasks = [serp_search(q) for q in fanout_queries]
    secondary_results = await asyncio.gather(*tasks)

    for result in secondary_results:
        nested_paa = extract_paa(result)
        all_questions.update(nested_paa)

    # Cap at max_questions
    return list(all_questions)[:max_questions]
```

## LLM Prompt - Semantic Filter

```
Filter these questions/searches for relevance to the keyword "{keyword}".

A relevant question:
- Would help someone researching or buying {keyword}
- Addresses a real concern about the product
- Could be naturally answered in product content

Questions to filter:
{questions_json}

Return JSON with relevance scores:
[
  {"question": "...", "relevance": 85, "keep": true},
  {"question": "...", "relevance": 45, "keep": false}
]

Only keep questions with relevance >= 70.
```

## PAA Question Categories

Group questions by intent for content planning:

```
buying_questions: ["best", "choose", "worth", "recommend", "need", "which"]
usage_questions: ["how to", "how do", "use", "work", "make", "can you"]
comparison_questions: ["vs", "versus", "better", "difference", "compare"]
care_questions: ["store", "clean", "care", "last", "maintain", "keep"]
other_questions: (everything else)
```

## API Endpoints

```
POST /api/v1/projects/{id}/phases/paa_enrichment/run     - Start enrichment
GET  /api/v1/projects/{id}/phases/paa_enrichment/status  - Get status
GET  /api/v1/projects/{id}/pages/{pageId}/paa            - Get PAA for page
PUT  /api/v1/projects/{id}/pages/{pageId}/paa            - Update/approve PAA
```

## Data Model

```
PagePAA:
  page_id: UUID (foreign key)
  keyword: string (the keyword searched)
  questions: [
    {
      question: string,
      source: "paa" | "related_search" | "fanout",
      category: "buying" | "usage" | "comparison" | "care" | "other",
      status: "pending" | "approved" | "rejected"
    }
  ]
  raw_paa: string[] (original unfiltered)
  related_searches: string[] (for fallback)
  enriched_at: datetime
```

## Caching Strategy

Cache SERP results to reduce API costs:
```
serp:{keyword}:{location} → 24h TTL
```

PAA questions change slowly, 24h cache is safe.

## Progress Tracking

```
progress = (keywords_enriched / total_keywords) * 100
```

## Error Handling

- SERP API timeout: Retry up to 3 times with backoff
- SERP API rate limit: Queue requests, increase delay
- No PAA found: Use Related Searches fallback
- No Related Searches: Return empty questions array, flag for manual review
- LLM timeout: Skip semantic filter, use all questions

## Cost Estimation

Per keyword:
- Initial SERP search: $0.002 (DataForSEO)
- Fan-out searches (5): $0.010
- Total per keyword: ~$0.012

For 50 collections: ~$0.60

## Database Schema

```sql
CREATE TABLE page_paa (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id UUID NOT NULL REFERENCES crawled_pages(id),
  keyword VARCHAR(200) NOT NULL,
  questions JSONB DEFAULT '[]',
  raw_paa JSONB DEFAULT '[]',
  related_searches JSONB DEFAULT '[]',
  enriched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(page_id)
);

CREATE INDEX idx_page_paa_page ON page_paa(page_id);
```
