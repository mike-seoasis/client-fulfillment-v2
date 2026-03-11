# Existing Client Fulfillment App - Complete Analysis

**Analysis Date**: January 31, 2026  
**Repository**: mike-seoasis/client-fulfilment-app  
**Purpose**: Document all features, architecture, and functionality for complete rebuild

---

## Executive Summary

The existing Client Fulfillment App is a **7-phase SEO content generation pipeline** built with FastAPI backend and HTML/Tailwind frontend. It automates the process of crawling e-commerce sites (primarily Shopify), categorizing pages, researching keywords, enriching with PAA data, generating brand configurations, and producing SEO-optimized content for collection pages.

### Current State

**Architecture**: 3-layer system (Directives → Orchestration → Execution)  
**Backend**: FastAPI (Python 3.12) with 3,217 lines in main.py  
**Frontend**: 11 HTML templates using Tailwind CSS  
**Database**: PostgreSQL + JSON fallback  
**Deployment**: Railway (configured)  
**Status**: MVP deployed and functional

### Key Strengths

✅ Complete 7-phase workflow implemented  
✅ All execution scripts working and tested  
✅ Background task processing with status tracking  
✅ Scheduled crawls with APScheduler  
✅ Comprehensive error handling and logging  
✅ Modular architecture with clear separation of concerns

### Key Weaknesses

⚠️ Monolithic main.py (3,217 lines - needs refactoring)  
⚠️ Mixed UI quality (some templates modern, others basic)  
⚠️ No NLP content optimization features  
⚠️ Limited code reusability (some duplication)  
⚠️ No comprehensive testing suite  
⚠️ Documentation scattered across multiple files

---

## Application Architecture

### High-Level Structure

```
Client Fulfillment App/
├── webapp/                          # Main application
│   ├── backend/                     # FastAPI server
│   │   ├── main.py                  # 3,217 lines - all API endpoints
│   │   ├── database.py              # PostgreSQL + JSON fallback
│   │   ├── repository.py            # Data access layer
│   │   └── requirements.txt         # Backend dependencies
│   ├── frontend/                    # HTML templates
│   │   ├── templates/               # 11 HTML files
│   │   └── static/                  # CSS/JS (minimal)
│   ├── execution/                   # Python scripts (17 files)
│   │   ├── lib/                     # Shared utilities (17 files)
│   │   └── *.py                     # Phase execution scripts
│   ├── directives/                  # SOPs in Markdown (9 files)
│   ├── config/                      # Brand configurations
│   └── skills/                      # Copywriting guidelines
├── directives/                      # Top-level directives
├── execution/                       # Top-level execution scripts
└── openspec/                        # OpenSpec specifications
```

### Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Backend** | FastAPI | Latest | REST API server |
| **Database** | PostgreSQL | Latest | Primary data store |
| **Database Fallback** | JSON files | N/A | Local development |
| **Task Queue** | APScheduler | 3.10+ | Scheduled crawls |
| **Frontend** | HTML + Tailwind CSS | 3.x | UI templates |
| **Web Crawler** | crawl4ai | 0.7+ | Site crawling |
| **LLM** | Anthropic Claude | 3.5 | Content generation |
| **NLP** | None | N/A | **Missing - to be added** |
| **Keyword API** | Keywords Everywhere | N/A | Keyword research |
| **PAA API** | AlsoAsked | N/A | People Also Ask data |
| **Deployment** | Railway | N/A | Cloud hosting |

---

## Feature Inventory

### 1. Project Management

**Location**: `backend/main.py` + `frontend/templates/dashboard.html`

**Features**:
- Create new client projects with website URL
- Auto-extract project name from domain
- Upload brand documents (PDF, DOC, DOCX, TXT, MD)
- Add brand notes and instructions
- Delete projects
- View all projects in dashboard
- Track project status across 7 phases

**API Endpoints**:
```
GET    /api/projects              # List all projects
POST   /api/projects              # Create project
GET    /api/projects/{id}         # Get project details
DELETE /api/projects/{id}         # Delete project
PUT    /api/projects/{id}         # Update project
```

**Database Schema** (Project model):
```python
{
    "id": str,                          # UUID
    "name": str,                        # Project/client name
    "website_url": str,                 # Target website
    "created_at": str,                  # ISO timestamp
    "updated_at": str,                  # ISO timestamp
    
    # Phase status tracking
    "phase1_status": str,               # pending|in_progress|completed|failed
    "phase2_status": str,
    "phase3_status": str,
    "phase4_status": str,
    "phase45_status": str,
    "phase46_status": str,
    "phase5_status": str,
    "phase5a_status": str,              # Research sub-phase
    "phase5b_status": str,              # Writing sub-phase
    "phase5c_status": str,              # QA sub-phase
    
    # Statistics
    "total_pages": int,
    "collection_pages": int,
    "keywords_approved": int,
    
    # File paths (outputs from each phase)
    "crawl_results_path": str,
    "categorized_pages_path": str,
    "labeled_pages_path": str,
    "keyword_enriched_path": str,
    "keyword_with_paa_path": str,
    "brand_config_path": str,
    "collection_content_path": str,
    "research_briefs_path": str,
    "draft_content_path": str,
    "validated_content_path": str,
    "collection_registry_path": str,
    
    # Scheduling
    "schedule_enabled": bool,
    "schedule_day": str,                # mon-sun
    "schedule_hour": int,               # 0-23
    "schedule_minute": int              # 0-59
}
```

---

### 2. Phase 1: Site Crawling

**Location**: `execution/crawl_site.py` + `frontend/templates/phase1.html`

**Purpose**: Crawl target website to discover all pages, extract metadata, and identify page types.

**Features**:
- Crawl website with configurable max pages
- Include/exclude URL patterns (e.g., `/collections/`, `/products/`)
- Exclude URLs from previous crawls
- Fetch-only mode (provide URL list, skip discovery)
- Extract page metadata (title, meta description, headers)
- Detect page types (collection, product, blog, etc.)
- Real-time progress tracking
- Dynamic timeout calculation based on page count

**Configuration Options**:
```python
{
    "website_url": str,                 # Required
    "max_pages": int,                   # Default: 50
    "include_patterns": str,            # e.g., "/collections/"
    "exclude_patterns": str,            # e.g., "/products/,/blogs/"
    "exclude_previous": bool,           # Skip previously crawled URLs
    "url_list": str                     # One URL per line (fetch-only mode)
}
```

**Output Format** (`crawl_results.json`):
```json
{
    "metadata": {
        "website_url": "https://example.com",
        "total_pages_crawled": 47,
        "crawl_started_at": "2025-12-27T...",
        "crawl_completed_at": "2025-12-27T...",
        "duration_seconds": 94
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "title": "Toronto Blue Jays Flags & Banners",
            "meta_description": "...",
            "h1": "Toronto Blue Jays Flags",
            "status_code": 200,
            "discovered_at": "2025-12-27T..."
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase1/run     # Start crawl
GET  /api/projects/{id}/phase1/status  # Check status
GET  /api/projects/{id}/phase1/results # Get results
```

**Performance**:
- Speed: ~2 seconds per page (network-bound)
- Timeout: Dynamic (base + 50% padding)
- Cost: Free (crawl4ai is open-source)

---

### 3. Phase 2: Page Categorization

**Location**: `execution/categorize_pages.py` + `frontend/templates/phase2.html`

**Purpose**: Use LLM to categorize each page into types (collection, product, blog, etc.).

**Features**:
- LLM-based categorization (Claude 3.5 Haiku)
- Predefined categories: collection, product, blog, about, contact, policy, other
- Batch processing for efficiency
- Confidence scoring
- Manual override capability

**Categories**:
- `collection` - Collection/category pages
- `product` - Individual product pages
- `blog` - Blog posts/articles
- `about` - About us, team, story pages
- `contact` - Contact, support pages
- `policy` - Terms, privacy, shipping policy
- `other` - Everything else

**Output Format** (`categorized_pages.json`):
```json
{
    "metadata": {
        "source_file": "crawl_results.json",
        "total_pages": 47,
        "categorized": 47,
        "categories": {
            "collection": 12,
            "product": 28,
            "blog": 4,
            "other": 3
        }
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "category": "collection",
            "confidence": 0.95,
            "reasoning": "URL pattern and content indicate collection page"
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase2/run     # Start categorization
GET  /api/projects/{id}/phase2/status  # Check status
GET  /api/projects/{id}/phase2/results # Get results
```

**Performance**:
- Speed: ~0.5 seconds per page
- Cost: ~$0.01-0.05 per 50 pages
- Accuracy: ~95% with Claude 3.5 Haiku

---

### 4. Phase 3: Labeling & Grouping

**Location**: `execution/label_pages.py` + `frontend/templates/phase3.html`

**Purpose**: Label collection pages with themes and identify related collections for internal linking.

**Features**:
- LLM-based thematic labeling
- Identify related collections (semantic similarity)
- Group pages by labels
- Generate internal linking recommendations
- Support for custom labels

**Label Examples**:
- Sports teams (e.g., "MLB", "NFL", "NBA")
- Geographic (e.g., "US States", "Cities")
- Product types (e.g., "Flags", "Banners", "Accessories")

**Output Format** (`labeled_pages.json`):
```json
{
    "metadata": {
        "source_file": "categorized_pages.json",
        "collection_pages": 12,
        "labels_generated": 8
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "category": "collection",
            "labels": ["MLB", "American League", "Sports Teams"],
            "related_collections": [
                {
                    "url": "https://example.com/collections/seattle-mariners",
                    "similarity_score": 0.89,
                    "reason": "Same league and sport"
                }
            ]
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase3/run     # Start labeling
GET  /api/projects/{id}/phase3/status  # Check status
GET  /api/projects/{id}/phase3/results # Get results
```

**Performance**:
- Speed: ~1 second per page
- Cost: ~$0.01-0.02 per 50 pages

---

### 5. Phase 4: Keyword Research

**Location**: `execution/keyword_research.py` + `frontend/templates/phase4.html`

**Purpose**: Research primary and secondary keywords for each collection page using LLM + Keywords Everywhere API.

**Features**:
- LLM-based keyword generation
- Keywords Everywhere API integration for volume data
- Primary keyword (1 per page)
- Secondary keywords (3-5 per page)
- Search volume and competition data
- Keyword difficulty scoring

**Output Format** (`keyword_enriched.json`):
```json
{
    "metadata": {
        "source_file": "labeled_pages.json",
        "collection_pages": 12,
        "keywords_researched": 12,
        "total_cost": "$0.15"
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "category": "collection",
            "keywords": {
                "primary": {
                    "keyword": "toronto blue jays flags",
                    "volume": 1200,
                    "competition": "medium",
                    "difficulty": 45
                },
                "secondary": [
                    {
                        "keyword": "blue jays banners",
                        "volume": 480,
                        "competition": "low"
                    }
                ]
            }
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase4/run     # Start keyword research
GET  /api/projects/{id}/phase4/status  # Check status
GET  /api/projects/{id}/phase4/results # Get results
```

**Performance**:
- Speed: ~3 seconds per page
- Cost: ~$0.07-0.22 per 50 pages (Keywords Everywhere API)

---

### 6. Phase 4.5: Keyword Approval & PAA Enrichment

**Location**: `frontend/templates/phase45.html` (manual checkpoint)

**Purpose**: Manual review and approval of keywords before expensive PAA enrichment.

**Features**:
- Full data table with search/filters
- Edit primary and secondary keywords
- View/edit PAA Q&A pairs
- Approval status tracking (pending, approved, rejected)
- Bulk approve/reject actions
- Cost estimator for PAA enrichment
- Category filters
- Search functionality

**Workflow**:
1. User reviews keyword research results
2. Edits keywords if needed
3. Approves collections for PAA enrichment
4. System estimates cost (AlsoAsked API)
5. User confirms and runs PAA enrichment
6. System fetches PAA questions and answers

**Output Format** (`keyword_with_paa.json`):
```json
{
    "metadata": {
        "source_file": "keyword_enriched.json",
        "approved_pages": 8,
        "paa_enriched": 8,
        "total_cost": "$0.24"
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "keywords": {...},
            "paa_data": [
                {
                    "question": "What size are Toronto Blue Jays flags?",
                    "answer": "Most Blue Jays flags come in 3x5 feet..."
                }
            ],
            "approval_status": "approved"
        }
    ]
}
```

**API Endpoints**:
```
GET  /api/projects/{id}/keywords          # Get keywords for approval
PUT  /api/projects/{id}/keywords          # Update approved keywords
POST /api/projects/{id}/enrich-paa        # Run PAA enrichment
GET  /api/projects/{id}/paa-status        # Check PAA status
```

**Performance**:
- PAA Speed: ~2 seconds per page
- PAA Cost: ~$0.03 per keyword (AlsoAsked API)

---

### 7. Phase 4.6: Brand Config Generator

**Location**: `execution/generate_brand_config_v2.py` + `frontend/templates/phase46.html`

**Purpose**: Generate comprehensive brand configuration from uploaded documents and website analysis.

**Features**:
- Upload brand documents (PDF, DOC, DOCX, TXT, MD)
- Extract brand voice, tone, style guidelines
- Identify target audience
- Extract value propositions
- Define priority pages for internal linking
- Perplexity API integration for web research
- Manual text input option

**Output Format** (`brand_config.json`):
```json
{
    "brand_info": {
        "name": "Heartland Flags",
        "tagline": "Premium American-made flags",
        "target_audience": "Patriotic Americans, sports fans, businesses",
        "value_propositions": [
            "Made in USA",
            "Free shipping",
            "Lifetime warranty"
        ]
    },
    "writing_style": {
        "tone": "Professional, patriotic, confident",
        "voice": "Authoritative but approachable",
        "avoid_phrases": ["em dashes (—)", "fluffy language"],
        "preferred_phrases": ["premium quality", "American-made"]
    },
    "priority_pages": [
        {
            "url": "https://example.com/collections/american-flags",
            "anchor": "American Flags"
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase46/run       # Generate brand config
POST /api/projects/{id}/upload-brand-doc  # Upload brand document
GET  /api/projects/{id}/brand-config      # Get brand config
```

**Performance**:
- Speed: ~30 seconds (single Perplexity call)
- Cost: ~$0.01-0.03 per project

---

### 8. Phase 5: Content Generation (3-Phase System)

**Location**: `execution/phase5a_research.py`, `phase5b_write.py`, `phase5c_qa.py` + `frontend/templates/phase5.html`

**Purpose**: Generate complete SEO-optimized content for collection pages.

#### Phase 5A: Research & Briefs

**Features**:
- Analyze competitor content
- Extract content patterns
- Generate content briefs
- Identify gaps and opportunities

**Output**: Research briefs for each page

#### Phase 5B: Content Writing

**Features**:
- Generate 5 SEO content pieces per page:
  1. **H1** (5-10 words)
  2. **Title Tag** (50-60 characters)
  3. **Meta Description** (150-160 characters)
  4. **Top Description** (1-2 sentences)
  5. **Bottom Description** (300-450 words with H2/H3 structure)

**Content Structure** (Bottom Description):
```html
<h2>Primary Keyword Header (Title Case, max 7 words)</h2>
<p>Opening paragraph (80-100 words: quality, selection, value props)</p>

<h3>First Selling Point (Title Case, max 7 words)</h3>
<p>Advantages paragraph (80-100 words: PAA-inspired, differentiators)</p>

<p>Related Collections: <a href="...">Link 1</a> | <a href="...">Link 2</a> | <a href="...">Link 3</a></p>
<p>Priority Pages: <a href="...">Link 1</a> | <a href="...">Link 2</a> | <a href="...">Link 3</a></p>

<h3>Second Selling Point (Title Case, max 7 words)</h3>
<p>Closing paragraph (60-80 words: CTA, free shipping, guarantees)</p>
```

**Content Rules**:
- NO em dashes (—)
- Headers in Title Case, max 7 words
- DON'T bold keywords
- Sales-driven, specific, concrete
- Use absolute URLs for all links
- Pipe separators (|) between links
- 300-450 words total

#### Phase 5C: QA & Validation

**Features**:
- AI trope detection (remove clichés)
- Keyword density check
- Readability scoring
- Link validation
- Brand voice consistency check
- Schema pollution detection

**Output Format** (`collection_content.json`):
```json
{
    "metadata": {
        "source_files": {
            "keywords": "keyword_with_paa.json",
            "labels": "labeled_pages.json",
            "brand_config": "brand_config.json"
        },
        "content_format": "html",
        "collection_pages_found": 12,
        "content_generated": 12,
        "content_failed": 0,
        "total_tokens_used": 24000,
        "estimated_cost": "$0.20"
    },
    "pages": [
        {
            "url": "https://example.com/collections/toronto-blue-jays",
            "content": {
                "h1": "Toronto Blue Jays Flags & Banners",
                "title_tag": "Toronto Blue Jays Flags - Official MLB Team Banners",
                "meta_description": "Show your Toronto Blue Jays pride...",
                "top_description": {
                    "format": "json",
                    "content": {...}
                },
                "bottom_description": {
                    "format": "html",
                    "content": "<h2>...</h2>..."
                },
                "word_count": 325,
                "tokens_used": 2600,
                "qa_passed": true,
                "qa_issues": []
            }
        }
    ]
}
```

**API Endpoints**:
```
POST /api/projects/{id}/phase5/run        # Generate content
POST /api/projects/{id}/phase5a/run       # Research phase
POST /api/projects/{id}/phase5b/run       # Writing phase
POST /api/projects/{id}/phase5c/run       # QA phase
GET  /api/projects/{id}/content           # Get generated content
GET  /api/projects/{id}/content/{page_id} # Get single page content
PUT  /api/projects/{id}/content/{page_id} # Edit content
```

**Performance**:
- Speed: ~5 seconds per page (writing phase)
- Cost: ~$0.20-0.30 per 50 pages (Claude 3.5 Haiku)

---

### 9. Scheduled Crawls

**Location**: `backend/main.py` (APScheduler integration)

**Purpose**: Automatically re-crawl sites on a schedule to detect new pages.

**Features**:
- Configure crawl schedule per project (day of week + time)
- Enable/disable scheduling
- Automatic crawl execution
- Status notifications
- Conflict prevention (don't run if already in progress)

**Configuration**:
```python
{
    "schedule_enabled": bool,
    "schedule_day": str,      # mon, tue, wed, thu, fri, sat, sun
    "schedule_hour": int,     # 0-23 (e.g., 22 = 10pm)
    "schedule_minute": int    # 0-59
}
```

**API Endpoints**:
```
PUT /api/projects/{id}/schedule    # Update schedule config
GET /api/projects/{id}/schedule    # Get schedule config
```

**Implementation**:
- Uses APScheduler with AsyncIOScheduler
- CronTrigger for scheduling
- Jobs persisted in database
- Loaded on server startup

---

### 10. Shopify Schema Generator (Standalone Tool)

**Location**: `execution/shopify_schema_generator.py` + `frontend/templates/shopify_schema.html`

**Purpose**: Generate JSON-LD structured data for Shopify themes.

**Features**:
- Generate Organization schema
- Generate Product schema
- Generate BreadcrumbList schema
- Generate Review/AggregateRating schema
- Theme file parser (detects existing schema)
- Schema pollution detection (avoid duplicates)

**API Endpoints**:
```
POST /api/shopify-schema/generate  # Generate schema
GET  /shopify-schema               # Schema generator UI
```

---

### 11. Content Editing Interface

**Location**: `frontend/templates/content_edit.html`

**Purpose**: Edit generated content before exporting.

**Features**:
- Rich text editor
- Live preview
- Word count tracking
- Keyword highlighting
- Undo/redo
- Save drafts
- Export to CSV/JSON

---

## Execution Scripts Inventory

### Core Phase Scripts

| Script | Purpose | Lines | Dependencies |
|--------|---------|-------|--------------|
| `crawl_site.py` | Phase 1: Crawl website | ~300 | crawl4ai, requests |
| `categorize_pages.py` | Phase 2: Categorize pages | ~200 | anthropic |
| `label_pages.py` | Phase 3: Label & group | ~250 | anthropic |
| `keyword_research.py` | Phase 4: Keyword research | ~350 | anthropic, requests (KE API) |
| `enrich_with_paa.py` | Phase 4.5: PAA enrichment | ~200 | requests (AlsoAsked API) |
| `generate_brand_config_v2.py` | Phase 4.6: Brand config | ~400 | anthropic, PyPDF2, python-docx |
| `generate_collection_content.py` | Phase 5: Content generation | ~500 | anthropic |
| `phase5a_research.py` | Phase 5A: Research | ~300 | anthropic |
| `phase5b_write.py` | Phase 5B: Writing | ~400 | anthropic |
| `phase5c_qa.py` | Phase 5C: QA | ~350 | anthropic |

### Utility Scripts

| Script | Purpose | Lines |
|--------|---------|-------|
| `crawl_specific_urls.py` | Crawl specific URL list | ~150 |
| `fetch_gsc_keywords.py` | Fetch Google Search Console data | ~200 |
| `generate_collection_registry.py` | Create collection index | ~150 |
| `update_collection_registry.py` | Update collection index | ~100 |
| `shopify_schema_generator.py` | Generate JSON-LD schema | ~600 |
| `test_browser_pooling.py` | Test browser pool performance | ~100 |

### Library Modules (`execution/lib/`)

| Module | Purpose | Lines |
|--------|---------|-------|
| `ai_trope_detector.py` | Detect AI-generated clichés | ~200 |
| `amazon_reviews_client.py` | Fetch Amazon reviews | ~150 |
| `async_processor.py` | Async batch processing | ~100 |
| `brand_schema.py` | Brand config schema validation | ~150 |
| `gsc_client.py` | Google Search Console API | ~250 |
| `link_validator.py` | Validate internal/external links | ~100 |
| `onsite_reviews_client.py` | Fetch on-site reviews | ~150 |
| `perplexity_client.py` | Perplexity API wrapper | ~100 |
| `prompt_logger.py` | Log LLM prompts/responses | ~80 |
| `qa_checklist.py` | Content QA checklist | ~200 |
| `schema_graph_builder.py` | Build schema graph | ~300 |
| `schema_pollution_detector.py` | Detect duplicate schema | ~150 |
| `shopify_theme_parser.py` | Parse Shopify theme files | ~250 |
| `social_client.py` | Fetch social media data | ~150 |
| `trustpilot_client.py` | Fetch Trustpilot reviews | ~150 |
| `volume_cache.py` | Cache keyword volume data | ~100 |

---

## Frontend Templates Inventory

| Template | Purpose | Lines | Status |
|----------|---------|-------|--------|
| `dashboard.html` | Project dashboard | ~400 | ✅ Complete |
| `phase1.html` | Crawl configuration | ~300 | ✅ Complete |
| `phase2.html` | Categorization results | ~250 | ✅ Complete |
| `phase3.html` | Labeling results | ~250 | ✅ Complete |
| `phase4.html` | Keyword research results | ~300 | ✅ Complete |
| `phase45.html` | Keyword approval | ~600 | ✅ Complete (most complex) |
| `phase46.html` | Brand config generator | ~350 | ✅ Complete |
| `phase5.html` | Content generation results | ~400 | ✅ Complete |
| `content_edit.html` | Content editor | ~500 | ✅ Complete |
| `client.html` | Client detail view | ~300 | ✅ Complete |
| `shopify_schema.html` | Schema generator | ~400 | ✅ Complete |

**Total Frontend Code**: ~4,050 lines of HTML/JS

---

## API Endpoints Summary

### Project Management
```
GET    /                                  # Dashboard
GET    /api/projects                      # List projects
POST   /api/projects                      # Create project
GET    /api/projects/{id}                 # Get project
DELETE /api/projects/{id}                 # Delete project
PUT    /api/projects/{id}                 # Update project
```

### Phase 1: Crawl
```
GET  /phase1                               # Crawl UI
POST /api/projects/{id}/phase1/run        # Start crawl
GET  /api/projects/{id}/phase1/status     # Check status
GET  /api/projects/{id}/phase1/results    # Get results
```

### Phase 2: Categorize
```
GET  /phase2                               # Categorize UI
POST /api/projects/{id}/phase2/run        # Start categorization
GET  /api/projects/{id}/phase2/status     # Check status
GET  /api/projects/{id}/phase2/results    # Get results
```

### Phase 3: Label
```
GET  /phase3                               # Label UI
POST /api/projects/{id}/phase3/run        # Start labeling
GET  /api/projects/{id}/phase3/status     # Check status
GET  /api/projects/{id}/phase3/results    # Get results
```

### Phase 4: Keywords
```
GET  /phase4                               # Keywords UI
POST /api/projects/{id}/phase4/run        # Start keyword research
GET  /api/projects/{id}/phase4/status     # Check status
GET  /api/projects/{id}/phase4/results    # Get results
```

### Phase 4.5: Approval & PAA
```
GET  /phase45                              # Approval UI
GET  /api/projects/{id}/keywords          # Get keywords
PUT  /api/projects/{id}/keywords          # Update keywords
POST /api/projects/{id}/enrich-paa        # Run PAA enrichment
GET  /api/projects/{id}/paa-status        # Check PAA status
```

### Phase 4.6: Brand Config
```
GET  /phase46                              # Brand config UI
POST /api/projects/{id}/phase46/run       # Generate brand config
POST /api/projects/{id}/upload-brand-doc  # Upload document
GET  /api/projects/{id}/brand-config      # Get brand config
```

### Phase 5: Content Generation
```
GET  /phase5                               # Content UI
POST /api/projects/{id}/phase5/run        # Generate content
POST /api/projects/{id}/phase5a/run       # Research phase
POST /api/projects/{id}/phase5b/run       # Writing phase
POST /api/projects/{id}/phase5c/run       # QA phase
GET  /api/projects/{id}/content           # Get all content
GET  /api/projects/{id}/content/{page_id} # Get single page
PUT  /api/projects/{id}/content/{page_id} # Edit content
```

### Scheduling
```
PUT /api/projects/{id}/schedule            # Update schedule
GET /api/projects/{id}/schedule            # Get schedule
```

### Standalone Tools
```
GET  /shopify-schema                       # Schema generator UI
POST /api/shopify-schema/generate          # Generate schema
```

**Total Endpoints**: 40+

---

## Database Schema

### PostgreSQL Tables

#### `projects` Table
```sql
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    website_url VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Phase status
    phase1_status VARCHAR(20) DEFAULT 'pending',
    phase2_status VARCHAR(20) DEFAULT 'pending',
    phase3_status VARCHAR(20) DEFAULT 'pending',
    phase4_status VARCHAR(20) DEFAULT 'pending',
    phase45_status VARCHAR(20) DEFAULT 'pending',
    phase46_status VARCHAR(20) DEFAULT 'pending',
    phase5_status VARCHAR(20) DEFAULT 'pending',
    phase5a_status VARCHAR(20) DEFAULT 'pending',
    phase5b_status VARCHAR(20) DEFAULT 'pending',
    phase5c_status VARCHAR(20) DEFAULT 'pending',
    
    -- Statistics
    total_pages INTEGER DEFAULT 0,
    collection_pages INTEGER DEFAULT 0,
    keywords_approved INTEGER DEFAULT 0,
    
    -- File paths
    crawl_results_path VARCHAR(500),
    categorized_pages_path VARCHAR(500),
    labeled_pages_path VARCHAR(500),
    keyword_enriched_path VARCHAR(500),
    keyword_with_paa_path VARCHAR(500),
    brand_config_path VARCHAR(500),
    collection_content_path VARCHAR(500),
    research_briefs_path VARCHAR(500),
    draft_content_path VARCHAR(500),
    validated_content_path VARCHAR(500),
    collection_registry_path VARCHAR(500),
    
    -- Scheduling
    schedule_enabled BOOLEAN DEFAULT FALSE,
    schedule_day VARCHAR(3) DEFAULT 'sun',
    schedule_hour INTEGER DEFAULT 22,
    schedule_minute INTEGER DEFAULT 0
);
```

#### `pages` Table (optional - for caching)
```sql
CREATE TABLE pages (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    category VARCHAR(50),
    title VARCHAR(500),
    meta_description TEXT,
    h1 VARCHAR(500),
    status_code INTEGER,
    crawled_at TIMESTAMP,
    UNIQUE(project_id, url)
);
```

#### `keywords` Table (optional - for caching)
```sql
CREATE TABLE keywords (
    id VARCHAR(36) PRIMARY KEY,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    page_url VARCHAR(500) NOT NULL,
    primary_keyword VARCHAR(255),
    secondary_keywords JSONB,
    paa_data JSONB,
    approval_status VARCHAR(20) DEFAULT 'pending',
    UNIQUE(project_id, page_url)
);
```

---

## Cost Analysis

### Per-Project Cost Breakdown (50 pages)

| Phase | Service | Cost |
|-------|---------|------|
| **Phase 1: Crawl** | crawl4ai (free) | $0.00 |
| **Phase 2: Categorize** | Claude 3.5 Haiku | $0.01-0.05 |
| **Phase 3: Label** | Claude 3.5 Haiku | $0.01-0.02 |
| **Phase 4: Keywords** | Claude + Keywords Everywhere | $0.07-0.22 |
| **Phase 4.5: PAA** | AlsoAsked API | $0.15-0.75 |
| **Phase 4.6: Brand** | Perplexity API | $0.01-0.03 |
| **Phase 5: Content** | Claude 3.5 Haiku | $0.20-0.30 |
| **Total** | | **$0.45-1.37** |

### Monthly Operating Costs (Hosting)

| Service | Cost |
|---------|------|
| Railway (Hobby plan) | $5/month |
| PostgreSQL (Railway) | $5/month |
| Total | **$10/month** |

---

## Issues & Technical Debt

### Critical Issues

1. **Monolithic main.py** (3,217 lines)
   - Hard to maintain
   - Difficult to test
   - Needs refactoring into modules

2. **No NLP Content Optimization**
   - Missing competitor analysis
   - No TF-IDF scoring
   - No readability optimization
   - No semantic similarity

3. **Limited Testing**
   - No unit tests
   - No integration tests
   - Manual testing only

### Medium Issues

4. **Inconsistent UI Quality**
   - Some templates modern (phase45.html)
   - Others basic (phase2.html, phase3.html)
   - Need consistent design system

5. **Code Duplication**
   - Similar patterns repeated across phases
   - Could extract shared utilities

6. **Error Handling**
   - Good in some areas
   - Inconsistent across scripts

7. **Documentation**
   - Scattered across multiple files
   - No centralized API docs
   - Missing inline comments

### Low Priority Issues

8. **No User Authentication**
   - Single-user only
   - No team collaboration

9. **Limited Export Options**
   - JSON only
   - Need CSV, Google Sheets, Shopify CSV

10. **No Analytics Dashboard**
    - Can't track costs per project
    - No performance metrics

---

## Dependencies

### Backend (`webapp/requirements.txt`)
```
python-dotenv>=1.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
crawl4ai>=0.7.0
pandas>=2.1.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
anthropic>=0.18.0
PyPDF2>=3.0.0
python-docx>=1.1.0
APScheduler>=3.10.0
pytest>=7.4.0
pytest-asyncio>=0.23.0
fastapi
uvicorn
```

### Frontend
- Tailwind CSS (CDN)
- No build step required

---

## Deployment Configuration

### Railway (`railway.json`)
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "cd webapp/backend && python3 main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Environment Variables Required
```
ANTHROPIC_API_KEY=...
KEYWORDS_EVERYWHERE_API_KEY=...
ALSOASKED_API_KEY=...
PERPLEXITY_API_KEY=...
DATABASE_URL=postgresql://...
DATA_DIR=/data
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Lines of Code** | ~15,000+ |
| **Backend (main.py)** | 3,217 lines |
| **Execution Scripts** | 17 files, ~5,000 lines |
| **Library Modules** | 17 files, ~2,500 lines |
| **Frontend Templates** | 11 files, ~4,050 lines |
| **API Endpoints** | 40+ |
| **Database Tables** | 3 (projects, pages, keywords) |
| **External APIs** | 5 (Claude, KE, AlsoAsked, Perplexity, GSC) |
| **Phases** | 7 main + 3 sub-phases |

---

## Recommendations for Rebuild

### Must-Have Improvements

1. **Refactor main.py** into modular structure:
   - `routers/` - Separate router files per phase
   - `services/` - Business logic layer
   - `models/` - Pydantic models
   - `utils/` - Shared utilities

2. **Add NLP Content Optimization**:
   - Integrate components from previous research
   - SERP scraping for competitor analysis
   - TF-IDF scoring
   - Readability analysis
   - Entity extraction

3. **Modernize UI**:
   - Use impeccable Claude skill for design
   - Consistent design system
   - Better UX flows
   - Responsive design

4. **Add Testing**:
   - Unit tests for all services
   - Integration tests for API endpoints
   - E2E tests for critical workflows

5. **Improve Documentation**:
   - OpenAPI/Swagger docs
   - Inline code comments
   - Architecture diagrams
   - Setup guides

### Nice-to-Have Improvements

6. **User Authentication** (Auth0, Clerk)
7. **Team Collaboration** (multi-user support)
8. **Export Options** (CSV, Google Sheets, Shopify CSV)
9. **Analytics Dashboard** (costs, performance)
10. **Webhook Integrations** (Slack, Discord notifications)

---

**Analysis Complete**  
**Next Step**: Design new architecture with NLP integration and modern UI
