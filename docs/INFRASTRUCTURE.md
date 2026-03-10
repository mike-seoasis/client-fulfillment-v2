# Infrastructure Overview

> Where everything lives and how it connects.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     RAILWAY                              │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐ │
│  │ Backend  │  │ Frontend │  │  Redis  │  │ Crawl4AI │ │
│  │ (FastAPI)│  │ (Next.js)│  │ (cache) │  │ (scraper)│ │
│  └────┬─────┘  └──────────┘  └─────────┘  └──────────┘ │
│       │                                                  │
└───────┼──────────────────────────────────────────────────┘
        │
        │ DATABASE_URL (SSL)
        ▼
┌──────────────────┐          ┌──────────────────────────┐
│   NEON            │          │   RAILWAY (separate proj) │
│   PostgreSQL      │◄─────────│   postgres-s3-backups     │
│   (free tier)     │  pg_dump │   (every 6 hours)         │
└──────────────────┘          └───────────┬──────────────┘
                                          │
                                          │ upload
                                          ▼
                              ┌──────────────────────────┐
                              │   CLOUDFLARE R2           │
                              │   client-fullfilment-     │
                              │   backups                 │
                              │   (30-day retention)      │
                              └──────────────────────────┘
```

---

## Services

### Railway (App Hosting)

| Service | What It Does | Branch |
|---------|-------------|--------|
| **Backend** | FastAPI API server | `staging` / `main` |
| **Frontend** | Next.js web app | `staging` / `main` |
| **Redis** | Caching, circuit breaker state | Railway addon |
| **Crawl4AI** | Web scraping service | Docker image |

- **Staging URL:** `fe-client-fulfillment-v2-staging.up.railway.app`
- **Dashboard:** https://railway.app

### Neon (Database)

| Field | Value |
|-------|-------|
| **Project** | `spring-fog-49733273` |
| **Organization** | `org-cold-waterfall-84590723` |
| **Region** | `aws-us-east-1` |
| **Plan** | Free (0.5 GB storage, 100 compute hours/mo) |
| **PostgreSQL Version** | 17 |
| **Scale-to-zero** | 5 minutes (free tier, can't disable) |
| **PITR Window** | 6 hours (free tier) |
| **Tables** | 24 |

- **Dashboard:** https://console.neon.tech
- **Connection:** Via `DATABASE_URL` env var in Railway (no `?sslmode=require` in URL — SSL handled in app code)

### Cloudflare R2 (Backups)

| Field | Value |
|-------|-------|
| **Bucket** | `client-fullfilment-backups` |
| **Account ID** | `fa80d2f9a9e3a5f7971ca70c11cd0458` |
| **Region** | Auto |
| **Retention** | 30-day lifecycle rule |
| **Backup Frequency** | Every 6 hours |
| **Backup Method** | `pg_dump` via Railway `postgres-s3-backups` template |

- **Dashboard:** https://dash.cloudflare.com → R2 Object Storage
- **Restore procedure:** See `BACKUP_RESTORE_RUNBOOK.md`

---

## Environment Variables (Railway Backend)

| Variable | Description | Notes |
|----------|-------------|-------|
| `DATABASE_URL` | Neon connection string | No `?sslmode=require` — SSL via code |
| `ENVIRONMENT` | `staging` or `production` | Must NOT be `development` (enables SSL) |
| `REDIS_URL` | Railway Redis connection | Set automatically by Railway |
| `PORT` | App port | Set automatically by Railway |

Full list: See `backend/RAILWAY_ENV.md`

---

## SSL Configuration

Neon requires SSL on all connections. The app handles this in code, NOT in the URL:

- **Where:** `backend/app/core/database.py` line 85 and `backend/alembic/env.py` line 109
- **Logic:** `{"ssl": "require"} if settings.environment != "development" else {}`
- **Important:** asyncpg does NOT support `?sslmode=require` in the URL — it must be set via `connect_args`
- **If you see SSL errors:** Check that `ENVIRONMENT` is set to `staging` or `production` (not `development`)

---

## Data Protection

| Layer | What | RPO | How |
|-------|------|-----|-----|
| **1. Neon PITR** | Point-in-time recovery | 6 hours | Built into Neon free tier, branch from any point |
| **2. R2 Backups** | Full database dumps | 6 hours | `pg_dump` every 6 hours, 30-day retention |

**RPO (Recovery Point Objective):** Maximum 6 hours of data loss in worst case.

---

## Costs

| Service | Monthly Cost |
|---------|-------------|
| Railway (Hobby plan) | ~$5/mo + usage |
| Neon (Free tier) | $0 |
| Cloudflare R2 | ~$0.01/mo (tiny database, minimal storage) |
| **Total backup cost** | **~$0/mo** |
