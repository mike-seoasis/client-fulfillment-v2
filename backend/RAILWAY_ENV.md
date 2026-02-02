# Railway Environment Variables

This document lists all environment variables for Railway deployment.

## Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `PORT` | Port to bind (set by Railway) | `8000` |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment name (staging, production) |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `json` | Log format (json, text) |
| `REDIS_URL` | - | Redis connection string for caching |

## Database Pool Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow connections |
| `DB_POOL_TIMEOUT` | `30` | Pool timeout in seconds |
| `DB_CONNECT_TIMEOUT` | `60` | Connection timeout (Railway cold-start) |
| `DB_COMMAND_TIMEOUT` | `60` | Command timeout in seconds |

## Redis Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_POOL_SIZE` | `10` | Redis connection pool size |
| `REDIS_CONNECT_TIMEOUT` | `10.0` | Connection timeout in seconds |
| `REDIS_SOCKET_TIMEOUT` | `5.0` | Socket timeout in seconds |

## Railway-Provided Variables

These are automatically set by Railway:

| Variable | Description |
|----------|-------------|
| `RAILWAY_DEPLOYMENT_ID` | Unique deployment identifier |
| `RAILWAY_SERVICE_NAME` | Service name in Railway |
| `RAILWAY_ENVIRONMENT_NAME` | Environment name (staging, production) |
| `RAILWAY_GIT_COMMIT_SHA` | Git commit SHA being deployed |

## Setting Up Railway Production Environment

### Step 1: Create Railway Project

1. Go to [Railway](https://railway.app) and create a new project
2. Connect your GitHub repository

### Step 2: Add Database Addons

1. **PostgreSQL**: Click "New" > "Database" > "PostgreSQL"
   - Railway automatically sets `DATABASE_URL`
   - Use the "Variables" tab to verify connection string

2. **Redis** (optional): Click "New" > "Database" > "Redis"
   - Railway automatically sets `REDIS_URL`
   - Used for caching and session management

### Step 3: Configure Environment Variables

In the Railway dashboard, go to your service's "Variables" tab and set:

**Staging Environment:**
```
ENVIRONMENT=staging
LOG_LEVEL=DEBUG
DEBUG=true
```

**Production Environment:**
```
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
```

### Step 4: Deploy Configuration

The `railway.toml` file handles:
- **Health checks**: Configured at `/health` with 120s timeout
- **Deploy hooks**: Migrations run automatically via `python -m app.deploy`
- **Restart policy**: Auto-restart on failure (max 3 retries)

### Step 5: Health Check Endpoints

The app provides multiple health endpoints:

| Endpoint | Description |
|----------|-------------|
| `/health` | Basic health (Railway uses this) |
| `/health/db` | Database connectivity |
| `/health/redis` | Redis connectivity and circuit breaker state |
| `/health/scheduler` | APScheduler status |

## Deployment Error Logging

The deploy script (`app/deploy.py`) logs:

| Event | Log Level | Details |
|-------|-----------|---------|
| Deployment start | INFO | App version, environment, commit SHA |
| Environment validation | INFO/ERROR | Variable presence (values masked) |
| Database connection | INFO/ERROR | Connection verification |
| Migration start | INFO | From/to revision |
| Migration step | INFO | Individual migration progress |
| Migration failure | ERROR | Error details, triggers rollback logging |
| Rollback trigger | WARNING | Reason, affected versions |
| Data integrity check | INFO/ERROR | Validation results |
| Deployment end | INFO | Success status, duration |

## Rollback Procedure

If a deployment fails:

1. **Automatic**: Railway reverts to previous deployment
2. **Manual database rollback**:
   ```bash
   # SSH into Railway or run locally with DATABASE_URL
   alembic downgrade -1  # Rollback one migration
   alembic downgrade <revision>  # Rollback to specific revision
   ```

3. **Check rollback logs**: Look for `"rollback_trigger"` in deployment logs

## Monitoring

After deployment, verify:

1. **Health endpoint**: `curl https://your-app.railway.app/health`
2. **Database health**: `curl https://your-app.railway.app/health/db`
3. **Railway logs**: Check for any ERROR or WARNING messages
4. **Deployment logs**: Verify migration steps completed successfully
