# Open-Source Auth Solutions: Developer Experience & UI/UX Evaluation

**Date:** 2026-02-08
**Analyst:** DX/UI-UX Analyst
**Scope:** Developer experience, SDK quality, documentation, pre-built UI, community health, and friction points for 5 open-source auth alternatives to WorkOS AuthKit.

---

## Executive Summary

| Criterion | Keycloak | SuperTokens | Ory (Kratos/Hydra) | Authentik | BoxyHQ / Ory Polis |
|---|---|---|---|---|---|
| **Time-to-First-Auth** | ~30 min | ~15 min | ~45-60 min | ~30-45 min | ~20 min |
| **SDK Breadth** | Medium | High | High (auto-gen) | Low-Medium | Low (JS-only) |
| **SDK Quality** | Mixed (community) | High (official) | Medium (auto-gen) | Medium (auto-gen) | High (focused) |
| **Pre-built UI** | Full (themed) | Full (React) | Headless + Elements | Full (web components) | Admin Portal only |
| **Docs Quality** | Good but sprawling | Excellent | Good but fragmented | Good | Good but narrow |
| **Community Size** | Largest (30k stars) | Growing (14.8k) | Large (13.1k Kratos) | Strong (19.5k) | Moderate (~3.5k) |
| **Setup Complexity** | Medium-High | Low | High | Medium | Low-Medium |
| **DX Rating** | B- | A | B- | B | B+ (for SSO scope) |

---

## 1. Keycloak

### SDK & Language Support

| Language | Package | Status | Quality |
|---|---|---|---|
| JavaScript | `keycloak-js` (official) | Active, v26.2+ (Feb 2025) | Good - official, well-maintained |
| Java | Built-in (Admin Client) | Official, core | Excellent - native ecosystem |
| Python | `python-keycloak` (community) | Active, v7.0.3 (Jan 2026) | Good - tracks latest KC versions |
| Go | `gocloak` (community) | Community-maintained | Adequate - not official |
| .NET | `Keycloak.AuthServices` (community) | Community-maintained | Adequate |
| PHP | Various community libs | Community-maintained | Mixed quality |

**Key observations:**
- Official SDKs are limited to JavaScript and Java. All other languages rely on community-maintained libraries.
- The `keycloak-js` adapter is well-maintained and tracks releases closely.
- `python-keycloak` is the standout community SDK, supporting the latest 5 major Keycloak versions.
- No official React/Vue/Angular-specific SDKs; the JS adapter works generically.

### API & Documentation

- **API Design:** REST API with OpenAPI spec. Admin REST API is comprehensive but complex.
- **Documentation Quality:** Extensive but can feel scattered due to breadth. The official docs cover every feature but navigation can be overwhelming for newcomers.
- **Getting-Started Guide:** Docker-based quickstart gets a server running in ~5 minutes. First secured app takes ~30 minutes.
- **Time-to-First-Auth:** ~30 minutes (Docker start + realm + client + first login)
- **API Reference:** Complete but dense. Admin REST API docs are auto-generated from OpenAPI spec.

### Pre-built UI Components

- **Login/Signup Pages:** Full pre-built login themes using FreeMarker templates (server-side rendered). New React-based UI packages available since late 2024.
- **Admin Console:** Comprehensive React-based admin console (`@keycloak/keycloak-admin-ui`). Full CRUD for realms, clients, users, roles, groups, identity providers.
- **Account Console:** Self-service account management UI (`@keycloak/keycloak-account-ui`).
- **Customization:** Multiple approaches:
  - CSS-only theme overrides (quickest)
  - FreeMarker template overrides (traditional)
  - React component packages (modern, via `npm create keycloak-theme`)
  - Keycloakify - third-party tool for building themes as React apps
- **Design System:** PatternFly (Red Hat's design system). Consistent but enterprise-y.

### Community & Ecosystem

- **GitHub Stars:** 30,000+ (celebrated milestone in Oct 2025)
- **Commit Activity:** Very active, frequent releases (26.x series in 2025)
- **Community Channels:** GitHub Discussions, CNCF Slack (#keycloak, #keycloak-dev)
- **Stack Overflow:** Large presence, thousands of questions
- **Extensions Ecosystem:** Rich ecosystem of SPIs (Service Provider Interfaces), community extensions page on keycloak.org
- **Enterprise Backing:** Red Hat (Red Hat Build of Keycloak for RHEL customers)
- **Migration Tools:** Built-in user federation (LDAP/AD), user import/export, third-party migration scripts available

### Developer Friction Points

- **Upgrade Pain:** Frequent breaking changes, even in minor/patch releases. Issue #44035 highlights community frustration with breaking changes in patch releases (e.g., v26.4.3 changed HTTP response behavior).
- **Configuration Complexity:** Extensive configuration surface. Realms, clients, protocols, mappers, flows, policies -- the learning curve is steep.
- **Java-Centric:** Custom providers (SPIs) must be written in Java. Non-Java teams face friction for deep customization.
- **Resource Hungry:** JVM-based, requires significant memory (~512MB-1GB minimum for production). Docker images are large.
- **Theme Customization:** FreeMarker templates are an older approach; the newer React packages are still maturing.
- **Documentation Navigation:** Hard to find specific answers quickly due to documentation sprawl.

---

## 2. SuperTokens

### SDK & Language Support

| Language | Package | Status | Quality |
|---|---|---|---|
| JavaScript/TypeScript | `supertokens-node` | Official, active | Excellent |
| Python | `supertokens-python` | Official, active | Excellent |
| Go | `supertokens-golang` | Official, active | Excellent |
| React | `supertokens-auth-react` | Official, active | Excellent |
| React Native | `supertokens-react-native` | Official, active | Good |
| Flutter | `supertokens-flutter` | Official, active | Good |
| iOS | `supertokens-ios` | Official, active | Good |
| Android | `supertokens-android` | Official, active | Good |

**Key observations:**
- All SDKs are officially maintained by the SuperTokens team.
- Backend coverage: Node.js, Python, Go (the three most common web backend languages).
- Frontend: React SDK with pre-built UI, plus vanilla JS SDK. Mobile SDKs for React Native, Flutter, iOS, Android.
- Framework-specific guides: Next.js (App Router + Pages Router), Remix, Express, Flask, Django, FastAPI, Gin, Chi.
- TypeScript-first in the Node.js SDK with full type definitions.

### API & Documentation

- **API Design:** REST APIs with recipe-based architecture. Each auth method (email/password, social, passwordless, etc.) is a "recipe" that can be composed.
- **Documentation Quality:** Excellent. Recently rebuilt from the ground up with improved structure and consistency. Step-by-step guides with code snippets for each supported framework.
- **Getting-Started Guide:** 15-minute quickstart. Clear, linear progression from install to working auth.
- **Time-to-First-Auth:** ~15 minutes (fastest of the 5 evaluated solutions)
- **API Reference:** Complete SDK references for all backend and frontend SDKs. Searchable and well-indexed.

### Pre-built UI Components

- **Login/Signup Pages:** Full pre-built React UI (`supertokens-auth-react`). Renders login, signup, password reset, email verification, MFA flows out-of-the-box.
- **Admin Dashboard:** Built-in dashboard for user management accessible at `/auth/dashboard`. Shows user list, session management, role management.
- **Customization:**
  - CSS overrides via `data-supertokens` attributes
  - Component overrides using React context providers (`AuthRecipeComponentsOverrideContextProvider`)
  - Full "Custom UI" path for building from scratch using headless APIs
- **Theming:** CSS-based theming with access to all component class names. Not a design system per se, but flexible CSS customization.

### Community & Ecosystem

- **GitHub Stars:** ~14,800 (supertokens-core)
- **Commit Activity:** Regular releases, active development
- **Community Channels:** Discord (responsive - team claims 15-minute response time), email support
- **Stack Overflow:** Growing presence, smaller than Keycloak
- **Contributor Program:** "SuperContributor" program with swag and recognition
- **Third-party Integrations:** Auth.js/NextAuth provider, Hasura, Supabase examples
- **Migration Tools:** Migration guides from Auth0, Firebase Auth, and others available

### Developer Friction Points

- **Java Core:** The core service is written in Java, which can be a surprise given the developer-friendly JS/Python/Go SDKs. This affects self-hosting (JVM memory requirements).
- **Recipe Model Learning Curve:** The "recipe" abstraction takes a moment to understand, especially for composing multiple auth methods.
- **Pre-built UI is React-only:** If you use Vue, Svelte, or Angular, you must build custom UI (the headless API approach).
- **Smaller Community:** Fewer community answers on Stack Overflow compared to Keycloak. More dependent on official Discord support.
- **Enterprise Features Gated:** Some features (like account linking, MFA) have limitations in the free tier or require the paid plan for full functionality.
- **Self-hosting Core:** Running the Java core adds operational complexity vs. pure-library approaches.

---

## 3. Ory (Kratos / Hydra)

### SDK & Language Support

| Language | Package | Status | Quality |
|---|---|---|---|
| JavaScript/TypeScript | `@ory/client` (unified) | Auto-generated, active | Medium - auto-gen quirks |
| Go | `github.com/ory/client-go` | Auto-generated, active | Medium |
| Python | `ory-kratos-client` / `ory-client` | Auto-generated, active | Medium |
| Java | `ory-client` | Auto-generated | Medium |
| PHP | `ory/client` | Auto-generated | Low-Medium |
| .NET | `Ory.Client` | Auto-generated | Low-Medium |
| Rust | `ory-client` | Auto-generated | Low-Medium |
| Dart | `ory_client` | Auto-generated | Low-Medium |
| Ruby | `ory-client` | Auto-generated | Low-Medium |

**Key observations:**
- Broadest language coverage due to OpenAPI auto-generation, but quality is inconsistent.
- Auto-generated SDKs can break backwards compatibility when openapi-generator upgrades. Ory explicitly warns they "do not make backwards compatibility promises" for generated SDKs.
- Two SDK families: `ory/client` (for Ory Network cloud) and individual `kratos-client-*` / `hydra-client-*` (for self-hosted). This can be confusing.
- Framework-specific: Ory Elements (React component library), reference implementations for Node.js/Express/Next.js.

### API & Documentation

- **API Design:** Clean REST APIs with OpenAPI specs. Each service (Kratos, Hydra, Oathkeeper, Keto) has its own API surface. API-first philosophy.
- **Documentation Quality:** Good technical depth but fragmented across multiple services. Developers must piece together docs for Kratos + Hydra + Oathkeeper + Keto to understand the full picture.
- **Getting-Started Guide:** More complex due to multi-service architecture. Requires understanding which services you need before starting.
- **Time-to-First-Auth:** ~45-60 minutes for self-hosted (multiple services to configure). Faster with Ory Network (managed cloud).
- **API Reference:** Auto-generated from OpenAPI specs. Accurate but can feel dry/mechanical.

### Pre-built UI Components

- **Login/Signup Pages:** Headless by design - no built-in UI. You bring your own UI.
  - **Ory Elements:** Official React component library for building auth pages. Modular and customizable.
  - **Reference implementations:** `kratos-selfservice-ui-node` (Express/Handlebars), `kratos-selfservice-ui-react-nextjs` (Next.js)
- **Admin Console:** No built-in admin UI for self-hosted. Ory Network (cloud) provides a management console.
- **Customization:** Complete freedom since you build the UI yourself. Ory Elements provides styled components that can be customized.

### Community & Ecosystem

- **GitHub Stars:** ~13,100 (Kratos), ~15,600 (Hydra), plus other services
- **Commit Activity:** Active, regular releases
- **Community Channels:** Ory Community (forum), GitHub Discussions, Slack
- **Stack Overflow:** Moderate presence
- **Ecosystem:** Ory acquired BoxyHQ (Polis for SSO). Integrations with various identity providers.
- **Migration Tools:** Limited. Community-contributed scripts exist.

### Developer Friction Points

- **Multi-Service Complexity:** Running Kratos + Hydra + Oathkeeper + Keto is operationally complex. You need to understand which services to use and how they interact.
- **Bring Your Own UI:** No default UI means more work upfront. Even with Ory Elements, you need to build and host your own login pages.
- **Documentation Fragmentation:** Information spread across multiple services' docs. Common complaint: "poor documentation", "cannot find complete references of all parameters for kratos.yml."
- **HTTP Status Code Issues:** Developers reported Kratos returns HTTP 400 for valid and successful requests, causing unnecessary debugging time.
- **Auto-generated SDK Instability:** Breaking changes between SDK versions without clear migration paths.
- **Ory Network vs Self-Hosted Divergence:** Features and DX differ significantly between cloud and self-hosted. Some features are cloud-only.
- **Customization via Webhooks Only:** Ory Actions (webhooks) are the primary extensibility mechanism, which can require a separate service for custom logic.

---

## 4. Authentik

### SDK & Language Support

| Language | Package | Status | Quality |
|---|---|---|---|
| JavaScript/TypeScript | `@goauthentik/api` | Auto-generated, active | Medium |
| Python | authentik API client | Auto-generated | Medium |
| Go | authentik API client | Auto-generated | Medium |

**Key observations:**
- SDKs are auto-generated from OpenAPI spec. Limited to Go, TypeScript, and Python.
- The API clients are primarily for managing Authentik configuration (CRUD operations on providers, applications, policies) -- NOT for implementing SSO in your app.
- For actual SSO integration, developers use standard SAML/OAuth2/OIDC libraries in their framework of choice (e.g., `next-auth`, `passport.js`, `django-allauth`).
- Community-maintained `sdk-integrations` repo provides examples for various languages and frameworks.

### API & Documentation

- **API Design:** REST API with OpenAPI v3 spec. Built-in API browser at `/api/v3/`. Every Authentik instance auto-generates its API docs.
- **Documentation Quality:** Good and improving. Clean documentation site with installation, configuration, and integration guides.
- **Getting-Started Guide:** Docker Compose setup. More complex than some alternatives (requires PostgreSQL, used to require Redis -- removed in 2025.10).
- **Time-to-First-Auth:** ~30-45 minutes (Docker Compose setup + initial flow configuration)
- **API Reference:** Auto-generated, available at every running instance. Complete but complex.

### Pre-built UI Components

- **Login/Signup Pages:** Full pre-built login flows using web components (Lit framework). Authentik's "flows" system allows drag-and-drop construction of login journeys.
- **Admin Console:** Comprehensive admin interface built with web components. Manages users, groups, applications, providers, policies, flows.
- **User Portal:** Self-service user dashboard showing available applications (app launcher style).
- **Customization:**
  - Brand settings (logo, favicon, title) per-brand (multi-tenant branding)
  - Custom CSS support (added in 2025.4.0+)
  - Theme settings (light/dark mode) per brand
  - Flow designer for custom auth journeys
  - Web component architecture allows targeted styling

### Community & Ecosystem

- **GitHub Stars:** ~19,500-20,000
- **Commit Activity:** Very active, regular bi-monthly releases (2025.2, 2025.4, 2025.6, 2025.8, 2025.10, 2025.12)
- **Community Channels:** Discord, GitHub Discussions
- **Stack Overflow:** Growing presence
- **Integrations:** Extensive integration documentation for popular services (Nextcloud, Grafana, GitLab, Portainer, etc.)
- **Migration Tools:** Import/export capabilities, LDAP integration

### Developer Friction Points

- **Not a Developer SDK:** Authentik is an identity provider, not an auth library. You integrate with it using standard protocols (SAML, OIDC), not an SDK. Developers expecting a "drop-in" auth library will be disappointed.
- **Flow Complexity:** The "flows" and "stages" abstraction is powerful but has a learning curve. Building custom auth journeys requires understanding the flow model.
- **Upgrade Issues:** Documented cases of upgrades breaking instances (e.g., 2025.2.4 to 2025.4 caused startup failures). System task flooding issues in 2025.10.0.
- **Python-Based:** Written in Python/Django, which affects performance at scale compared to Go/Rust alternatives.
- **Operational Overhead:** Requires PostgreSQL, background worker process. More infrastructure than library-based approaches.
- **Security Vulnerability:** CVE-2025-64521 - deactivated service accounts could still authenticate via OAuth. Fixed in 2025.8.5/2025.10.2.

---

## 5. BoxyHQ / Ory Polis (SAML Jackson)

### SDK & Language Support

| Language | Package | Status | Quality |
|---|---|---|---|
| JavaScript/TypeScript | `@boxyhq/saml-jackson` (NPM) | Active, v1.52.2 | High |
| Auth.js/NextAuth | BoxyHQ SAML provider | Official integration | High |

**Key observations:**
- JavaScript/TypeScript only for the core SDK. Designed for the Node.js ecosystem.
- Can be embedded as an NPM library (`@boxyhq/saml-jackson`) or deployed as a standalone Next.js service.
- First-class integration with Auth.js (NextAuth) -- just add the BoxyHQ SAML provider.
- For non-JS backends, must be deployed as a standalone service and integrated via its REST API (OAuth 2.0 flow).
- Multi-framework examples: Next.js, React, Remix, Laravel, Ruby on Rails.
- Now part of Ory ecosystem (acquired as "Ory Polis"), expanding integration options.

### API & Documentation

- **API Design:** OAuth 2.0 flow abstraction over SAML/OIDC. Clean REST API. The core insight is brilliant: present enterprise SSO as a standard OAuth 2.0 flow.
- **Documentation Quality:** Good, focused documentation. Clear README, step-by-step guides for each framework. Narrower scope makes docs more navigable.
- **Getting-Started Guide:** Quick to get started, especially as NPM library. Service quickstart available.
- **Time-to-First-Auth:** ~20 minutes (embed as library) or ~30 minutes (standalone service)
- **API Reference:** Adequate. Focused on SSO connection management and the OAuth flow.

### Pre-built UI Components

- **Login/Signup Pages:** No pre-built login UI. It handles the SAML/OIDC protocol layer, not the user-facing login page. Your app provides the login UI.
- **Admin Portal:** Available when deployed as standalone service. Includes:
  - SSO connection management (create, configure, test SAML/OIDC connections)
  - SAML Tracer for debugging failed SSO attempts
  - Directory Sync (SCIM) management
- **User Dashboard:** Not applicable (SSO infrastructure, not user-facing).
- **Customization:** Admin portal has limited customization. The focus is on infrastructure, not end-user UI.

### Community & Ecosystem

- **GitHub Stars:** ~3,500 (as boxyhq/jackson, now ory/polis)
- **Commit Activity:** Regular development, now under Ory stewardship
- **Community Channels:** Part of broader Ory community (50,000+ members), GitHub Discussions
- **Stack Overflow:** Small presence
- **Ecosystem:** Auth.js provider, SaaS Starter Kit (Next.js boilerplate with SSO built in), Ory Network integration
- **Migration Tools:** N/A (SSO infrastructure layer)

### Developer Friction Points

- **Narrow Scope:** SSO-only. Does not handle user management, session management, password auth, social login, MFA, or other auth concerns. Must be paired with another solution for full auth.
- **JS-Centric:** NPM library only works in Node.js. Other languages must use it as a standalone service.
- **Transition Uncertainty:** Acquired by Ory and rebranded as "Ory Polis." Package names, docs, and community may be in flux during transition.
- **Admin Portal Only with Service Deploy:** If you embed as NPM library, you lose the Admin Portal and must manage SSO connections via API.
- **Limited Standalone Features:** No built-in user database, no session management, no login UI. Requires pairing with other tools.

---

## Comparative Analysis

### SDK Coverage Matrix

| Language | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---|---|---|---|---|---|
| JavaScript/TS | Official | Official | Auto-gen | Auto-gen | Official |
| Python | Community | Official | Auto-gen | Auto-gen | -- |
| Go | Community | Official | Auto-gen | Auto-gen | -- |
| Java | Official | -- | Auto-gen | -- | -- |
| PHP | Community | -- | Auto-gen | -- | -- |
| .NET | Community | -- | Auto-gen | -- | -- |
| Ruby | -- | -- | Auto-gen | -- | -- |
| Rust | -- | -- | Auto-gen | -- | -- |
| Mobile (iOS/Android) | -- | Official | -- | -- | -- |
| React Native | -- | Official | -- | -- | -- |
| Flutter | -- | Official | -- | -- | -- |

### Pre-built UI Comparison

| Component | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---|---|---|---|---|---|
| Login/Signup UI | FreeMarker + React | React pre-built | Headless + Elements | Web components | None |
| Admin Console | Full React app | Basic dashboard | None (self-hosted) | Full web app | SSO management |
| User Self-Service | Account Console | Via dashboard | DIY | User portal | None |
| Theme Engine | FreeMarker/CSS/React | CSS + React overrides | Full custom | CSS + Brands | Limited |
| Mobile UI | Via keycloak-js | Native SDKs | DIY | Responsive web | N/A |
| Embeddable | Via JS adapter | React components | Ory Elements | Redirect-based | N/A |

### Documentation Quality Scorecard

| Aspect | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---|---|---|---|---|---|
| Getting Started | B | A+ | B- | B | A- |
| API Reference | B+ | A | B+ | B+ | B |
| Framework Guides | B- | A+ | B | B- | A (for JS) |
| Troubleshooting | B | A | C+ | B- | B |
| Search/Navigation | C+ | A | B- | B | B+ |
| Code Examples | B | A | B- | B- | A- |
| **Overall** | **B** | **A** | **B-** | **B** | **B+** |

### Community Health Metrics

| Metric | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---|---|---|---|---|---|
| GitHub Stars | 30,000+ | ~14,800 | ~13,100 | ~19,500 | ~3,500 |
| Star Growth Trend | Accelerating | Steady | Steady | Strong | Moderate |
| Release Cadence | Monthly | Regular | Regular | Bi-monthly | Regular |
| Issue Response | Moderate | Fast (15 min Discord) | Moderate | Active | Part of Ory |
| Enterprise Backing | Red Hat | SuperTokens Inc. | Ory Corp | Authentik Security | Ory Corp |
| SO Questions | 10,000+ | ~500 | ~1,000 | ~300 | <100 |

### Developer Friction Severity

| Friction Point | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---|---|---|---|---|---|
| Setup Complexity | HIGH | LOW | HIGH | MEDIUM | LOW |
| Learning Curve | HIGH | LOW-MED | HIGH | MEDIUM | LOW (narrow scope) |
| Upgrade Pain | HIGH | LOW | MEDIUM | MEDIUM-HIGH | LOW |
| Customization Effort | MEDIUM | LOW (React) | HIGH (DIY UI) | MEDIUM | N/A |
| Operational Overhead | HIGH (JVM) | MEDIUM (Java core) | HIGH (multi-svc) | MEDIUM | LOW |
| SDK Stability | MEDIUM | HIGH | LOW (auto-gen) | MEDIUM | HIGH |
| Debug Experience | MEDIUM | GOOD | POOR | MEDIUM | GOOD |

---

## Key Findings & Recommendations

### Best Developer Experience: SuperTokens
SuperTokens delivers the smoothest developer experience with official SDKs for all major backend languages (Node, Python, Go), pre-built React UI, 15-minute quickstart, and recently rebuilt documentation. The recipe-based architecture is intuitive once understood. Main downside: React-only pre-built UI and Java-based core service.

### Best Pre-built UI: Keycloak
Keycloak offers the most complete pre-built UI ecosystem with full admin console, account management, and login theming. The new React-based UI packages and Keycloakify tool make modern customization possible. However, the legacy FreeMarker approach and PatternFly design system can feel dated.

### Best for API-First / Headless: Ory
Ory's headless architecture gives complete UI freedom, ideal for teams that want pixel-perfect custom UIs. The trade-off is significant: you must build all user-facing UI yourself. Ory Elements helps but is not a complete solution.

### Best Admin Experience: Authentik
Authentik's flow-based admin UI and branding system is the most polished for admin users. The drag-and-drop flow designer is unique and powerful. Custom CSS support (added 2025.4) improves theming flexibility. Downsides: not an SDK-first approach, and upgrade reliability concerns.

### Best for Enterprise SSO Specifically: BoxyHQ / Ory Polis
If the primary need is enterprise SSO (SAML/OIDC), BoxyHQ/Polis is the most focused and elegant solution. The OAuth 2.0 abstraction over SAML is brilliant DX. But it only covers SSO -- you need a separate solution for everything else.

### Overall DX Ranking

1. **SuperTokens** - Best overall DX for app developers. Fastest time-to-auth, best docs, official SDKs.
2. **BoxyHQ / Ory Polis** - Best DX for enterprise SSO specifically. Clean API, easy embed. Limited scope.
3. **Authentik** - Best admin UX. Good for ops teams managing identity. Not SDK-first for developers.
4. **Keycloak** - Most complete feature set with decent UI. Steep learning curve, upgrade pain.
5. **Ory** - Most flexible architecture. Highest DX friction due to complexity and DIY UI requirement.

---

## Appendix: Source Links

- [Keycloak GitHub](https://github.com/keycloak/keycloak) | [Docs](https://www.keycloak.org/documentation) | [UI Customization](https://www.keycloak.org/ui-customization/themes)
- [SuperTokens GitHub](https://github.com/supertokens/supertokens-core) | [Docs](https://supertokens.com/docs) | [SDK Reference](https://supertokens.com/docs/community/sdks)
- [Ory Kratos GitHub](https://github.com/ory/kratos) | [Docs](https://www.ory.com/docs/kratos/sdk/overview) | [Ory Elements](https://www.ory.sh/docs/kratos/bring-your-own-ui/custom-ui-ory-elements)
- [Authentik GitHub](https://github.com/goauthentik/authentik) | [Docs](https://docs.goauthentik.io/) | [API](https://api.goauthentik.io/)
- [BoxyHQ/Polis GitHub](https://github.com/boxyhq/jackson) | [Docs](https://boxyhq.com/guides/jackson) | [NPM](https://www.npmjs.com/package/@boxyhq/saml-jackson)
- [Ory vs Keycloak vs SuperTokens Comparison](https://supertokens.com/blog/ory-vs-keycloak-vs-supertokens)
- [Open Source Auth Providers 2025 (Tesseral)](https://tesseral.com/guides/open-source-auth-providers-in-2025-best-solutions-for-open-source-auth)
- [State of Open-Source Identity 2025](https://www.houseoffoss.com/post/the-state-of-open-source-identity-in-2025-authentik-vs-authelia-vs-keycloak-vs-zitadel)
