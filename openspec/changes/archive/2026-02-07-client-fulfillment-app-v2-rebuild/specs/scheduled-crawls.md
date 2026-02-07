# Spec: scheduled-crawls

## Overview

Automatic re-crawling of project websites on a configurable schedule using APScheduler. Detects new pages, updates changed content, and notifies users of significant changes.

## Behaviors

### WHEN configuring a scheduled crawl
- THEN accept schedule configuration (frequency, time, timezone)
- AND validate schedule parameters
- AND create/update APScheduler job
- AND store schedule in database

### WHEN a scheduled crawl triggers
- THEN check if project is active
- AND run crawl with same settings as initial crawl
- AND compare results to previous crawl
- AND identify: new pages, removed pages, changed pages
- AND update database with new crawl results
- AND notify user if significant changes detected

### WHEN comparing crawl results
- THEN match pages by normalized URL
- AND new pages: URLs in new crawl not in previous
- AND removed pages: URLs in previous not in new crawl
- AND changed pages: Same URL but different content hash
- AND generate change summary

### WHEN significant changes detected
- THEN "significant" = 5+ new pages OR 10%+ content changes
- AND send notification (email/webhook based on project settings)
- AND flag project for user review

### WHEN schedule is disabled
- THEN remove APScheduler job
- AND mark schedule as inactive in database
- AND preserve schedule configuration for re-enabling

## Schedule Configuration

```
ScheduleConfig:
  enabled: boolean
  frequency: "daily" | "weekly" | "monthly"
  day_of_week: integer (0-6, for weekly)
  day_of_month: integer (1-28, for monthly)
  time: string (HH:MM in 24h format)
  timezone: string (e.g., "America/New_York")
  notify_on_changes: boolean
  notification_email: string | null
  notification_webhook: string | null
```

## APScheduler Integration

### Job Creation
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

def schedule_crawl(project_id: str, config: ScheduleConfig):
    trigger = CronTrigger(
        day_of_week=config.day_of_week if config.frequency == 'weekly' else '*',
        day=config.day_of_month if config.frequency == 'monthly' else '*',
        hour=int(config.time.split(':')[0]),
        minute=int(config.time.split(':')[1]),
        timezone=config.timezone
    )

    scheduler.add_job(
        run_scheduled_crawl,
        trigger=trigger,
        id=f"crawl_{project_id}",
        args=[project_id],
        replace_existing=True
    )
```

### Job Persistence
- Use APScheduler's SQLAlchemy job store
- Jobs survive application restarts
- Jobs are scoped to project_id

## Change Detection

### Content Hash
```python
import hashlib

def content_hash(page: CrawledPage) -> str:
    content = f"{page.title}|{page.h1}|{page.meta_description}|{page.content_text[:1000]}"
    return hashlib.md5(content.encode()).hexdigest()
```

### Change Summary
```json
{
  "crawl_id": "uuid",
  "compared_to": "previous_crawl_uuid",
  "summary": {
    "new_pages": 3,
    "removed_pages": 1,
    "changed_pages": 5,
    "unchanged_pages": 42
  },
  "new_page_urls": ["url1", "url2", "url3"],
  "removed_page_urls": ["url4"],
  "changed_page_urls": ["url5", "url6", "url7", "url8", "url9"],
  "is_significant": true
}
```

## API Endpoints

```
GET  /api/v1/projects/{id}/schedule          - Get schedule config
PUT  /api/v1/projects/{id}/schedule          - Update schedule
POST /api/v1/projects/{id}/schedule/run-now  - Trigger immediate crawl
GET  /api/v1/projects/{id}/crawl-history     - List previous crawls
GET  /api/v1/projects/{id}/crawl-history/{crawlId}/changes - Get change summary
```

## Notification Templates

### Email Notification
```
Subject: [Client Fulfillment] Significant changes detected for {project_name}

The scheduled crawl for {project_name} ({website_url}) completed and detected significant changes:

- New pages: {new_pages_count}
- Changed pages: {changed_pages_count}
- Removed pages: {removed_pages_count}

New pages:
{new_page_urls_list}

Please review these changes and determine if content regeneration is needed.

View details: {dashboard_url}
```

### Webhook Payload
```json
{
  "event": "crawl_completed",
  "project_id": "uuid",
  "project_name": "Acme Coffee",
  "website_url": "https://acme.coffee",
  "crawl_id": "uuid",
  "changes": {
    "new_pages": 3,
    "changed_pages": 5,
    "removed_pages": 1,
    "is_significant": true
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Error Handling

- Crawl fails: Retry up to 2 times, then mark as failed
- Notification fails: Log error, don't retry (user can check dashboard)
- Schedule job missing: Auto-recreate from database on app startup

## Database Schema

```sql
CREATE TABLE crawl_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) UNIQUE,
  enabled BOOLEAN DEFAULT FALSE,
  frequency VARCHAR(20) NOT NULL,
  day_of_week INTEGER,
  day_of_month INTEGER,
  time_of_day TIME NOT NULL,
  timezone VARCHAR(50) DEFAULT 'UTC',
  notify_on_changes BOOLEAN DEFAULT TRUE,
  notification_email VARCHAR(255),
  notification_webhook VARCHAR(500),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE crawl_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  crawl_type VARCHAR(20) NOT NULL, -- 'initial', 'scheduled', 'manual'
  started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  completed_at TIMESTAMP WITH TIME ZONE,
  status VARCHAR(20) DEFAULT 'in_progress',
  pages_crawled INTEGER,
  change_summary JSONB,
  error_message TEXT
);

CREATE INDEX idx_crawl_schedules_project ON crawl_schedules(project_id);
CREATE INDEX idx_crawl_history_project ON crawl_history(project_id);
CREATE INDEX idx_crawl_history_started ON crawl_history(project_id, started_at DESC);
```

## Startup Recovery

On application startup:
1. Load all enabled schedules from database
2. Recreate APScheduler jobs for each
3. Check for any "in_progress" crawls that were interrupted
4. Mark interrupted crawls as "failed"

```python
async def recover_schedules():
    schedules = await db.fetch_enabled_schedules()
    for schedule in schedules:
        schedule_crawl(schedule.project_id, schedule)

    # Mark interrupted crawls as failed
    await db.execute("""
        UPDATE crawl_history
        SET status = 'failed', error_message = 'Interrupted by server restart'
        WHERE status = 'in_progress'
    """)
```
