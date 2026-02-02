# Directive: Database Rollback Procedure

## Goal

Safely rollback database migrations when deployment issues occur, with comprehensive logging and data integrity validation.

## When to Use

Trigger a rollback when:
- Migration fails during deployment
- Data integrity validation fails post-migration
- Application health checks fail after migration
- Critical bugs discovered after deployment

## Prerequisites

- Access to Railway dashboard or CLI
- Alembic installed and configured
- Database credentials with migration permissions
- Knowledge of target revision to rollback to

## Steps

### 1. Assess the Situation

Before rolling back, gather information:

```bash
# Check current database revision
alembic current

# Check migration history
alembic history --verbose

# Review deployment logs for errors
# In Railway: View deployment logs for the failed deployment
```

Log this assessment step:
```python
db_logger.rollback_triggered(
    reason="migration_failure",  # or "integrity_check_failure", "health_check_failure"
    from_version="current_revision",
    to_version="target_revision"
)
```

### 2. Determine Target Revision

Identify the safe revision to rollback to:

```bash
# List all revisions
alembic history

# Check what each revision does
alembic show <revision_id>
```

Common targets:
- Previous revision: `alembic downgrade -1`
- Specific revision: `alembic downgrade <revision_id>`
- Base (no migrations): `alembic downgrade base`

### 3. Execute Rollback

**Option A: Single Step Rollback**
```bash
alembic downgrade -1
```

**Option B: Rollback to Specific Revision**
```bash
alembic downgrade <revision_id>
```

**Option C: Full Rollback (Emergency)**
```bash
alembic downgrade base
```

Monitor the rollback execution with logging:
```python
try:
    # Rollback commands execute here
    db_logger.rollback_executed(
        from_version="failed_revision",
        to_version="target_revision",
        success=True
    )
except Exception as e:
    db_logger.rollback_executed(
        from_version="failed_revision",
        to_version="target_revision",
        success=False
    )
    logger.error(
        "Rollback failed",
        extra={
            "error_type": type(e).__name__,
            "error_message": str(e),
        },
        exc_info=True
    )
```

### 4. Validate Rollback Success

After rollback, verify:

```bash
# Confirm current revision
alembic current

# Test database connection
python -c "from app.core.database import db_manager; import asyncio; asyncio.run(db_manager.check_connection())"
```

Run data integrity validation:
```python
from app.core.data_integrity import validate_data_integrity
from app.core.database import db_manager

async with db_manager.session_factory() as session:
    report = await validate_data_integrity(session)
    if report.success:
        logger.info("Rollback validation passed")
    else:
        logger.error("Rollback validation failed", extra={"issues": report.total_issues})
```

### 5. Redeploy Previous Version

On Railway:
1. Go to Deployments tab
2. Find the last working deployment
3. Click "Redeploy" on that deployment

Or via CLI:
```bash
railway up --detach
```

## Inputs

- `current_revision`: Current database migration version
- `target_revision`: Revision to rollback to
- `failure_reason`: Why the rollback is needed
- `deployment_id`: Railway deployment ID (for logging)

## Outputs

- Database rolled back to target revision
- Application redeployed on previous working version
- Rollback logged with full context:
  - `db_logger.rollback_triggered()` - Reason and versions
  - `db_logger.rollback_executed()` - Success/failure status
  - Data integrity validation report

## Error Logging Requirements

All rollback operations must follow these logging standards:

### Method Entry/Exit (DEBUG level)
```python
logger.debug(
    "Starting rollback operation",
    extra={
        "from_revision": from_revision,
        "to_revision": to_revision,
    }
)
```

### Exception Logging (ERROR level with stack trace)
```python
logger.error(
    "Rollback failed",
    extra={
        "error_type": type(e).__name__,
        "error_message": str(e),
        "from_revision": from_revision,
        "to_revision": to_revision,
    },
    exc_info=True  # Includes full stack trace
)
```

### State Transitions (INFO level)
```python
logger.info(
    "Rollback state transition",
    extra={
        "from_revision": from_revision,
        "to_revision": to_revision,
        "status": "completed",
    }
)
```

### Slow Operations (WARNING level for >1 second)
```python
if duration_ms > 1000:
    logger.warning(
        "Slow rollback operation",
        extra={
            "duration_ms": round(duration_ms, 2),
            "operation": "downgrade",
        }
    )
```

## Edge Cases

| Scenario | Resolution |
|----------|------------|
| Rollback fails mid-execution | Database may be in inconsistent state. Check `alembic current` and manually resolve. Contact DBA if needed. |
| Target revision doesn't exist | Verify revision ID with `alembic history`. Use full revision hash. |
| Foreign key constraints block rollback | May need to delete dependent data first. Review migration's downgrade() method. |
| Connection timeout during rollback | Retry with `--sql` flag to generate SQL, then execute directly on database. |
| Railway cold-start delays | Increase connection timeout. Default is 60s for cold-start scenarios. |

## Automated Rollback (via deploy.py)

The deployment script (`app/deploy.py`) handles rollback triggers automatically:

```python
# Migration failure triggers rollback warning
if not run_migrations():
    logger.warning(
        "Migration failure may trigger rollback",
        extra={
            "rollback_trigger": "migration_failure",
            "failed_revision": target_rev,
            "current_revision": current_rev,
        }
    )
```

Data integrity failures also block deployment:
```python
if not await run_data_integrity_validation():
    logger.error(
        "Data integrity validation failed - deployment blocked",
        extra={"action": "deployment_blocked"}
    )
```

## Related Scripts

- `backend/app/deploy.py` - Deployment with migration and validation
- `backend/app/core/data_integrity.py` - Post-migration validation
- `backend/app/core/logging.py` - `DatabaseLogger` with rollback methods
- `backend/app/services/crawl_recovery.py` - Interrupted crawl recovery

## Learnings

<!-- Update this section as you discover constraints, gotchas, or better approaches -->

- Railway deployments may cold-start, requiring extended connection timeouts (60s default)
- Always run data integrity validation after rollback to ensure consistency
- Keep migration downgrade() methods simple and reversible
- Use `--sql` flag to preview migration SQL before executing on production
