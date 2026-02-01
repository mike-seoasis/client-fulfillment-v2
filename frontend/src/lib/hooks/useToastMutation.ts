/**
 * React Query mutation hook with automatic toast notifications
 *
 * Provides a convenient wrapper around useMutation that automatically
 * shows success and error toasts based on mutation results.
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Errors are logged with full API context (endpoint, status, response)
 * - User action context is captured for debugging
 * - Breadcrumbs are added for mutation lifecycle events
 */

import { useMutation, type UseMutationOptions, type UseMutationResult } from '@tanstack/react-query'
import { useToast } from '@/components/ui/toast-provider'
import { showApiErrorToast } from '@/lib/toastHelpers'
import { ApiError } from '@/lib/api'
import { addBreadcrumb } from '@/lib/errorReporting'

export interface ToastMutationOptions<TData, TError, TVariables, TContext>
  extends Omit<UseMutationOptions<TData, TError, TVariables, TContext>, 'onSuccess' | 'onError'> {
  /** User action description for logging */
  userAction: string
  /** Toast message on success */
  successMessage?: string | ((data: TData, variables: TVariables) => string)
  /** Success toast description */
  successDescription?: string | ((data: TData, variables: TVariables) => string)
  /** Error toast title (default: "Something went wrong") */
  errorTitle?: string
  /** Custom error description (defaults to error message) */
  errorDescription?: string | ((error: TError, variables: TVariables) => string)
  /** Whether to show success toast (default: true) */
  showSuccessToast?: boolean
  /** Whether to show error toast (default: true) */
  showErrorToast?: boolean
  /** Custom onSuccess callback (runs after toast) */
  onSuccess?: (data: TData, variables: TVariables, context: TContext | undefined) => void
  /** Custom onError callback (runs after toast) */
  onError?: (error: TError, variables: TVariables, context: TContext | undefined) => void
}

/**
 * useMutation wrapper with automatic toast notifications
 *
 * @example
 * const updateProject = useToastMutation({
 *   mutationFn: (data) => api.patch(`/projects/${id}`, data),
 *   userAction: 'Update project',
 *   successMessage: 'Project updated',
 *   successDescription: 'Your changes have been saved.',
 * })
 *
 * // In your handler:
 * updateProject.mutate({ name: 'New Name' })
 */
export function useToastMutation<
  TData = unknown,
  TError = Error,
  TVariables = void,
  TContext = unknown,
>(
  options: ToastMutationOptions<TData, TError, TVariables, TContext>,
): UseMutationResult<TData, TError, TVariables, TContext> {
  const toast = useToast()

  const {
    userAction,
    successMessage,
    successDescription,
    errorTitle = 'Something went wrong',
    errorDescription,
    showSuccessToast = true,
    showErrorToast = true,
    onSuccess: customOnSuccess,
    onError: customOnError,
    ...mutationOptions
  } = options

  return useMutation({
    ...mutationOptions,
    onSuccess: (data, variables, context) => {
      addBreadcrumb(`Mutation success: ${userAction}`, 'mutation', { data })

      if (showSuccessToast && successMessage) {
        const title = typeof successMessage === 'function'
          ? successMessage(data, variables)
          : successMessage
        const description = typeof successDescription === 'function'
          ? successDescription(data, variables)
          : successDescription

        toast.success(title, description)
      }

      customOnSuccess?.(data, variables, context)
    },
    onError: (error, variables, context) => {
      addBreadcrumb(`Mutation error: ${userAction}`, 'mutation', {
        error: String(error),
        variables,
      })

      if (showErrorToast) {
        if (error instanceof ApiError) {
          showApiErrorToast(toast.toast, error, userAction)
        } else {
          const description = typeof errorDescription === 'function'
            ? errorDescription(error, variables)
            : errorDescription ?? (error instanceof Error ? error.message : String(error))

          toast.error(errorTitle, description)
        }
      }

      customOnError?.(error, variables, context)
    },
  })
}
