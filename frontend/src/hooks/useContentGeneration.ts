/**
 * TanStack Query hooks for content generation operations.
 *
 * Query keys:
 * - ['projects', projectId, 'content-generation', 'status'] for generation status
 * - ['projects', projectId, 'pages', pageId, 'content'] for page content
 * - ['projects', projectId, 'pages', pageId, 'prompts'] for prompt logs
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  triggerContentGeneration,
  pollContentGenerationStatus,
  getPageContent,
  getPagePrompts,
  updatePageContent,
  approvePageContent,
  recheckPageContent,
  bulkApproveContent,
  type ContentGenerationTriggerResponse,
  type ContentGenerationStatus,
  type PageContentResponse,
  type PromptLogResponse,
  type ContentUpdateRequest,
  type ContentBulkApproveResponse,
} from '@/lib/api';

// Query keys factory
export const contentGenerationKeys = {
  status: (projectId: string) =>
    ['projects', projectId, 'content-generation', 'status'] as const,
  pageContent: (projectId: string, pageId: string) =>
    ['projects', projectId, 'pages', pageId, 'content'] as const,
  pagePrompts: (projectId: string, pageId: string) =>
    ['projects', projectId, 'pages', pageId, 'prompts'] as const,
};

/**
 * Poll content generation status for a project.
 * Refetches every 3 seconds while overall_status is 'generating'.
 */
export function useContentGenerationStatus(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<ContentGenerationStatus> {
  return useQuery({
    queryKey: contentGenerationKeys.status(projectId),
    queryFn: () => pollContentGenerationStatus(projectId),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: (query) => {
      const data = query.state.data as ContentGenerationStatus | undefined;
      if (data?.overall_status === 'generating') {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Fetch generated content for a specific page.
 */
export function usePageContent(
  projectId: string,
  pageId: string,
  options?: { enabled?: boolean }
): UseQueryResult<PageContentResponse> {
  return useQuery({
    queryKey: contentGenerationKeys.pageContent(projectId, pageId),
    queryFn: () => getPageContent(projectId, pageId),
    enabled: options?.enabled ?? (!!projectId && !!pageId),
  });
}

/**
 * Fetch prompt logs for a specific page.
 */
export function usePagePrompts(
  projectId: string,
  pageId: string,
  options?: { enabled?: boolean }
): UseQueryResult<PromptLogResponse[]> {
  return useQuery({
    queryKey: contentGenerationKeys.pagePrompts(projectId, pageId),
    queryFn: () => getPagePrompts(projectId, pageId),
    enabled: options?.enabled ?? (!!projectId && !!pageId),
  });
}

/**
 * Mutation to trigger content generation for a project.
 * Invalidates the status query on success to start polling.
 */
export function useTriggerContentGeneration(): UseMutationResult<
  ContentGenerationTriggerResponse,
  Error,
  { projectId: string; forceRefresh?: boolean; refreshBriefs?: boolean }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      forceRefresh,
      refreshBriefs,
    }: {
      projectId: string;
      forceRefresh?: boolean;
      refreshBriefs?: boolean;
    }) => triggerContentGeneration(projectId, { forceRefresh, refreshBriefs }),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.status(projectId),
      });
    },
  });
}

/**
 * Helper hook that manages the full content generation flow.
 * - Starts generation when triggered
 * - Polls for status every 3 seconds while generating
 * - Stops polling when status='complete' or status='failed'
 * - Returns status, progress, isGenerating, error
 * - Exposes startGeneration function
 */
export function useContentGeneration(projectId: string) {
  const queryClient = useQueryClient();

  const status = useContentGenerationStatus(projectId);
  const triggerMutation = useTriggerContentGeneration();

  const pagesTotal = status.data?.pages_total ?? 0;
  const pagesCompleted = status.data?.pages_completed ?? 0;
  const pagesFailed = status.data?.pages_failed ?? 0;
  const pagesApproved = status.data?.pages_approved ?? 0;
  const progress = pagesTotal > 0 ? Math.round((pagesCompleted / pagesTotal) * 100) : 0;

  return {
    // Status data
    overallStatus: status.data?.overall_status ?? 'idle',
    pagesTotal,
    pagesCompleted,
    pagesFailed,
    pagesApproved,
    progress,
    pages: status.data?.pages ?? [],

    // Query states
    isLoading: status.isLoading,
    isError: status.isError,
    isGenerating: status.data?.overall_status === 'generating',
    isComplete: status.data?.overall_status === 'complete',
    isFailed: status.data?.overall_status === 'failed',

    // Actions
    startGeneration: () => triggerMutation.mutate({ projectId }),
    startGenerationAsync: () => triggerMutation.mutateAsync({ projectId }),
    regenerate: (opts?: { refreshBriefs?: boolean }) =>
      triggerMutation.mutate({ projectId, forceRefresh: true, refreshBriefs: opts?.refreshBriefs }),
    regenerateAsync: (opts?: { refreshBriefs?: boolean }) =>
      triggerMutation.mutateAsync({ projectId, forceRefresh: true, refreshBriefs: opts?.refreshBriefs }),
    isStarting: triggerMutation.isPending,
    startError: triggerMutation.error,

    // Refetch and invalidate
    refetch: status.refetch,
    invalidate: () =>
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.status(projectId),
      }),
  };
}

// =============================================================================
// CONTENT EDITING / APPROVAL MUTATION HOOKS
// =============================================================================

/**
 * Mutation hook to update page content (partial update).
 * Invalidates the page content query on success.
 */
export function useUpdatePageContent(): UseMutationResult<
  PageContentResponse,
  Error,
  { projectId: string; pageId: string; data: ContentUpdateRequest }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      pageId,
      data,
    }: {
      projectId: string;
      pageId: string;
      data: ContentUpdateRequest;
    }) => updatePageContent(projectId, pageId, data),
    onSuccess: (_data, { projectId, pageId }) => {
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.pageContent(projectId, pageId),
      });
    },
  });
}

/**
 * Mutation hook to approve or unapprove page content.
 * Invalidates both the page content and generation status queries on success.
 */
export function useApprovePageContent(): UseMutationResult<
  PageContentResponse,
  Error,
  { projectId: string; pageId: string; value?: boolean }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      pageId,
      value = true,
    }: {
      projectId: string;
      pageId: string;
      value?: boolean;
    }) => approvePageContent(projectId, pageId, value),
    onSuccess: (_data, { projectId, pageId }) => {
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.pageContent(projectId, pageId),
      });
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.status(projectId),
      });
    },
  });
}

/**
 * Mutation hook to re-run quality checks on page content.
 * Invalidates the page content query on success.
 */
export function useRecheckPageContent(): UseMutationResult<
  PageContentResponse,
  Error,
  { projectId: string; pageId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, pageId }: { projectId: string; pageId: string }) =>
      recheckPageContent(projectId, pageId),
    onSuccess: (_data, { projectId, pageId }) => {
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.pageContent(projectId, pageId),
      });
    },
  });
}

/**
 * Mutation hook to bulk approve all eligible content in a project.
 * Invalidates the generation status query on success.
 */
export function useBulkApproveContent(): UseMutationResult<
  ContentBulkApproveResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId: string) => bulkApproveContent(projectId),
    onSuccess: (_data, projectId) => {
      queryClient.invalidateQueries({
        queryKey: contentGenerationKeys.status(projectId),
      });
    },
  });
}
