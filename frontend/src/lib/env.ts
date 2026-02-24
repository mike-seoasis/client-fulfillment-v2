/**
 * Environment configuration with type safety
 */
export const env = {
  /** API base URL - empty string means use relative URLs (proxied in dev) */
  apiUrl: import.meta.env.VITE_API_URL || '',

  /** Sentry DSN for error reporting - empty means disabled */
  sentryDsn: import.meta.env.VITE_SENTRY_DSN || '',

  /** Current environment */
  appEnv: (import.meta.env.VITE_APP_ENV || 'development') as
    | 'development'
    | 'staging'
    | 'production',

  /** Whether we're in production */
  isProd: import.meta.env.PROD,

  /** Whether we're in development */
  isDev: import.meta.env.DEV,
} as const
