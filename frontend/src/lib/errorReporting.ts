/**
 * Error reporting service integration point
 *
 * This module provides a centralized place for error reporting.
 * Currently logs to console, but designed for easy Sentry integration.
 *
 * To integrate Sentry:
 * 1. npm install @sentry/react
 * 2. Set VITE_SENTRY_DSN in environment
 * 3. Uncomment Sentry initialization in this file
 */

import { env } from './env'

export interface ErrorContext {
  /** User action that triggered the error */
  userAction?: string
  /** Component where error occurred */
  component?: string
  /** Additional metadata */
  extra?: Record<string, unknown>
}

export interface ApiErrorContext extends ErrorContext {
  endpoint: string
  method: string
  status?: number
  responseBody?: unknown
}

/**
 * Initialize error reporting service
 * Call this once at app startup
 */
export function initErrorReporting(): void {
  if (env.sentryDsn) {
    // Sentry integration point
    // Sentry.init({
    //   dsn: env.sentryDsn,
    //   environment: env.appEnv,
    //   tracesSampleRate: env.isProd ? 0.1 : 1.0,
    // })
    console.log('[ErrorReporting] Sentry DSN configured (stub implementation)')
  } else {
    console.log('[ErrorReporting] No Sentry DSN configured, using console logging')
  }
}

/**
 * Report a caught error to the error reporting service
 */
export function reportError(error: Error, context?: ErrorContext): void {
  const errorInfo = {
    message: error.message,
    name: error.name,
    stack: error.stack,
    ...context,
  }

  // Always log to console in development
  if (env.isDev) {
    console.error('[ErrorReporting] Caught error:', errorInfo)
  }

  if (env.sentryDsn) {
    // Sentry.captureException(error, { extra: context })
    console.log('[ErrorReporting] Would send to Sentry:', errorInfo)
  }
}

/**
 * Report an API error with full context
 */
export function reportApiError(
  error: Error,
  context: ApiErrorContext,
): void {
  const errorInfo = {
    message: error.message,
    name: error.name,
    endpoint: context.endpoint,
    method: context.method,
    status: context.status,
    responseBody: context.responseBody,
    userAction: context.userAction,
    component: context.component,
  }

  // Always log API errors with full context
  console.error('[API Error]', errorInfo)

  if (env.sentryDsn) {
    // Sentry.captureException(error, {
    //   tags: {
    //     endpoint: context.endpoint,
    //     method: context.method,
    //     status: context.status?.toString(),
    //   },
    //   extra: context,
    // })
    console.log('[ErrorReporting] Would send API error to Sentry:', errorInfo)
  }
}

/**
 * Set user context for error reporting
 */
export function setUserContext(user: { id: string; email?: string } | null): void {
  if (env.sentryDsn) {
    // Sentry.setUser(user)
    console.log('[ErrorReporting] User context set:', user)
  }
}

/**
 * Add breadcrumb for debugging
 */
export function addBreadcrumb(
  message: string,
  category: string,
  data?: Record<string, unknown>,
): void {
  if (env.sentryDsn) {
    // Sentry.addBreadcrumb({
    //   message,
    //   category,
    //   data,
    //   level: 'info',
    // })
  }

  if (env.isDev) {
    console.debug(`[Breadcrumb:${category}] ${message}`, data || '')
  }
}
