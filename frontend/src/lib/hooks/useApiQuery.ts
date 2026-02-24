/**
 * React Query hooks with typed API client integration
 *
 * Provides type-safe query and mutation hooks that work with
 * the API client's error handling and logging.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  UseQueryOptions,
  UseMutationOptions,
  QueryKey,
} from '@tanstack/react-query'
import { api, ApiError, ApiRequestOptions } from '../api'

/**
 * Options for API queries
 */
export interface UseApiQueryOptions<TData>
  extends Omit<UseQueryOptions<TData, ApiError>, 'queryFn'> {
  /** API endpoint to fetch */
  endpoint: string
  /** Request options passed to api client */
  requestOptions?: ApiRequestOptions
}

/**
 * Hook for fetching data from API endpoints
 *
 * @example
 * const { data, isLoading, error } = useApiQuery<Project[]>({
 *   queryKey: ['projects'],
 *   endpoint: '/api/v1/projects',
 *   requestOptions: { userAction: 'Load projects list', component: 'ProjectList' }
 * })
 */
export function useApiQuery<TData>({
  endpoint,
  requestOptions,
  ...queryOptions
}: UseApiQueryOptions<TData>) {
  return useQuery<TData, ApiError>({
    ...queryOptions,
    queryFn: () => api.get<TData>(endpoint, requestOptions),
  })
}

/**
 * Options for mutations (POST, PUT, PATCH, DELETE)
 */
export interface UseApiMutationOptions<TData, TVariables>
  extends Omit<UseMutationOptions<TData, ApiError, TVariables>, 'mutationFn'> {
  /** API endpoint */
  endpoint: string | ((variables: TVariables) => string)
  /** HTTP method */
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Request options passed to api client */
  requestOptions?: ApiRequestOptions
  /** Query keys to invalidate on success */
  invalidateKeys?: QueryKey[]
}

/**
 * Hook for mutations (create, update, delete operations)
 *
 * @example
 * const mutation = useApiMutation<Project, CreateProjectInput>({
 *   endpoint: '/api/v1/projects',
 *   method: 'POST',
 *   invalidateKeys: [['projects']],
 *   requestOptions: { userAction: 'Create project', component: 'ProjectForm' }
 * })
 *
 * // Dynamic endpoint example
 * const updateMutation = useApiMutation<Project, { id: string; data: UpdateInput }>({
 *   endpoint: (vars) => `/api/v1/projects/${vars.id}`,
 *   method: 'PATCH',
 *   invalidateKeys: [['projects']],
 * })
 */
export function useApiMutation<TData, TVariables = void>({
  endpoint,
  method,
  requestOptions,
  invalidateKeys,
  onSuccess,
  ...mutationOptions
}: UseApiMutationOptions<TData, TVariables>) {
  const queryClient = useQueryClient()

  return useMutation<TData, ApiError, TVariables>({
    ...mutationOptions,
    mutationFn: async (variables) => {
      const url = typeof endpoint === 'function' ? endpoint(variables) : endpoint

      switch (method) {
        case 'POST':
          return api.post<TData>(url, variables, requestOptions)
        case 'PUT':
          return api.put<TData>(url, variables, requestOptions)
        case 'PATCH':
          return api.patch<TData>(url, variables, requestOptions)
        case 'DELETE':
          return api.delete<TData>(url, requestOptions)
      }
    },
    onSuccess: (data, variables, context, mutation) => {
      // Invalidate specified queries on success
      if (invalidateKeys) {
        invalidateKeys.forEach((key) => {
          queryClient.invalidateQueries({ queryKey: key })
        })
      }

      // Call user-provided onSuccess if present
      onSuccess?.(data, variables, context, mutation)
    },
  })
}

/**
 * Prefetch data for an endpoint
 * Useful for prefetching on hover or route transitions
 *
 * @example
 * const prefetchProject = usePrefetch<Project>({
 *   queryKey: ['project', id],
 *   endpoint: `/api/v1/projects/${id}`,
 * })
 *
 * // Prefetch on hover
 * <button onMouseEnter={() => prefetchProject()}>View Project</button>
 */
export function usePrefetch<TData>({
  queryKey,
  endpoint,
  requestOptions,
}: {
  queryKey: QueryKey
  endpoint: string
  requestOptions?: ApiRequestOptions
}) {
  const queryClient = useQueryClient()

  return () => {
    queryClient.prefetchQuery({
      queryKey,
      queryFn: () => api.get<TData>(endpoint, requestOptions),
    })
  }
}
