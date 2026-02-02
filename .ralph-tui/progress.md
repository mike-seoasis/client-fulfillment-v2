# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Handling Architecture
- **Error Boundaries**: Use `<ErrorBoundary componentName="...">` wrapper around route components in `App.tsx`
- **Global Handlers**: `setupGlobalErrorHandlers()` in `main.tsx` catches window.onerror and unhandledrejection
- **API Errors**: Use `ApiError` class from `src/lib/api.ts` with endpoint, method, status, responseBody
- **Error Reporting**: Call `reportError()` or `reportApiError()` from `src/lib/errorReporting.ts`
- **Breadcrumbs**: Use `addBreadcrumb()` for debugging context

### Environment Configuration
- **env.ts**: Centralized config in `src/lib/env.ts` with `apiUrl`, `sentryDsn`, `appEnv`, `isProd`, `isDev`
- **Type Definitions**: `vite-env.d.ts` defines `ImportMetaEnv` interface
- **Relative URLs**: Empty `VITE_API_URL` uses relative URLs (works with Vite proxy in dev)

---

## 2026-02-01 - client-onboarding-v2-c3y.134
- Verified error logging requirements already fully implemented
- Error Boundaries wrap all routes in App.tsx
- Global handlers in globalErrorHandlers.ts
- API errors logged with full context in api.ts
- Sentry integration stub ready in errorReporting.ts
- Railway deployment configuration complete
- **No code changes needed - all acceptance criteria already satisfied**

**Files reviewed (no changes):**
- frontend/src/App.tsx - routes with ErrorBoundary
- frontend/src/main.tsx - error handler initialization
- frontend/src/components/ErrorBoundary.tsx - React error boundary
- frontend/src/lib/errorReporting.ts - Sentry stub and error reporting
- frontend/src/lib/globalErrorHandlers.ts - window.onerror handlers
- frontend/src/lib/api.ts - API client with error logging
- frontend/src/lib/env.ts - environment configuration
- frontend/vite.config.ts - build configuration

**Learnings:**
- Error logging infrastructure was already comprehensive
- Pattern: Initialize error handlers before React mounts in main.tsx
- Pattern: Use relative URLs (empty apiUrl) for Railway deployment compatibility
---

