/**
 * TanStack Query hooks for Reddit accounts and project config.
 *
 * Query keys:
 * - ['reddit-accounts', params] for the account list
 * - ['reddit-config', projectId] for a project's Reddit config
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
  type RedditAccount,
  type RedditAccountCreate,
  type RedditAccountUpdate,
  type RedditProjectConfig,
  type RedditProjectConfigCreate,
} from '@/lib/api';

// =============================================================================
// QUERY KEY FACTORY
// =============================================================================

export const redditKeys = {
  accounts: (params?: { niche?: string; status?: string; warmup_stage?: string }) =>
    ['reddit-accounts', params] as const,
  config: (projectId: string) =>
    ['reddit-config', projectId] as const,
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
): UseQueryResult<RedditProjectConfig> {
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
