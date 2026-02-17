/**
 * TanStack Query hooks for Reddit accounts, project config, and post discovery.
 *
 * Query keys:
 * - ['reddit-accounts', params] for the account list
 * - ['reddit-config', projectId] for a project's Reddit config
 * - ['reddit-discovery-status', projectId] for discovery pipeline progress
 * - ['reddit-posts', projectId, params] for discovered posts
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  fetchRedditAccounts,
  createRedditAccount,
  updateRedditAccount,
  deleteRedditAccount,
  fetchRedditConfig,
  upsertRedditConfig,
  triggerRedditDiscovery,
  fetchDiscoveryStatus,
  fetchRedditPosts,
  updateRedditPostStatus,
  bulkUpdateRedditPosts,
  type RedditAccount,
  type RedditAccountCreate,
  type RedditAccountUpdate,
  type RedditProjectConfig,
  type RedditProjectConfigCreate,
  type DiscoveryTriggerResponse,
  type DiscoveryStatus,
  type RedditDiscoveredPost,
  type RedditPostsFilterParams,
  type RedditPostUpdateRequest,
  type RedditBulkPostActionRequest,
} from '@/lib/api';

// =============================================================================
// QUERY KEY FACTORY
// =============================================================================

export const redditKeys = {
  accounts: (params?: { niche?: string; status?: string; warmup_stage?: string }) =>
    ['reddit-accounts', params] as const,
  config: (projectId: string) =>
    ['reddit-config', projectId] as const,
  discoveryStatus: (projectId: string) =>
    ['reddit-discovery-status', projectId] as const,
  posts: (projectId: string, params?: RedditPostsFilterParams) =>
    ['reddit-posts', projectId, params] as const,
};

// =============================================================================
// ACCOUNT HOOKS
// =============================================================================

/**
 * Fetch all Reddit accounts with optional filters.
 */
export function useRedditAccounts(
  params?: { niche?: string; status?: string; warmup_stage?: string },
  options?: { enabled?: boolean }
): UseQueryResult<RedditAccount[]> {
  return useQuery({
    queryKey: redditKeys.accounts(params),
    queryFn: () => fetchRedditAccounts(params),
    enabled: options?.enabled,
  });
}

/**
 * Create a new Reddit account.
 * Invalidates the accounts list on success.
 */
export function useCreateRedditAccount(): UseMutationResult<
  RedditAccount,
  Error,
  RedditAccountCreate
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RedditAccountCreate) => createRedditAccount(data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-accounts'],
      });
    },
  });
}

/**
 * Update a Reddit account.
 * Invalidates the accounts list on success.
 */
export function useUpdateRedditAccount(): UseMutationResult<
  RedditAccount,
  Error,
  { accountId: string; data: RedditAccountUpdate }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ accountId, data }: { accountId: string; data: RedditAccountUpdate }) =>
      updateRedditAccount(accountId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-accounts'],
      });
    },
  });
}

/**
 * Delete a Reddit account with optimistic removal from cache.
 * Removes the account from cache immediately, rolls back on error.
 */
export function useDeleteRedditAccount(): UseMutationResult<
  void,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: string) => deleteRedditAccount(accountId),
    onMutate: async (accountId) => {
      // Cancel in-flight refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries({ queryKey: ['reddit-accounts'] });

      // Snapshot all account queries for rollback
      const previousQueries = queryClient.getQueriesData<RedditAccount[]>({
        queryKey: ['reddit-accounts'],
      });

      // Optimistically remove the account from all cached account lists
      queryClient.setQueriesData<RedditAccount[]>(
        { queryKey: ['reddit-accounts'] },
        (old) => old?.filter((a) => a.id !== accountId),
      );

      return { previousQueries };
    },
    onError: (_err, _accountId, context) => {
      // Roll back to snapshots on error
      if (context?.previousQueries) {
        for (const [queryKey, data] of context.previousQueries) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSettled: () => {
      // Always refetch after mutation settles to sync with server
      queryClient.invalidateQueries({
        queryKey: ['reddit-accounts'],
      });
    },
  });
}

// =============================================================================
// PROJECT CONFIG HOOKS
// =============================================================================

/**
 * Fetch Reddit config for a project.
 * Only enabled when projectId is truthy.
 */
export function useRedditConfig(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<RedditProjectConfig | null> {
  return useQuery({
    queryKey: redditKeys.config(projectId),
    queryFn: () => fetchRedditConfig(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Create or update Reddit config for a project (upsert).
 * Invalidates the config query on success.
 */
export function useUpsertRedditConfig(projectId: string): UseMutationResult<
  RedditProjectConfig,
  Error,
  RedditProjectConfigCreate
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RedditProjectConfigCreate) =>
      upsertRedditConfig(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: redditKeys.config(projectId),
      });
    },
  });
}

// =============================================================================
// DISCOVERY HOOKS
// =============================================================================

/**
 * Trigger Reddit post discovery for a project.
 * Invalidates discovery status and posts on success.
 */
export function useTriggerDiscovery(projectId: string): UseMutationResult<
  DiscoveryTriggerResponse,
  Error,
  string | undefined
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (timeRange?: string) =>
      triggerRedditDiscovery(projectId, timeRange),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: redditKeys.discoveryStatus(projectId),
      });
    },
  });
}

/**
 * Poll discovery pipeline status for a project.
 * Automatically polls every 2 seconds when status is active (searching/scoring/storing).
 */
export function useDiscoveryStatus(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<DiscoveryStatus> {
  return useQuery({
    queryKey: redditKeys.discoveryStatus(projectId),
    queryFn: () => fetchDiscoveryStatus(projectId),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'searching' || status === 'scoring' || status === 'storing') {
        return 2000;
      }
      return false;
    },
  });
}

/**
 * Fetch discovered Reddit posts for a project with optional filters.
 */
export function useRedditPosts(
  projectId: string,
  params?: RedditPostsFilterParams,
  options?: { enabled?: boolean }
): UseQueryResult<RedditDiscoveredPost[]> {
  return useQuery({
    queryKey: redditKeys.posts(projectId, params),
    queryFn: () => fetchRedditPosts(projectId, params),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Update a single post's filter status with optimistic update.
 * Immediately updates the post in cache, rolls back on error.
 */
export function useUpdatePostStatus(projectId: string): UseMutationResult<
  RedditDiscoveredPost,
  Error,
  { postId: string; data: RedditPostUpdateRequest }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ postId, data }: { postId: string; data: RedditPostUpdateRequest }) =>
      updateRedditPostStatus(projectId, postId, data),
    onMutate: async ({ postId, data }) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-posts', projectId] });

      const previousQueries = queryClient.getQueriesData<RedditDiscoveredPost[]>({
        queryKey: ['reddit-posts', projectId],
      });

      queryClient.setQueriesData<RedditDiscoveredPost[]>(
        { queryKey: ['reddit-posts', projectId] },
        (old) =>
          old?.map((post) =>
            post.id === postId ? { ...post, filter_status: data.filter_status } : post
          ),
      );

      return { previousQueries };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousQueries) {
        for (const [queryKey, data] of context.previousQueries) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-posts', projectId],
      });
    },
  });
}

/**
 * Bulk update filter status for multiple posts.
 * Invalidates posts query on success.
 */
export function useBulkUpdatePosts(projectId: string): UseMutationResult<
  { updated_count: number },
  Error,
  RedditBulkPostActionRequest
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RedditBulkPostActionRequest) =>
      bulkUpdateRedditPosts(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-posts', projectId],
      });
    },
  });
}
