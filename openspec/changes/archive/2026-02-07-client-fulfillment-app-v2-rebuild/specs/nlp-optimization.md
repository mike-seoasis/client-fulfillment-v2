# Spec: nlp-optimization

## Overview

Content scoring and optimization recommendations based on competitor analysis, TF-IDF term extraction, entity recognition, and readability scoring. This is a NEW capability not in the existing app, designed to help users improve content quality.

## Capabilities

1. **Content Scoring**: 0-100 optimization score based on multiple factors
2. **Competitor Analysis**: Analyze top SERP results for a keyword
3. **Term Recommendations**: TF-IDF analysis to find missing important terms
4. **Entity Extraction**: Identify entities competitors mention
5. **Readability Analysis**: Flesch-Kincaid and other readability metrics

## Behaviors

### WHEN analyzing content for optimization score
- THEN fetch competitor data for the primary keyword
- AND calculate component scores:
  - Word count score (compare to competitor average)
  - Semantic score (term coverage)
  - Readability score (Flesch-Kincaid)
  - Keyword density score
  - Entity coverage score
- AND weight components to produce 0-100 score
- AND generate specific recommendations

### WHEN analyzing competitors
- THEN fetch SERP results for keyword (top 10)
- AND scrape/fetch content from top 3-5 organic results
- AND extract: word counts, common terms, entities mentioned
- AND cache results for 24 hours

### WHEN recommending terms
- THEN perform TF-IDF analysis on competitor content
- AND identify terms that appear frequently in competitors
- AND filter to terms NOT in user's content
- AND rank by relevance score
- AND return top 20 recommended terms

### WHEN extracting entities
- THEN call Google Cloud NLP API on competitor content
- AND identify: products, brands, concepts, locations
- AND aggregate entity frequency across competitors
- AND return entities user's content is missing

### WHEN calculating readability
- THEN compute Flesch-Kincaid Grade Level
- AND compute Flesch Reading Ease score
- AND compare to competitor average
- AND recommend adjustments if too complex or too simple

## Score Components

### Word Count Score (20% weight)
```
target = competitor_avg_word_count
if user_word_count >= target * 0.9:
    score = 100
elif user_word_count >= target * 0.7:
    score = 80
elif user_word_count >= target * 0.5:
    score = 60
else:
    score = 40
```

### Semantic Score (25% weight)
Based on coverage of top TF-IDF terms from competitors:
```
covered_terms = terms_in_user_content ∩ top_competitor_terms
score = (len(covered_terms) / len(top_competitor_terms)) * 100
```

### Keyword Density Score (15% weight)
```
density = (keyword_occurrences / total_words) * 100
if 1.0 <= density <= 2.5:
    score = 100
elif 0.5 <= density < 1.0 or 2.5 < density <= 3.5:
    score = 70
else:
    score = 40
```

### Readability Score (20% weight)
```
fk_grade = flesch_kincaid_grade_level(content)
if 7 <= fk_grade <= 10:  # Ideal range for e-commerce
    score = 100
elif 5 <= fk_grade < 7 or 10 < fk_grade <= 12:
    score = 80
else:
    score = 60
```

### Entity Coverage Score (20% weight)
```
competitor_entities = extract_entities(competitor_content)
user_entities = extract_entities(user_content)
overlap = user_entities ∩ competitor_entities
score = (len(overlap) / len(competitor_entities)) * 100
```

## API Endpoints

```
POST /api/v1/nlp/analyze-content      - Full content analysis
POST /api/v1/nlp/analyze-competitors  - Competitor analysis only
POST /api/v1/nlp/recommend-terms      - Term recommendations
```

## Request/Response Schemas

### Analyze Content

**Request:**
```json
{
  "content": "<html content>",
  "keyword": "airtight coffee containers"
}
```

**Response:**
```json
{
  "score": 78,
  "components": {
    "word_count": {"score": 85, "value": 380, "target": 420},
    "semantic": {"score": 72, "covered": 18, "total": 25},
    "keyword_density": {"score": 100, "density": 1.8},
    "readability": {"score": 90, "grade_level": 8.2},
    "entity_coverage": {"score": 65, "covered": 8, "total": 12}
  },
  "recommendations": [
    "Add 40 more words to match competitor average",
    "Include terms: vacuum seal, freshness, aroma preservation",
    "Consider mentioning: BPA-free, food-grade materials"
  ],
  "word_count": 380,
  "readability_score": 65.2
}
```

### Analyze Competitors

**Request:**
```json
{
  "keyword": "airtight coffee containers"
}
```

**Response:**
```json
{
  "avg_word_count": 420,
  "top_terms": ["airtight", "seal", "freshness", "vacuum", "storage", ...],
  "top_entities": ["coffee beans", "stainless steel", "BPA-free", ...],
  "competitors_analyzed": 5
}
```

### Recommend Terms

**Request:**
```json
{
  "keyword": "airtight coffee containers",
  "current_content": "<html content>"
}
```

**Response:**
```json
{
  "terms": [
    {"term": "vacuum seal", "relevance": 0.92},
    {"term": "freshness", "relevance": 0.88},
    {"term": "aroma", "relevance": 0.85}
  ],
  "entities": [
    {"entity": "CO2 valve", "relevance": 0.78},
    {"entity": "food-grade", "relevance": 0.75}
  ]
}
```

## External Service Integration

### DataForSEO (SERP Data)
- Endpoint: POST /v3/serp/google/organic/live/advanced
- Cost: ~$0.002 per search
- Cache: 24 hours

### Google Cloud NLP (Entity Extraction)
- Endpoint: POST /v1/documents:analyzeEntities
- Cost: ~$0.001 per 1000 characters
- Use only on competitor content (not user content)

## Caching Strategy

```
serp:{keyword}:{location}        → 24h TTL (SERP results)
competitor_analysis:{keyword}    → 7d TTL (aggregated competitor data)
entities:{content_hash}          → 30d TTL (entity extraction results)
```

## TF-IDF Implementation

Use scikit-learn TfidfVectorizer or manual implementation:

```python
from sklearn.feature_extraction.text import TfidfVectorizer

def extract_top_terms(competitor_texts: List[str], top_n: int = 25):
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words='english',
        ngram_range=(1, 2)  # Include bigrams
    )
    tfidf_matrix = vectorizer.fit_transform(competitor_texts)

    # Average TF-IDF scores across documents
    avg_scores = tfidf_matrix.mean(axis=0).A1
    terms = vectorizer.get_feature_names_out()

    # Sort by score and return top N
    ranked = sorted(zip(terms, avg_scores), key=lambda x: -x[1])
    return ranked[:top_n]
```

## Readability Implementation

Flesch-Kincaid Grade Level formula:
```
FKGL = 0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
```

Flesch Reading Ease formula:
```
FRE = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
```

Use `textstat` Python library for reliable implementation.

## Error Handling

- SERP API failure: Return partial results with warning
- Google NLP quota exceeded: Skip entity analysis, return other scores
- Competitor content fetch failed: Use fewer competitors, adjust targets

## Database Schema

```sql
CREATE TABLE nlp_analysis_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key VARCHAR(500) NOT NULL UNIQUE,
  data JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX idx_nlp_cache_key ON nlp_analysis_cache(cache_key);
CREATE INDEX idx_nlp_cache_expires ON nlp_analysis_cache(expires_at);
```
