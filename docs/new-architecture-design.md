# New Application Architecture Design
## Client Fulfillment App V2 with NLP Content Optimization

**Design Date**: January 31, 2026  
**Target**: Complete rebuild with modern architecture, clean code, and NLP features

---

## Design Principles

### Core Principles

1. **Modularity**: Break monolithic code into small, focused modules
2. **Testability**: Every component should be unit-testable
3. **Maintainability**: Clean code, clear naming, comprehensive documentation
4. **Scalability**: Design for growth (more clients, more features)
5. **Performance**: Optimize for speed and cost-efficiency
6. **User Experience**: Modern, intuitive, responsive UI

### Technical Principles

- **Separation of Concerns**: API → Services → Repository → Database
- **DRY (Don't Repeat Yourself)**: Extract common patterns
- **SOLID Principles**: Single responsibility, open/closed, etc.
- **Error Handling**: Comprehensive logging and user-friendly messages
- **Type Safety**: Use Pydantic models and type hints everywhere
- **Async First**: Leverage async/await for I/O operations

---

## High-Level Architecture

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  React + TypeScript + Tailwind CSS                     │ │
│  │  - Modern component-based UI                           │ │
│  │  - Real-time updates (WebSocket)                       │ │
│  │  - Responsive design                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────┐
│                       API Layer                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  FastAPI Routers                                       │ │
│  │  - /api/projects (CRUD)                                │ │
│  │  - /api/phases/* (Phase execution)                     │ │
│  │  - /api/nlp/* (NLP optimization)                       │ │
│  │  - /api/content/* (Content management)                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Business Logic Services                               │ │
│  │  - ProjectService                                      │ │
│  │  - CrawlService                                        │ │
│  │  - KeywordService                                      │ │
│  │  - ContentService                                      │ │
│  │  - NLPService (NEW)                                    │ │
│  │  - BrandService                                        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Repository Layer                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Data Access Objects (DAOs)                            │ │
│  │  - ProjectRepository                                   │ │
│  │  - PageRepository                                      │ │
│  │  - KeywordRepository                                   │ │
│  │  - ContentRepository                                   │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL (Primary)                                  │ │
│  │  Redis (Caching)                                       │ │
│  │  File Storage (S3 or local)                            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  - Claude API (LLM)                                    │ │
│  │  - Keywords Everywhere (Keyword data)                  │ │
│  │  - AlsoAsked (PAA data)                                │ │
│  │  - DataForSEO / SerpAPI (SERP data) [NEW]             │ │
│  │  - Google Cloud NLP (Entity extraction) [NEW]         │ │
│  │  - Perplexity (Brand research)                         │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
client-fulfillment-app-v2/
├── frontend/                           # React frontend
│   ├── src/
│   │   ├── components/                 # Reusable UI components
│   │   │   ├── common/                 # Buttons, inputs, modals
│   │   │   ├── dashboard/              # Dashboard components
│   │   │   ├── phases/                 # Phase-specific components
│   │   │   └── nlp/                    # NLP optimization components
│   │   ├── pages/                      # Page components
│   │   │   ├── Dashboard.tsx
│   │   │   ├── ProjectDetail.tsx
│   │   │   ├── Phase1.tsx
│   │   │   └── ...
│   │   ├── hooks/                      # Custom React hooks
│   │   ├── services/                   # API client services
│   │   ├── types/                      # TypeScript types
│   │   ├── utils/                      # Utility functions
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/                            # FastAPI backend
│   ├── app/
│   │   ├── api/                        # API routers
│   │   │   ├── v1/
│   │   │   │   ├── projects.py         # Project CRUD
│   │   │   │   ├── phases.py           # Phase execution
│   │   │   │   ├── nlp.py              # NLP optimization [NEW]
│   │   │   │   ├── content.py          # Content management
│   │   │   │   └── tools.py            # Standalone tools
│   │   │   └── deps.py                 # Dependency injection
│   │   │
│   │   ├── services/                   # Business logic
│   │   │   ├── project_service.py
│   │   │   ├── crawl_service.py
│   │   │   ├── categorize_service.py
│   │   │   ├── label_service.py
│   │   │   ├── keyword_service.py
│   │   │   ├── paa_service.py
│   │   │   ├── brand_service.py
│   │   │   ├── content_service.py
│   │   │   ├── nlp_service.py          # [NEW]
│   │   │   └── schedule_service.py
│   │   │
│   │   ├── repositories/               # Data access
│   │   │   ├── project_repository.py
│   │   │   ├── page_repository.py
│   │   │   ├── keyword_repository.py
│   │   │   ├── content_repository.py
│   │   │   └── base_repository.py
│   │   │
│   │   ├── models/                     # SQLAlchemy models
│   │   │   ├── project.py
│   │   │   ├── page.py
│   │   │   ├── keyword.py
│   │   │   ├── content.py
│   │   │   └── base.py
│   │   │
│   │   ├── schemas/                    # Pydantic schemas
│   │   │   ├── project.py
│   │   │   ├── page.py
│   │   │   ├── keyword.py
│   │   │   ├── content.py
│   │   │   └── nlp.py                  # [NEW]
│   │   │
│   │   ├── core/                       # Core utilities
│   │   │   ├── config.py               # Configuration
│   │   │   ├── database.py             # Database connection
│   │   │   ├── cache.py                # Redis caching
│   │   │   ├── security.py             # Auth (future)
│   │   │   └── logging.py              # Logging setup
│   │   │
│   │   ├── integrations/               # External API clients
│   │   │   ├── claude_client.py
│   │   │   ├── keywords_everywhere_client.py
│   │   │   ├── alsoasked_client.py
│   │   │   ├── serp_client.py          # [NEW]
│   │   │   ├── google_nlp_client.py    # [NEW]
│   │   │   ├── perplexity_client.py
│   │   │   └── gsc_client.py
│   │   │
│   │   ├── workers/                    # Background tasks
│   │   │   ├── crawl_worker.py
│   │   │   ├── keyword_worker.py
│   │   │   ├── content_worker.py
│   │   │   └── nlp_worker.py           # [NEW]
│   │   │
│   │   ├── utils/                      # Utility functions
│   │   │   ├── text_analysis.py        # [NEW] TF-IDF, readability
│   │   │   ├── html_parser.py          # [NEW] HTML parsing
│   │   │   ├── file_handler.py
│   │   │   ├── validators.py
│   │   │   └── helpers.py
│   │   │
│   │   ├── main.py                     # FastAPI app entry
│   │   └── __init__.py
│   │
│   ├── tests/                          # Test suite
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   │
│   ├── alembic/                        # Database migrations
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── pytest.ini
│
├── shared/                             # Shared types/schemas
│   └── types.ts
│
├── docs/                               # Documentation
│   ├── api/                            # API documentation
│   ├── architecture/                   # Architecture diagrams
│   └── guides/                         # User guides
│
├── scripts/                            # Utility scripts
│   ├── setup.sh
│   ├── migrate.sh
│   └── seed_db.py
│
├── .github/                            # GitHub Actions
│   └── workflows/
│       ├── test.yml
│       └── deploy.yml
│
├── docker-compose.yml                  # Local development
├── Dockerfile                          # Production build
├── .env.example
├── .gitignore
└── README.md
```

---

## Backend Architecture Details

### 1. API Layer (`app/api/`)

**Purpose**: Handle HTTP requests, validate input, return responses

**Structure**:
```python
# app/api/v1/projects.py
from fastapi import APIRouter, Depends, HTTPException
from app.services.project_service import ProjectService
from app.schemas.project import ProjectCreate, ProjectResponse
from app.api.deps import get_project_service

router = APIRouter(prefix="/projects", tags=["projects"])

@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    service: ProjectService = Depends(get_project_service)
):
    """Create a new project."""
    return await service.create_project(project)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service)
):
    """Get project by ID."""
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
```

**Key Features**:
- Dependency injection for services
- Pydantic validation
- Comprehensive error handling
- OpenAPI documentation (auto-generated)

---

### 2. Service Layer (`app/services/`)

**Purpose**: Business logic, orchestration, validation

**Example**: `NLPService` (NEW)

```python
# app/services/nlp_service.py
from typing import List, Dict
from app.integrations.serp_client import SerpClient
from app.integrations.google_nlp_client import GoogleNLPClient
from app.utils.text_analysis import calculate_tfidf, calculate_readability
from app.schemas.nlp import ContentAnalysisRequest, ContentAnalysisResponse

class NLPService:
    def __init__(
        self,
        serp_client: SerpClient,
        nlp_client: GoogleNLPClient
    ):
        self.serp_client = serp_client
        self.nlp_client = nlp_client
    
    async def analyze_content(
        self,
        request: ContentAnalysisRequest
    ) -> ContentAnalysisResponse:
        """
        Analyze draft content against competitors.
        
        Steps:
        1. Fetch SERP data for target keyword
        2. Scrape top 5 competitor pages
        3. Extract entities from competitors
        4. Calculate TF-IDF scores
        5. Calculate readability
        6. Generate optimization score
        7. Provide recommendations
        """
        # Fetch competitors
        serp_data = await self.serp_client.search(request.keyword)
        competitors = serp_data['organic_results'][:5]
        
        # Scrape competitor content
        competitor_texts = await self._scrape_competitors(competitors)
        
        # Extract entities
        competitor_entities = await self._extract_entities(competitor_texts)
        your_entities = await self.nlp_client.extract_entities(request.content)
        
        # Calculate TF-IDF
        tfidf_scores = calculate_tfidf(
            your_content=request.content,
            competitor_contents=competitor_texts
        )
        
        # Calculate readability
        readability = calculate_readability(request.content)
        
        # Generate score
        score = self._calculate_optimization_score(
            your_content=request.content,
            competitor_data={
                'texts': competitor_texts,
                'entities': competitor_entities,
                'avg_word_count': sum(len(t.split()) for t in competitor_texts) / len(competitor_texts)
            },
            tfidf_scores=tfidf_scores,
            readability=readability,
            your_entities=your_entities
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            score=score,
            tfidf_scores=tfidf_scores,
            competitor_entities=competitor_entities,
            your_entities=your_entities
        )
        
        return ContentAnalysisResponse(
            score=score,
            recommendations=recommendations,
            competitor_analysis={
                'avg_word_count': int(score['word_count_target']),
                'top_entities': competitor_entities[:10],
                'top_terms': tfidf_scores[:20]
            },
            readability=readability
        )
    
    def _calculate_optimization_score(
        self,
        your_content: str,
        competitor_data: Dict,
        tfidf_scores: List[Dict],
        readability: Dict,
        your_entities: List[Dict]
    ) -> Dict:
        """
        Calculate optimization score (0-100) based on:
        - Word count (20%)
        - Keyword usage (15%)
        - Semantic relevance (20%)
        - Readability (15%)
        - Content structure (15%)
        - Entity coverage (10%)
        - PAA coverage (5%)
        """
        score = 0
        breakdown = {}
        
        # Word count (20 points)
        your_word_count = len(your_content.split())
        target_word_count = competitor_data['avg_word_count']
        word_count_ratio = your_word_count / target_word_count
        
        if 0.8 <= word_count_ratio <= 1.2:
            word_count_score = 20
        else:
            word_count_score = max(0, 20 - abs(1 - word_count_ratio) * 40)
        
        score += word_count_score
        breakdown['word_count'] = {
            'score': word_count_score,
            'your_count': your_word_count,
            'target_count': int(target_word_count),
            'ratio': round(word_count_ratio, 2)
        }
        
        # Semantic relevance (20 points)
        # Based on TF-IDF coverage of top competitor terms
        top_competitor_terms = set(t['term'] for t in tfidf_scores[:30])
        your_terms = set(t['term'] for t in tfidf_scores if t['your_score'] > 0)
        coverage = len(your_terms & top_competitor_terms) / len(top_competitor_terms)
        semantic_score = coverage * 20
        
        score += semantic_score
        breakdown['semantic_relevance'] = {
            'score': semantic_score,
            'coverage': round(coverage, 2),
            'missing_terms': list(top_competitor_terms - your_terms)[:10]
        }
        
        # Readability (15 points)
        flesch_score = readability['flesch_reading_ease']
        if 60 <= flesch_score <= 70:
            readability_score = 15
        elif 50 <= flesch_score < 60 or 70 < flesch_score <= 80:
            readability_score = 12
        else:
            readability_score = max(0, 15 - abs(65 - flesch_score) / 2)
        
        score += readability_score
        breakdown['readability'] = {
            'score': readability_score,
            'flesch_score': flesch_score,
            'grade_level': readability['flesch_kincaid_grade']
        }
        
        # Entity coverage (10 points)
        competitor_entities = set(e['name'] for e in competitor_data['entities'][:20])
        your_entity_names = set(e['name'] for e in your_entities)
        entity_coverage = len(your_entity_names & competitor_entities) / len(competitor_entities)
        entity_score = entity_coverage * 10
        
        score += entity_score
        breakdown['entity_coverage'] = {
            'score': entity_score,
            'coverage': round(entity_coverage, 2),
            'missing_entities': list(competitor_entities - your_entity_names)[:5]
        }
        
        return {
            'total_score': round(score, 1),
            'grade': self._get_grade(score),
            'breakdown': breakdown,
            'word_count_target': target_word_count
        }
    
    def _get_grade(self, score: float) -> str:
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        else:
            return 'D'
    
    def _generate_recommendations(
        self,
        score: Dict,
        tfidf_scores: List[Dict],
        competitor_entities: List[Dict],
        your_entities: List[Dict]
    ) -> List[Dict]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Word count recommendation
        breakdown = score['breakdown']
        if breakdown['word_count']['ratio'] < 0.8:
            recommendations.append({
                'type': 'word_count',
                'priority': 'high',
                'message': f"Add {breakdown['word_count']['target_count'] - breakdown['word_count']['your_count']} words to match competitor average",
                'action': 'Expand content sections'
            })
        
        # Missing terms recommendation
        if breakdown['semantic_relevance']['missing_terms']:
            recommendations.append({
                'type': 'semantic',
                'priority': 'high',
                'message': f"Include these important terms: {', '.join(breakdown['semantic_relevance']['missing_terms'][:5])}",
                'action': 'Add semantically related terms'
            })
        
        # Readability recommendation
        if breakdown['readability']['flesch_score'] < 60:
            recommendations.append({
                'type': 'readability',
                'priority': 'medium',
                'message': "Content is too complex. Simplify sentences and use shorter words.",
                'action': 'Improve readability'
            })
        
        # Entity recommendation
        if breakdown['entity_coverage']['missing_entities']:
            recommendations.append({
                'type': 'entities',
                'priority': 'medium',
                'message': f"Mention these entities: {', '.join(breakdown['entity_coverage']['missing_entities'])}",
                'action': 'Add relevant entities'
            })
        
        return recommendations
```

---

### 3. Repository Layer (`app/repositories/`)

**Purpose**: Data access, database queries

**Example**: `ContentRepository`

```python
# app/repositories/content_repository.py
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.content import Content
from app.schemas.content import ContentCreate, ContentUpdate

class ContentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(self, content: ContentCreate) -> Content:
        """Create new content."""
        db_content = Content(**content.dict())
        self.session.add(db_content)
        await self.session.commit()
        await self.session.refresh(db_content)
        return db_content
    
    async def get_by_id(self, content_id: str) -> Optional[Content]:
        """Get content by ID."""
        result = await self.session.execute(
            select(Content).where(Content.id == content_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_project(self, project_id: str) -> List[Content]:
        """Get all content for a project."""
        result = await self.session.execute(
            select(Content).where(Content.project_id == project_id)
        )
        return result.scalars().all()
    
    async def update(self, content_id: str, updates: ContentUpdate) -> Optional[Content]:
        """Update content."""
        await self.session.execute(
            update(Content)
            .where(Content.id == content_id)
            .values(**updates.dict(exclude_unset=True))
        )
        await self.session.commit()
        return await self.get_by_id(content_id)
    
    async def delete(self, content_id: str) -> bool:
        """Delete content."""
        result = await self.session.execute(
            delete(Content).where(Content.id == content_id)
        )
        await self.session.commit()
        return result.rowcount > 0
```

---

### 4. Integration Layer (`app/integrations/`)

**Purpose**: External API clients

**Example**: `SerpClient` (NEW)

```python
# app/integrations/serp_client.py
import aiohttp
from typing import Dict, List
from app.core.config import settings
from app.core.cache import cache_result

class SerpClient:
    def __init__(self):
        self.api_key = settings.DATAFORSEO_API_KEY
        self.base_url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    
    @cache_result(ttl=86400)  # Cache for 24 hours
    async def search(
        self,
        keyword: str,
        location: str = "United States",
        language: str = "English",
        depth: int = 10
    ) -> Dict:
        """
        Fetch SERP data for a keyword.
        
        Returns:
            {
                'organic_results': [
                    {
                        'url': '...',
                        'title': '...',
                        'description': '...',
                        'position': 1
                    }
                ],
                'paa_questions': [...]
            }
        """
        payload = [{
            "keyword": keyword,
            "location_name": location,
            "language_name": language,
            "device": "desktop",
            "depth": depth
        }]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                json=payload,
                auth=aiohttp.BasicAuth(
                    settings.DATAFORSEO_USERNAME,
                    settings.DATAFORSEO_PASSWORD
                )
            ) as response:
                data = await response.json()
                
                if data['status_code'] != 20000:
                    raise Exception(f"DataForSEO API error: {data['status_message']}")
                
                result = data['tasks'][0]['result'][0]
                
                return {
                    'organic_results': [
                        {
                            'url': item['url'],
                            'title': item['title'],
                            'description': item['description'],
                            'position': item['rank_absolute']
                        }
                        for item in result['items']
                        if item['type'] == 'organic'
                    ],
                    'paa_questions': [
                        {
                            'question': item['title'],
                            'answer': item['snippet']
                        }
                        for item in result['items']
                        if item['type'] == 'people_also_ask'
                    ]
                }
```

---

## New NLP Features

### Feature 1: Content Optimization Score

**Endpoint**: `POST /api/nlp/analyze-content`

**Request**:
```json
{
    "keyword": "toronto blue jays flags",
    "content": "<h1>Toronto Blue Jays Flags</h1><p>...</p>",
    "format": "html"
}
```

**Response**:
```json
{
    "score": 87.5,
    "grade": "A",
    "breakdown": {
        "word_count": {
            "score": 18,
            "your_count": 425,
            "target_count": 450,
            "ratio": 0.94
        },
        "semantic_relevance": {
            "score": 17.5,
            "coverage": 0.88,
            "missing_terms": ["mlb", "baseball", "team colors"]
        },
        "readability": {
            "score": 15,
            "flesch_score": 65,
            "grade_level": 8.2
        },
        "entity_coverage": {
            "score": 8.5,
            "coverage": 0.85,
            "missing_entities": ["Rogers Centre", "American League"]
        }
    },
    "recommendations": [
        {
            "type": "semantic",
            "priority": "high",
            "message": "Include these important terms: mlb, baseball, team colors",
            "action": "Add semantically related terms"
        }
    ],
    "competitor_analysis": {
        "avg_word_count": 450,
        "top_entities": ["Toronto Blue Jays", "MLB", "Canada"],
        "top_terms": ["flags", "banners", "mlb", "baseball"]
    }
}
```

---

### Feature 2: Competitor Analysis

**Endpoint**: `POST /api/nlp/analyze-competitors`

**Request**:
```json
{
    "keyword": "toronto blue jays flags",
    "num_competitors": 5
}
```

**Response**:
```json
{
    "keyword": "toronto blue jays flags",
    "competitors": [
        {
            "url": "https://competitor1.com/...",
            "position": 1,
            "word_count": 520,
            "headers": {
                "h1": ["Toronto Blue Jays Flags"],
                "h2": ["Premium MLB Flags", "Official Team Merchandise"],
                "h3": ["Why Choose Our Flags", "Shipping & Returns"]
            },
            "top_entities": ["Toronto Blue Jays", "MLB", "Canada"],
            "readability_score": 68
        }
    ],
    "aggregate_analysis": {
        "avg_word_count": 450,
        "common_entities": ["Toronto Blue Jays", "MLB", "Baseball"],
        "common_terms": ["flags", "banners", "official", "team"],
        "avg_readability": 65,
        "header_patterns": {
            "h2_count": 3,
            "h3_count": 5
        }
    },
    "recommendations": {
        "target_word_count": 450,
        "suggested_headers": [
            "Premium Toronto Blue Jays Flags",
            "Official MLB Team Merchandise",
            "Why Choose Our Blue Jays Flags"
        ],
        "entities_to_include": ["Toronto Blue Jays", "MLB", "Canada", "Rogers Centre"],
        "terms_to_include": ["flags", "banners", "official", "team", "baseball"]
    }
}
```

---

### Feature 3: Term Recommendations

**Endpoint**: `POST /api/nlp/recommend-terms`

**Request**:
```json
{
    "keyword": "toronto blue jays flags",
    "current_content": "...",
    "num_terms": 20
}
```

**Response**:
```json
{
    "keyword": "toronto blue jays flags",
    "recommended_terms": [
        {
            "term": "mlb",
            "importance": 0.92,
            "frequency_in_competitors": 4.8,
            "frequency_in_your_content": 0,
            "priority": "high"
        },
        {
            "term": "baseball team",
            "importance": 0.85,
            "frequency_in_competitors": 3.6,
            "frequency_in_your_content": 1,
            "priority": "medium"
        }
    ],
    "entities_to_add": [
        {
            "entity": "Rogers Centre",
            "type": "LOCATION",
            "importance": 0.78,
            "context": "Home stadium of Toronto Blue Jays"
        }
    ]
}
```

---

## Frontend Architecture

### Technology Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: React Query + Context API
- **Routing**: React Router v6
- **Forms**: React Hook Form + Zod validation
- **HTTP Client**: Axios
- **Real-time**: WebSocket (for progress updates)

### Component Structure

```
src/
├── components/
│   ├── common/
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Modal.tsx
│   │   ├── Table.tsx
│   │   ├── Card.tsx
│   │   ├── Badge.tsx
│   │   ├── ProgressBar.tsx
│   │   └── LoadingSpinner.tsx
│   │
│   ├── layout/
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   ├── Footer.tsx
│   │   └── PageLayout.tsx
│   │
│   ├── dashboard/
│   │   ├── ProjectCard.tsx
│   │   ├── PhaseProgress.tsx
│   │   ├── StatsGrid.tsx
│   │   └── CreateProjectModal.tsx
│   │
│   ├── phases/
│   │   ├── Phase1/
│   │   │   ├── CrawlConfig.tsx
│   │   │   ├── CrawlProgress.tsx
│   │   │   └── CrawlResults.tsx
│   │   ├── Phase45/
│   │   │   ├── KeywordTable.tsx
│   │   │   ├── KeywordEditModal.tsx
│   │   │   └── PAAViewer.tsx
│   │   └── Phase5/
│   │       ├── ContentList.tsx
│   │       ├── ContentEditor.tsx
│   │       └── ContentPreview.tsx
│   │
│   └── nlp/                           # NEW
│       ├── ContentScoreCard.tsx
│       ├── CompetitorAnalysis.tsx
│       ├── TermRecommendations.tsx
│       └── OptimizationPanel.tsx
│
├── pages/
│   ├── Dashboard.tsx
│   ├── ProjectDetail.tsx
│   ├── Phase1.tsx
│   ├── Phase2.tsx
│   ├── Phase3.tsx
│   ├── Phase4.tsx
│   ├── Phase45.tsx
│   ├── Phase46.tsx
│   ├── Phase5.tsx
│   └── ContentOptimization.tsx        # NEW
│
├── hooks/
│   ├── useProjects.ts
│   ├── usePhases.ts
│   ├── useContent.ts
│   ├── useNLP.ts                      # NEW
│   └── useWebSocket.ts
│
├── services/
│   ├── api.ts                         # Axios instance
│   ├── projectService.ts
│   ├── phaseService.ts
│   ├── contentService.ts
│   └── nlpService.ts                  # NEW
│
├── types/
│   ├── project.ts
│   ├── phase.ts
│   ├── content.ts
│   └── nlp.ts                         # NEW
│
└── utils/
    ├── formatters.ts
    ├── validators.ts
    └── helpers.ts
```

---

## Database Schema (PostgreSQL)

### Tables

```sql
-- Projects
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    
    -- Statistics
    total_pages INTEGER DEFAULT 0,
    collection_pages INTEGER DEFAULT 0,
    keywords_approved INTEGER DEFAULT 0,
    
    -- Scheduling
    schedule_enabled BOOLEAN DEFAULT FALSE,
    schedule_day VARCHAR(3),
    schedule_hour INTEGER,
    schedule_minute INTEGER,
    
    -- Metadata
    brand_config JSONB,
    settings JSONB
);

-- Pages
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    category VARCHAR(50),
    title VARCHAR(500),
    meta_description TEXT,
    h1 VARCHAR(500),
    status_code INTEGER,
    crawled_at TIMESTAMP,
    
    -- Categorization
    labels JSONB,
    related_pages JSONB,
    
    UNIQUE(project_id, url)
);

-- Keywords
CREATE TABLE keywords (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    page_url VARCHAR(500) NOT NULL,
    
    -- Keywords
    primary_keyword VARCHAR(255),
    primary_keyword_volume INTEGER,
    secondary_keywords JSONB,
    
    -- PAA data
    paa_questions JSONB,
    
    -- Approval
    approval_status VARCHAR(20) DEFAULT 'pending',
    approved_at TIMESTAMP,
    
    UNIQUE(project_id, page_url)
);

-- Content
CREATE TABLE content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    page_id UUID REFERENCES pages(id) ON DELETE CASCADE,
    page_url VARCHAR(500) NOT NULL,
    
    -- Content pieces
    h1 VARCHAR(255),
    title_tag VARCHAR(255),
    meta_description VARCHAR(500),
    top_description TEXT,
    top_description_format VARCHAR(20),
    bottom_description TEXT,
    bottom_description_format VARCHAR(20),
    
    -- Metadata
    word_count INTEGER,
    tokens_used INTEGER,
    generated_at TIMESTAMP,
    
    -- QA
    qa_passed BOOLEAN,
    qa_issues JSONB,
    
    -- NLP Analysis (NEW)
    optimization_score DECIMAL(5,2),
    optimization_breakdown JSONB,
    
    UNIQUE(project_id, page_url)
);

-- NLP Cache (NEW)
CREATE TABLE nlp_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    keyword VARCHAR(255) NOT NULL,
    location VARCHAR(100) DEFAULT 'United States',
    
    -- SERP data
    serp_data JSONB,
    
    -- Competitor analysis
    competitor_analysis JSONB,
    
    -- Cache metadata
    cached_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    
    UNIQUE(keyword, location)
);

-- Indexes
CREATE INDEX idx_pages_project_id ON pages(project_id);
CREATE INDEX idx_pages_category ON pages(category);
CREATE INDEX idx_keywords_project_id ON keywords(project_id);
CREATE INDEX idx_keywords_approval ON keywords(approval_status);
CREATE INDEX idx_content_project_id ON content(project_id);
CREATE INDEX idx_nlp_cache_keyword ON nlp_cache(keyword);
CREATE INDEX idx_nlp_cache_expires ON nlp_cache(expires_at);
```

---

## Caching Strategy

### Redis Cache Structure

```
# SERP results (24 hour TTL)
serp:{keyword}:{location} → JSON

# Competitor analysis (7 day TTL)
competitor:{keyword} → JSON

# Keyword volume (30 day TTL)
keyword_volume:{keyword} → JSON

# Project status (5 minute TTL)
project_status:{project_id} → JSON

# Phase results (1 hour TTL)
phase_results:{project_id}:{phase} → JSON
```

---

## Testing Strategy

### Unit Tests
- Test all service methods
- Test all repository methods
- Test all utility functions
- Target: 80%+ code coverage

### Integration Tests
- Test API endpoints
- Test database operations
- Test external API integrations

### E2E Tests
- Test complete workflows
- Test UI interactions
- Use Playwright or Cypress

---

## Deployment Strategy

### Development
- Docker Compose for local development
- Hot reload for frontend and backend
- PostgreSQL + Redis in containers

### Staging
- Deploy to Railway staging environment
- Run integration tests
- Manual QA

### Production
- Deploy to Railway production
- Blue-green deployment
- Automated rollback on failure

---

## Migration Plan

### Phase 1: Setup New Project (Week 1)
1. Initialize new repository
2. Set up project structure
3. Configure development environment
4. Set up CI/CD pipelines

### Phase 2: Backend Core (Week 2-3)
1. Implement database models
2. Implement repositories
3. Implement core services (Project, Crawl, Keyword)
4. Implement API routers
5. Write unit tests

### Phase 3: NLP Integration (Week 4)
1. Implement SERP client
2. Implement Google NLP client
3. Implement NLP service
4. Implement text analysis utilities
5. Write integration tests

### Phase 4: Frontend Core (Week 5-6)
1. Set up React project
2. Implement common components
3. Implement dashboard
4. Implement phase pages
5. Implement NLP optimization UI

### Phase 5: Migration & Testing (Week 7)
1. Migrate existing data
2. Run comprehensive tests
3. Fix bugs
4. Performance optimization

### Phase 6: Deployment (Week 8)
1. Deploy to staging
2. User acceptance testing
3. Deploy to production
4. Monitor and fix issues

---

**Architecture Design Complete**  
**Next Step**: Create modern UI design using impeccable Claude skill
