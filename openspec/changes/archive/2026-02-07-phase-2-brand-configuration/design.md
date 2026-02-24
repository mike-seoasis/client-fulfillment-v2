## Context

Phase 1 established the project CRUD foundation. Projects currently have `name`, `site_url`, and basic metadata. A `BrandConfig` model already exists but uses a minimal v2_schema structure focused on visual branding (colors, typography, logo). Phase 2 expands this to comprehensive brand guidelines that power AI content generation.

**Existing infrastructure:**
- `BrandConfig` model with `v2_schema` JSONB field (per-project, FK to projects)
- `ClaudeClient` integration with circuit breaker pattern
- `Crawl4AIClient` for website crawling
- FastAPI background tasks pattern
- TanStack Query for frontend data fetching

**Constraints:**
- Single-user MVP (no auth complexity)
- S3 for file storage in production, local filesystem for dev
- Background tasks via FastAPI BackgroundTasks (no Celery)
- Polling for status updates (2-3s interval)

## Goals / Non-Goals

**Goals:**
- Upload brand documents during project creation (PDF, DOCX, TXT)
- Generate comprehensive brand config following the 9-section skill bible structure
- Store extracted text and file metadata for regeneration
- View brand config in sectioned, readable UI
- Edit any section inline
- Regenerate individual sections or entire config

**Non-Goals:**
- Real-time streaming of generation progress (polling is sufficient)
- Document versioning (regeneration replaces current config)
- Multiple brand configs per project (one-to-one relationship)
- Image extraction from documents (text only for MVP)
- Authentication/authorization (single user for MVP)

## Decisions

### 1. File Storage: S3 with LocalStack fallback for dev

**Decision:** Use boto3 with S3-compatible API. LocalStack for local dev, real S3 for staging/production.

**Alternatives considered:**
- Local filesystem only: Simpler but doesn't match production, complicates Railway deployment
- Cloudflare R2: Good but S3 compatibility varies, and we already have AWS patterns

**Rationale:** S3 is battle-tested, boto3 is well-documented, LocalStack provides identical API for dev. Single abstraction layer works everywhere.

### 2. Text Extraction: pypdf + python-docx

**Decision:** Use `pypdf` for PDF text extraction and `python-docx` for Word documents. Plain text files read directly.

**Alternatives considered:**
- Apache Tika: More comprehensive but heavy dependency, requires Java
- AWS Textract: Better OCR but adds cost and complexity for text-only docs
- Unstructured.io: Good but adds external dependency

**Rationale:** pypdf and python-docx are pure Python, lightweight, and handle 95% of brand documents (which are typically text-heavy guides, not scanned images).

### 3. Brand Config Schema: Extend existing BrandConfig model

**Decision:** Extend the existing `BrandConfig.v2_schema` JSONB field with the full 9-section structure from the skill bible. Add `source_documents` and `additional_info` fields to track generation inputs.

**Structure:**
```json
{
  "version": "2.0",
  "generated_at": "2024-01-15T10:00:00Z",
  "source_documents": ["uuid1", "uuid2"],
  "additional_info": "User-provided notes...",

  "brand_foundation": { ... },
  "target_audience": { ... },
  "voice_dimensions": { ... },
  "voice_characteristics": { ... },
  "writing_style": { ... },
  "vocabulary": { ... },
  "trust_elements": { ... },
  "examples_bank": { ... },
  "competitor_context": { ... },
  "ai_prompt_snippet": "..."
}
```

**Alternatives considered:**
- Separate tables per section: Normalized but overcomplicates queries
- New BrandGuidelines model: Duplication with existing BrandConfig

**Rationale:** The existing model already has JSONB flexibility. Extending it keeps the data model simple and uses established patterns.

### 4. File Model: New ProjectFile table

**Decision:** Create `ProjectFile` model to track uploaded files with S3 keys, extracted text, and metadata.

**Schema:**
```python
class ProjectFile(Base):
    id: UUID
    project_id: UUID (FK)
    filename: str
    content_type: str  # MIME type
    s3_key: str
    extracted_text: Text | None
    file_size: int
    created_at: datetime
```

**Rationale:** Separate table allows multiple files per project, easy querying, and clear separation of concerns.

### 5. Generation Flow: Background task with status polling

**Decision:** Generation runs as a FastAPI BackgroundTask. Frontend polls `/api/v1/projects/{id}/brand-config/status` every 2 seconds.

**Status structure:**
```json
{
  "status": "generating",  // "pending" | "generating" | "complete" | "failed"
  "current_step": "voice_dimensions",
  "steps_completed": ["perplexity_research", "crawling", "processing_docs", "brand_foundation", "target_audience"],
  "steps_total": 13,
  "error": null
}
```

**Generation steps (13 total):**
1. `perplexity_research` - Web research via Perplexity API
2. `crawling` - Website crawl via Crawl4AI
3. `processing_docs` - Extract text from uploaded documents
4. `brand_foundation` - Generate section
5. `target_audience` - Generate section
6. `voice_dimensions` - Generate section
7. `voice_characteristics` - Generate section
8. `writing_style` - Generate section
9. `vocabulary` - Generate section
10. `trust_elements` - Generate section
11. `examples_bank` - Generate section
12. `competitor_context` - Generate section
13. `ai_prompt_snippet` - Generate final summary

**Alternatives considered:**
- WebSockets: More complex, overkill for this use case
- Server-Sent Events: Good but polling is simpler and sufficient

**Rationale:** Background tasks + polling is the established pattern per V2_REBUILD_PLAN.md decisions. Generation takes ~30-60 seconds, so 2s polling is responsive enough.

### 6. Generation Service: Research-first, then synthesis

**Decision:** Use a two-phase approach: (1) gather all research/source material in parallel, (2) synthesize into brand config sections using Claude.

**Phase 1 - Research (parallel where possible):**
1. **Perplexity brand research** → web research covering all 9 brand sections (reviews, press mentions, competitor info, social proof)
2. **Crawl website** (if URL provided) → extract markdown from homepage + key pages
3. **Extract text** from uploaded documents → PDF/DOCX text extraction

**Phase 2 - Synthesis (sequential):**
4. Combine all research into a context document
5. Generate sections in order using Claude (brand_foundation first, ai_prompt_snippet last)
6. Store complete config in BrandConfig.v2_schema

**Perplexity research prompt structure:**
The existing `PerplexityClient.research_brand()` method has a prompt covering 6 areas. We'll extend it to cover all 9 sections:
1. Brand Foundation (company info, mission, values, differentiators)
2. Target Audience (personas, demographics, psychographics)
3. Voice Indicators (formality, humor, tone analysis)
4. Voice Characteristics (what they are/aren't)
5. Writing Style (sentence patterns, punctuation, formatting)
6. Vocabulary (power words, banned words, industry terms)
7. Trust Elements (stats, credentials, testimonials, guarantees)
8. Examples Bank (headlines, CTAs, sample copy from their site)
9. Competitor Context (market position, differentiation)

**Why Perplexity + Crawl4AI + Docs?**
- **Perplexity**: External perspective (reviews, press, competitor analysis, social proof) - things not on their website
- **Crawl4AI**: Actual website content and voice patterns - ground truth
- **Uploaded docs**: Internal brand guidelines they already have - authoritative source

**Rationale:** Research-first means Claude has comprehensive context before synthesizing. Perplexity finds external data (reviews, press, competitor info) that wouldn't be in uploaded docs or the website itself.

### 7. API Design: RESTful with nested resources

**Endpoints:**
```
POST   /api/v1/projects/{id}/files           # Upload file
GET    /api/v1/projects/{id}/files           # List files
DELETE /api/v1/projects/{id}/files/{file_id} # Delete file

POST   /api/v1/projects/{id}/brand-config/generate   # Start generation
GET    /api/v1/projects/{id}/brand-config/status     # Poll status
GET    /api/v1/projects/{id}/brand-config            # Get config
PATCH  /api/v1/projects/{id}/brand-config            # Update section(s)
POST   /api/v1/projects/{id}/brand-config/regenerate # Regenerate (all or section)
```

**Rationale:** Nested under projects keeps resources logically grouped. Separate generate/status endpoints provide clear async workflow.

### 8. Frontend: Multi-step wizard for creation, tabbed view for editing

**Decision:**
- Project creation becomes a 2-step wizard (details → generation)
- Brand config view uses vertical tabs for sections (like wireframe)
- Inline editing with save per section

**Alternatives considered:**
- Single long form: Poor UX for 9 sections
- Modal per section: Disruptive

**Rationale:** Matches wireframe design, provides focused editing experience.

## Risks / Trade-offs

**Risk: Large document text extraction fails**
→ Mitigation: Cap file size at 10MB, truncate extracted text to 100k chars per document. Log warnings for oversized docs.

**Risk: Generation takes too long (>2 min)**
→ Mitigation: Run Perplexity, Crawl4AI, and doc extraction in parallel (Phase 1). Use faster Claude model (Haiku) for simpler sections, Sonnet for synthesis. Add timeout handling per step.

**Risk: S3 unavailable during upload**
→ Mitigation: Circuit breaker on S3 client, clear error messages, allow retry.

**Risk: Perplexity research returns limited data**
→ Mitigation: Perplexity research is additive, not required. If it fails or returns sparse data, continue with website crawl + docs. Log warning and note in generated config that external research was limited.

**Risk: Brand config schema evolves**
→ Mitigation: Version field in JSON allows migration logic. Non-breaking additions are fine.

**Trade-off: No real-time progress updates**
→ Polling at 2s intervals is "good enough" for MVP. Can add WebSockets later if users complain.

**Trade-off: Text-only extraction (no OCR)**
→ Acceptable for MVP. Most brand guides are text-based. Can add Textract later for scanned docs.

**Trade-off: Single Perplexity call vs. per-section calls**
→ One comprehensive research call is more efficient and cheaper than 9 separate calls. The prompt is structured to cover all sections in one response.
