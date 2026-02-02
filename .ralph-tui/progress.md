# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

### Error Handling Architecture
The frontend uses a 5-layer error handling approach:
1. **ErrorBoundary** (`src/components/ErrorBoundary.tsx`) - Wraps route components, logs with `componentStack`
2. **Global handlers** (`src/lib/globalErrorHandlers.ts`) - `window.onerror` and `onunhandledrejection`
3. **Error reporting service** (`src/lib/errorReporting.ts`) - Sentry-ready stub with `reportError()` and `reportApiError()`
4. **API client** (`src/lib/api.ts`) - Custom `ApiError` class with endpoint, status, responseBody
5. **React Query** (`src/lib/queryClient.ts`) - Error hooks calling reportApiError

### API Error Context Pattern
Always include `userAction` and `component` in API calls for debugging:
```typescript
api.get('/projects', { userAction: 'Load projects', component: 'ProjectList' })
```

### Environment Configuration
Use `src/lib/env.ts` for all environment variables:
- `VITE_API_URL` - API base URL (empty = relative URLs for proxy)
- `VITE_SENTRY_DSN` - Error reporting (empty = disabled)
- `VITE_APP_ENV` - development | staging | production

---

## 2026-02-01 - client-onboarding-v2-c3y.144
- **Verified already implemented:** All error logging and Railway deployment requirements
- **Files verified (no changes needed):**
  - `src/components/ErrorBoundary.tsx` - React Error Boundaries for all routes with componentStack logging
  - `src/lib/globalErrorHandlers.ts` - window.onerror and onunhandledrejection handlers
  - `src/lib/errorReporting.ts` - Sentry stub with reportError, reportApiError, setUserContext, addBreadcrumb
  - `src/lib/api.ts` - API errors logged with endpoint, status, response body, userAction context
  - `src/lib/env.ts` - VITE_API_URL environment variable support
  - `src/App.tsx` - All 6 routes wrapped in ErrorBoundary
  - `vite.config.ts` - Build to dist/, sourcemaps enabled, proxy configured
  - `package.json` - `npm run build` script for static assets
- **Quality checks:**
  - TypeScript: ✅ Passes
  - Build: ✅ Produces static assets in dist/
  - ESLint: ⚠️ npm cache permission issue (system-level, not code issue)
- **Learnings:**
  - Error boundaries should wrap individual routes, not just the root App
  - userAction context in API calls is critical for debugging production issues
  - Empty VITE_API_URL = relative URLs, works with Vite dev proxy and production deployment
---

