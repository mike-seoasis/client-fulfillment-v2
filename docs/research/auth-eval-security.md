# Security & Compliance Analysis: Open-Source Authentication Solutions

**Analyst:** Security & Compliance Team
**Date:** 2026-02-08
**Scope:** Keycloak, SuperTokens, Ory (Kratos/Hydra), Authentik, BoxyHQ (SAML Jackson / Ory Polis)

---

## Executive Summary

This report provides a critical security assessment of five open-source authentication solutions being evaluated as alternatives to WorkOS AuthKit. The analysis covers vulnerability history, authentication/authorization features, security infrastructure, compliance posture, and supply chain risk.

**Key Findings:**
- **Keycloak** has the largest attack surface and most CVEs (100+), but also the most mature security response process backed by Red Hat.
- **SuperTokens** has the cleanest CVE record and strongest session security, but is the youngest and least battle-tested at enterprise scale.
- **Ory** is the only solution with SOC 2 Type 2 + ISO 27001 certifications for its managed service, making it the strongest compliance story.
- **Authentik** has had multiple critical CVEs (CVSS 9.0+) in 2024 alone, which is concerning for a relatively young project.
- **BoxyHQ/Ory Polis** is now part of Ory; it is narrowly scoped (SSO bridge only) so its security surface is smaller but it cannot stand alone.

---

## 1. Vulnerability History

### CVE Summary Table

| Solution | Total Known CVEs | Critical (9.0+) | High (7.0-8.9) | Medium (4.0-6.9) | Low (0-3.9) | Avg Response Time | Security Advisory Process |
|----------|-----------------|-----------------|-----------------|-------------------|-------------|-------------------|--------------------------|
| **Keycloak** | 100+ (all-time) | ~5-8 | ~25-30 | ~50+ | ~15+ | Days to weeks (Red Hat coordinated) | Red Hat Security Advisories, GitHub Security Advisories |
| **SuperTokens** | 0 known public CVEs | 0 | 0 | 0 | 0 | N/A | GitHub Security tab, responsible disclosure |
| **Ory (Kratos/Hydra)** | ~5-10 (all-time) | 0 known | 1-2 | 3-5 | 1-2 | Days (via GitHub) | GitHub Security Advisories, security@ory.sh |
| **Authentik** | ~10-15 (since 2023) | 2 (CVE-2024-47070: 9.0, CVE-2024-52289: 9.8) | 2-3 | 5-7 | 2-3 | Days to weeks | GitHub Security Advisories, docs.goauthentik.io/security |
| **BoxyHQ/Ory Polis** | 1 known (AIKIDO-2025-10105, medium) | 0 | 0 | 1 | 0 | Unknown | GitHub-based, now Ory's process |

### Notable Vulnerabilities by Solution

#### Keycloak
| CVE | Year | Severity | Description |
|-----|------|----------|-------------|
| CVE-2025-7784 | 2025 | High | Privilege escalation when FGAPv2 enabled; user can edit own role to gain realm-admin |
| CVE-2025-13467 | 2025 | High | LDAP User Federation allows admin-triggered untrusted Java deserialization |
| CVE-2025-12390 | 2025 | High | Session takeover due to reuse of session identifiers |
| CVE-2025-11419 | 2025 | Medium | TLS Client-Initiated Renegotiation DoS |
| CVE-2025-2559 | 2025 | Medium | DoS via JWT token cache OOM |
| CVE-2024-3656 | 2024 | High | Broken access control - low-privilege users access admin API |
| CVE-2024-1249 | 2024 | Medium | Cross-origin message validation DDoS |

**Assessment:** Keycloak's high CVE count is partly a function of its maturity, wide deployment, and large attack surface. Red Hat's structured security response is a significant positive. However, the volume and recurring patterns (privilege escalation, session management flaws) indicate systemic complexity risks.

#### SuperTokens
No public CVEs assigned. Snyk vulnerability database shows no direct vulnerabilities for core packages (supertokens-website, supertokens-python, supertokens-node).

**Assessment:** The absence of CVEs could indicate strong security practices, but it could also reflect lower scrutiny due to smaller market share and fewer security researchers targeting it. This is a double-edged sword -- less battle-tested means less proven.

#### Ory (Kratos/Hydra)
| CVE | Year | Severity | Description |
|-----|------|----------|-------------|
| CVE-2025-27144 | 2025 | Medium | go-jose dependency vulnerability (patched via backport) |
| Historical | Pre-2024 | Medium | Reflected XSS in Hydra error_hint parameter |

**Assessment:** Ory's Go-based architecture and API-first design limits attack surface. The composable architecture means each component (Kratos, Hydra, Keto) has a smaller surface area than monolithic solutions. The dependency on go-jose is a notable supply chain consideration.

#### Authentik
| CVE | Year | Severity | Description |
|-----|------|----------|-------------|
| CVE-2024-52289 | 2024 | **Critical (9.8)** | Details limited but critical severity rating |
| CVE-2024-47070 | 2024 | **Critical (9.0)** | Password authentication bypass via X-Forwarded-For header spoofing |
| CVE-2024-37905 | 2024 | High | Privilege escalation via token user ID manipulation |
| CVE-2024-52307 | 2024 | High | Metrics endpoint key brute-force via timing attack |
| CVE-2024-11623 | 2024 | Medium | Stored XSS via SVG upload |
| CVE-2024-21637 | 2024 | Medium | Reflected XSS via JavaScript URIs in OIDC flows |

**Assessment:** **RED FLAG.** Two critical-severity CVEs in a single year is alarming for any auth provider. CVE-2024-47070 (password bypass via X-Forwarded-For) reveals a fundamental architectural weakness in how Authentik handles proxy headers in its default authentication flow. CVE-2024-52289 at 9.8 CVSS is near-maximum severity. The frequency and severity of 2024 vulnerabilities raise questions about Authentik's security review processes.

#### BoxyHQ / Ory Polis
| ID | Year | Severity | Description |
|----|------|----------|-------------|
| AIKIDO-2025-10105 | 2025 | Medium | Vulnerability in @boxyhq/saml-jackson (details limited) |

**Assessment:** Narrow scope (SAML/OIDC bridge + SCIM) means smaller attack surface. Now under Ory's security umbrella, which is a net positive. Cannot be evaluated as a standalone auth solution.

---

## 2. Authentication Features

### MFA Methods Comparison

| Feature | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|--------------|-----------|--------------|
| TOTP | Yes | Yes | Yes | Yes | No (SSO only) |
| WebAuthn/FIDO2 | Yes | Yes | Yes | Yes | No |
| Passkeys | Yes (v26+) | Yes | Yes | Yes | No |
| SMS OTP | No (plugin) | Yes | Yes | Yes (fallback) |No |
| Email OTP | Yes | Yes | Yes | Yes | No |
| Push Notification | No | No | No | Yes (Duo) | No |
| Hardware Keys | Yes | Yes (YubiKey) | Yes | Yes | No |
| Backup/Recovery Codes | Yes | No | Yes | No | No |
| Adaptive/Conditional MFA | Yes (auth flows) | Yes (role-based) | Yes (config) | Yes (policy) | No |

### Passwordless Options

| Feature | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|--------------|-----------|--------------|
| Magic Links | Yes | Yes | Yes | Yes | No |
| WebAuthn Passwordless | Yes | Yes | Yes | Yes | No |
| Passkey-only Login | Yes | Yes | Yes | Yes | No |

### Social Login & SSO

| Feature | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|--------------|-----------|--------------|
| Social Login Providers | 20+ | 10+ | 15+ | 10+ | N/A |
| SAML 2.0 IdP | Yes | No | No (Polis needed) | Yes | Yes (bridge) |
| OIDC Provider | Yes | No | Yes (Hydra) | Yes | Yes (bridge) |
| LDAP/AD Integration | Yes | No | No | Yes | No |
| Kerberos | Yes | No | No | No | No |

### Brute-Force & Rate Limiting

| Feature | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|--------------|-----------|--------------|
| Built-in Brute-Force Protection | Yes | Yes | Yes (config) | Yes (policies) | No |
| Account Lockout | Yes (configurable) | Yes | Yes | Yes | No |
| Rate Limiting | Yes | Yes | External (API gateway) | Yes | No |
| IP-based Blocking | Yes | No | No | Yes | No |

### Session & Token Management

| Feature | Keycloak | SuperTokens | Ory (Kratos) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|--------------|-----------|--------------|
| JWT Tokens | Yes | Yes | Yes (Hydra) | Yes | Yes |
| Opaque Tokens | Yes | Yes | Yes | Yes | No |
| Rotating Refresh Tokens | Yes | Yes (with theft detection) | Yes | Yes | N/A |
| Token Theft Detection | No | **Yes (unique)** | No | No | No |
| Session Revocation | Yes | Yes | Yes | Yes | N/A |
| Concurrent Session Limits | Yes | Yes | No | Yes | N/A |
| Anti-CSRF Protection | Yes | Yes (VIA_TOKEN + VIA_CUSTOM_HEADER) | Yes | Yes | N/A |

**SuperTokens stands out** with its rotating refresh token + theft detection mechanism, which follows RFC 6819 specifications. When a stolen token is used, the system detects the anomaly and invalidates all sessions for that user.

---

## 3. Authorization & Access Control

| Feature | Keycloak | SuperTokens | Ory (Keto) | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|------------|-----------|--------------|
| RBAC | Yes (native) | Yes (basic) | Yes (Zanzibar) | Yes (policies) | No |
| ABAC | Yes (UMA 2.0) | No | Yes (Zanzibar) | Yes (attribute policies) | No |
| Fine-Grained Permissions | Yes (Authorization Services) | No (needs Cerbos/external) | **Yes (Google Zanzibar)** | Limited | No |
| Multi-Tenancy | Yes (realms) | Yes (native) | Yes (projects) | Yes (tenants) | Yes (connections) |
| Organization-Level ACL | Yes (Organizations feature, v26+) | Yes | Yes | Yes | Yes (per-connection) |
| Policy Engine | Yes (UMA, built-in) | No | **Yes (Ory Permission Language)** | Yes (expression-based) | No |
| Delegation/Impersonation | Yes | No | No | Yes | No |

**Ory Keto** is the standout for authorization, implementing Google's Zanzibar paper -- the same system Google uses internally for YouTube, Drive, Calendar, etc. Sub-10ms P95 latency at scale.

**Keycloak** has the most comprehensive built-in authorization via UMA 2.0 Authorization Services, but it adds significant complexity.

**SuperTokens** is weakest here -- RBAC only, no ABAC or fine-grained permissions without external tools like Cerbos.

---

## 4. Security Infrastructure

### Encryption & Key Management

| Feature | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|-----|-----------|--------------|
| Encryption at Rest | DB-level (configurable) | DB-level | DB-level + application-level | DB-level | DB-level |
| Encryption in Transit | TLS 1.2+ | TLS 1.2+ | TLS 1.2+ | TLS 1.2+ | TLS 1.2+ |
| Key Rotation | Yes (realm keys) | Managed service handles | Yes (configurable) | Yes | N/A |
| HSM Support | Yes (via Java KeyStore) | No | No | No | No |
| Algorithm Configurability | Yes (RS256, ES256, etc.) | Limited | Yes | Yes | Limited |

### Audit Logging

| Feature | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|-----|-----------|--------------|
| Login/Logout Events | Yes | Yes | Yes | Yes | Limited |
| Admin Actions | Yes | Yes | Yes | Yes | Limited |
| Policy Changes | Yes | No | Yes | Yes | No |
| Failed Auth Attempts | Yes | Yes | Yes | Yes | No |
| API Access Logs | Yes | Yes | Yes | Yes | Limited |
| Exportable Audit Trail | Yes (events SPI) | Yes (webhooks) | Yes (API) | Yes (export) | No |
| Retention Policies | Configurable | Managed service | Configurable | Configurable | N/A |

### Security Headers & Protections

| Feature | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|---------|----------|-------------|-----|-----------|--------------|
| CSRF Protection | Yes | Yes (dual method) | Yes | Yes | Basic |
| XSS Prevention | Yes (CSP) | Yes (HttpOnly cookies) | Yes | Yes | Yes |
| Clickjacking Protection | Yes (X-Frame-Options) | Yes | Yes | Yes | Basic |
| CORS Configuration | Yes | Yes | Yes | Yes | Yes |
| Security Headers | Comprehensive | Good | Good | Good | Basic |

---

## 5. Compliance

### Certification & Compliance Matrix

| Standard | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|----------|----------|-------------|-----|-----------|--------------|
| **SOC 2 Type II** | No (self-hosted OSS) | Yes (managed service) | **Yes** | No | Via Ory |
| **ISO 27001** | No | No | **Yes** | No | Via Ory |
| **GDPR** | Features available (self-managed) | Yes (managed) | **Yes (built-in data locality)** | Features available | Via Ory |
| **HIPAA** | Possible (self-configured) | Yes (managed) | Enterprise tier | Features available | Via Ory |
| **FedRAMP** | No | No | No | Enterprise tier (FIPS) | No |
| **Data Residency** | Self-hosted (you control) | Managed: limited regions | **Yes (Ory Network regions)** | Self-hosted (you control) | Self-hosted |
| **Data Export/Deletion (GDPR Art. 17)** | Yes (admin API) | Yes (API) | Yes (API) | Yes (admin UI + API) | Limited |
| **Consent Management** | Yes (required actions) | No | Yes | Yes | No |
| **Right to Be Forgotten** | Manual (API) | API support | API support | API support | N/A |

### Compliance Assessment

**Ory is the clear compliance leader** -- the only solution with both SOC 2 Type 2 and ISO 27001 certifications on its managed service. Audit partner is BARR Advisory.

**SuperTokens** has SOC 2 Type II for its managed service, which is strong for a younger company.

**Keycloak and Authentik** as purely self-hosted open-source projects do not hold certifications themselves. Your organization must achieve compliance around them, which is significantly more work.

**BoxyHQ/Polis** benefits from Ory's compliance posture post-acquisition.

---

## 6. Security Red Flags & Risk Matrix

### Critical Red Flags

| Solution | Red Flag | Severity | Details |
|----------|----------|----------|---------|
| **Authentik** | Two critical CVEs in 2024 | **HIGH** | CVE-2024-47070 (auth bypass, 9.0) and CVE-2024-52289 (9.8) indicate fundamental security design issues. Password bypass via X-Forwarded-For is a basic mistake for an identity provider. |
| **Keycloak** | Recurring privilege escalation patterns | **MEDIUM-HIGH** | CVE-2025-7784, CVE-2024-3656 show repeated broken access control issues. Large Java dependency tree increases supply chain risk. |
| **Keycloak** | Java deserialization vulnerability | **MEDIUM-HIGH** | CVE-2025-13467 -- untrusted Java deserialization is a well-known dangerous vulnerability class. |
| **Keycloak** | Session management flaws | **MEDIUM** | CVE-2025-12390 shows session identifier reuse. For an auth provider, this is a fundamental concern. |
| **SuperTokens** | Limited battle-testing | **MEDIUM** | Zero CVEs is suspicious for any software handling authentication. Either very secure or under-scrutinized. |
| **SuperTokens** | No built-in fine-grained authorization | **MEDIUM** | Requires external tools (Cerbos) for anything beyond basic RBAC. |
| **Authentik** | No formal security audit published | **MEDIUM** | No public third-party penetration test report. CVE-2024-47070 was found during an external pentest, not internal review. |
| **BoxyHQ/Polis** | Not a complete auth solution | **MEDIUM** | SSO bridge only. Must be paired with other components. Recent acquisition means organizational transition risk. |
| **Ory** | Smaller community than Keycloak | **LOW-MEDIUM** | Fewer eyes on the code, though Go's type safety helps. |

### Supply Chain Risk Assessment

| Solution | Language | Dependency Count | Notable Supply Chain Risks |
|----------|----------|-----------------|---------------------------|
| **Keycloak** | Java (Quarkus) | **Very High** (~500+ transitive Maven deps) | Large Java ecosystem = large attack surface. Known vulnerable libraries in distributions. Java deserialization is a recurring risk class. |
| **SuperTokens** | Node.js + Java (core) | **Medium** (~200+ npm deps for SDK) | Node.js ecosystem has higher package-squatting risk. Core is Java-based. |
| **Ory** | Go | **Low** (~50-80 direct deps) | Go's static compilation reduces runtime dependency risks. go-jose is a key dependency. |
| **Authentik** | Python (Django) | **Medium** (~150+ pip deps) | Python ecosystem has moderate supply chain risk. Django framework is well-maintained. |
| **BoxyHQ/Polis** | TypeScript/Node.js | **Low-Medium** (~100+ npm deps) | Narrow scope limits dependency surface. |

### Architectural Security Concerns

| Solution | Concern | Impact |
|----------|---------|--------|
| **Keycloak** | Monolithic architecture means a vulnerability in any component exposes the entire system | High -- compromise of one feature can cascade |
| **Keycloak** | Default configuration is permissive; security requires significant hardening | Medium -- misconfiguration is common |
| **SuperTokens** | SDK-embedded model means auth logic runs in your application process | Medium -- vulnerability in app can impact auth |
| **Ory** | Composable architecture means multiple services to secure and monitor | Low-Medium -- more operational overhead but better isolation |
| **Authentik** | Python/Django performance under high load can impact security features (rate limiting, etc.) | Low-Medium |
| **Authentik** | Default auth flow design was vulnerable to header spoofing (CVE-2024-47070) | High -- default insecurity is a design philosophy concern |

---

## 7. Security Risk Matrix (Overall)

| Dimension | Keycloak | SuperTokens | Ory | Authentik | BoxyHQ/Polis |
|-----------|----------|-------------|-----|-----------|--------------|
| **Vulnerability History** | C | A- | A | D | B+ |
| **Auth Feature Depth** | A+ | B+ | A | A- | C (SSO only) |
| **Authorization** | A | C | A+ | B | D |
| **Session Security** | B | A+ | B+ | B | N/A |
| **Encryption/Key Mgmt** | A | B | B+ | B | C |
| **Audit Logging** | A | B | A | A | D |
| **Compliance Certs** | D (self-hosted) | B+ (managed) | **A+** | D (self-hosted) | B (via Ory) |
| **Supply Chain Risk** | D (Java deps) | B | **A** (Go) | B- | B |
| **Security Response** | A (Red Hat) | B- (small team) | A- | B- | B (via Ory) |
| **Overall Security Grade** | **B** | **B+** | **A** | **C+** | **C+** |

### Grade Explanations

- **Ory: A** -- Fewest vulnerabilities relative to age, strongest compliance story (SOC 2 + ISO 27001), Go's type safety reduces vulnerability classes, Zanzibar-based authorization is industry-leading. Main risk is smaller community scrutiny.

- **SuperTokens: B+** -- Cleanest vulnerability record, best session security in the group, SOC 2 compliant. Docked for limited authorization, smaller battle-testing surface, and reliance on Node.js ecosystem.

- **Keycloak: B** -- Most comprehensive feature set and strongest security response process (Red Hat). Significantly docked for high CVE volume, Java supply chain risk, recurring privilege escalation patterns, and no compliance certifications for the OSS project.

- **Authentik: C+** -- Two critical CVEs in 2024 is a serious concern for an identity provider. The password bypass via header spoofing (CVE-2024-47070) suggests insufficient security review of default configurations. No formal compliance certifications. Good feature set but trust is undermined by vulnerability history.

- **BoxyHQ/Polis: C+** -- Not a complete auth solution. Narrow scope limits both risk and value. Now benefits from Ory's security umbrella. Cannot be evaluated standalone for most security dimensions.

---

## 8. Recommendations

### For Security-Critical Deployments

1. **Ory** is the recommended choice when compliance certifications matter. SOC 2 Type 2 + ISO 27001 + GDPR built-in is unmatched in this group.

2. **SuperTokens** is recommended when session security is paramount and the use case is simpler (web app auth without complex enterprise SSO needs).

3. **Keycloak** is recommended only when the full breadth of enterprise auth features is needed AND the team has dedicated security expertise to harden and maintain it.

### Solutions to Approach with Caution

4. **Authentik** -- The 2024 critical CVE pattern is a significant red flag. Would not recommend for production use handling sensitive data without a thorough independent security audit. The password bypass vulnerability in particular (CVE-2024-47070) indicates a design-level security gap.

5. **BoxyHQ/Polis** -- Only suitable as a supplementary SSO bridge component, not a primary auth solution. If choosing Ory, it integrates naturally.

### Mandatory Security Measures (Regardless of Solution)

- Conduct an independent penetration test before production deployment
- Enable all available MFA methods and enforce MFA for admin accounts
- Configure comprehensive audit logging and monitoring
- Implement network segmentation to isolate the auth service
- Establish a vulnerability monitoring process for the chosen solution
- Review and harden default configurations (especially Keycloak and Authentik)
- Implement rate limiting at both the application and infrastructure level
- Set up automated dependency scanning for supply chain monitoring

---

*Report compiled from CVE databases, vendor security advisories, GitHub security tabs, Snyk vulnerability database, vendor documentation, and community security discussions.*
