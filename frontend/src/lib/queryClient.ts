/**
 * React Query client configuration with error handling integration
 *
 * Provides centralized query client with:
 * - Global error handling tied to error reporting service
 * - Sensible retry and cache defaults
 * - API error integration
 */

import { QueryClient, QueryCache, MutationCache } from '@tanstack/react-query'
import { ApiError } from './api'
import { reportError, reportApiError, addBreadcrumb } from './errorReporting'

/**
 * Handle query errors with appropriate logging
 */
function handleQueryError(error: unknown, queryKey: unknown): void {
  const keyString = JSON.stringify(queryKey)
  addBreadcrumb(`Query error: ${keyString}`, 'query', { error: String(error) })

  if (error instanceof ApiError) {
    reportApiError(error, {
      endpoint: error.endpoint,
      method: error.method,
      status: error.status,
      responseBody: error.responseBody,
      userAction: `Query: ${keyString}`,
    })
  } else if (error instanceof Error) {
    reportError(error, {
      userAction: `Query error: ${keyString}`,
    })
  } else {
    const syntheticError = new Error(String(error))
    syntheticError.name = 'QueryError'
    reportError(syntheticError, {
      userAction: `Query error: ${keyString}`,
    })
  }
}

/**
 * Handle mutation errors with appropriate logging
 */
function handleMutationError(
  error: unknown,
  variables: unknown,
  mutationKey: unknown,
): void {
  const keyString = mutationKey ? JSON.stringify(mutationKey) : 'unnamed'
  addBreadcrumb(`Mutation error: ${keyString}`, 'mutation', {
    error: String(error),
    variables,
  })

  if (error instanceof ApiError) {
    reportApiError(error, {
      endpoint: error.endpoint,
      method: error.method,
      status: error.status,
      responseBody: error.responseBody,
      userAction: `Mutation: ${keyString}`,
    })
  } else if (error instanceof Error) {
    reportError(error, {
      userAction: `Mutation error: ${keyString}`,
      extra: { variables },
    })
  } else {
    const syntheticError = new Error(String(error))
    syntheticError.name = 'MutationError'
    reportError(syntheticError, {
      userAction: `Mutation error: ${keyString}`,
      extra: { variables },
    })
  }
}

/**
 * Determine if an error should trigger a retry
 * - Don't retry client errors (4xx) except 408 (timeout) and 429 (rate limit)
 * - Retry network errors and server errors (5xx)
 */
function shouldRetry(failureCount: number, error: unknown): boolean {
  // Max 3 retries
  if (failureCount >= 3) return false

  if (error instanceof ApiError) {
    // Don't retry most client errors
    if (error.status >= 400 && error.status < 500) {
      // Retry timeout and rate limit
      return error.status === 408 || error.status === 429
    }
    // Retry server errors
    return true
  }

  // Retry network errors (status 0 in our ApiError)
  return true
}

/**
 * Create a configured QueryClient instance
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error, query) => {
        handleQueryError(error, query.queryKey)
      },
    }),
    mutationCache: new MutationCache({
      onError: (error, variables, _context, mutation) => {
        handleMutationError(error, variables, mutation.options.mutationKey)
      },
    }),
    defaultOptions: {
      queries: {
        // Stale time: data is fresh for 30 seconds
        staleTime: 30 * 1000,
        // Cache time: keep unused data in cache for 5 minutes
        gcTime: 5 * 60 * 1000,
        // Retry configuration
        retry: shouldRetry,
        // Exponential backoff for retries
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
        // Refetch settings
        refetchOnWindowFocus: true,
        refetchOnReconnect: true,
        // Network mode: always try the fetch (handles offline gracefully)
        networkMode: 'offlineFirst',
      },
      mutations: {
        // Retry mutations more conservatively
        retry: (failureCount, error) => {
          // Only retry once for mutations
          if (failureCount >= 1) return false
          // Only retry on network errors
          return error instanceof ApiError && error.status === 0
        },
        networkMode: 'offlineFirst',
      },
    },
  })
}

/**
 * Default query client instance
 * Used when a custom client isn't needed
 */
export const queryClient = createQueryClient()
