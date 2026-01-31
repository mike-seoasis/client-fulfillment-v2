# Tasks: Client Fulfillment App V2 Rebuild

## 1. Project Setup & Infrastructure

- [ ] 1.1 Initialize backend project structure with layered architecture (app/api, app/services, app/repositories, app/models, app/schemas, app/integrations, app/workers)
- [ ] 1.2 Set up FastAPI application with CORS, exception handlers, and OpenAPI docs
- [ ] 1.3 Configure SQLAlchemy with async support and PostgreSQL connection
- [ ] 1.4 Set up Alembic for database migrations with auto-generation
- [ ] 1.5 Add Redis client with connection pooling and circuit breaker pattern
- [ ] 1.6 Create pytest configuration with fixtures for database and Redis mocking
- [ ] 1.7 Set up GitHub Actions CI pipeline (lint, test, type-check)
- [ ] 1.8 Configure Railway deployment for staging environment

## 2. Database Models & Migrations

- [ ] 2.1 Create Project model with phase_status JSONB field
- [ ] 2.2 Create CrawledPage model with normalized_url, category, labels fields
- [ ] 2.3 Create PageKeywords model with primary/secondary keyword structure
- [ ] 2.4 Create PagePAA model for PAA enrichment data
- [ ] 2.5 Create BrandConfig model with V2 schema JSONB
- [ ] 2.6 Create GeneratedContent model with QA results
- [ ] 2.7 Create CrawlSchedule and CrawlHistory models
- [ ] 2.8 Create NLPAnalysisCache model for competitor data
- [ ] 2.9 Generate and run initial Alembic migration

## 3. Core Services - Project Management

- [ ] 3.1 Implement ProjectRepository with CRUD operations
- [ ] 3.2 Implement ProjectService with validation logic
- [ ] 3.3 Create Pydantic schemas for Project create/update/response
- [ ] 3.4 Implement /api/v1/projects endpoints (list, create, get, update, delete)
- [ ] 3.5 Add WebSocket endpoint for project status updates
- [ ] 3.6 Write unit tests for ProjectService (target 80% coverage)

## 4. Core Services - Crawl Pipeline

- [ ] 4.1 Create crawl4ai integration client with async support
- [ ] 4.2 Implement URL normalization utility (fragments, trailing slashes, query params)
- [ ] 4.3 Implement priority queue for URL crawling (homepage=0, include=1, other=2)
- [ ] 4.4 Implement CrawlService with include/exclude pattern matching
- [ ] 4.5 Implement CrawlRepository for page storage with deduplication
- [ ] 4.6 Add fetch-only mode for re-crawling specific URLs
- [ ] 4.7 Implement progress tracking and WebSocket broadcasts
- [ ] 4.8 Create /api/v1/projects/{id}/phases/crawl endpoints
- [ ] 4.9 Write unit tests for CrawlService (URL normalization, pattern matching)

## 5. Core Services - Page Categorization

- [ ] 5.1 Implement URL pattern rules (collection, product, blog, policy patterns)
- [ ] 5.2 Implement content signal detection for confidence boosting
- [ ] 5.3 Create LLM categorization client using Claude Haiku
- [ ] 5.4 Implement CategoryService with two-tier approach (patterns → LLM fallback)
- [ ] 5.5 Add batch processing for LLM calls (groups of 10)
- [ ] 5.6 Create /api/v1/projects/{id}/phases/categorize endpoints
- [ ] 5.7 Write unit tests for pattern matching and confidence scoring

## 6. Core Services - Page Labeling

- [ ] 6.1 Implement LabelService for generating 2-5 thematic labels per collection
- [ ] 6.2 Create LLM prompt template for label generation
- [ ] 6.3 Implement related collections algorithm (label overlap scoring)
- [ ] 6.4 Add parallel processing for label generation (max 5 concurrent)
- [ ] 6.5 Create /api/v1/projects/{id}/phases/label endpoints
- [ ] 6.6 Write unit tests for related collections algorithm

## 7. Core Services - Keyword Research

- [ ] 7.1 Create Keywords Everywhere API integration client
- [ ] 7.2 Implement keyword volume caching in Redis (30d TTL)
- [ ] 7.3 Implement Step 1: LLM keyword idea generation (20-30 ideas)
- [ ] 7.4 Implement Step 2: Batch volume lookup with caching
- [ ] 7.5 Implement Step 4: LLM specificity filter (CRITICAL logic)
- [ ] 7.6 Implement Step 5: Primary keyword selection (highest volume specific)
- [ ] 7.7 Implement Step 6: Secondary keyword selection (specific + broader mix)
- [ ] 7.8 Add duplicate primary prevention across project
- [ ] 7.9 Create /api/v1/projects/{id}/phases/keyword_research endpoints
- [ ] 7.10 Write unit tests for specificity filter and selection logic

## 8. Core Services - PAA Enrichment

- [ ] 8.1 Create DataForSEO API integration client (or SerpAPI fallback)
- [ ] 8.2 Implement SERP result caching in Redis (24h TTL)
- [ ] 8.3 Implement fan-out strategy (search initial PAA questions for nested)
- [ ] 8.4 Implement Related Searches fallback with LLM semantic filter
- [ ] 8.5 Add PAA question categorization by intent (buying, usage, care, comparison)
- [ ] 8.6 Implement parallel processing with rate limiting (max 5 concurrent)
- [ ] 8.7 Create /api/v1/projects/{id}/phases/paa_enrichment endpoints
- [ ] 8.8 Write unit tests for fan-out and categorization logic

## 9. Core Services - Brand Config

- [ ] 9.1 Create Perplexity API integration client for website analysis
- [ ] 9.2 Implement Amazon store auto-detection and review fetching
- [ ] 9.3 Implement on-site review platform detection (Yotpo, Judge.me)
- [ ] 9.4 Create document parser for PDF, DOCX, TXT brand documents
- [ ] 9.5 Implement Claude synthesis for V2 brand config schema
- [ ] 9.6 Add fallback persona generation when no reviews available
- [ ] 9.7 Create /api/v1/projects/{id}/phases/brand_config endpoints
- [ ] 9.8 Add document upload endpoint with S3/local storage
- [ ] 9.9 Write unit tests for brand config synthesis

## 10. Core Services - Content Generation

- [ ] 10.1 Implement Phase 5A: PAA analysis by intent categorization
- [ ] 10.2 Implement Phase 5A: Perplexity research integration
- [ ] 10.3 Implement Phase 5A: Content plan builder (main angle, benefits, questions)
- [ ] 10.4 Implement Phase 5B: Skill Bible rules in prompt template
- [ ] 10.5 Implement Phase 5B: Brand voice context injection
- [ ] 10.6 Implement Phase 5B: Internal link insertion (Related + See Also rows)
- [ ] 10.7 Implement Phase 5B: Structured content generation (H1, meta, descriptions)
- [ ] 10.8 Implement Phase 5C: AI trope detection (banned words, patterns, em dashes)
- [ ] 10.9 Implement Phase 5C: Link validation against collection registry
- [ ] 10.10 Implement Phase 5C: Word count validation (300-450 required)
- [ ] 10.11 Implement Phase 5C: LLM QA fix for minimal corrections
- [ ] 10.12 Add parallel processing for all three phases
- [ ] 10.13 Create /api/v1/projects/{id}/phases/content_generation endpoints
- [ ] 10.14 Add regeneration endpoint for failed pages
- [ ] 10.15 Write unit tests for trope detection and QA logic

## 11. Core Services - NLP Optimization (New Feature)

- [ ] 11.1 Create Google Cloud NLP integration client for entity extraction
- [ ] 11.2 Implement competitor content fetching and scraping
- [ ] 11.3 Implement TF-IDF analysis for term extraction
- [ ] 11.4 Implement content scoring algorithm (word count, semantic, readability, keyword density, entity coverage)
- [ ] 11.5 Implement Flesch-Kincaid readability calculation
- [ ] 11.6 Add competitor analysis caching (7d TTL)
- [ ] 11.7 Create /api/v1/nlp/analyze-content endpoint
- [ ] 11.8 Create /api/v1/nlp/analyze-competitors endpoint
- [ ] 11.9 Create /api/v1/nlp/recommend-terms endpoint
- [ ] 11.10 Write unit tests for scoring algorithm

## 12. Core Services - Scheduled Crawls

- [ ] 12.1 Set up APScheduler with SQLAlchemy job store
- [ ] 12.2 Implement schedule configuration CRUD
- [ ] 12.3 Implement change detection algorithm (content hash comparison)
- [ ] 12.4 Implement notification system (email templates, webhook payloads)
- [ ] 12.5 Add startup recovery for interrupted crawls
- [ ] 12.6 Create /api/v1/projects/{id}/schedule endpoints
- [ ] 12.7 Create /api/v1/projects/{id}/crawl-history endpoints
- [ ] 12.8 Write unit tests for change detection

## 13. Frontend - Project Setup

- [ ] 13.1 Initialize React 18 + TypeScript + Vite project
- [ ] 13.2 Configure Tailwind CSS with custom design tokens
- [ ] 13.3 Set up React Router for navigation
- [ ] 13.4 Configure React Query for data fetching and caching
- [ ] 13.5 Set up Axios client with base URL and error interceptors
- [ ] 13.6 Add WebSocket client for real-time updates
- [ ] 13.7 Install and configure shadcn/ui component library

## 14. Frontend - Core Components

- [ ] 14.1 Create AppLayout with navigation sidebar
- [ ] 14.2 Create ProjectCard component for project list
- [ ] 14.3 Create PhaseProgress component with status indicators
- [ ] 14.4 Create DataTable component for page listings
- [ ] 14.5 Create FormField components with validation display
- [ ] 14.6 Create LoadingSpinner and skeleton states
- [ ] 14.7 Create Toast notification system

## 15. Frontend - Project Management Views

- [ ] 15.1 Build ProjectListPage with create button and search
- [ ] 15.2 Build ProjectDetailPage with phase status overview
- [ ] 15.3 Build CreateProjectModal with URL validation
- [ ] 15.4 Build ProjectSettingsPage for configuration

## 16. Frontend - Phase Execution Views

- [ ] 16.1 Build CrawlPhasePanel with config form and progress
- [ ] 16.2 Build CategorizePhasePanel with page category breakdown
- [ ] 16.3 Build LabelPhasePanel with label visualization
- [ ] 16.4 Build KeywordResearchPanel with approval workflow
- [ ] 16.5 Build PAAEnrichmentPanel with question review
- [ ] 16.6 Build BrandConfigPanel with document upload and editor
- [ ] 16.7 Build ContentGenerationPanel with 3-phase progress

## 17. Frontend - Content Management Views

- [ ] 17.1 Build ContentListPage with status filtering
- [ ] 17.2 Build ContentEditorPage with live preview
- [ ] 17.3 Build NLPOptimizationPanel with score breakdown
- [ ] 17.4 Build ContentExportModal with format options

## 18. Frontend - Real-Time Updates

- [ ] 18.1 Implement WebSocket connection manager
- [ ] 18.2 Add phase progress real-time updates
- [ ] 18.3 Add toast notifications for phase completion
- [ ] 18.4 Implement optimistic updates for approval workflows

## 19. Testing & Quality

- [ ] 19.1 Achieve 80% test coverage on backend services
- [ ] 19.2 Add integration tests for API endpoints
- [ ] 19.3 Add E2E tests for critical workflows (crawl → content generation)
- [ ] 19.4 Run type checking with mypy (backend) and tsc (frontend)
- [ ] 19.5 Configure pre-commit hooks (black, isort, eslint, prettier)

## 20. Data Migration

- [ ] 20.1 Create V1 data export script (projects, pages, keywords, content)
- [ ] 20.2 Create V2 schema transformation script
- [ ] 20.3 Test migration on staging with production data snapshot
- [ ] 20.4 Validate data integrity post-migration
- [ ] 20.5 Document rollback procedure

## 21. Deployment & Cutover

- [ ] 21.1 Set up Railway production environment
- [ ] 21.2 Configure production PostgreSQL and Redis
- [ ] 21.3 Set up environment variables for API keys
- [ ] 21.4 Deploy V2 to production (parallel with V1)
- [ ] 21.5 Run production data migration
- [ ] 21.6 DNS cutover to V2
- [ ] 21.7 Monitor for 48 hours
- [ ] 21.8 Decommission V1 after validation
