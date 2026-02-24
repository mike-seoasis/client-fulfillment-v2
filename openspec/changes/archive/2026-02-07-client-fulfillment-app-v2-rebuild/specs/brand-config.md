# Spec: brand-config

## Overview

Extracts brand voice, tone, and messaging guidelines from multiple sources: website analysis, customer reviews, and uploaded brand documents. Generates a comprehensive brand configuration that guides all content generation.

## Key Logic from Existing Implementation

The existing brand config uses a multi-source approach that MUST be preserved:

1. **Perplexity Website Analysis**: Deep analysis of brand positioning, voice, competitors
2. **Amazon Reviews Integration**: Auto-detect Amazon store, extract customer language
3. **On-Site Reviews**: Support Yotpo, Judge.me, and native review systems
4. **Document Parsing**: Extract guidelines from uploaded PDF/DOCX/TXT files
5. **Claude Synthesis**: Combine all sources into cohesive brand config
6. **Fallback Persona**: Generate from website when no reviews available

## Data Model - V2 Brand Config Schema

```
BrandConfig:
  # Foundation
  foundation:
    brand_name: string
    tagline: string
    core_promise: string
    key_differentiators: string[]
    target_audience: string

  # Voice Dimensions (1-10 scales)
  voice_dimensions:
    enthusiasm:
      score: integer (1-10)
      description: string
    formality:
      score: integer (1-10)
      description: string
    technical:
      score: integer (1-10)
      description: string
    warmth:
      score: integer (1-10)
      description: string

  # Writing Rules
  writing_rules:
    contractions_allowed: boolean
    punctuation:
      em_dashes_allowed: boolean
      exclamation_limit: integer
    sentence_structure:
      max_words: integer
      active_voice_preference: boolean

  # Vocabulary
  vocabulary:
    power_words: string[]
    banned_words: string[]
    brand_terms: string[]

  # Examples Bank
  examples_bank:
    headlines: string[]
    taglines: string[]
    cta_phrases: string[]

  # AI Prompts (for content generation)
  ai_prompts:
    writing_style: string
    tone_guidance: string
    things_to_avoid: string

  # Quick Reference
  quick_reference:
    voice_summary: string (1-2 sentences)
    dos: string[]
    donts: string[]

  # Metadata
  sources_used: string[]
  generated_at: datetime
  user_notes: string (user overrides)
```

## Behaviors

### WHEN starting brand config generation
- THEN set phase status to "in_progress"
- AND begin source collection in parallel

### WHEN analyzing website via Perplexity
- THEN query Perplexity with brand URL
- AND extract: brand positioning, target audience, voice characteristics
- AND identify competitors mentioned
- AND extract key product benefits and messaging themes

### WHEN detecting Amazon store
- THEN search for brand name + "amazon" via Perplexity
- AND if Amazon store found, extract store URL
- AND fetch top product reviews (first 20-30)
- AND extract customer language patterns

### WHEN integrating on-site reviews
- THEN detect review platform (Yotpo, Judge.me, native)
- AND fetch recent reviews via platform API or scraping
- AND extract common praise phrases
- AND identify customer pain points addressed

### WHEN parsing uploaded documents
- THEN accept PDF, DOCX, TXT formats
- AND extract text content
- AND identify sections: brand guidelines, tone of voice, do's/don'ts
- AND preserve exact wording from official guidelines

### WHEN synthesizing brand config
- THEN invoke Claude with all collected source data
- AND generate structured V2 brand config
- AND prioritize official documents over inferred data
- AND resolve conflicts by preferring explicit guidelines

### WHEN no reviews available
- THEN generate fallback persona from website analysis only
- AND flag config as "needs_review" for user validation
- AND provide reasonable defaults for voice dimensions

### WHEN user provides notes/overrides
- THEN store in user_notes field
- AND user_notes take precedence in content generation prompts
- AND preserve original generated config alongside

## Perplexity Prompt - Website Analysis

```
Analyze the brand at {website_url} and extract:

1. Brand Foundation
   - Brand name and tagline
   - Core value proposition
   - Key differentiators from competitors
   - Target audience description

2. Voice & Tone
   - Overall voice (friendly, professional, playful, etc.)
   - Enthusiasm level (subdued to energetic)
   - Formality level (casual to formal)
   - Technical complexity (simple to expert)

3. Messaging Themes
   - Recurring benefits mentioned
   - Emotional appeals used
   - Call-to-action patterns

4. Competitor Context
   - Main competitors in the space
   - How this brand differentiates

Return structured JSON following the schema above.
```

## Claude Prompt - Synthesis

```
Synthesize a brand configuration from these sources:

Website Analysis:
{perplexity_analysis}

Customer Reviews (if available):
{reviews_summary}

Brand Documents (if available):
{document_excerpts}

Create a complete V2 brand config that:
1. Captures the authentic brand voice
2. Uses customer language where available
3. Respects explicit guidelines from documents
4. Provides actionable writing guidance

Return the complete brand config JSON.
```

## API Endpoints

```
POST /api/v1/projects/{id}/phases/brand_config/run     - Start generation
GET  /api/v1/projects/{id}/phases/brand_config/status  - Get status
GET  /api/v1/projects/{id}/brand-config                - Get brand config
PUT  /api/v1/projects/{id}/brand-config                - Update config
POST /api/v1/projects/{id}/brand-config/documents      - Upload document
```

## Document Upload

**Supported formats**: PDF, DOCX, TXT
**Max size**: 10MB per document
**Max documents**: 5 per project

Storage: S3 or local filesystem with project-scoped paths

## Priority Pages Configuration

The brand config also includes priority pages for internal linking:
```
priority_pages: [
  {
    url: string,
    anchor_options: string[] (suggested anchor text variations)
  }
]
```

These are pages the business wants to promote via internal linking.

## Progress Tracking

```
progress breakdown:
  0-20%:   Website analysis (Perplexity)
  20-40%:  Review collection (Amazon, on-site)
  40-60%:  Document parsing
  60-90%:  Claude synthesis
  90-100%: Validation and storage
```

## Error Handling

- Perplexity timeout: Retry up to 2 times, then use fallback analysis
- No Amazon store found: Skip, not an error
- Review platform auth failed: Skip, log warning
- Document parsing failed: Log error, continue with other sources
- Claude synthesis failed: Retry, then fail phase with error

## Caching

- Website analysis: Cache for 7 days
- Review data: Cache for 24 hours (more dynamic)
- Generated config: Store in database, no TTL

## Database Schema

```sql
CREATE TABLE brand_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  config JSONB NOT NULL,
  sources_used JSONB DEFAULT '[]',
  user_notes TEXT,
  generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(project_id)
);

CREATE TABLE brand_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  filename VARCHAR(255) NOT NULL,
  file_type VARCHAR(20) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  extracted_text TEXT,
  uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_brand_configs_project ON brand_configs(project_id);
CREATE INDEX idx_brand_documents_project ON brand_documents(project_id);
```
