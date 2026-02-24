# Spec: page-categorization

## Overview

Classifies crawled pages into types (collection, product, blog, policy, etc.) using a two-tier approach: fast URL pattern matching for high-confidence cases, LLM fallback for ambiguous cases. Includes confidence scoring to indicate certainty.

## Key Logic from Existing Implementation

The existing categorizer uses a refined approach that MUST be preserved:

1. **Rule-Based First**: URL patterns provide instant, free classification for obvious cases
2. **Confidence Tiers**: High (patterns + content signals), Medium (patterns only), Low (neither)
3. **LLM Fallback**: Only invoked for medium/low confidence cases (saves API costs)
4. **Batch Processing**: Groups pages for efficient LLM calls

## Page Categories

```
collection  - Product listing pages (e.g., /collections/coffee-mugs)
product     - Individual product pages (e.g., /products/ceramic-mug)
blog        - Blog posts and articles (e.g., /blogs/news/article-title)
page        - Static content pages (e.g., /pages/about-us)
policy      - Legal/policy pages (e.g., /policies/privacy-policy)
homepage    - Site homepage
other       - Uncategorized pages
```

## Behaviors

### WHEN categorizing pages
- THEN first apply URL pattern rules
- AND check content signals to boost confidence
- AND for medium/low confidence, invoke LLM classification
- AND store category and confidence for each page

### WHEN applying URL pattern rules

**Collection patterns** (high confidence if matched):
```
/collections/
/collection/
/c/
/shop/
/category/
```

**Product patterns**:
```
/products/
/product/
/p/
/item/
```

**Blog patterns**:
```
/blogs/
/blog/
/articles/
/news/
/journal/
```

**Policy patterns** (exact match):
```
/policies/
/privacy
/terms
/refund
/shipping-policy
```

### WHEN calculating confidence score

**High confidence (90-100%):**
- URL matches pattern AND content confirms (e.g., collection URL with product grid)
- Exact policy URL match

**Medium confidence (60-89%):**
- URL matches pattern but content unclear
- OR content signals present but URL ambiguous

**Low confidence (0-59%):**
- Neither URL nor content provides clear signals
- Requires LLM classification

### WHEN invoking LLM classification
- THEN batch pages in groups of 10 for efficiency
- AND provide URL, title, h1, and content excerpt (first 500 chars)
- AND use Claude 3.5 Haiku for cost efficiency
- AND parse structured response with category and reasoning

### WHEN LLM classifies a page
- THEN accept the LLM's category as final
- AND store the reasoning for debugging
- AND set confidence based on LLM's expressed certainty

## LLM Prompt Template

```
Classify these pages into categories: collection, product, blog, page, policy, homepage, other.

For each page, analyze the URL structure and content to determine the most likely category.

Pages to classify:
{pages_json}

Return JSON array:
[
  {"url": "...", "category": "collection", "confidence": 85, "reasoning": "URL contains /collections/ and content shows product grid"}
]
```

## Content Signals

**Collection signals:**
- Multiple product cards/images
- Filter/sort UI elements
- Pagination
- "X products" count text

**Product signals:**
- Add to cart button
- Price display
- Product variants (size, color)
- Single main product image

**Blog signals:**
- Article date
- Author byline
- Social share buttons
- Comment section

## API Endpoints

```
POST /api/v1/projects/{id}/phases/categorize/run     - Start categorization
GET  /api/v1/projects/{id}/phases/categorize/status  - Get status
GET  /api/v1/projects/{id}/pages?category=collection - Filter by category
```

## Data Updates

After categorization, each CrawledPage gains:
```
category: string (one of the defined categories)
category_confidence: integer (0-100)
category_source: "pattern" | "llm"
category_reasoning: string | null
```

## Performance Optimization

- Pattern matching: ~1ms per page (run on all pages)
- LLM classification: ~500ms per batch of 10 pages
- Only invoke LLM for medium/low confidence pages
- Expected LLM usage: 10-30% of pages for typical Shopify sites

## Error Handling

- LLM timeout: Retry up to 2 times, then mark as "other" with low confidence
- LLM rate limit: Queue and retry with backoff
- Invalid LLM response: Fall back to "other" category

## Database Schema Updates

```sql
ALTER TABLE crawled_pages ADD COLUMN category VARCHAR(20);
ALTER TABLE crawled_pages ADD COLUMN category_confidence INTEGER;
ALTER TABLE crawled_pages ADD COLUMN category_source VARCHAR(20);
ALTER TABLE crawled_pages ADD COLUMN category_reasoning TEXT;

CREATE INDEX idx_crawled_pages_category ON crawled_pages(project_id, category);
```
