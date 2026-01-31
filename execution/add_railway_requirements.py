#!/usr/bin/env python3
"""
Update tasks to include Railway deployment requirements from the start.
"""

import subprocess
import json

# Railway-specific requirements by task category
RAILWAY_REQUIREMENTS = {
    # Backend setup - CRITICAL
    "setup_backend": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Bind to PORT from environment variable (Railway sets this dynamically)
- All config via environment variables (DATABASE_URL, REDIS_URL, API keys)
- NO hardcoded URLs, ports, or credentials
- Add /health endpoint returning {"status": "ok"} for Railway health checks
- Log to stdout/stderr only (Railway captures these)
- Use Procfile or railway.toml for start command
- Support graceful shutdown (SIGTERM handling)
""",

    # Database - CRITICAL
    "database": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via DATABASE_URL environment variable (Railway provides this)
- Use connection pooling (SQLAlchemy pool_size=5, max_overflow=10)
- Handle connection timeouts gracefully (Railway can cold-start)
- Migrations must run via `alembic upgrade head` in deploy command
- NO sqlite - PostgreSQL only
- Use SSL mode for database connections (sslmode=require)
""",

    # Redis - CRITICAL
    "redis": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Connect via REDIS_URL environment variable (Railway provides this)
- Handle Redis connection failures gracefully (cache is optional)
- Use SSL/TLS for Redis connections in production
- Implement connection retry logic for cold starts
""",

    # API endpoints
    "api": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- CORS must allow frontend domain (configure via FRONTEND_URL env var)
- Return proper error responses (Railway shows these in logs)
- Include request_id in all responses for debugging
- Health check endpoint at /health or /api/v1/health
""",

    # External integrations
    "integration": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- All API keys via environment variables (ANTHROPIC_API_KEY, etc.)
- Never log or expose API keys
- Handle cold-start latency (first request may be slow)
- Implement request timeouts (Railway has 5min request limit)
""",

    # Background workers/schedulers
    "worker": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Can run as separate Railway service OR in-process
- Handle SIGTERM for graceful shutdown (Railway sends this on deploy)
- Persist job state to database (not memory) for restart survival
- Use DATABASE_URL for job store, not local files
- APScheduler jobs must survive service restarts
""",

    # WebSocket
    "websocket": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Railway supports WebSocket connections
- Implement heartbeat/ping to keep connections alive
- Handle reconnection gracefully (deploys will disconnect clients)
- Consider fallback to polling for reliability
""",

    # Frontend
    "frontend": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Build as static assets (npm run build)
- API URL via VITE_API_URL environment variable
- Configure for production build (NODE_ENV=production)
- Can deploy to Railway static hosting or separate service
- Use relative paths or env-configured absolute URLs
""",

    # Frontend API layer
    "frontend_api": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- API base URL from environment variable (VITE_API_URL)
- Handle API errors gracefully (show user-friendly messages)
- Implement retry logic for transient failures
- Support both HTTP and HTTPS (Railway provides SSL)
""",

    # Testing (less critical but still relevant)
    "testing": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Tests must work with DATABASE_URL env var
- Use test database, not production
- CI should mirror Railway environment where possible
""",

    # Deployment tasks - already Railway-focused
    "deployment": """
RAILWAY DEPLOYMENT REQUIREMENTS:
- Use railway.toml or Procfile for configuration
- Set up Railway project with PostgreSQL and Redis addons
- Configure environment variables in Railway dashboard
- Set up deploy hooks for migrations
- Configure health check path in Railway settings
""",
}

def get_railway_category(title: str) -> str:
    """Determine the Railway requirement category based on task title."""
    title_lower = title.lower()

    # Specific patterns first
    if any(x in title_lower for x in ['redis', 'cache', 'caching']):
        return "redis"
    if any(x in title_lower for x in ['initialize backend', 'fastapi', 'set up fastapi']):
        return "setup_backend"
    if any(x in title_lower for x in ['model', 'migration', 'alembic', 'sqlalchemy', 'database', 'postgresql']):
        return "database"
    if any(x in title_lower for x in ['websocket', 'real-time', 'broadcast']):
        return "websocket"
    if any(x in title_lower for x in ['scheduler', 'apscheduler', 'worker', 'background', 'scheduled']):
        return "worker"
    if any(x in title_lower for x in ['api', 'endpoint', '/api/']):
        return "api"
    if any(x in title_lower for x in ['integration', 'client', 'perplexity', 'keywords everywhere',
                                        'dataforseo', 'serp', 'google cloud', 'anthropic', 'crawl4ai']):
        return "integration"
    if any(x in title_lower for x in ['react', 'component', 'panel', 'page', 'modal', 'vite', 'tailwind']):
        return "frontend"
    if any(x in title_lower for x in ['axios', 'react query', 'fetch']):
        return "frontend_api"
    if any(x in title_lower for x in ['test', 'coverage', 'pytest', 'e2e']):
        return "testing"
    if any(x in title_lower for x in ['deploy', 'railway', 'production', 'staging']):
        return "deployment"

    return None  # No Railway-specific requirements needed

def update_task_with_railway(task_id: str, title: str):
    """Update a task to include Railway requirements."""
    category = get_railway_category(title)

    if category is None:
        return False, "no_category"

    railway_req = RAILWAY_REQUIREMENTS.get(category)
    if not railway_req:
        return False, "no_requirements"

    # Get current task details
    result = subprocess.run(
        ['bd', 'show', task_id, '--json'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        return False, "fetch_failed"

    try:
        task_list = json.loads(result.stdout)
        task_data = task_list[0] if isinstance(task_list, list) else task_list
        current_desc = task_data.get('description', '') or ''

        # Check if Railway requirements already added
        if 'RAILWAY DEPLOYMENT REQUIREMENTS' in current_desc:
            return False, "already_has"

        # Append Railway requirements
        new_desc = current_desc + "\n\n" + railway_req.strip()

        # Update the task
        update_result = subprocess.run(
            ['bd', 'update', task_id, '--description', new_desc],
            capture_output=True, text=True
        )

        return update_result.returncode == 0, category

    except json.JSONDecodeError:
        return False, "parse_failed"

def main():
    print("Adding Railway deployment requirements to relevant tasks...\n")

    # Get all tasks
    result = subprocess.run(
        ['bd', 'list', '--json', '--type', 'task', '--limit', '200'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("Error: Could not list tasks")
        return

    tasks = json.loads(result.stdout)
    print(f"Found {len(tasks)} tasks to check\n")

    # Track results
    category_counts = {}
    updated_count = 0
    skipped_count = 0
    no_category_count = 0

    for i, task in enumerate(tasks, 1):
        task_id = task['id']
        title = task['title']

        success, result_info = update_task_with_railway(task_id, title)

        if success:
            updated_count += 1
            category_counts[result_info] = category_counts.get(result_info, 0) + 1
            print(f"[{i}/{len(tasks)}] [{result_info}] ✓ {task_id}: {title[:50]}...")
        elif result_info == "no_category":
            no_category_count += 1
            print(f"[{i}/{len(tasks)}] [skip] {task_id}: {title[:50]}...")
        elif result_info == "already_has":
            skipped_count += 1
            print(f"[{i}/{len(tasks)}] [exists] {task_id}: {title[:50]}...")
        else:
            print(f"[{i}/{len(tasks)}] [error:{result_info}] {task_id}")

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Total tasks: {len(tasks)}")
    print(f"  Updated with Railway requirements: {updated_count}")
    print(f"  Already had Railway requirements: {skipped_count}")
    print(f"  No Railway requirements needed: {no_category_count}")
    print(f"\nCategory breakdown (updated):")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} tasks")

    # Re-export to JSONL for BV
    print("\nRe-exporting to JSONL...")
    subprocess.run(['bd', 'export', '-o', '.beads/beads.jsonl'], capture_output=True)
    print("Done! Tasks now include Railway deployment requirements.")

if __name__ == '__main__':
    main()
