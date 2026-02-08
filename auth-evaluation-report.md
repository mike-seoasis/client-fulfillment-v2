# Open-Source Authentication Solutions: Comprehensive Evaluation Report

**Date:** 2026-02-08
**Purpose:** Evaluate open-source alternatives to WorkOS AuthKit for authentication infrastructure
**Solutions Evaluated:** Keycloak, SuperTokens, Ory (Kratos/Hydra), Authentik, BoxyHQ/Ory Polis
**Baseline:** WorkOS AuthKit

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Feature Matrix](#1-detailed-feature-matrix)
3. [Comparative Analysis](#2-comparative-analysis)
4. [Final Recommendation](#3-final-recommendation)
5. [Quick Start Guide](#4-quick-start-guide)

---

## Executive Summary

After evaluating five open-source authentication solutions across four dimensions (technical architecture, developer experience, security/compliance, and cost/licensing), we recommend **SuperTokens** as the primary choice and **Ory (Kratos/Hydra)** as the runner-up.

**SuperTokens** wins on developer experience, cost efficiency, and security track record. **Ory** wins on compliance certifications, scalability ceiling, and authorization capabilities. The right choice depends on whether DX/speed-to-market or compliance/enterprise-grade authorization is your priority.

**Authentik is not recommended** due to critical security vulnerabilities discovered in 2024 (CVSS 9.0 and 9.8), including a fundamental authentication bypass via header spoofing.

**Key cost insight:** Self-hosting becomes cheaper than WorkOS at just 3 SSO connections (~$375/mo WorkOS vs ~$260/mo SuperTokens self-hosted). At 50 connections, the gap is 18.7x ($4,850 vs $260).

---

## 1. Detailed Feature Matrix

### Core Authentication Features

| Feature | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|---------|:--------:|:-----------:|:-------------------:|:---------:|:----------------:|
| Email/Password | Yes | Yes | Yes | Yes | No |
| Social Login | 20+ providers | 10+ providers | 15+ providers | 10+ providers | No |
| Passwordless/Magic Links | Yes | Yes | Yes | Yes | No |
| TOTP MFA | Yes | Yes | Yes | Yes | No |
| WebAuthn/Passkeys | Yes | Yes | Yes | Yes | No |
| SMS OTP | Plugin | Yes | Yes | Yes (fallback) | No |
| Backup/Recovery Codes | Yes | No | Yes | No | No |
| Adaptive MFA | Yes | Yes | Yes | Yes | No |

### Enterprise / Protocol Features

| Feature | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|---------|:--------:|:-----------:|:-------------------:|:---------:|:----------------:|
| OIDC/OAuth2 Provider | Yes (certified) | Via integration | Yes (Hydra, certified) | Yes | Converts to OAuth2 |
| SAML 2.0 IdP | Yes | No | Via Polis (enterprise) | Yes | Yes (bridge) |
| SCIM 2.0 | Via extension | Via integration | Via Polis (enterprise) | Yes | Yes |
| LDAP | Yes | No | No | Yes | No |
| RADIUS | Via extension | No | No | Yes | No |
| Kerberos | Yes | No | No | No | No |

### Authorization & Access Control

| Feature | Keycloak | SuperTokens | Ory (Keto) | Authentik | BoxyHQ/Ory Polis |
|---------|:--------:|:-----------:|:----------:|:---------:|:----------------:|
| RBAC | Yes | Yes (basic) | Yes (Zanzibar) | Yes | No |
| ABAC/Policy Engine | Yes (UMA 2.0) | No | Yes (Zanzibar) | Yes | No |
| Fine-Grained Permissions | Yes | No | Yes (Google Zanzibar) | Limited | No |
| Multi-Tenancy | Yes (realms) | Yes (paid) | Yes (projects) | Yes (brands) | Yes (connections) |
| Admin Portal | Yes (full) | Yes (basic) | No (headless) | Yes (excellent) | Yes (SSO mgmt) |

### Session & Token Security

| Feature | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Ory Polis |
|---------|:--------:|:-----------:|:---:|:---------:|:----------------:|
| JWT Tokens | Yes | Yes | Yes | Yes | Yes |
| Rotating Refresh Tokens | Yes | Yes + theft detection | Yes | Yes | N/A |
| Token Theft Detection | No | **Yes (unique)** | No | No | No |
| Session Revocation | Yes | Yes | Yes | Yes | N/A |
| Brute-Force Protection | Yes | Yes | Yes (config) | Yes | No |

### Infrastructure & Operations

| Feature | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ/Ory Polis |
|---------|:--------:|:-----------:|:-------------------:|:---------:|:----------------:|
| Language | Java (Quarkus) | Java (Core) | Go | Python (Django) | Node.js/TypeScript |
| Architecture | Monolith | 3-tier (SDK-based) | Composable microservices | Monolith + workers | Focused microservice |
| Database | PostgreSQL + others | PostgreSQL only | PostgreSQL, CockroachDB | PostgreSQL only | PostgreSQL + others |
| Pre-built UI | Full (themed) | React components | Headless (BYO UI) | Full (web components) | None (SSO infra) |
| Self-Host Complexity | 3.4/5 (highest) | 2.0/5 | 2.6/5 | 2.2/5 | 1.6/5 (lowest) |

---

## 2. Comparative Analysis

### 2.1 Technical Architecture & Scalability

**Ory leads on scalability.** OpenAI runs Ory Hydra at 800M+ weekly active users — the largest publicly known deployment of any solution evaluated. Its stateless Go microservices scale by simply adding pods with no cache coordination. CockroachDB support enables globally distributed deployments.

**SuperTokens leads on simplicity.** Its unique 3-tier architecture (Frontend SDK -> Backend SDK -> Core) runs the lightest infrastructure. A single PostgreSQL instance supports tens of millions of MAU. Self-hosting requires just a Docker container and a database.

**Keycloak is the most feature-complete but heaviest.** Official benchmarks reach ~12,000 req/s, but JVM memory tuning, Infinispan cache management, and StatefulSet deployments on Kubernetes add significant operational burden.

**Authentik simplified its stack in 2025** by eliminating Redis (all state now in PostgreSQL), but limited published performance data positions it for SMB-to-mid-enterprise rather than internet-scale.

**BoxyHQ was acquired by Ory** (rebranded as Ory Polis), reducing the field to four distinct solution families. It remains a focused SSO bridge, not a standalone auth platform.

| Dimension | Winner | Runner-Up |
|-----------|--------|-----------|
| Proven scale ceiling | Ory (800M+ WAU) | Keycloak (12K req/s benchmarked) |
| Easiest self-hosting | SuperTokens (2.0/5) | Authentik (2.2/5) |
| Broadest protocol support | Keycloak | Authentik |
| Most cloud-native | Ory (stateless Go) | SuperTokens (stateless core) |

### 2.2 Developer Experience & Ease of Integration

**SuperTokens is the clear DX winner.** 15-minute time-to-first-auth, official SDKs for Node.js/Python/Go, pre-built React UI, and recently rebuilt documentation that is the best in class. The recipe-based architecture is intuitive. Main downside: React-only pre-built UI.

**BoxyHQ/Ory Polis is the DX winner for enterprise SSO specifically.** Its elegant abstraction of SAML into standard OAuth 2.0 flows is brilliant. But it only covers SSO — you need another solution for everything else.

**Ory has the highest DX friction.** Multi-service complexity, mandatory BYO UI, auto-generated SDKs with no backwards-compatibility guarantees, and fragmented documentation across multiple services. Powerful but demanding.

**Keycloak's learning curve is steep.** Most complete feature set with the largest community (30K+ stars), but frequent breaking changes (even in patch releases), JVM resource requirements, and Java-centric extensibility create friction.

| Dimension | Winner | Runner-Up |
|-----------|--------|-----------|
| Time-to-first-auth | SuperTokens (15 min) | BoxyHQ/Polis (20 min) |
| SDK quality | SuperTokens (hand-crafted) | BoxyHQ (hand-crafted, JS only) |
| Documentation | SuperTokens (A) | BoxyHQ (B+, narrow) |
| Pre-built UI | Keycloak (most complete) | SuperTokens (best React) |
| Admin experience | Authentik (flow designer) | Keycloak (comprehensive) |
| Community size | Keycloak (30K stars) | Authentik (19.5K stars) |

### 2.3 Security Posture & Compliance

**Ory is the security and compliance leader (Grade: A).** The only solution with both SOC 2 Type 2 and ISO 27001 certifications. Go-based architecture has the lowest supply chain risk (~50-80 direct dependencies vs Keycloak's 500+). Zanzibar-based authorization is industry-leading. Fewest CVEs relative to project age.

**SuperTokens has the cleanest security record (Grade: B+).** Zero known public CVEs. Unique rotating refresh token theft detection (RFC 6819). SOC 2 compliant on managed service. Weakness: limited authorization (RBAC only) and zero CVEs may reflect under-scrutiny.

**Keycloak has the most CVEs but strongest response process (Grade: B).** 100+ all-time CVEs with recurring privilege escalation patterns and a massive Java dependency tree. However, Red Hat's structured security response is the most mature in the group.

**Authentik is a security risk (Grade: C+).** Two critical-severity CVEs in 2024 alone — including a CVSS 9.8 and a password authentication bypass via X-Forwarded-For header spoofing (CVSS 9.0). The header spoofing vulnerability is a fundamental design-level gap for an identity provider. **Not recommended for production without an independent security audit.**

| Dimension | Winner | Runner-Up |
|-----------|--------|-----------|
| Compliance certifications | Ory (SOC 2 + ISO 27001) | SuperTokens (SOC 2) |
| Vulnerability record | SuperTokens (0 CVEs) | Ory (~5-10, all low-med) |
| Session security | SuperTokens (theft detection) | Ory |
| Authorization depth | Ory (Zanzibar) | Keycloak (UMA 2.0) |
| Supply chain risk | Ory (Go, ~80 deps) | BoxyHQ (~100 deps) |
| Security response process | Keycloak (Red Hat) | Ory |

### 2.4 Total Cost of Ownership & Licensing

**All solutions use permissive licenses** (Apache 2.0 or MIT). No AGPL or copyleft concerns.

**WorkOS is free until you need SSO.** The 1M MAU free tier is unbeatable for basic auth, but per-connection SSO pricing ($125/connection/month) becomes the dominant cost for B2B SaaS.

**SuperTokens is cheapest to self-host.** Runs on a t3.micro (~$30-50/mo infra) with minimal DevOps overhead (~2-4 hrs/month). At 10K MAU with 20 SSO connections: $350/mo vs WorkOS's $2,250/mo.

**Keycloak is free on features but expensive to operate.** JVM resource demands push infrastructure costs to $350-900/mo, plus 8-16 hrs/month DevOps time. Total TCO: $950-$2,100/mo across scale tiers.

**The SSO break-even is 3 connections.** At just 3 enterprise SSO connections, self-hosting any solution (except Keycloak) is cheaper than WorkOS. At 50 connections, the gap is massive:

| Scale | WorkOS (w/ SSO) | SuperTokens SH | Ory SH | Authentik OSS | Keycloak SH |
|-------|----------------:|---------------:|-------:|--------------:|------------:|
| 1K MAU + 5 SSO | $625/mo | $260/mo | $350/mo | $370/mo | $1,150/mo |
| 10K MAU + 20 SSO | $2,250/mo | $350/mo | $435/mo | $465/mo | $1,400/mo |
| 100K MAU + 50 SSO | $4,850/mo | $530/mo | $700/mo | $750/mo | $2,100/mo |

**Licensing risk is lowest for Keycloak** (CNCF governance). SuperTokens and Ory are VC-backed with Apache 2.0 (existing code always forkable). Authentik is a public benefit company with explicit pledge not to remove OSS features.

---

## 3. Final Recommendation

### Primary Recommendation: SuperTokens

**SuperTokens is the best overall choice** for teams that need a practical, cost-effective authentication solution with excellent developer experience.

| Criterion | SuperTokens Score | Why |
|-----------|:-----------------:|-----|
| Developer Experience | **A** | 15-min setup, best docs, official SDKs for Node/Python/Go |
| Security | **B+** | Zero CVEs, unique token theft detection, SOC 2 (cloud) |
| Cost Efficiency | **A** | $30-50/mo infra self-hosted, 6-18x cheaper than WorkOS with SSO |
| Self-Hosting | **A-** | Simplest infrastructure (1 container + PostgreSQL) |
| Scalability | **B+** | Stateless core, proven at tens of millions MAU |

**Strengths:**
- Fastest time-to-first-auth (15 minutes)
- All major backend languages covered with hand-crafted, stable SDKs
- Pre-built React UI components for login, signup, MFA flows
- Recipe-based architecture is intuitive and composable
- Apache 2.0 license with no copyleft concerns
- Cheapest self-hosted TCO ($260-530/mo across all scale tiers)
- Rotating refresh token theft detection is unique and valuable

**Weaknesses to plan for:**
- Pre-built UI is React-only (Vue/Angular/Svelte require custom UI via headless APIs)
- No native SAML IdP — needs BoxyHQ/Polis integration for enterprise SSO
- Multi-tenancy is a paid feature
- Authorization is RBAC-only (no ABAC/fine-grained without external tools like Cerbos)
- Smaller community than Keycloak (14.8K vs 30K stars)
- VC-backed with limited funding ($1.35M) — monitor sustainability

**Mitigation strategy for SSO:** Pair SuperTokens with Ory Polis (formerly BoxyHQ) for SAML/SCIM enterprise SSO. Polis is Apache 2.0 and purpose-built to bridge SAML into OAuth 2.0 flows. This combination provides full B2B auth coverage at the lowest cost.

---

### Runner-Up: Ory (Kratos/Hydra)

**Ory is the best choice when compliance, scale, or authorization complexity are primary drivers.**

| Criterion | Ory Score | Why |
|-----------|:---------:|-----|
| Security & Compliance | **A** | Only solution with SOC 2 Type 2 + ISO 27001; Go minimizes supply chain risk |
| Scalability | **A+** | Proven at 800M+ WAU (OpenAI); stateless Go microservices |
| Authorization | **A+** | Google Zanzibar-based permissions (Keto), sub-10ms P95 |
| Cost Efficiency | **B+** | $350-700/mo self-hosted, competitive but slightly more than SuperTokens |
| Developer Experience | **B-** | High friction: multi-service, BYO UI, auto-generated SDKs |

**Choose Ory over SuperTokens when:**
- You need SOC 2 Type 2 or ISO 27001 certification out of the box
- You need fine-grained authorization beyond RBAC (Zanzibar via Keto)
- You anticipate internet-scale traffic (100M+ users)
- You have a strong DevOps team comfortable with multi-service architectures
- You need CockroachDB support for global data distribution

**Choose SuperTokens over Ory when:**
- Speed to market is critical (15 min vs 45-60 min setup)
- Your team prefers hand-crafted SDKs with stability guarantees
- You want pre-built UI components out of the box
- Your authorization needs are simple (RBAC is sufficient)
- You want the lowest possible infrastructure cost

---

### Solutions NOT Recommended

**Authentik: Not recommended for production.** Two critical-severity CVEs in 2024 (CVSS 9.0 auth bypass via header spoofing, CVSS 9.8 additional critical) represent fundamental security design concerns for an identity provider. The admin UI is excellent but trust is undermined by the vulnerability pattern.

**Keycloak: Recommended only with dedicated DevOps.** The most feature-complete solution but highest operational overhead (JVM tuning, Infinispan management, $950-2,100/mo TCO). Choose only if you need the full breadth of SAML + OIDC + LDAP + Kerberos + RADIUS and have a team to maintain it.

**BoxyHQ/Ory Polis: Not standalone.** Excellent as a supplementary SSO bridge (pair with SuperTokens or Ory), but cannot serve as a primary auth solution.

---

### Decision Matrix Summary

| Priority | Choose This |
|----------|-------------|
| Best DX + lowest cost | **SuperTokens** |
| Best compliance + scale | **Ory** |
| Best DX + compliance combo | **SuperTokens + Ory Polis** (for SSO) |
| Need LDAP/Kerberos/RADIUS | **Keycloak** (with dedicated ops team) |
| Zero cost to start, migrate later | **WorkOS free tier** -> SuperTokens when SSO needed |

---

## 4. Quick Start Guide: SuperTokens (Self-Hosted)

### Prerequisites

- Docker and Docker Compose installed
- PostgreSQL 13+ (or use the Docker Compose setup below)
- Node.js 16+ (for your backend)

### Step 1: Start SuperTokens Core

Create a `docker-compose.yml`:

```yaml
version: "3.8"

services:
  supertokens:
    image: registry.supertokens.io/supertokens/supertokens-postgresql:latest
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "3567:3567"
    environment:
      POSTGRESQL_CONNECTION_URI: "postgresql://supertokens:changeme@db:5432/supertokens"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3567/hello"]
      interval: 10s
      timeout: 5s
      retries: 5

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: supertokens
      POSTGRES_PASSWORD: changeme
      POSTGRES_DB: supertokens
    ports:
      - "5432:5432"
    volumes:
      - supertokens_db:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-LINE", "pg_isready -U supertokens"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  supertokens_db:
```

Start the services:

```bash
docker compose up -d
```

Verify the core is running:

```bash
curl http://localhost:3567/hello
# Expected: "Hello"
```

### Step 2: Install Backend SDK (Node.js / Express Example)

```bash
npm install supertokens-node
```

Initialize in your app:

```typescript
import supertokens from "supertokens-node";
import Session from "supertokens-node/recipe/session";
import EmailPassword from "supertokens-node/recipe/emailpassword";
import { middleware } from "supertokens-node/framework/express";
import express from "express";
import cors from "cors";

supertokens.init({
  framework: "express",
  supertokens: {
    connectionURI: "http://localhost:3567",
  },
  appInfo: {
    appName: "My App",
    apiDomain: "http://localhost:3001",
    websiteDomain: "http://localhost:3000",
    apiBasePath: "/auth",
    websiteBasePath: "/auth",
  },
  recipeList: [
    EmailPassword.init(),
    Session.init(),
  ],
});

const app = express();

app.use(
  cors({
    origin: "http://localhost:3000",
    allowedHeaders: ["content-type", ...supertokens.getAllCORSHeaders()],
    credentials: true,
  })
);

// SuperTokens middleware handles /auth/* routes
app.use(middleware());

// Your protected route
app.get("/api/user", Session.verifySession(), async (req, res) => {
  const userId = req.session!.getUserId();
  res.json({ userId });
});

app.listen(3001, () => console.log("Backend running on :3001"));
```

### Step 3: Install Frontend SDK (React Example)

```bash
npm install supertokens-auth-react supertokens-web-js
```

Initialize in your React app:

```tsx
import React from "react";
import SuperTokens, { SuperTokensWrapper } from "supertokens-auth-react";
import EmailPassword from "supertokens-auth-react/recipe/emailpassword";
import Session from "supertokens-auth-react/recipe/session";

SuperTokens.init({
  appInfo: {
    appName: "My App",
    apiDomain: "http://localhost:3001",
    websiteDomain: "http://localhost:3000",
    apiBasePath: "/auth",
    websiteBasePath: "/auth",
  },
  recipeList: [
    EmailPassword.init(),
    Session.init(),
  ],
});

function App() {
  return (
    <SuperTokensWrapper>
      {/* SuperTokens renders login UI at /auth */}
      <YourAppRoutes />
    </SuperTokensWrapper>
  );
}

export default App;
```

### Step 4: Add Route Protection

```tsx
import { SessionAuth } from "supertokens-auth-react/recipe/session";

function ProtectedPage() {
  return (
    <SessionAuth>
      <Dashboard />
    </SessionAuth>
  );
}
```

### Step 5: Add Enterprise SSO (Optional — via Ory Polis)

If you need SAML SSO for enterprise customers, add Ory Polis as a bridge:

```bash
docker pull boxyhq/jackson:latest
```

Add to your `docker-compose.yml`:

```yaml
  jackson:
    image: boxyhq/jackson:latest
    ports:
      - "5225:5225"
    environment:
      JACKSON_API_KEYS: "your-api-key-here"
      DB_ENGINE: "sql"
      DB_TYPE: "postgres"
      DB_URL: "postgresql://supertokens:changeme@db:5432/jackson"
      NEXTAUTH_URL: "http://localhost:5225"
    restart: unless-stopped
```

This gives you SAML-to-OAuth2 bridging at zero per-connection cost.

### What You Get

After these steps (~15 minutes), you have:
- Email/password authentication with pre-built React UI
- Secure session management with rotating refresh tokens + theft detection
- CSRF protection
- A protected API route
- Optional: Enterprise SAML SSO via Ory Polis

### Next Steps

- **Add social login:** Add `ThirdParty.init()` recipe with Google/GitHub/etc. providers
- **Add MFA:** Add `MultiFactorAuth.init()` recipe (paid add-on)
- **Add passwordless:** Add `Passwordless.init()` recipe
- **Production hardening:** Set `SUPERTOKENS_API_KEY` environment variable, configure HTTPS, set up database backups
- **Monitoring:** SuperTokens core exposes health endpoint at `/hello` for liveness checks

---

## Appendix: Individual Research Reports

The following detailed reports were produced by the evaluation team and are available in `.tmp/`:

- `.tmp/auth-eval-technical.md` — Technical Architecture Evaluation (Solution Architect)
- `.tmp/auth-eval-dx.md` — Developer Experience & UI/UX Evaluation (DX Analyst)
- `.tmp/auth-eval-security.md` — Security & Compliance Analysis (Security Analyst)
- `.tmp/auth-eval-cost.md` — Business Cost & Licensing Analysis (Cost Analyst)

---

*Report compiled 2026-02-08. Solutions evaluated at their latest stable versions as of this date. Pricing and features are subject to change — verify with vendor documentation before making purchasing decisions.*
