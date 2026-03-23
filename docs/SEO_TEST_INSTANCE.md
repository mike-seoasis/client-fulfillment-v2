# Lorem Ipsum SEO Test Instance

A local-only instance of Grove that generates lorem ipsum body content with real keywords in SEO-critical positions. Used for Kyle Roof's lorem ipsum ranking experiment — testing whether pages can rank on Google with placeholder body text as long as keywords appear in title tags, H1s, H2s, meta descriptions, and schema markup.

## Quick Start

```bash
# 1. Start database + redis (isolated volumes, won't touch production)
docker-compose -f docker-compose.yml -f docker-compose.seo-test.yml up -d db redis

# 2. Run migrations on the fresh local database
cd backend
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/onboarding" .venv/bin/python3.12 -m alembic upgrade head

# 3. Start backend (port 8001)
DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/onboarding" \
  CONTENT_MODE=lorem AUTH_REQUIRED=false REDIS_URL="redis://localhost:6379/0" DEBUG=true \
  .venv/bin/python3.12 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 4. Start frontend (port 3001)
cd frontend
NEXT_PUBLIC_API_URL="http://localhost:8001/api/v1" npx next dev -p 3001
```

Then open http://localhost:3001.

## How It Works

### Same Codebase, Different Mode

The `CONTENT_MODE` environment variable (`real` or `lorem`) toggles content generation behavior. When set to `lorem`:

- **Headings (H2, H3)** — contain real target keywords and LSI terms from POP brief
- **Title tags & meta descriptions** — real, natural English with keywords
- **Lead paragraphs** — one keyword sentence + lorem ipsum
- **All other body text** — standard latin lorem ipsum

Everything else is identical to production: POP briefs, keyword clusters, blog campaigns, internal linking.

### Simplified UI in Lorem Mode

- **Project creation** — just name + domain (no brand config, no file uploads, no crawling)
- **Project detail** — shows only Clusters and Blogs sections (no onboarding, no Reddit, no brand config)
- **Header badge** — coral "SEO Test Mode" badge to distinguish from production
- **Export button** — "Export All Sites (XLSX)" on dashboard (only visible in lorem mode)

### XLSX Export

`GET /api/v1/export/sites-xlsx` generates a workbook matching the `sites-template.xlsx` format:

- **INSTRUCTIONS tab** — static documentation
- **One tab per project** — tab name = domain from site_url
- **Columns**: page_type, Title, title, meta_description, h1, Top description, Bottom Description, Blog Content
- **Collection rows** from cluster pages with complete content
- **Blog rows** from blog posts with generated content

The XLSX output feeds into the separate static site generator project that builds the actual deployable sites.

## Architecture

### Isolation

| Component | Production | SEO Test Instance |
|-----------|-----------|-------------------|
| Database | Neon PostgreSQL (cloud) | Local PostgreSQL (docker volume `seo_test_postgres_data`) |
| Backend port | 8000 (Railway) | 8001 (local) |
| Frontend port | 3000 (Railway) | 3001 (local) |
| Auth | Neon Auth (Better Auth SDK) | Disabled (`AUTH_REQUIRED=false`) |
| Content mode | `real` | `lorem` |

Zero risk of cross-contamination — completely separate database volumes and ports.

### API Keys

The SEO test instance uses the same API keys as production (POP, Claude, DataForSEO). This is safe because:
- Data goes to a separate database — no content mixing
- API billing is shared but that's intentional
- `.env.seo-test` has placeholder values — fill in your keys before running

### Key Files

| File | Purpose |
|------|---------|
| `docker-compose.seo-test.yml` | Docker override — separate DB volume, ports, env vars |
| `.env.seo-test` | Environment template for local instance |
| `backend/app/core/config.py` | `CONTENT_MODE` setting definition |
| `backend/app/services/content_writing.py` | Lorem ipsum prompt injection points |
| `backend/app/services/content_outline.py` | Lorem mode outline adjustments |
| `backend/app/services/export_xlsx.py` | Multi-site XLSX export service |
| `backend/app/api/v1/export.py` | Export endpoint |
| `frontend/src/hooks/use-app-config.ts` | Config hook for mode detection |

## Workflow

1. Create projects (one per exact-match domain)
2. Build keyword clusters for each project
3. Generate content (lorem ipsum mode — keywords in headings, lorem body)
4. Create blog campaigns with supporting posts
5. Export all sites as XLSX
6. Feed XLSX into the static site generator
7. Deploy generated sites to their domains

## Domains

| Domain | Niche |
|--------|-------|
| selfcleaninglitterbox.shop | Pet tech |
| crossbodywaterbottlebag.shop | Accessories |
| nadfacecream.shop | Skincare |
| arthritisjaropener.shop | Accessibility tools |
| diytinyarcarde.shop | Gaming/DIY |
| antistripclothing.shop | Fashion |
| 148scalemodels.shop | Hobby/Models |
| woodendollhousekits.shop | Toys/Hobby |
