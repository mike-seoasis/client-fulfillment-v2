/**
 * React Query mutation hook with optimistic updates and automatic rollback
 *
 * Provides a convenient wrapper around useMutation that:
 * - Applies optimistic updates to the cache immediately
 * - Automatically rolls back on error
 * - Integrates with toast notifications
 * - Logs all state transitions per error logging requirements
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log method entry/exit at DEBUG level with parameters (sanitized)
 * - Log all exceptions with full stack trace and context
 * - Include entity IDs (project_id, page_id) in all service logs
 * - Log validation failures with field names and rejected values
 * - Log state transitions at INFO level
 * - Add timing logs for operations >1 second
 */

import { useMutation, useQueryClient, type UseMutationResult, type QueryKey } from '@tanstack/react-query'
import { useToast } from '@/components/ui/toast-provider'
import { showApiErrorToast } from '@/lib/toastHelpers'
import { ApiError } from '@/lib/api'
import { addBreadcrumb, reportError } from '@/lib/errorReporting'

/** Threshold for logging slow operations (in milliseconds) */
const SLOW_OPERATION_THRESHOLD_MS = 1000

/**
 * Context stored during optimistic update for rollback
 */
interface OptimisticContext<TSnapshot> {
  /** Snapshot of previous data for rollback */
  snapshot: TSnapshot
  /** Timestamp when mutation started */
  startTime: number
}

/**
 * Options for optimistic mutations
 */
export interface UseOptimisticMutationOptions<TData, TVariables, TSnapshot = unknown> {
  /** The mutation function that calls the API */
  mutationFn: (variables: TVariables) => Promise<TData>

  /** Query key(s) to update optimistically */
  queryKey: QueryKey

  /**
   * Function to create the optimistic data update
   * Receives current cache data and mutation variables
   * Returns the new cache data to set optimistically
   */
  getOptimisticData: (currentData: TSnapshot | undefined, variables: TVariables) => TSnapshot

  /**
   * Optional function to update the cache with server response
   * If not provided, the cache is invalidated to refetch fresh data
   */
  updateCacheWithResult?: (currentData: TSnapshot | undefined, result: TData, variables: TVariables) => TSnapshot

  /** Additional query keys to invalidate on success */
  invalidateKeys?: QueryKey[]

  /** User action description for logging and toasts */
  userAction: string

  /** Component name for error context */
  component?: string

  /** Entity IDs for logging (e.g., projectId, pageId) */
  entityIds?: Record<string, string | undefined>

  /** Toast message on success (omit for silent mutations) */
  successMessage?: string | ((data: TData, variables: TVariables) => string)

  /** Success toast description */
  successDescription?: string | ((data: TData, variables: TVariables) => string)

  /** Error toast title (default: "Something went wrong") */
  errorTitle?: string

  /** Whether to show error toast (default: true) */
  showErrorToast?: boolean

  /** Custom onSuccess callback (runs after cache update and toast) */
  onSuccess?: (data: TData, variables: TVariables) => void

  /** Custom onError callback (runs after rollback and toast) */
  onError?: (error: Error, variables: TVariables) => void
}

/**
 * Hook for mutations with optimistic updates and automatic rollback
 *
 * @example
 * // Basic usage for project settings update
 * const updateProject = useOptimisticMutation({
 *   mutationFn: (data) => api.patch(`/api/v1/projects/${projectId}`, data),
 *   queryKey: ['project', projectId],
 *   getOptimisticData: (current, data) => ({
 *     ...current,
 *     ...data,
 *     updated_at: new Date().toISOString(),
 *   }),
 *   userAction: 'Update project',
 *   entityIds: { projectId },
 *   successMessage: 'Project updated',
 * })
 *
 * @example
 * // Phase status update with nested data
 * const updatePhaseStatus = useOptimisticMutation({
 *   mutationFn: (data) => api.patch(`/api/v1/projects/${projectId}/phases`, data),
 *   queryKey: ['project', projectId],
 *   getOptimisticData: (current, { phase, status }) => ({
 *     ...current,
 *     phase_status: {
 *       ...current?.phase_status,
 *       [phase]: {
 *         ...current?.phase_status?.[phase],
 *         status,
 *         ...(status === 'in_progress' ? { started_at: new Date().toISOString() } : {}),
 *         ...(status === 'completed' ? { completed_at: new Date().toISOString() } : {}),
 *       },
 *     },
 *     updated_at: new Date().toISOString(),
 *   }),
 *   userAction: 'Update phase status',
 *   entityIds: { projectId },
 *   successMessage: 'Phase status updated',
 * })
 */
export function useOptimisticMutation<TData, TVariables, TSnapshot = unknown>({
  mutationFn,
  queryKey,
  getOptimisticData,
  updateCacheWithResult,
  invalidateKeys = [],
  userAction,
  component = 'Unknown',
  entityIds = {},
  successMessage,
  successDescription,
  errorTitle = 'Something went wrong',
  showErrorToast = true,
  onSuccess,
  onError,
}: UseOptimisticMutationOptions<TData, TVariables, TSnapshot>): UseMutationResult<
  TData,
  Error,
  TVariables,
  OptimisticContext<TSnapshot>
> {
  const queryClient = useQueryClient()
  const toast = useToast()

  // Sanitize entity IDs for logging (remove undefined values)
  const sanitizedEntityIds = Object.fromEntries(
    Object.entries(entityIds).filter(([, v]) => v !== undefined)
  )

  return useMutation<TData, Error, TVariables, OptimisticContext<TSnapshot>>({
    mutationFn,

    onMutate: async (variables) => {
      const startTime = Date.now()

      // Log mutation start at DEBUG level
      console.debug(`[${component}] Optimistic mutation started:`, {
        userAction,
        ...sanitizedEntityIds,
        variableKeys: Object.keys(variables as object),
      })
      addBreadcrumb(`Optimistic mutation: ${userAction}`, 'mutation', {
        ...sanitizedEntityIds,
        status: 'started',
      })

      // Cancel any in-flight queries for this key to avoid race conditions
      await queryClient.cancelQueries({ queryKey })

      // Snapshot current data for rollback
      const snapshot = queryClient.getQueryData<TSnapshot>(queryKey)

      // Apply optimistic update
      const optimisticData = getOptimisticData(snapshot, variables)
      queryClient.setQueryData<TSnapshot>(queryKey, optimisticData)

      console.debug(`[${component}] Optimistic update applied:`, {
        userAction,
        ...sanitizedEntityIds,
        hadPreviousData: snapshot !== undefined,
      })

      return { snapshot: snapshot as TSnapshot, startTime }
    },

    onSuccess: (data, variables, context) => {
      const duration = Date.now() - (context?.startTime ?? Date.now())

      // Log slow operations
      if (duration > SLOW_OPERATION_THRESHOLD_MS) {
        console.warn(`[${component}] Slow mutation detected:`, {
          userAction,
          ...sanitizedEntityIds,
          duration_ms: duration,
        })
      }

      // Log success at INFO level (state transition)
      console.info(`[${component}] Mutation succeeded:`, {
        userAction,
        ...sanitizedEntityIds,
        duration_ms: duration,
      })
      addBreadcrumb(`Mutation success: ${userAction}`, 'mutation', {
        ...sanitizedEntityIds,
        status: 'succeeded',
        duration_ms: duration,
      })

      // Update cache with server response if handler provided
      if (updateCacheWithResult) {
        const currentData = queryClient.getQueryData<TSnapshot>(queryKey)
        const updatedData = updateCacheWithResult(currentData, data, variables)
        queryClient.setQueryData<TSnapshot>(queryKey, updatedData)
      } else {
        // Otherwise, invalidate to ensure fresh data
        queryClient.invalidateQueries({ queryKey })
      }

      // Invalidate additional keys
      for (const key of invalidateKeys) {
        queryClient.invalidateQueries({ queryKey: key })
      }

      // Show success toast
      if (successMessage) {
        const title =
          typeof successMessage === 'function'
            ? successMessage(data, variables)
            : successMessage
        const description =
          typeof successDescription === 'function'
            ? successDescription(data, variables)
            : successDescription

        toast.success(title, description)
      }

      // Call custom onSuccess
      onSuccess?.(data, variables)
    },

    onError: (error, variables, context) => {
      const duration = Date.now() - (context?.startTime ?? Date.now())

      // Log error with full stack trace
      console.error(`[${component}] Mutation failed:`, {
        userAction,
        ...sanitizedEntityIds,
        error_type: error.name,
        error_message: error.message,
        stack_trace: error.stack,
        duration_ms: duration,
      })
      addBreadcrumb(`Mutation error: ${userAction}`, 'mutation', {
        ...sanitizedEntityIds,
        status: 'failed',
        error: error.message,
      })

      // Report error to error reporting service
      reportError(error, {
        component,
        userAction,
        extra: {
          ...sanitizedEntityIds,
          variableKeys: Object.keys(variables as object),
        },
      })

      // Rollback to snapshot
      if (context?.snapshot !== undefined) {
        console.debug(`[${component}] Rolling back optimistic update:`, {
          userAction,
          ...sanitizedEntityIds,
        })
        queryClient.setQueryData<TSnapshot>(queryKey, context.snapshot)
      }

      // Show error toast
      if (showErrorToast) {
        if (error instanceof ApiError) {
          showApiErrorToast(toast.toast, error, userAction)
        } else {
          toast.error(errorTitle, error.message)
        }
      }

      // Call custom onError
      onError?.(error, variables)
    },
  })
}
