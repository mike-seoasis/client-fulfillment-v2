# Spec: keyword-research

## Overview

Generates primary and secondary keywords for collection pages using a sophisticated 6-step workflow: LLM idea generation, volume lookup, specificity filtering, and intelligent selection. Integrates with Keywords Everywhere API for search volume data.

## Key Logic from Existing Implementation

The existing keyword research uses a refined 6-step process that MUST be preserved:

1. **Step 1 - LLM Generation**: Generate 20-30 keyword ideas per collection
2. **Step 2 - Volume Lookup**: Batch lookup via Keywords Everywhere API
3. **Step 3 - (Removed)**: Previously URL keywords, now skipped
4. **Step 4 - Specificity Filter**: LLM filters to SPECIFIC keywords only
5. **Step 5 - Primary Selection**: Highest volume specific keyword
6. **Step 6 - Secondary Selection**: Mix of specific + broader terms

## Critical Concept: Specificity

The most important insight from the existing implementation:

**SPECIFIC keywords** reference the exact products on the page:
- "airtight coffee containers" for a coffee container collection
- "ceramic pour over dripper" for a pour over collection

**GENERIC keywords** are too broad:
- "coffee storage" (could be any storage)
- "kitchen containers" (not specific to the collection)

The LLM filter in Step 4 is crucial for quality. Without it, the system selects high-volume generic terms that don't convert.

## Behaviors

### WHEN starting keyword research for a collection
- THEN verify collection has category = "collection"
- AND extract collection context (URL, title, h1, content)
- AND begin 6-step workflow

### WHEN generating keyword ideas (Step 1)
- THEN invoke LLM with collection context
- AND request 20-30 keyword variations
- AND include long-tail variations (3-5 words)
- AND include question-based keywords
- AND avoid brand names unless instructed

### WHEN looking up search volumes (Step 2)
- THEN batch keywords (max 100 per API call)
- AND call Keywords Everywhere API
- AND cache results for 30 days (volumes change slowly)
- AND handle missing keywords gracefully (volume = 0)

### WHEN filtering for specificity (Step 4)
- THEN invoke LLM with collection context AND keyword list with volumes
- AND ask: "Which keywords SPECIFICALLY describe THIS collection's products?"
- AND LLM returns only keywords that pass specificity test
- AND preserve volume data for passing keywords

### WHEN selecting primary keyword (Step 5)
- THEN from specific keywords, select highest volume
- AND ensure no duplicate primaries across collections in same project
- AND if duplicate detected, select next highest volume
- AND minimum volume threshold: 100 searches/month

### WHEN selecting secondary keywords (Step 6)
- THEN select 3-5 secondary keywords
- AND include: 2-3 specific keywords (lower volume than primary)
- AND include: 1-2 broader terms with volume > 1000
- AND avoid keywords already used as primary elsewhere

### WHEN caching volume data
- THEN cache key: `keyword_volume:{keyword}`
- AND TTL: 30 days
- AND check cache before API call
- AND batch uncached keywords for API

## LLM Prompt - Keyword Generation (Step 1)

```
Generate 20-30 keyword ideas for this collection page.

Collection: {collection_title}
URL: {url}
Products include: {content_excerpt}

Include:
- Primary search terms (what people search to find these products)
- Long-tail variations (3-5 words)
- Question keywords ("best X for Y", "how to choose X")
- Comparison keywords ("X vs Y")

Return JSON array of keywords:
["keyword 1", "keyword 2", ...]
```

## LLM Prompt - Specificity Filter (Step 4)

```
Filter these keywords to only those that SPECIFICALLY describe THIS collection's products.

Collection: {collection_title}
URL: {url}
Products: {content_excerpt}

Keywords with volumes:
{keywords_with_volumes_json}

A SPECIFIC keyword:
- References the exact product type in this collection
- Would make sense as the H1 for this specific page
- Is not so broad it could apply to many different collections

A GENERIC keyword (EXCLUDE):
- Too broad ("kitchen storage" for a coffee container collection)
- Could apply to many different product types
- Doesn't specifically describe what's on this page

Return JSON array of SPECIFIC keywords only:
["specific keyword 1", "specific keyword 2", ...]
```

## Keywords Everywhere API Integration

**Endpoint**: POST https://api.keywordseverywhere.com/v1/get_keyword_data

**Request**:
```json
{
  "dataSource": "gkp",
  "country": "us",
  "currency": "USD",
  "kw": ["keyword1", "keyword2"]
}
```

**Response fields used**:
- `vol`: Monthly search volume
- `cpc`: Cost per click (for competition indicator)
- `competition`: Competition score 0-1

## API Endpoints

```
POST /api/v1/projects/{id}/phases/keyword_research/run     - Start research
GET  /api/v1/projects/{id}/phases/keyword_research/status  - Get status
GET  /api/v1/projects/{id}/pages/{pageId}/keywords         - Get keywords for page
PUT  /api/v1/projects/{id}/pages/{pageId}/keywords         - Update/approve keywords
```

## Data Model

```
PageKeywords:
  page_id: UUID (foreign key)
  primary: {
    keyword: string,
    volume: integer,
    status: "pending" | "approved" | "rejected"
  }
  secondary: [
    {
      keyword: string,
      volume: integer,
      status: "pending" | "approved" | "rejected"
    }
  ]
  all_ideas: string[] (original 20-30 ideas)
  specific_keywords: string[] (post-filter)
  generated_at: datetime
```

## Duplicate Prevention

Track used primary keywords at project level:
```
used_primaries: Set<string>
```

Before assigning primary:
1. Check if keyword in used_primaries
2. If yes, select next highest volume specific keyword
3. Add selected keyword to used_primaries

## Progress Tracking

```
progress = (collections_processed / total_collections) * 100
```

Sub-steps per collection:
- Generating ideas: 0-20%
- Volume lookup: 20-40%
- Specificity filter: 40-60%
- Selection: 60-100%

## Error Handling

- Keywords Everywhere rate limit: Queue and retry with backoff
- API key invalid: Fail phase with clear error message
- Zero volume keywords: Still usable, flag for review
- LLM timeout: Retry up to 2 times

## Database Schema

```sql
CREATE TABLE page_keywords (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id UUID NOT NULL REFERENCES crawled_pages(id),
  primary_keyword VARCHAR(200),
  primary_volume INTEGER,
  primary_status VARCHAR(20) DEFAULT 'pending',
  secondary_keywords JSONB DEFAULT '[]',
  all_ideas JSONB DEFAULT '[]',
  specific_keywords JSONB DEFAULT '[]',
  generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(page_id)
);

CREATE INDEX idx_page_keywords_page ON page_keywords(page_id);
```
