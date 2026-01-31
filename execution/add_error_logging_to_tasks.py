#!/usr/bin/env python3
"""
Update all Beads tasks to include comprehensive error logging requirements.
"""

import subprocess
import json
import re

# Error logging requirements by task category
LOGGING_REQUIREMENTS = {
    # Backend infrastructure
    "setup": """
ERROR LOGGING REQUIREMENTS:
- Configure structured JSON logging with python-json-logger
- Set up log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include correlation IDs (request_id) in all log entries
- Configure log rotation and retention
- Add timing/performance logging for slow operations (>500ms)
- Ensure stack traces are captured for all exceptions
""",

    # Database/Models
    "database": """
ERROR LOGGING REQUIREMENTS:
- Log all database connection errors with connection string (masked)
- Log query execution time for slow queries (>100ms) at WARNING level
- Log transaction failures with rollback context
- Log migration start/end with version info
- Include table/model name in all database error logs
- Log connection pool exhaustion at CRITICAL level
""",

    # Services (business logic)
    "service": """
ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
""",

    # API endpoints
    "api": """
ERROR LOGGING REQUIREMENTS:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
""",

    # External API integrations
    "integration": """
ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes
""",

    # Background workers
    "worker": """
ERROR LOGGING REQUIREMENTS:
- Log job start with job_id, type, parameters
- Log progress at regular intervals (every 10% or N items)
- Log job completion with duration and result summary
- Log failures with full context for retry/debugging
- Include job_id in all related log entries
- Log queue depth and processing rate
- Log dead letter queue additions at ERROR level
""",

    # WebSocket
    "websocket": """
ERROR LOGGING REQUIREMENTS:
- Log connection open/close with client info
- Log message send/receive at DEBUG level
- Log connection errors and reconnection attempts
- Include connection_id in all WebSocket logs
- Log broadcast failures per-client
- Log heartbeat timeouts at WARNING level
""",

    # Frontend components
    "frontend": """
ERROR LOGGING REQUIREMENTS:
- Implement React Error Boundaries for all route components
- Log caught errors to console with component stack
- Set up global window.onerror and unhandledrejection handlers
- Log API errors with endpoint, status, response body
- Include user action context in error logs
- Set up error reporting service integration point (e.g., Sentry stub)
""",

    # Frontend API/data fetching
    "frontend_api": """
ERROR LOGGING REQUIREMENTS:
- Log all API requests with method, endpoint, timing
- Log API errors with status code and response body
- Implement retry logic with attempt logging
- Log network failures distinctly from API errors
- Include request_id from response headers in logs
- Log cache hits/misses at DEBUG level
""",

    # Testing
    "testing": """
ERROR LOGGING REQUIREMENTS:
- Ensure test failures include full assertion context
- Log test setup/teardown at DEBUG level
- Capture and display logs from failed tests
- Include timing information in test reports
- Log mock/stub invocations for debugging
""",

    # Deployment/Migration
    "deployment": """
ERROR LOGGING REQUIREMENTS:
- Log deployment start/end with version info
- Log each migration step with success/failure status
- Log rollback triggers and execution
- Log environment variable validation (mask values)
- Log health check results during deployment
- Log database connection verification
""",
}

def get_logging_category(title: str) -> str:
    """Determine the logging category based on task title."""
    title_lower = title.lower()

    # Check for specific patterns
    if any(x in title_lower for x in ['model', 'migration', 'alembic', 'database', 'sqlalchemy']):
        return "database"
    if any(x in title_lower for x in ['api', 'endpoint', '/api/']):
        return "api"
    if any(x in title_lower for x in ['integration', 'client', 'perplexity', 'keywords everywhere', 'dataforseo', 'serp', 'google cloud', 'anthropic']):
        return "integration"
    if any(x in title_lower for x in ['websocket', 'real-time', 'broadcast']):
        return "websocket"
    if any(x in title_lower for x in ['scheduler', 'apscheduler', 'worker', 'background', 'scheduled']):
        return "worker"
    if any(x in title_lower for x in ['service', 'implement', 'repository']):
        return "service"
    if any(x in title_lower for x in ['react', 'component', 'panel', 'page', 'modal', 'build ', 'create app', 'create project', 'create phase', 'create content', 'create data', 'create form', 'create loading', 'create toast']):
        return "frontend"
    if any(x in title_lower for x in ['axios', 'react query', 'fetch', 'websocket client']):
        return "frontend_api"
    if any(x in title_lower for x in ['test', 'coverage', 'pytest', 'e2e']):
        return "testing"
    if any(x in title_lower for x in ['deploy', 'railway', 'migration script', 'cutover', 'dns']):
        return "deployment"
    if any(x in title_lower for x in ['initialize', 'set up', 'configure', 'fastapi', 'redis', 'github actions']):
        return "setup"

    # Default to service for backend tasks
    return "service"

def update_task_with_logging(task_id: str, title: str):
    """Update a task to include error logging requirements."""
    category = get_logging_category(title)
    logging_req = LOGGING_REQUIREMENTS.get(category, LOGGING_REQUIREMENTS["service"])

    # Get current task details
    result = subprocess.run(
        ['bd', 'show', task_id, '--json'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"  Warning: Could not get task {task_id}")
        return False

    try:
        task_list = json.loads(result.stdout)
        task_data = task_list[0] if isinstance(task_list, list) else task_list
        current_desc = task_data.get('description', '') or ''

        # Check if logging requirements already added
        if 'ERROR LOGGING REQUIREMENTS' in current_desc:
            return False  # Already has logging requirements

        # Append logging requirements
        new_desc = current_desc + "\n\n" + logging_req.strip() if current_desc else logging_req.strip()

        # Update the task
        update_result = subprocess.run(
            ['bd', 'update', task_id, '--description', new_desc],
            capture_output=True, text=True
        )

        return update_result.returncode == 0

    except json.JSONDecodeError:
        print(f"  Warning: Could not parse task {task_id}")
        return False

def main():
    print("Adding comprehensive error logging requirements to all tasks...\n")

    # Get all tasks
    result = subprocess.run(
        ['bd', 'list', '--json', '--type', 'task', '--limit', '200'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print("Error: Could not list tasks")
        return

    tasks = json.loads(result.stdout)
    print(f"Found {len(tasks)} tasks to update\n")

    # Track categories for summary
    category_counts = {}
    updated_count = 0
    skipped_count = 0

    for i, task in enumerate(tasks, 1):
        task_id = task['id']
        title = task['title']
        category = get_logging_category(title)

        category_counts[category] = category_counts.get(category, 0) + 1

        print(f"[{i}/{len(tasks)}] [{category}] {task_id}: {title[:50]}...")

        if update_task_with_logging(task_id, title):
            updated_count += 1
        else:
            skipped_count += 1

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Total tasks: {len(tasks)}")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped (already had logging): {skipped_count}")
    print(f"\nCategory breakdown:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} tasks")

    # Re-export to JSONL for BV
    print("\nRe-exporting to JSONL...")
    subprocess.run(['bd', 'export', '-o', '.beads/beads.jsonl'], capture_output=True)
    print("Done! Tasks now include comprehensive error logging requirements.")

if __name__ == '__main__':
    main()
