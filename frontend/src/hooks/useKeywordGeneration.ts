/**
 * TanStack Query hooks for primary keyword generation operations.
 *
 * Query keys:
 * - ['projects', projectId, 'primary-keywords', 'status'] for generation status
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  generatePrimaryKeywords,
  getPrimaryKeywordsStatus,
  type GeneratePrimaryKeywordsResponse,
  type PrimaryKeywordGenerationStatus,
} from '@/lib/api';

// Query keys factory
export const keywordGenerationKeys = {
  status: (projectId: string) => ['projects', projectId, 'primary-keywords', 'status'] as const,
  pagesWithKeywords: (projectId: string) => ['projects', projectId, 'pages-with-keywords'] as const,
};

/**
 * Fetch the current keyword generation status for a project.
 * Supports polling when generation is in progress.
 */
export function useKeywordGenerationStatus(
  projectId: string,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<PrimaryKeywordGenerationStatus> {
  return useQuery({
    queryKey: keywordGenerationKeys.status(projectId),
    queryFn: () => getPrimaryKeywordsStatus(projectId),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: options?.refetchInterval,
  });
}

/**
 * Start primary keyword generation for a project.
 * Returns the task_id and initial status.
 */
export function useStartKeywordGeneration(): UseMutationResult<
  GeneratePrimaryKeywordsResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId: string) => generatePrimaryKeywords(projectId),
    onSuccess: (_data, projectId) => {
      // Invalidate status to trigger a fresh fetch
      queryClient.invalidateQueries({
        queryKey: keywordGenerationKeys.status(projectId),
      });
    },
  });
}

/**
 * Helper hook that manages the full keyword generation flow.
 * - Starts generation when triggered
 * - Polls for status every 2 seconds while generating
 * - Stops polling when status='complete' or status='failed'
 * - Returns status, progress, isGenerating, error
 * - Exposes startGeneration function
 */
export function useKeywordGeneration(projectId: string) {
  const queryClient = useQueryClient();

  // Poll status - refetch every 2 seconds while generating or pending
  const status = useQuery({
    queryKey: keywordGenerationKeys.status(projectId),
    queryFn: () => getPrimaryKeywordsStatus(projectId),
    enabled: !!projectId,
    // Poll every 2 seconds while generating or pending, stop when complete/failed
    refetchInterval: (query) => {
      const data = query.state.data as PrimaryKeywordGenerationStatus | undefined;
      // Poll while generating
      if (data?.status === 'generating') {
        return 2000;
      }
      // Also poll while pending if we have pages to process (generation may be starting)
      if (data?.status === 'pending' && data?.total > 0) {
        return 2000;
      }
      return false;
    },
  });

  const startGenerationMutation = useStartKeywordGeneration();

  // Calculate progress percentage
  const total = status.data?.total ?? 0;
  const completed = status.data?.completed ?? 0;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;

  return {
    // Status data
    status: status.data?.status ?? 'pending',
    total,
    completed,
    failed: status.data?.failed ?? 0,
    progress,
    currentPage: status.data?.current_page,
    error: status.data?.error,

    // Query states
    isLoading: status.isLoading,
    isError: status.isError,
    isGenerating: status.data?.status === 'generating',
    isComplete: status.data?.status === 'completed',
    isFailed: status.data?.status === 'failed',

    // Actions
    startGeneration: () => startGenerationMutation.mutate(projectId),
    startGenerationAsync: () => startGenerationMutation.mutateAsync(projectId),
    isStarting: startGenerationMutation.isPending,
    startError: startGenerationMutation.error,

    // Refetch and invalidate
    refetch: status.refetch,
    invalidate: () =>
      queryClient.invalidateQueries({
        queryKey: keywordGenerationKeys.status(projectId),
      }),
    invalidatePagesWithKeywords: () =>
      queryClient.invalidateQueries({
        queryKey: keywordGenerationKeys.pagesWithKeywords(projectId),
      }),
  };
}
