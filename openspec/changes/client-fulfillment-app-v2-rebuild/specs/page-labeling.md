# Spec: page-labeling

## Overview

Generates thematic labels for collection pages and identifies related collections based on label overlap. Labels enable intelligent internal linking by grouping semantically similar collections.

## Key Logic from Existing Implementation

The existing labeler uses a two-pass approach that MUST be preserved:

1. **First Pass - Label Generation**: LLM analyzes each collection and generates 2-5 thematic labels
2. **Second Pass - Related Collections**: For each collection, find others with overlapping labels
3. **Top 5 Related**: Return the 5 most related collections with similarity reasoning

## Behaviors

### WHEN generating labels for a collection
- THEN invoke LLM with collection URL, title, h1, and content excerpt
- AND request 2-5 descriptive labels that capture the collection's theme
- AND labels should be lowercase, hyphenated (e.g., "home-organization", "kitchen-storage")
- AND avoid overly generic labels (e.g., "products", "items")

### WHEN finding related collections
- THEN for each collection, compare its labels against all other collections
- AND calculate overlap score (number of shared labels)
- AND rank by overlap score descending
- AND return top 5 with highest overlap
- AND include reasoning explaining the connection

### WHEN collections share no labels
- THEN return empty related_collections array
- AND this is valid - not all collections are related

### WHEN processing labels in batch
- THEN process collections in parallel (max 5 concurrent)
- AND use Claude 3.5 Haiku for cost efficiency
- AND batch size of 1 collection per LLM call (labels need full context)

## LLM Prompt Template - Label Generation

```
Analyze this collection page and generate 2-5 thematic labels.

URL: {url}
Title: {title}
H1: {h1}
Content excerpt: {content_excerpt}

Labels should:
- Be lowercase with hyphens (e.g., "coffee-storage", "kitchen-organization")
- Capture the collection's theme, not just product type
- Be specific enough to enable meaningful grouping
- Avoid generic terms like "products", "items", "shop"

Return JSON:
{
  "labels": ["label-1", "label-2", "label-3"],
  "reasoning": "Brief explanation of why these labels fit"
}
```

## Label Examples

**Good labels:**
- "coffee-storage" (specific theme)
- "kitchen-organization" (functional category)
- "gift-sets" (purchase intent)
- "eco-friendly" (product attribute)
- "premium-glassware" (quality + type)

**Bad labels:**
- "products" (too generic)
- "collection" (meaningless)
- "items" (too generic)
- "store" (not descriptive)

## Related Collections Algorithm

```python
def find_related_collections(target_collection, all_collections):
    target_labels = set(target_collection.labels)
    candidates = []

    for collection in all_collections:
        if collection.url == target_collection.url:
            continue

        collection_labels = set(collection.labels)
        shared = target_labels & collection_labels

        if shared:
            candidates.append({
                'url': collection.url,
                'title': collection.title,
                'shared_labels': list(shared),
                'overlap_count': len(shared),
                'reason': f"Shares labels: {', '.join(list(shared)[:3])}"
            })

    # Sort by overlap count, take top 5
    candidates.sort(key=lambda x: x['overlap_count'], reverse=True)
    return candidates[:5]
```

## API Endpoints

```
POST /api/v1/projects/{id}/phases/label/run     - Start labeling
GET  /api/v1/projects/{id}/phases/label/status  - Get status
GET  /api/v1/projects/{id}/pages/{pageId}/related - Get related collections
```

## Data Updates

After labeling, collection pages gain:
```
labels: string[] (2-5 thematic labels)
label_reasoning: string (LLM's explanation)
related_collections: [
  {
    "url": string,
    "title": string,
    "reason": string,
    "shared_labels": string[]
  }
]
```

## Processing Order

1. Filter pages to only process collections (category = "collection")
2. Generate labels for all collections (parallel, max 5 concurrent)
3. After all labels generated, compute related collections (CPU-bound, fast)
4. Update database with labels and related collections

## Progress Tracking

```
progress = (collections_labeled / total_collections) * 100
```

Split into two sub-phases:
- Labeling: 0-80%
- Finding related: 80-100%

## Error Handling

- LLM timeout: Retry up to 2 times, then assign empty labels
- Invalid JSON response: Parse what's possible, log warning
- Empty content: Generate labels from URL and title only

## Database Schema Updates

```sql
ALTER TABLE crawled_pages ADD COLUMN labels JSONB DEFAULT '[]';
ALTER TABLE crawled_pages ADD COLUMN label_reasoning TEXT;
ALTER TABLE crawled_pages ADD COLUMN related_collections JSONB DEFAULT '[]';

CREATE INDEX idx_crawled_pages_labels ON crawled_pages USING GIN(labels);
```
