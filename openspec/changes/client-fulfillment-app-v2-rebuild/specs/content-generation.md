# Spec: content-generation

## Overview

Three-phase content pipeline for generating SEO-optimized collection page content: Research (5A), Writing (5B), and QA (5C). Applies "Skill Bible" copywriting rules and brand voice to produce human-sounding content with proper internal linking.

## Key Logic from Existing Implementation

The existing content generation uses sophisticated logic that MUST be preserved:

### Phase 5A - Research
1. **PAA Analysis**: Group questions by intent (buying, usage, care, comparison)
2. **Perplexity Research**: Deep dive on keyword topic for benefits and concerns
3. **Content Plan**: Synthesize main angle, priority questions, competitive points

### Phase 5B - Writing
1. **Skill Bible Rules**: Strict copywriting guidelines that prevent AI-sounding content
2. **Brand Voice Integration**: Apply V2 brand config to writing prompts
3. **Internal Linking**: Insert related collections + priority pages
4. **Structured Output**: H1, title tag, meta description, top description, bottom description

### Phase 5C - QA
1. **AI Trope Detection**: Catch banned words, em dashes, negation patterns
2. **Link Validation**: Verify all internal links exist in collection registry
3. **Word Count Check**: Bottom description MUST be 300-450 words
4. **LLM QA Fix**: Second-pass cleanup for patterns regex might miss

## Skill Bible Rules (CRITICAL)

These rules are essential for human-sounding content:

### The 5 Laws
1. **Benefits Over Features**: Say what it DOES FOR THE CUSTOMER
2. **Specificity Sells**: Use numbers, materials, specific details
3. **One Idea Per Sentence**: Short, punchy sentences
4. **Write Like You Talk**: If you stumble reading aloud, rewrite
5. **Every Word Earns Its Place**: Cut unnecessary words

### Structure Requirements
- H1: 3-7 words, Title Case, includes primary keyword naturally
- H1 MUST NOT have benefit taglines ("for Ultimate Freshness")
- Paragraphs: 2-4 sentences max
- Bottom description: EXACTLY 300-450 words

### BANNED (instant AI detection)
- Em dashes (—) - use commas or periods
- Words: delve, unlock, unleash, journey, game-changer, revolutionary, crucial, cutting-edge
- Phrases: "In today's fast-paced world", "It's important to note"
- Triplet patterns (Fast. Simple. Powerful.)
- Negation patterns: "aren't just X, they're Y", "more than just X"
- Max 1 of: indeed, furthermore, moreover, robust, seamless, comprehensive

## Behaviors

### WHEN starting Phase 5A (Research)
- THEN filter to collection pages with approved primary keywords
- AND for each, analyze PAA questions by intent category
- AND query Perplexity for keyword research
- AND build content plan with main angle and priority questions

### WHEN analyzing PAA questions
- THEN categorize by intent keywords:
  - buying: "buy", "best", "choose", "worth", "recommend"
  - usage: "how to", "how do", "use", "work", "make"
  - comparison: "vs", "versus", "better", "difference"
  - care: "store", "clean", "care", "last", "maintain"
- AND prioritize: buying questions first, then care, then usage
- AND select top 5 as priority questions

### WHEN building content plan
- THEN determine main angle based on question distribution:
  - More care questions → focus on storage/freshness/longevity
  - More buying questions → focus on purchase decision/value
  - More usage questions → focus on practical benefits
- AND extract benefits from Perplexity research (top 5)
- AND identify competitive differentiators

### WHEN starting Phase 5B (Writing)
- THEN load research briefs from 5A
- AND load brand config and labeled pages
- AND process each page sequentially or in parallel

### WHEN generating content for a page
- THEN build prompt with:
  - Skill Bible rules (full text)
  - Brand voice context
  - Research insights (benefits, questions, angle)
  - Internal link options (related + priority)
- AND call Claude with temperature 0.4 (slightly creative but controlled)
- AND parse JSON response

### WHEN inserting internal links
- THEN include 3 "Related:" links from related_collections (by label overlap)
- AND include 3 "See Also:" links from priority_pages (business priority)
- AND use descriptive anchor text (not URLs)
- AND format: `<a href="URL">Anchor</a> | <a href="URL">Anchor</a>`

### WHEN starting Phase 5C (QA)
- THEN load draft content from 5B
- AND validate each page

### WHEN validating content
- THEN run AI trope detection (regex-based)
- AND validate internal links against collection registry
- AND check word count (300-450 required)
- AND run QA checklist
- AND if issues found, run LLM QA fix

### WHEN LLM QA fix runs
- THEN send content with fix instructions
- AND LLM makes minimal changes to fix specific issues
- AND preserve structure, links, and length
- AND return fixed content

### WHEN QA fails with hard blockers
- THEN mark page as needs_manual_review
- AND hard blockers: broken links, word count out of range
- AND soft issues (tropes) are fixed by LLM, not failures

## Content Structure

### Bottom Description (EXACTLY 300-450 words)

```html
<h2>[Primary keyword phrase, Title Case, max 7 words]</h2>
<p>[Opening paragraph: 80-100 words about quality, selection. Address customer with "you/your".]</p>

<h3>[Selling point with keyword, Title Case, max 7 words]</h3>
<p>[Benefits paragraph: 80-100 words. Weave in PAA answers naturally.]</p>

<p>Related: <a href="URL1">Anchor1</a> | <a href="URL2">Anchor2</a> | <a href="URL3">Anchor3</a></p>

<p>See Also: <a href="URL1">Anchor1</a> | <a href="URL2">Anchor2</a> | <a href="URL3">Anchor3</a></p>

<h3>[Second selling point, Title Case, max 7 words]</h3>
<p>[REQUIRED Closing paragraph: 60-80 words with CTA. Mention shipping, guarantee. THIS IS MANDATORY.]</p>
```

## API Endpoints

```
POST /api/v1/projects/{id}/phases/content_generation/run     - Start pipeline
GET  /api/v1/projects/{id}/phases/content_generation/status  - Get status
GET  /api/v1/projects/{id}/content                           - List all content
GET  /api/v1/projects/{id}/content/{contentId}               - Get single content
PUT  /api/v1/projects/{id}/content/{contentId}               - Update content
POST /api/v1/projects/{id}/content/{contentId}/regenerate    - Regenerate single page
```

## Parallel Processing

All three phases support parallel processing:
- 5A: Max 3 concurrent Perplexity calls (Tier 0 limit)
- 5B: Max 5 concurrent Claude calls
- 5C: Max 5 concurrent Claude QA calls

## Progress Tracking

Overall content_generation phase progress:
```
0-33%:   Phase 5A (Research)
33-66%:  Phase 5B (Writing)
66-100%: Phase 5C (QA)
```

## Regeneration Flow

When a page needs regeneration (manual or after QA failure):
1. Add QA failure reasons to brief as `qa_failures_to_avoid`
2. Re-run Phase 5B for that page only
3. Re-run Phase 5C for that page only
4. Update content in database

## Data Model

```
GeneratedContent:
  id: UUID
  page_id: UUID (foreign key)
  h1: string
  title_tag: string
  meta_description: string
  top_description: string
  bottom_description: string (HTML)
  word_count: integer
  optimization_score: integer (0-100, from NLP analysis)
  research_brief: JSON (from 5A)
  qa_results: JSON (from 5C)
  status: "draft" | "validated" | "needs_review" | "approved"
  generated_at: datetime
  validated_at: datetime
```

## Database Schema

```sql
CREATE TABLE generated_content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id UUID NOT NULL REFERENCES crawled_pages(id),
  h1 VARCHAR(200),
  title_tag VARCHAR(100),
  meta_description VARCHAR(200),
  top_description TEXT,
  bottom_description TEXT,
  word_count INTEGER,
  optimization_score INTEGER,
  research_brief JSONB,
  qa_results JSONB,
  status VARCHAR(20) DEFAULT 'draft',
  generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  validated_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(page_id)
);

CREATE INDEX idx_generated_content_page ON generated_content(page_id);
CREATE INDEX idx_generated_content_status ON generated_content(status);
```
