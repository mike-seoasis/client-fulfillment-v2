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

## Setting Up Railway

1. Create a new Railway project
2. Add PostgreSQL addon (sets `DATABASE_URL` automatically)
3. Add Redis addon if needed (sets `REDIS_URL` automatically)
4. Set environment variables in Railway dashboard:
   - `ENVIRONMENT=staging`
   - `LOG_LEVEL=INFO`
5. Deploy from GitHub repository
