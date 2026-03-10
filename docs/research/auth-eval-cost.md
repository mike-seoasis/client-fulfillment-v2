# Authentication Solutions: Business Cost & Licensing Analysis

> Prepared: 2026-02-08 | Analyst: Cost & Business Analyst Agent

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pricing Models Comparison](#pricing-models-comparison)
3. [Self-Hosted TCO Modeling](#self-hosted-tco-modeling)
4. [Licensing Analysis](#licensing-analysis)
5. [Vendor Risk & Sustainability](#vendor-risk--sustainability)
6. [Commercial Support](#commercial-support)
7. [WorkOS Baseline Comparison](#workos-baseline-comparison)
8. [Break-Even Analysis](#break-even-analysis)
9. [Recommendations](#recommendations)

---

## 1. Executive Summary

This analysis evaluates the financial and licensing implications of five open-source authentication solutions against WorkOS AuthKit as the baseline. Key findings:

- **WorkOS** offers the most generous free tier (1M MAU) but per-connection SSO/SCIM pricing ($125/connection/month) adds up fast for B2B SaaS.
- **SuperTokens** is the most cost-effective at low-to-mid scale with lightweight infrastructure needs and Apache 2.0 licensing.
- **Ory (Kratos/Hydra)** is the most lightweight to self-host but enterprise features (SAML, SCIM, SSO) require the paid Ory Enterprise License.
- **Keycloak** is fully free and feature-complete but has the highest operational TCO due to JVM resource demands and maintenance overhead.
- **Authentik** offers excellent value for internal/B2B identity with straightforward per-user pricing and MIT license.
- **BoxyHQ (Ory Polis)** was acquired by Ory in 2025 and is now part of the Ory ecosystem; evaluate via Ory pricing.

**Bottom line:** For a project at early stage (<1,000 MAU), WorkOS free tier or SuperTokens self-hosted are the cheapest options. At scale (>10K MAU), self-hosted solutions become significantly cheaper than SaaS, but only if you have the DevOps capacity to maintain them.

---

## 2. Pricing Models Comparison

### Overview Table

| Solution | Pricing Model | Free Tier | First Paid Tier | Enterprise |
|----------|--------------|-----------|----------------|------------|
| **WorkOS** | MAU + per-connection | 1M MAU free | $125/SSO connection/mo | Annual credits, custom |
| **Keycloak** | Free (self-host only) | Unlimited | N/A (fully free) | Red Hat subscription bundle |
| **SuperTokens** | Per-MAU (cloud) / Free (self-host core) | 5K MAU (cloud) / Unlimited (self-host core) | $0.02/MAU (cloud) | Contact sales |
| **Ory (Kratos/Hydra)** | aDAU-based (cloud) / Free (self-host OSS) | Developer plan (cloud) / Unlimited (self-host OSS) | $0.14/aDAU/mo + $770/yr base | Custom enterprise license |
| **Authentik** | Per-user (enterprise features) | Unlimited (open source) | $5/internal user/mo, $0.02/external user/mo | Starting $20K/year |
| **BoxyHQ (Ory Polis)** | Part of Ory ecosystem | N/A (acquired) | Via Ory pricing | Via Ory pricing |

### Detailed Pricing Breakdowns

#### WorkOS AuthKit

| Component | Price |
|-----------|-------|
| User Management (AuthKit) | Free up to 1M MAU, then $2,500/mo per 1M block |
| SSO (per connection) | $125/mo (1-15), $100 (16-30), $80 (31-50), $65 (51-100), $50 (101-200) |
| Directory Sync / SCIM | $125/mo per connection (same volume tiers as SSO) |
| Audit Logs | $99/mo per 1M events + $125/mo per SIEM connection |
| Custom Domain | $99/mo flat |
| Radar (Bot Detection) | 1,000 checks free, then $100/mo per 50K checks |

**Key insight:** User management is essentially free for most companies. The real cost driver is SSO/SCIM connections -- a B2B SaaS with 20 enterprise customers needing SSO pays ~$2,250/mo just for SSO connections.

#### Keycloak

| Component | Price |
|-----------|-------|
| Software license | $0 (Apache 2.0) |
| All features | Included free |
| Red Hat commercial build | Bundled with Red Hat Runtimes / OpenShift subscriptions |
| Third-party managed hosting | $99-$500+/mo (Cloud-IAM, Phase Two, SkyCloak, Elest.io) |

**Key insight:** Keycloak is the only solution where 100% of features are free. The cost is entirely operational.

#### SuperTokens

| Component | Cloud Price | Self-Hosted Price |
|-----------|------------|-------------------|
| Core auth (email/password, social, passwordless) | $0.02/MAU (free <5K) | Free, no limits |
| MFA | +$0.01/MAU (min $100/mo) | +$0.01/MAU (min $100/mo) |
| Account Linking | +$0.005/MAU (min $100/mo) | +$0.005/MAU (min $100/mo) |
| Dashboard Users | $20/user/mo (first 3 free) | $20/user/mo (first 3 free) |
| Multi-tenancy | Contact sales | Contact sales |
| Attack Protection | Contact sales | Contact sales |

**Key insight:** Self-hosted core features are completely free. Paid add-ons (MFA, account linking) cost the same whether self-hosted or cloud.

#### Ory (Kratos/Hydra)

| Tier | Base Cost | Usage Cost | Key Inclusions |
|------|-----------|------------|----------------|
| Developer (Free) | $0 | N/A | Testing/PoC only |
| Production | $770/yr ($64/mo) | $0.14/aDAU/mo | 1 prod + 3 staging envs, $21/mo credit |
| Growth | $9,350/yr | $0.12/aDAU/mo | 2 prod + 5 staging, analytics, $255/mo credit |
| Enterprise | Custom | Custom | 99.99% SLA, multi-region |
| Self-Hosted OSS | $0 | N/A | Core features only (no SAML, SCIM, org SSO) |
| Enterprise License (self-hosted) | Custom | Custom | SAML, SCIM, SSO, CAPTCHAs, security SLAs |

**Key insight:** "aDAU" (average daily active user) is a unique metric. A user logging in daily counts more than one logging in monthly. For a 10K MAU app where ~20% are daily active, that's ~2K aDAU = $280/mo on Production tier + $770/yr base.

#### Authentik

| Tier | Internal Users | External Users | Support |
|------|---------------|----------------|---------|
| Open Source | Free, unlimited | Free, unlimited | Community Discord only |
| Enterprise | $5/user/mo | $0.02/user/mo | Ticket-based (annual >$1K) |
| Enterprise Plus | $5/user/mo (volume discounts) | $0.02/user/mo | Dedicated SLA support |

Enterprise Plus minimum: $20K/year annual commitment.

**Key insight:** At $5/internal user/month, Authentik is very affordable for small-to-mid teams. 50 internal users + 5,000 external users = $350/mo.

#### BoxyHQ / Ory Polis

BoxyHQ was acquired by Ory in May 2025 and rebranded as Ory Polis. The standalone BoxyHQ product no longer exists independently. SAML Jackson remains open source on GitHub (Apache 2.0), but for a supported product, pricing is now via Ory's tiers. See Ory pricing above.

---

## 3. Self-Hosted TCO Modeling

### Infrastructure Cost Estimates

All estimates assume AWS cloud hosting. Costs include compute, database, and basic networking.

#### Minimum Infrastructure Per Solution

| Solution | Compute | Database | Cache/Other | Min Monthly Infra |
|----------|---------|----------|-------------|-------------------|
| **Keycloak** | 3x t3.medium (3x4GB RAM, Java/JVM) | RDS PostgreSQL (db.t3.medium) | N/A | ~$350-500/mo |
| **SuperTokens** | 1x t3.micro (1GB RAM, Java core) | RDS PostgreSQL (db.t3.micro) | N/A | ~$30-50/mo |
| **Ory Kratos** | 1x t3.small (2GB RAM, Go binary ~15MB) | RDS PostgreSQL (db.t3.micro) | N/A | ~$40-60/mo |
| **Authentik** | 1x t3.small (2GB RAM, Python/Django) | RDS PostgreSQL (db.t3.small) | Redis (dropping in 2025.10+) | ~$60-90/mo |
| **BoxyHQ/Polis** | 1x t3.micro (Node.js) | RDS PostgreSQL (db.t3.micro) | N/A | ~$25-40/mo |

### Full TCO at Scale Tiers (Monthly)

Includes: infrastructure, DevOps time (estimated at $75/hr), security patching, and monitoring.

#### 100 MAU (Startup / Early Stage)

| Solution | Infra | DevOps (hrs/mo) | DevOps Cost | Software License | Total/mo |
|----------|-------|-----------------|-------------|-----------------|----------|
| **WorkOS** | $0 | 0 | $0 | $0 (free tier) | **$0** |
| **Keycloak** | $350 | 8 | $600 | $0 | **$950** |
| **SuperTokens** | $30 | 2 | $150 | $0 | **$180** |
| **Ory Kratos** | $40 | 3 | $225 | $0 | **$265** |
| **Authentik** | $60 | 3 | $225 | $0 | **$285** |
| **BoxyHQ/Polis** | $25 | 2 | $150 | $0 | **$175** |

**Winner at 100 MAU:** WorkOS (free tier) -- no contest. Self-hosting makes no financial sense at this scale.

#### 1,000 MAU (Growing App)

| Solution | Infra | DevOps (hrs/mo) | DevOps Cost | Software License | Total/mo |
|----------|-------|-----------------|-------------|-----------------|----------|
| **WorkOS** | $0 | 0 | $0 | $0 (free tier) | **$0** |
| **WorkOS + 5 SSO** | $0 | 0 | $0 | $625 | **$625** |
| **Keycloak** | $400 | 10 | $750 | $0 | **$1,150** |
| **SuperTokens** | $35 | 3 | $225 | $0 | **$260** |
| **Ory Kratos** | $50 | 4 | $300 | $0 | **$350** |
| **Authentik** | $70 | 4 | $300 | $0 | **$370** |
| **BoxyHQ/Polis** | $30 | 3 | $225 | $0 | **$255** |

**Winner at 1K MAU:** WorkOS (free tier, no SSO) or SuperTokens/BoxyHQ self-hosted (if avoiding WorkOS lock-in).

**Note:** WorkOS cost jumps significantly when SSO connections are needed. 5 enterprise SSO connections = $625/mo.

#### 10,000 MAU (Established Product)

| Solution | Infra | DevOps (hrs/mo) | DevOps Cost | Software License | Total/mo |
|----------|-------|-----------------|-------------|-----------------|----------|
| **WorkOS** | $0 | 0 | $0 | $0 (free tier) | **$0** |
| **WorkOS + 20 SSO** | $0 | 0 | $0 | $2,250 | **$2,250** |
| **Keycloak** | $500 | 12 | $900 | $0 | **$1,400** |
| **SuperTokens** | $50 | 4 | $300 | $0 | **$350** |
| **SuperTokens Cloud** | $0 | 0 | $0 | $200 | **$200** |
| **Ory Cloud (Production)** | $0 | 0 | $0 | ~$344 | **$344** |
| **Ory Self-Hosted** | $60 | 5 | $375 | $0 | **$435** |
| **Authentik** | $90 | 5 | $375 | $0 (OSS) | **$465** |
| **Authentik Enterprise** | $90 | 5 | $375 | ~$350 | **$815** |

**Winner at 10K MAU:** SuperTokens Cloud ($200/mo) or WorkOS free tier (if no SSO needed). Self-hosted SuperTokens ($350) if avoiding vendor dependence.

#### 100,000 MAU (Scale)

| Solution | Infra | DevOps (hrs/mo) | DevOps Cost | Software License | Total/mo |
|----------|-------|-----------------|-------------|-----------------|----------|
| **WorkOS** | $0 | 0 | $0 | $0 (free tier) | **$0** |
| **WorkOS + 50 SSO** | $0 | 0 | $0 | $4,850 | **$4,850** |
| **Keycloak** | $900 | 16 | $1,200 | $0 | **$2,100** |
| **SuperTokens** | $80 | 6 | $450 | $0 | **$530** |
| **SuperTokens Cloud** | $0 | 0 | $0 | $2,000 | **$2,000** |
| **Ory Cloud (Growth)** | $0 | 0 | $0 | ~$3,179 | **$3,179** |
| **Ory Self-Hosted** | $100 | 8 | $600 | $0 | **$700** |
| **Authentik** | $150 | 8 | $600 | $0 (OSS) | **$750** |
| **Authentik Enterprise** | $150 | 8 | $600 | ~$2,500 | **$3,250** |

**Winner at 100K MAU:** SuperTokens self-hosted ($530/mo). Keycloak is more expensive due to JVM infrastructure demands and maintenance overhead.

### TCO Summary Chart

```
Monthly Cost by Scale (no SSO connections)
=========================================

                100 MAU    1K MAU    10K MAU   100K MAU
WorkOS          $0         $0        $0        $0
Keycloak        $950       $1,150    $1,400    $2,100
SuperTokens SH  $180       $260      $350      $530
SuperTokens CL  --         --        $200      $2,000
Ory SH          $265       $350      $435      $700
Authentik       $285       $370      $465      $750
BoxyHQ/Polis    $175       $255      --        --

SH = Self-Hosted, CL = Cloud
Note: WorkOS $0 assumes no SSO/SCIM connections needed


Monthly Cost WITH SSO (assuming 10 enterprise SSO connections)
=============================================================

                100 MAU    1K MAU    10K MAU   100K MAU
WorkOS          $1,250     $1,250    $1,250    $1,250
Keycloak        $950       $1,150    $1,400    $2,100
SuperTokens SH  $180       $260      $350      $530
Ory SH          $265       $350      $435      $700
Authentik       $285       $370      $465      $750
```

---

## 4. Licensing Analysis

### License Comparison Table

| Solution | License | Type | OSI Approved | Redistribution | Commercial Use | Modification |
|----------|---------|------|--------------|---------------|----------------|-------------|
| **Keycloak** | Apache 2.0 | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **SuperTokens** | Apache 2.0 | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **Ory Kratos** | Apache 2.0 | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **Ory Hydra** | Apache 2.0 | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **Authentik** | MIT | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **BoxyHQ/Polis** | Apache 2.0 | Permissive | Yes | Unrestricted | Unrestricted | Unrestricted |
| **WorkOS** | Proprietary | N/A | No | Not allowed | Per terms | Not allowed |

### Key Licensing Insights

#### Apache 2.0 (Keycloak, SuperTokens, Ory, BoxyHQ)
- **Business implications:** Maximum freedom. Can use, modify, distribute, and sublicense freely.
- **Patent clause:** Includes explicit patent grant, protecting users from patent litigation by contributors.
- **Attribution:** Must include copyright notice and license text in distributions.
- **No copyleft:** No requirement to open-source derivative works.
- **Best for:** Companies that want maximum flexibility and no legal concerns about future use.

#### MIT (Authentik)
- **Business implications:** Even more permissive than Apache 2.0. No patent clause, simpler terms.
- **Risk:** Lack of explicit patent grant means theoretically higher (but practically low) patent risk.
- **Attribution:** Must include copyright notice.
- **Best for:** Maximum simplicity; minimal legal overhead.

### Open Source vs. Source-Available Concerns

| Solution | Core OSS? | Enterprise Features | Concern Level |
|----------|----------|-------------------|---------------|
| **Keycloak** | 100% OSS | N/A -- all features included | None |
| **SuperTokens** | Core is OSS | MFA, Account Linking are paid add-ons | Low -- core is genuinely free |
| **Ory** | Core is OSS | SAML, SCIM, org SSO require Enterprise License | Medium -- key enterprise features gated |
| **Authentik** | Core is OSS | Google Workspace, Entra ID integration, advanced compliance in Enterprise | Low -- committed to not removing OSS features |
| **BoxyHQ/Polis** | Core is OSS | Now part of Ory ecosystem | Medium -- acquisition may change direction |

### License Change (Rug-Pull) Risk Assessment

| Solution | Risk Level | Rationale |
|----------|-----------|-----------|
| **Keycloak** | Very Low | CNCF incubating project. License change would require CNCF governance approval. Apache 2.0 code can always be forked. |
| **SuperTokens** | Low-Medium | VC-backed startup ($1.35M). Small team. Apache 2.0 means existing code is safe, but future versions could change. |
| **Ory** | Low-Medium | VC-backed ($27.5M). Already uses dual model (OSS + Enterprise License). Pattern is stable but enterprise feature gating could expand. |
| **Authentik** | Low | Public benefit company model. Explicit pledge not to move OSS features to enterprise. Small but growing community. |
| **BoxyHQ/Polis** | Medium | Acquired by Ory. Future licensing tied to Ory's decisions. Original Apache 2.0 code on GitHub is safe to fork. |

**Industry context:** The 2018-2024 wave of license changes (MongoDB SSPL, Elastic dual-license, HashiCorp BSL, Redis RSALv2) affected primarily infrastructure-as-a-service projects threatened by cloud providers. Auth solutions face less pressure from this vector because cloud providers already have native auth offerings (Cognito, Firebase Auth, Entra ID). However, VC-backed companies face pressure to monetize, which could lead to feature gating rather than license changes.

---

## 5. Vendor Risk & Sustainability

### Company & Governance Overview

| Solution | Backing | Funding | Governance | Sustainability |
|----------|---------|---------|------------|---------------|
| **Keycloak** | CNCF / Red Hat heritage | N/A (non-profit foundation) | CNCF governance, open community | **Strong** -- CNCF ensures long-term stewardship |
| **SuperTokens** | SuperTokens Inc. | $1.35M (YC, Root Ventures, Irregular Expressions) | Company-controlled | **Moderate** -- small funding, relies on growth |
| **Ory** | Ory Corp | $27.5M Series A (Insight Partners, Balderton, In-Q-Tel) | Company-controlled, active OSS community | **Strong** -- well-funded, notable investors including In-Q-Tel |
| **Authentik** | Authentik Security (PBC) | Seed (Open Core Ventures, Aviso Ventures, SNR, AWS Startups) | Company-controlled, public benefit corp | **Moderate** -- small but mission-driven |
| **BoxyHQ/Polis** | Ory Corp (acquired) | Via Ory funding | Ory-controlled | **Strong** (via Ory) |
| **WorkOS** | WorkOS Inc. | $200M+ (multiple rounds, Greenoaks Capital lead) | Proprietary | **Very Strong** -- heavily funded, large customer base |

### Sustainability Deep Dive

**Keycloak:**
- Lowest vendor risk due to CNCF stewardship and Red Hat heritage
- Active contributor community (800+ contributors on GitHub)
- Red Hat continues to maintain a commercial build
- CNCF graduation track provides long-term assurance
- Risk: JVM/Java ecosystem may feel dated vs. modern Go/Rust alternatives

**SuperTokens:**
- Small team, limited funding ($1.35M total)
- Y Combinator pedigree provides network and credibility
- Revenue model is clear (cloud + paid features)
- Risk: Insufficient funding for long-term sustainability if growth stalls
- Mitigation: Apache 2.0 means community can fork if company fails

**Ory:**
- Best-funded OSS auth company ($27.5M)
- In-Q-Tel investment signals government/security sector interest
- Recent acquisition of BoxyHQ shows expansion strategy
- CEO change (Jeff Kukowski, April 2024) suggests maturation
- Risk: VC pressure to monetize could expand enterprise-only features

**Authentik:**
- Public benefit company model reduces rug-pull risk
- Active community (50K+ GitHub stars)
- Smaller funding but sustainable growth trajectory
- Explicit commitment: "We will not move features from OSS to enterprise"
- Risk: Small team, limited professional support capacity

---

## 6. Commercial Support

### Support Comparison Table

| Solution | Free Support | Paid Support | SLA | Professional Services | Training |
|----------|-------------|-------------|-----|----------------------|----------|
| **WorkOS** | Docs + community | Included in pricing | Enterprise SLA available | Migration support | Documentation |
| **Keycloak** | Community forums, GitHub | Via Red Hat subscription ($$$) or 3rd-party (Phase Two, SkyCloak, Cloud-IAM) | Red Hat SLA with subscription | Red Hat consulting | Red Hat training catalog |
| **SuperTokens** | Community Discord, GitHub | Enterprise plans (contact sales) | Enterprise SLA (contact) | Implementation support | Documentation |
| **Ory** | Community Slack, GitHub | Growth: email support; Enterprise: dedicated | Enterprise 99.99% SLA | Migration, implementation | Documentation |
| **Authentik** | Community Discord | Enterprise: ticket-based (>$1K annual) | Enterprise Plus: dedicated SLA | Custom contracts available | Documentation |
| **BoxyHQ/Polis** | GitHub | Via Ory support tiers | Via Ory | Via Ory | Via Ory |

### Third-Party Keycloak Support Options

Since Keycloak has the richest third-party ecosystem:

| Provider | Service | Starting Price |
|----------|---------|---------------|
| **Cloud-IAM** | Managed Keycloak hosting | ~$99/mo |
| **Phase Two** | Managed hosting + extensions | ~$99/mo |
| **SkyCloak** | Managed Keycloak as a service | ~$149/mo |
| **Elest.io** | Managed hosting | ~$25/mo |
| **Red Hat** | Commercial build + support | Part of Red Hat subscription |

---

## 7. WorkOS Baseline Comparison

### Feature-for-Feature at Each Price Point

#### At $0/month (Free Tier)

| Feature | WorkOS (Free) | Keycloak | SuperTokens SH | Ory SH | Authentik |
|---------|--------------|----------|---------------|--------|-----------|
| Email/Password | Yes | Yes | Yes | Yes | Yes |
| Social Login | Yes | Yes | Yes | Yes | Yes |
| MFA | Yes | Yes | Paid add-on | Yes | Yes |
| Passwordless/Magic Link | Yes | Yes | Yes | Yes | Yes |
| User Management UI | Yes (AuthKit) | Yes (Admin Console) | Yes (Dashboard) | No (API only) | Yes (Admin) |
| SSO/SAML | No (paid) | Yes | No (enterprise) | No (enterprise) | Yes |
| SCIM/Dir Sync | No (paid) | No (extension) | No (enterprise) | No (enterprise) | Yes |
| Self-hosted option | No | Yes | Yes | Yes | Yes |

#### At ~$500/month Budget

| Feature | WorkOS ($500) | Keycloak (self-host) | SuperTokens | Ory | Authentik |
|---------|--------------|---------------------|-------------|-----|-----------|
| MAU capacity | 1M | Unlimited | ~25K cloud / Unlimited SH | ~3K aDAU cloud | Unlimited |
| SSO connections | 4 | Unlimited | Enterprise (contact) | Enterprise License | Unlimited (OSS) |
| SCIM connections | 0 ($125 ea.) | Via extension | Enterprise | Enterprise License | Unlimited (OSS) |
| Audit Logs | ~5 orgs | Built-in | Basic | Built-in | Built-in |
| Custom Domain | No ($99 extra) | Yes (self-config) | Yes (self-config) | Yes | Yes (self-config) |

#### At ~$2,500/month Budget

| Feature | WorkOS ($2.5K) | Keycloak | SuperTokens Cloud | Ory Growth | Authentik Enterprise |
|---------|---------------|----------|-------------------|------------|---------------------|
| MAU capacity | 1M+ | Unlimited | ~125K | ~20K aDAU | ~500 internal users |
| SSO connections | ~16-20 | Unlimited | Enterprise | Enterprise | Unlimited |
| Support | Standard | Community/3rd-party | Enterprise | Email | Ticket-based |
| Infrastructure mgmt | None (SaaS) | Your responsibility | None (SaaS) | None (SaaS) | Your responsibility |

---

## 8. Break-Even Analysis

### When Does Self-Hosting Become Cheaper Than WorkOS?

**Scenario A: No SSO/SCIM needed (pure user management)**

WorkOS is free up to 1M MAU. Self-hosting is **never** cheaper than WorkOS for pure user management at any scale below 1M MAU. Above 1M MAU, WorkOS charges $2,500/mo per 1M block.

- SuperTokens self-hosted break-even vs. WorkOS: **At 1M+ MAU** (WorkOS starts charging $2,500/mo; SuperTokens SH costs ~$530/mo at 100K MAU scale)
- Keycloak break-even vs. WorkOS: **Never** (at $0 WorkOS, Keycloak's operational costs always exceed)

**Scenario B: With SSO connections (the realistic B2B scenario)**

This is where the math changes dramatically. WorkOS charges per SSO/SCIM connection:

| # SSO Connections | WorkOS Monthly Cost | SuperTokens SH | Keycloak SH | Ory SH | Authentik OSS |
|-------------------|--------------------:|---------------:|------------:|-------:|--------------:|
| 1 | $125 | $260 | $1,150 | $350 | $370 |
| 3 | $375 | $260 | $1,150 | $350 | $370 |
| 5 | $625 | $260 | $1,150 | $350 | $370 |
| 10 | $1,250 | $260 | $1,150 | $350 | $370 |
| 20 | $2,250 | $260 | $1,150 | $350 | $370 |
| 50 | $4,850 | $260 | $1,150 | $350 | $370 |
| 100 | $7,750 | $260 | $1,150 | $350 | $370 |

**Break-even points (assuming 1K MAU scale):**
- **vs. SuperTokens SH:** WorkOS becomes more expensive at **~3 SSO connections** ($375 vs $260)
- **vs. Ory SH:** WorkOS becomes more expensive at **~3 SSO connections** ($375 vs $350)
- **vs. Authentik OSS:** WorkOS becomes more expensive at **~3 SSO connections** ($375 vs $370)
- **vs. Keycloak SH:** WorkOS becomes more expensive at **~10 SSO connections** ($1,250 vs $1,150)

**Key finding:** If you need more than 3 enterprise SSO connections, self-hosting almost any solution is cheaper than WorkOS. The savings compound rapidly -- at 50 connections, WorkOS costs $4,850/mo while SuperTokens self-hosted costs $260/mo (18.7x cheaper).

**Scenario C: Combined (MAU + SSO at scale)**

At 10K MAU with 20 SSO connections:

| Solution | Monthly Cost |
|----------|------------:|
| WorkOS | $2,250 |
| SuperTokens SH | $350 |
| Ory SH | $435 |
| Authentik OSS | $465 |
| Keycloak SH | $1,400 |

Self-hosting saves $1,800-$1,900/mo (~$22K/year) compared to WorkOS at this scale.

---

## 9. Recommendations

### By Company Stage

| Stage | Recommendation | Rationale |
|-------|---------------|-----------|
| **Pre-revenue / MVP** | WorkOS Free Tier | Zero cost, zero ops, focus on product |
| **Early revenue, <5 enterprise customers** | WorkOS Free Tier | SSO cost ($625/mo for 5) manageable, no ops overhead |
| **Growth, 5-20 enterprise customers** | Migrate to self-hosted | WorkOS SSO costs ($625-$2,250/mo) exceed self-hosting TCO |
| **Scale, 20+ enterprise customers** | Self-hosted (SuperTokens or Keycloak) | Savings of $2,000-$5,000+/mo justify DevOps investment |

### By Technical Capability

| DevOps Maturity | Best Self-Hosted Option | Why |
|-----------------|------------------------|-----|
| **No DevOps team** | WorkOS or SuperTokens Cloud | SaaS, no infrastructure to manage |
| **Basic Docker/K8s** | SuperTokens or Authentik | Lightweight, easy to deploy, good docs |
| **Strong DevOps** | Keycloak or Ory | Full control, maximum features, but need expertise |
| **Enterprise IT team** | Keycloak + Red Hat support | Enterprise-grade support, compliance, training |

### Risk-Adjusted Recommendation

For this project specifically (client onboarding tool, internal operations team):

1. **Short-term:** Use WorkOS AuthKit free tier. Zero cost, immediate productivity, excellent DX.
2. **If SSO becomes needed:** Evaluate SuperTokens self-hosted or Authentik OSS as the migration target. Both offer Apache 2.0/MIT licensing, low infrastructure requirements, and SSO without per-connection fees.
3. **Avoid Keycloak unless** you have a dedicated DevOps resource and need its extensive protocol support (SAML, OIDC, LDAP, Kerberos all built-in).

---

## Appendix: Data Sources

- [WorkOS Pricing](https://workos.com/pricing)
- [SuperTokens Pricing](https://supertokens.com/pricing)
- [Ory Pricing](https://www.ory.com/pricing)
- [Authentik Pricing](https://goauthentik.io/pricing/)
- [Keycloak Self-Hosted Cost Analysis (SkyCloak)](https://skycloak.io/blog/what-is-the-cost-of-self-hosting-keycloak/)
- [Keycloak Pricing Guide 2025 (Inteca)](https://inteca.com/business-insights/keycloak-pricing-guide-2025-cost-estimation-for-hosting-open-source-identity-and-access-management/)
- [Keycloak CNCF Status](https://www.cncf.io/projects/keycloak/)
- [Ory Series A Funding ($22.5M)](https://www.ory.sh/blog/ory-series-a-funding-update)
- [Ory Acquires BoxyHQ](https://www.ory.com/blog/introducing-ory-polis-for-enterprise-single-sign-on)
- [SuperTokens on Y Combinator](https://www.ycombinator.com/companies/supertokens)
- [Authentik Enterprise Updates (Feb 2025)](https://goauthentik.io/blog/2025-02-04-open-source-rac-and-pricing-support-updates/)
- [Keycloak CPU/Memory Sizing](https://www.keycloak.org/high-availability/concepts-memory-and-cpu-sizing)
- [SuperTokens Scalability Docs](https://supertokens.com/docs/deployment/scalability)
- [Open Source License Change Patterns](https://www.softwareseni.com/the-open-source-license-change-pattern-mongodb-to-redis-timeline-2018-to-2026-and-what-comes-next/)
