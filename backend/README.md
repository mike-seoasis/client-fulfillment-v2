# Client Onboarding Backend

FastAPI backend for the client onboarding system.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

## Documentation

- [POP Integration](docs/POP_INTEGRATION.md) - PageOptimizer Pro API integration for content scoring
- [Logging Reference](docs/LOGGING.md) - Log fields and levels for ops/monitoring

## External Integrations

### PageOptimizer Pro (POP)

SERP-based content optimization scoring. Provides:
- **Content Brief**: Fetch word count targets, LSI terms, heading structure before content generation
- **Content Scoring**: Score generated content against SERP competitors

**Configuration:**
```bash
POP_API_KEY=your_api_key
USE_POP_CONTENT_BRIEF=false  # Enable POP for content briefs
USE_POP_SCORING=false        # Enable POP for content scoring
POP_SHADOW_MODE=false        # Run both POP and legacy for comparison
```

**Endpoints:**
- `POST /api/v1/projects/{project_id}/phases/content_brief/fetch`
- `GET /api/v1/projects/{project_id}/phases/content_brief/pages/{page_id}/brief`
- `POST /api/v1/projects/{project_id}/phases/content_score/score`
- `POST /api/v1/projects/{project_id}/phases/content_score/batch`

**Fallback:** When POP is unavailable (circuit open, timeout, API error), scoring automatically falls back to the legacy `ContentScoreService`.

See [POP Integration docs](docs/POP_INTEGRATION.md) for full details.

### DataForSEO

SERP and keyword data. Used for:
- Keyword research
- Competitor analysis
- SERP feature tracking

### Anthropic (Claude)

LLM for content generation and categorization.

### Other Integrations

- Perplexity - Website analysis
- Keywords Everywhere - Keyword data
- Google Cloud NLP - Entity extraction
- Crawl4AI - Web crawling

## Project Structure

```
backend/
├── alembic/              # Database migrations
├── app/
│   ├── api/v1/          # API endpoints
│   ├── core/            # Config, logging, database
│   ├── integrations/    # External API clients
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   └── services/        # Business logic
├── docs/                # Documentation
└── tests/               # Test suite
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/services/test_pop_content_score.py
```

## API Documentation

When running locally, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
