## ADDED Requirements

### Requirement: docker-compose for local development
The system SHALL provide a `docker-compose.yml` at the project root that runs all services needed for local development.

#### Scenario: All services defined
- **WHEN** examining `docker-compose.yml`
- **THEN** it defines services for: PostgreSQL, Redis, backend, and frontend

#### Scenario: Services start successfully
- **WHEN** running `docker-compose up -d`
- **THEN** all services start without errors

### Requirement: PostgreSQL service
The docker-compose SHALL include a PostgreSQL 15 service with health checks.

#### Scenario: PostgreSQL configuration
- **WHEN** examining the `db` service in docker-compose.yml
- **THEN** it uses `postgres:15-alpine` image with POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB environment variables

#### Scenario: PostgreSQL health check
- **WHEN** the db service is running
- **THEN** health check uses `pg_isready` command

#### Scenario: PostgreSQL data persistence
- **WHEN** docker-compose is restarted
- **THEN** PostgreSQL data persists via named volume

### Requirement: Redis service
The docker-compose SHALL include a Redis 7 service with health checks.

#### Scenario: Redis configuration
- **WHEN** examining the `redis` service in docker-compose.yml
- **THEN** it uses `redis:7-alpine` image

#### Scenario: Redis health check
- **WHEN** the redis service is running
- **THEN** health check uses `redis-cli ping` command

### Requirement: Backend service
The docker-compose SHALL include a backend service that builds from `backend/Dockerfile`.

#### Scenario: Backend build context
- **WHEN** examining the `backend` service in docker-compose.yml
- **THEN** build context is `./backend` with Dockerfile specified

#### Scenario: Backend environment variables
- **WHEN** the backend service starts
- **THEN** DATABASE_URL and REDIS_URL are configured to connect to the db and redis services

#### Scenario: Backend depends on databases
- **WHEN** docker-compose starts
- **THEN** backend waits for db and redis health checks before starting

#### Scenario: Backend hot reload in development
- **WHEN** backend service is running
- **THEN** app code is mounted as volume for hot reload with uvicorn --reload

### Requirement: Backend Dockerfile
The system SHALL provide a `backend/Dockerfile` for containerizing the FastAPI application.

#### Scenario: Multi-stage build
- **WHEN** examining `backend/Dockerfile`
- **THEN** it uses multi-stage build with separate build and production stages

#### Scenario: Python 3.11 slim base
- **WHEN** examining `backend/Dockerfile`
- **THEN** it uses `python:3.11-slim` as base image

#### Scenario: uv for dependency installation
- **WHEN** the Dockerfile installs dependencies
- **THEN** it uses uv instead of pip

#### Scenario: Non-root user
- **WHEN** the container runs
- **THEN** it runs as a non-root user for security

#### Scenario: Railway PORT compatibility
- **WHEN** deployed to Railway
- **THEN** the container respects the PORT environment variable

#### Scenario: Health check endpoint
- **WHEN** the container is running
- **THEN** `/health` endpoint responds with 200 OK

### Requirement: Frontend service (optional)
The docker-compose MAY include a frontend service for Next.js development.

#### Scenario: Frontend defined
- **WHEN** examining `docker-compose.yml`
- **THEN** frontend service is defined (can be commented out for backend-only dev)

#### Scenario: Frontend connects to backend
- **WHEN** frontend service runs
- **THEN** BACKEND_URL environment variable points to backend service
