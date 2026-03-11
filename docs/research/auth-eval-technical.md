# Technical Architecture Evaluation: Open-Source Auth Solutions

**Prepared by:** Solution Architect Agent
**Date:** 2026-02-08
**Purpose:** Deep technical evaluation of 5 open-source authentication solutions as alternatives to WorkOS AuthKit

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Solution Overviews](#solution-overviews)
3. [Architecture Comparison](#architecture-comparison)
4. [Protocol Support Matrix](#protocol-support-matrix)
5. [Scalability Analysis](#scalability-analysis)
6. [Self-Hosting Complexity](#self-hosting-complexity)
7. [Extensibility Comparison](#extensibility-comparison)
8. [Individual Deep Dives](#individual-deep-dives)
9. [Key Findings and Architectural Recommendations](#key-findings)

---

## Executive Summary

This evaluation examines five open-source identity and access management (IAM) solutions: **Keycloak**, **SuperTokens**, **Ory (Kratos/Hydra)**, **Authentik**, and **BoxyHQ (SAML Jackson / Ory Polis)**. Each occupies a different niche in the auth landscape, ranging from full-featured enterprise IAM (Keycloak) to focused SSO bridging (BoxyHQ/Polis).

**Key finding:** BoxyHQ has been acquired by Ory and rebranded as **Ory Polis**, merging it into the Ory ecosystem. This effectively reduces the field to four distinct solution families, with Ory now offering the broadest composable stack.

**Top-line comparison:**

| Dimension | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|-----------|----------|-------------|---------------------|-----------|------------------|
| **Maturity** | Very High | Medium | High | Medium-High | Medium (now part of Ory) |
| **Enterprise readiness** | Excellent | Good | Excellent | Good | Focused (SSO/SCIM only) |
| **Self-host complexity** | High | Low-Medium | Medium | Low-Medium | Low |
| **Scalability ceiling** | Very High | High | Very High | Medium-High | N/A (SSO bridge) |
| **Protocol breadth** | Broadest | Moderate | Broad (w/ Polis) | Broad | SAML/OIDC/SCIM only |

---

## Solution Overviews

### 1. Keycloak
- **Origin:** Red Hat / JBoss, now a CNCF incubation project
- **License:** Apache 2.0
- **GitHub:** 41,000+ stars, 1,350+ contributors
- **Current version:** 26.x (as of late 2025)
- **Summary:** The most mature and feature-complete open-source IAM solution. Built on Java/Quarkus, it provides a full-featured admin console, user federation, identity brokering, and comprehensive protocol support. It is the default choice for organizations that need enterprise-grade IAM and can manage the operational overhead.

### 2. SuperTokens
- **Origin:** SuperTokens Inc. (venture-backed startup)
- **License:** Apache 2.0 (core), some enterprise features paid
- **GitHub:** 14,700+ stars
- **Current version:** 11.x+
- **Summary:** A modern, developer-first authentication platform designed to sit between your frontend and backend. The core service runs as a lightweight Java HTTP microservice. Strongest for B2C authentication flows (email/password, social login, passwordless). Enterprise SSO (SAML) and multi-tenancy require paid plans or integration with external tools.

### 3. Ory (Kratos / Hydra / Keto / Oathkeeper / Polis)
- **Origin:** Ory Corp (venture-backed, Berlin-based)
- **License:** Apache 2.0 (open-source components)
- **GitHub:** Kratos ~11k stars, Hydra ~16k stars, 50,000+ community members
- **Current version:** Kratos 1.x, Hydra 2.x
- **Summary:** A composable, API-first identity infrastructure built in Go. Each component handles one concern: Kratos (identity/auth), Hydra (OAuth2/OIDC), Keto (permissions), Oathkeeper (proxy), Polis (SAML/SCIM). Proven at massive scale -- OpenAI uses Ory Hydra for 800M+ weekly active users. The most cloud-native architecture of the group.

### 4. Authentik
- **Origin:** Authentik Security Inc. (community-driven, VC-backed as of 2024)
- **License:** Open-source (custom license with source-available enterprise features)
- **GitHub:** ~15,000+ stars
- **Current version:** 2025.12 (year-month versioning)
- **Summary:** A Python/Django-based identity provider with an excellent admin UI and powerful flow-based authentication engine. Popular in the homelab/SMB community for its approachability. Supports SAML, OIDC, LDAP, RADIUS, and SCIM. As of 2025.10, Redis is no longer required (all state moved to PostgreSQL).

### 5. BoxyHQ / Ory Polis (formerly SAML Jackson)
- **Origin:** BoxyHQ (acquired by Ory in 2025)
- **License:** Apache 2.0
- **GitHub:** ~6,000+ stars (as SAML Jackson)
- **Summary:** A focused SSO bridge that converts SAML/OIDC enterprise login flows into standard OAuth2.0/OIDC, abstracting SAML complexity. Now part of the Ory ecosystem as "Ory Polis." Also supports SCIM 2.0 for directory sync. Built in Node.js/TypeScript. Best used as a complement to another auth system rather than a standalone IAM solution.

---

## Architecture Comparison

| Aspect | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|--------|----------|-------------|---------------------|-----------|------------------|
| **Language** | Java (Quarkus) | Java (Core) | Go | Python (Django) | Node.js/TypeScript |
| **Architecture** | Monolith | Microservice (core + SDKs) | Composable microservices | Monolith (server + worker) | Focused microservice |
| **Database** | PostgreSQL, MySQL, MariaDB, Oracle, MSSQL | PostgreSQL only (as of v11) | PostgreSQL, MySQL, CockroachDB, SQLite* | PostgreSQL only | PostgreSQL, MySQL, MariaDB, MongoDB, Redis, PlanetScale |
| **Caching** | Infinispan (embedded) | None (stateless core) | None required | PostgreSQL (Redis removed in 2025.10) | In-memory or Redis |
| **Message queue** | None required | None required | None required | None required | None required |
| **UI** | Full admin console + login themes | Pre-built login UI components | Headless (BYO UI) | Full admin console + flow editor | Headless (BYO UI) |
| **Multi-tenancy** | Realms (logical, single DB) | Tenant-based (paid feature) | Multi-project via config | Brands/tenants | Per-tenant SSO connections |

*SQLite for development only, not production.

### Architecture Patterns

**Keycloak (Monolith):**
The entire IAM stack runs as a single Java application on Quarkus. Internal subsystems handle user management, authentication, authorization, identity brokering, and admin. Clustering uses embedded Infinispan for cache replication. This makes deployment simpler but means you scale the entire application as a unit.

**SuperTokens (Layered Microservice):**
Unique three-layer architecture: Frontend SDK -> Backend SDK -> SuperTokens Core. The backend SDK sits in YOUR application server, meaning auth logic runs in your process alongside your business logic. The Core is a separate stateless Java service that handles database operations and core auth algorithms. This design allows deep customization at the backend SDK layer without modifying core auth logic.

**Ory (Composable Microservices):**
Each concern is a separate Go binary that communicates via HTTP APIs. You pick and choose which components you need. Kratos handles identity, Hydra handles OAuth2/OIDC, Keto handles authorization, Oathkeeper handles API gateway auth, and Polis handles SAML/SCIM bridging. Components are stateless (all state in the database), making horizontal scaling trivial.

**Authentik (Monolith with Workers):**
A Django-based server handles HTTP requests and authentication flows, while background workers handle async tasks (LDAP outpost, SCIM sync, etc.). The flow-based engine is a distinguishing feature: admins build authentication journeys by composing stages (password check, MFA, consent, etc.) and policies (conditional logic) in a visual editor.

**BoxyHQ/Ory Polis (Focused Service):**
A single-purpose Node.js service that acts as a SAML-to-OAuth2 bridge. Can be embedded as an NPM library directly into your Node.js application or deployed as a standalone Docker service. The narrowest scope of all solutions evaluated.

---

## Protocol Support Matrix

| Protocol | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|----------|----------|-------------|---------------------|-----------|------------------|
| **OAuth 2.0** | Full | Via integration | Full (Hydra, certified) | Full | Converts to OAuth2 |
| **OIDC** | Full (certified) | Via integration | Full (Hydra, certified) | Full | Converts to OIDC |
| **SAML 2.0 (IdP)** | Full | No native support | Via Polis (enterprise) | Full | Full (bridge) |
| **SAML 2.0 (SP)** | Full | Via BoxyHQ/Polis | Via Polis | Full | Full |
| **SCIM 2.0** | Via extension | Via integration | Via Polis | Native | Native |
| **LDAP** | Full (federation) | No | No | Full (outpost) | No |
| **RADIUS** | Via extension | No | No | Native | No |
| **Passkeys/WebAuthn** | Yes | Yes | Yes (Kratos) | Yes | No |
| **MFA/TOTP** | Yes | Yes | Yes (Kratos) | Yes | No |
| **Magic Links** | Via extension | Yes | Yes (Kratos) | Yes | No |
| **Social Login** | Extensive (20+ providers) | Yes (multiple) | Yes (Kratos, via OIDC) | Yes | No |

### Protocol Support Notes

- **Keycloak** has the broadest native protocol support. SCIM is the main gap, addressed via a community extension (Phase Two).
- **SuperTokens** focuses on modern B2C auth patterns. SAML/SCIM require integration with BoxyHQ/Polis or similar. Not ideal if you need to act as a SAML IdP.
- **Ory** is strongest for OAuth2/OIDC (Hydra is OpenID Certified and used at massive scale). SAML/SCIM were historically missing but now addressed via Polis (enterprise/paid feature on Ory Network, open-source self-host).
- **Authentik** provides comprehensive protocol coverage including LDAP and RADIUS outposts, making it suitable for environments with legacy applications.
- **BoxyHQ/Ory Polis** is purpose-built for SAML/OIDC bridging and SCIM directory sync. It does not provide user management, session management, or MFA -- it must be paired with another auth system.

---

## Scalability Analysis

### Performance Benchmarks

| Metric | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|--------|----------|-------------|---------------------|-----------|------------------|
| **Max tested throughput** | ~12,000 req/s (official benchmark) | 10s of millions MAU | 800M WAU (OpenAI, Hydra) | Not published | Not published |
| **Scaling model** | Horizontal (StatefulSet) | Horizontal (stateless) | Horizontal (stateless) | Horizontal (Deployment) | Horizontal (stateless) |
| **Scaling linearity** | Near-linear to 12k req/s | Linear (stateless core) | Near-linear | Limited data | N/A |
| **Key constraint** | Database IOPS, Infinispan cache | Database (PostgreSQL) | Database | PostgreSQL | Database |
| **Tested scale** | 300 logins/s, 2000 client cred/s | 10s of millions MAU | Billions of API requests/day | SMB to mid-enterprise | Unknown |

### Detailed Scalability Notes

**Keycloak:**
- Official benchmarks (v26.4): ~15 password logins/s per vCPU, ~120 client credential grants/s per vCPU
- Scales near-linearly to 12,000 req/s with proper database and Infinispan tuning
- Database sizing: ~1400 write IOPS per 100 login/logout/refresh req/s
- Pod resource baseline: ~1250 MB RAM (including 10,000 cached sessions), recommend 150% CPU headroom
- Multi-site active-active supported since v26
- Key limitation: High realm/client counts can blow Infinispan caches (default 10,000 entries each), requiring cache size tuning

**SuperTokens:**
- Stateless core enables trivial horizontal scaling behind a load balancer
- One PostgreSQL instance sufficient for tens of millions of MAUs
- Database partitioned by tenant and user for consistent per-tenant performance as scale grows
- Dropped MySQL/MongoDB support in v11 to focus on PostgreSQL optimization
- Lower operational overhead for scaling vs. Keycloak

**Ory (Kratos/Hydra):**
- The most proven at internet-scale: OpenAI migrated to self-hosted Ory Hydra backed by CockroachDB, handling 400M+ WAU by early 2025, growing to ~800M WAU by mid-2025
- Stateless Go services scale by simply adding pods -- no cache coordination needed
- No message queues or key-value stores required for high-traffic environments
- CockroachDB support enables globally distributed database layer
- 7+ billion API requests protected daily across the ecosystem

**Authentik:**
- Horizontal scaling supported by running multiple server/worker replicas behind a load balancer
- Redis removed in 2025.10 (all state in PostgreSQL) -- simplifies architecture but means PostgreSQL is the sole scaling bottleneck
- Limited published performance data; positioned for SMB to mid-enterprise rather than internet-scale
- For large deployments: increase PostgreSQL connection limits, use Prometheus monitoring

**BoxyHQ/Ory Polis:**
- As a focused bridge service, scaling is straightforward -- stateless Node.js instances behind a load balancer
- Scaling characteristics largely determined by the backing database
- Not a scaling concern in most deployments (SSO login events are relatively infrequent)

---

## Self-Hosting Complexity

### Infrastructure Requirements

| Requirement | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|-------------|----------|-------------|---------------------|-----------|------------------|
| **Min RAM (production)** | ~1.5 GB per pod | ~512 MB - 1 GB | ~512 MB per service | ~1-2 GB (server + worker) | ~256-512 MB |
| **Database** | PostgreSQL/MySQL/etc. | PostgreSQL 13+ | PostgreSQL (recommended) | PostgreSQL | PostgreSQL/MySQL/MongoDB |
| **Redis/Cache** | No (embedded Infinispan) | No | No | No (removed 2025.10) | Optional |
| **Docker images** | Official | Official | Official (multi-arch) | Official | Official |
| **Helm chart** | Community + Bitnami | Community | Official | Official (goauthentik/helm) | Community |
| **Min services to run** | 1 (Keycloak + DB) | 2 (Core + your app + DB) | 2+ (Kratos + DB, optionally Hydra) | 2 (server + worker + DB) | 1 (service + DB) |

### Deployment Complexity Rating (1-5, 5 = most complex)

| Aspect | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|--------|----------|-------------|---------------------|-----------|------------------|
| **Initial setup** | 3 | 2 | 3 | 2 | 1 |
| **Configuration** | 4 (XML/JSON/Admin UI) | 2 (config file + SDK) | 3 (YAML per component) | 2 (admin UI) | 2 (env vars) |
| **HA setup** | 4 (Infinispan tuning) | 2 (add pods) | 2 (add pods) | 3 (PostgreSQL tuning) | 1 (add pods) |
| **Upgrade path** | 3 (DB migrations) | 2 (auto-migrations) | 3 (CLI migrations, no skip) | 2 (auto-migrations) | 2 (standard) |
| **Backup/DR** | 3 (DB + realm export) | 2 (DB backup only) | 2 (DB backup only) | 2 (DB backup only) | 2 (DB backup only) |
| **Overall** | **3.4** | **2.0** | **2.6** | **2.2** | **1.6** |

### Deployment Notes

**Keycloak:**
- Highest operational complexity due to Java memory management, Infinispan cache tuning, and the breadth of configuration options
- Realm export/import for configuration management, but large realms can be unwieldy
- On Kubernetes: must use StatefulSet with sequential pod handling (no Deployment)
- Extensive documentation and large community mean most issues are well-documented
- Red Hat offers commercial support (Red Hat build of Keycloak)

**SuperTokens:**
- Simplest architecture for developers already running a Node.js/Python/Go backend
- Core runs as a single Docker container alongside your database
- Auto-migrations on startup simplify upgrades
- Managed cloud option available as a fallback if self-hosting becomes burdensome
- No UI admin console for self-hosted (management via API or dashboard with paid plan)

**Ory (Kratos/Hydra):**
- Multiple components mean multiple configs, but each is simple YAML
- Built-in CLI migration tool (`kratos migrate sql`); migrations run automatically on `serve`
- Zero-downtime upgrades require sequential version upgrades (no skipping versions)
- Headless architecture means you must build or provide your own login/registration UI
- Official Docker images support multi-architecture (amd64, arm64, arm/v7, arm/v6)

**Authentik:**
- Docker Compose is the recommended path for small/medium deployments
- Server runs as user 1000:1000; persistent volumes must be writable by this UID
- Removal of Redis dependency (2025.10) significantly simplified the stack
- Excellent admin UI reduces configuration complexity
- Helm chart available for Kubernetes with PostgreSQL subchart option

**BoxyHQ/Ory Polis:**
- Simplest deployment of all: one Docker container + database
- Can also be embedded as an NPM library (no separate service needed)
- BYOD (Bring Your Own Database) model with wide database support
- Minimal configuration via environment variables
- Being absorbed into the Ory ecosystem may affect long-term independent deployment

---

## Extensibility Comparison

| Capability | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|------------|----------|-------------|---------------------|-----------|------------------|
| **Extension system** | SPI (Java JAR plugins) | Backend SDK overrides | Webhooks (Ory Actions) | Flows + Policies (Python) | NPM library API |
| **Custom auth flows** | Yes (Authentication SPI) | Yes (override functions) | Yes (webhook hooks) | Yes (flow editor) | No (SSO bridge only) |
| **Webhooks** | Via community plugin | No native webhooks | Native (configurable) | Native (notification transport) | Limited |
| **Custom identity schemas** | Limited (user attributes) | Custom claims | Full (JSON Schema) | Custom via property mappings | N/A |
| **Admin API** | Comprehensive REST API | Comprehensive REST API | Comprehensive REST API | Comprehensive REST API | REST API |
| **Theme/UI customization** | FreeMarker templates | React component overrides | BYO UI (headless) | Flow-based + CSS | BYO UI (headless) |
| **Plugin marketplace** | Yes (extensions.keycloak.org) | No | No | No | No |

### Extensibility Deep Dive

**Keycloak -- SPI (Service Provider Interface):**
- Most extensible through a formal Java plugin system
- SPIs available for: authenticators, user storage, event listeners, token mappers, themes, REST endpoints, and more
- Plugins deployed as JAR files, auto-discovered at startup
- Extensions marketplace (extensions.keycloak.org) with community contributions
- Webhook support via community plugins (e.g., vymalo/keycloak-webhook) with HTTP, AMQP, and Syslog delivery
- Downside: requires Java development skills and understanding of Keycloak internals

**SuperTokens -- Backend SDK Override Pattern:**
- Override any API endpoint or core function from your backend SDK (Node.js, Python, Go)
- No special plugin system -- you write overrides in your own backend code
- Can modify any part of the auth flow: pre-sign-up, post-sign-up, custom password hashing, etc.
- Downside: no webhook system (you implement side effects in overrides); tightly coupled to your application code

**Ory -- Webhooks (Ory Actions):**
- Four action types for extending self-service flows
- `web_hook` action triggers external HTTP calls at any point in auth flows
- Hooks available before and after: login, registration, recovery, settings, verification
- Jsonnet templates for webhook payload customization
- Supports both blocking (synchronous) and non-blocking (async) webhooks
- Known issue: generic hook configuration can conflict with method-specific hooks silently

**Authentik -- Flow + Policy Engine:**
- Visual flow editor for composing authentication journeys from stages and policies
- Policies written in Python with access to request context
- Property mappings use Python code for SAML/OIDC claim transformation
- Webhook notifications via configurable notification transports with Python payload templates
- Downside: Python-based policies require Python knowledge; no formal plugin marketplace

**BoxyHQ/Ory Polis -- NPM Library:**
- Can be imported as a library (`@boxyhq/saml-jackson`) for deepest integration
- Hooks into your application's auth flow to handle SAML negotiation
- Limited extensibility beyond SSO/SCIM use cases (by design)
- Integration examples for Next.js, Express, and other frameworks

---

## Individual Deep Dives

### Keycloak

**Architecture:** Java monolith on Quarkus (migrated from WildFly). Uses Hibernate for ORM, JAX-RS for REST APIs, Infinispan for distributed caching. The admin console is a React SPA, and login pages use FreeMarker templates.

**Deployment model:** Docker container or bare JAR. On Kubernetes, official guidance uses StatefulSet with sequential pod handling. Supports multi-site active-active deployments since v26. Docker images: `quay.io/keycloak/keycloak`.

**Multi-tenancy:** Realm-based. Each realm is a fully isolated namespace with its own users, clients, roles, and authentication flows. All realms share a single database instance (per-realm databases are not officially supported). For true data isolation, deploy separate Keycloak instances.

**Strengths:** Broadest protocol support. Largest community and ecosystem. CNCF incubation project. Red Hat commercial backing. Extensive documentation. Proven in large enterprise deployments.

**Weaknesses:** Highest operational complexity. Java/Quarkus runtime requires careful memory tuning. Extension development requires Java expertise. Admin UI can be overwhelming. Configuration sprawl in large deployments.

---

### SuperTokens

**Architecture:** Three-tier: Frontend SDK (React/Angular/Vue) -> Backend SDK (Node.js/Python/Go) -> SuperTokens Core (Java HTTP service). The Backend SDK is the key differentiator -- it runs inside your application server, enabling deep customization without modifying core auth logic.

**Deployment model:** Core runs as a Docker container (`supertokens/supertokens-postgresql`). Backend SDK is a library dependency in your application. PostgreSQL 13+ only (MySQL/MongoDB dropped in v11).

**Multi-tenancy:** Supported via tenant-based isolation. Each tenant can have different login methods and configurations. Database queries are partitioned by tenant for consistent performance at scale. Multi-tenancy is a paid feature.

**Strengths:** Best developer experience for B2C apps. Lightweight core with minimal infrastructure. Pre-built UI components. Deep customization via SDK overrides. Active development and responsive team.

**Weaknesses:** No native SAML IdP capability. SCIM requires external integration. Multi-tenancy is paid. No admin console in self-hosted OSS version. Smaller community than Keycloak/Ory. Limited protocol breadth for enterprise scenarios.

---

### Ory (Kratos / Hydra)

**Architecture:** Composable Go microservices. Each component is a single statically-compiled binary with no external dependencies beyond a database. Kratos handles identity management (registration, login, account recovery, MFA). Hydra handles OAuth2/OIDC (OpenID Certified). Keto handles permissions. Oathkeeper handles API gateway auth. Polis handles SAML/SCIM.

**Deployment model:** Docker containers or bare binaries. Each component has its own Docker image (`oryd/kratos`, `oryd/hydra`, etc.). Multi-architecture support (amd64, arm64, armv7, armv6). Kubernetes, Docker Compose, ECS, bare metal all supported. Each component needs its own database.

**Multi-tenancy:** Via configuration and project separation. No built-in realm concept like Keycloak. Multi-tenancy is typically implemented at the application layer or via Ory Network (managed service).

**Strengths:** Proven at internet-scale (OpenAI, 800M+ WAU). Stateless architecture enables trivial horizontal scaling. CockroachDB support for global distribution. Most modern, cloud-native design. API-first / headless enables complete UI flexibility. Go binaries are lightweight and fast-starting.

**Weaknesses:** Headless = no admin UI (must build or use community UIs). Multiple components increase configuration surface area. SAML/SCIM only via Polis (enterprise-licensed on Ory Network). Zero-downtime upgrades require sequential versions. Smaller protocol breadth in OSS vs. Keycloak.

---

### Authentik

**Architecture:** Python/Django backend with a Go-based LDAP/RADIUS outpost system. Server process handles HTTP requests and authentication flows. Worker process handles background tasks (SCIM sync, LDAP federation, etc.). As of 2025.10, all state (caching, sessions, WebSockets) moved to PostgreSQL, eliminating the Redis dependency.

**Deployment model:** Docker Compose (small/medium) or Kubernetes via Helm chart. Docker images: `authentik/server`. Server runs as UID 1000:1000. Worker and server are the same image with different entrypoints.

**Multi-tenancy:** Brand-based tenant separation. Each brand can have its own domain, theme, and default flows. Less granular than Keycloak's realm model.

**Strengths:** Best admin UI of the group. Flow-based authentication engine is powerful and visual. Broad protocol support including LDAP and RADIUS. Simplified stack since Redis removal. Device management capabilities (2025.12). Strong and growing community. Lower learning curve than Keycloak.

**Weaknesses:** Python/Django runtime may have performance limitations at very high scale. Limited published performance benchmarks. Smaller ecosystem than Keycloak. Enterprise features moving behind paid licenses. Multi-tenancy model less mature than Keycloak's realms.

---

### BoxyHQ / Ory Polis

**Architecture:** Next.js frontend + Node.js backend with a database abstraction layer. Can run as a standalone service or be embedded as an NPM library (`@boxyhq/saml-jackson`). Acts as a translation layer converting SAML assertions and OIDC responses into standardized OAuth2/OIDC tokens.

**Deployment model:** Docker container (`boxyhq/jackson`) or NPM library. Supports PostgreSQL, MySQL, MariaDB, MongoDB, Redis, and PlanetScale as database backends. Configuration via environment variables.

**Multi-tenancy:** Per-tenant SSO connections. Each tenant can have its own SAML/OIDC identity provider configuration.

**Strengths:** Purpose-built for the "add enterprise SSO to your SaaS" use case (direct WorkOS competitor). Wide database support. Can embed directly into Node.js apps. Simple deployment and configuration. Now part of the Ory ecosystem with broader backing.

**Weaknesses:** Not a full IAM solution -- must be paired with another auth system for user management, sessions, MFA. Acquired by Ory, so long-term independent roadmap uncertain. Limited to SSO/SCIM use cases. Node.js-only for library embedding.

---

## Key Findings

### 1. There is no single "best" solution -- it depends on requirements

- **Need a full-featured enterprise IAM with broad protocol support?** -> **Keycloak** (accept the operational overhead)
- **Building a B2C SaaS and want the best developer experience?** -> **SuperTokens** (accept limited enterprise protocol support)
- **Need internet-scale, cloud-native auth with maximum flexibility?** -> **Ory (Kratos/Hydra)** (accept the headless/BYO-UI requirement)
- **Want the easiest self-hosted identity provider with a great admin UI?** -> **Authentik** (accept potential scale limitations)
- **Just need to add enterprise SSO/SCIM to an existing app?** -> **BoxyHQ/Ory Polis** (pair with another auth system)

### 2. BoxyHQ acquisition changes the landscape

BoxyHQ's acquisition by Ory and rebranding as Ory Polis means:
- The Ory ecosystem now covers SAML/SCIM, filling its biggest protocol gap
- BoxyHQ's independent roadmap is now part of Ory's strategy
- For teams evaluating standalone SSO bridges, Ory Polis remains the leading open-source option

### 3. Scale-proven: Only Ory has public evidence of internet-scale deployment

OpenAI's migration to Ory Hydra (800M+ WAU) is the largest publicly known deployment of any solution evaluated. Keycloak has extensive enterprise deployments but no comparable public benchmarks at that scale.

### 4. Protocol coverage varies significantly

If SAML IdP functionality, LDAP federation, and RADIUS are requirements:
- **Keycloak** and **Authentik** are the only solutions with native support for all three
- **Ory** requires Polis for SAML and has no LDAP/RADIUS support
- **SuperTokens** has none of these natively

### 5. Self-hosting complexity correlates with feature breadth

Solutions with more features (Keycloak) have more moving parts to configure and maintain. The simplest to self-host (SuperTokens, BoxyHQ/Polis) have the narrowest feature sets. Authentik strikes a good balance with broad features and moderate complexity.

### 6. Database convergence on PostgreSQL

Four of five solutions support or require PostgreSQL. It is the clear default for self-hosted identity infrastructure. CockroachDB support (Ory) is a differentiator for globally distributed deployments.

---

*End of Technical Architecture Evaluation*
