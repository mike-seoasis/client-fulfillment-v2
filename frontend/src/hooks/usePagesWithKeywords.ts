/**
 * TanStack Query hook for fetching pages with their keyword data.
 *
 * Query keys:
 * - ['projects', projectId, 'pages-with-keywords'] for the pages list
 */

import {
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  getPagesWithKeywords,
  type PageWithKeywords,
} from '@/lib/api';

// Query keys factory
export const pagesWithKeywordsKeys = {
  list: (projectId: string, batch?: number | null) =>
    batch != null
      ? (['projects', projectId, 'pages-with-keywords', batch] as const)
      : (['projects', projectId, 'pages-with-keywords'] as const),
};

/**
 * Fetch all pages with their keyword data for the approval interface.
 * Only returns pages with status=completed.
 *
 * @param projectId - The project ID to fetch pages for
 * @param options - Optional configuration
 * @param options.enabled - Whether the query is enabled (default: true if projectId exists)
 * @param options.staleTime - Time in ms until data is considered stale (default: 30 seconds)
 * @param options.gcTime - Time in ms to keep unused data in cache (default: 5 minutes)
 */
export function usePagesWithKeywords(
  projectId: string,
  options?: {
    enabled?: boolean;
    staleTime?: number;
    gcTime?: number;
    batch?: number | null;
  }
): UseQueryResult<PageWithKeywords[]> {
  const batch = options?.batch;
  return useQuery({
    queryKey: pagesWithKeywordsKeys.list(projectId, batch),
    queryFn: () => getPagesWithKeywords(projectId, batch),
    enabled: options?.enabled ?? !!projectId,
    staleTime: options?.staleTime ?? 30_000, // 30 seconds
    gcTime: options?.gcTime ?? 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Helper hook that provides pages with keywords data along with
 * convenient derived state and actions.
 */
export function usePagesWithKeywordsData(projectId: string, options?: { batch?: number | null }) {
  const batch = options?.batch;
  const queryClient = useQueryClient();
  const query = usePagesWithKeywords(projectId, { batch });

  return {
    // Data
    pages: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,

    // Actions
    refetch: query.refetch,
    invalidate: () =>
      queryClient.invalidateQueries({
        queryKey: pagesWithKeywordsKeys.list(projectId, batch),
      }),
  };
}
