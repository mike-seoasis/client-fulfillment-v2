/**
 * TanStack Query hooks for Reddit accounts, project config, and post discovery.
 *
 * Query keys:
 * - ['reddit-accounts', params] for the account list
 * - ['reddit-config', projectId] for a project's Reddit config
 * - ['reddit-discovery-status', projectId] for discovery pipeline progress
 * - ['reddit-posts', projectId, params] for discovered posts
 */

import { useEffect, useRef } from 'react';
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
  deleteRedditConfig,
  triggerRedditDiscovery,
  fetchDiscoveryStatus,
  fetchRedditPosts,
  updateRedditPostStatus,
  bulkUpdateRedditPosts,
  generateComment,
  generateBatch,
  fetchGenerationStatus,
  fetchComments,
  updateComment,
  deleteComment,
  revertCommentToDraft,
  fetchCommentQueue,
  approveQueueComment,
  rejectQueueComment,
  bulkApproveQueueComments,
  bulkRejectQueueComments,
  fetchRedditProjects,
  fetchCrowdReplyBalance,
  submitComments,
  type RedditAccount,
  type RedditAccountCreate,
  type RedditAccountUpdate,
  type RedditProjectConfig,
  type RedditProjectConfigCreate,
  type RedditProjectListResponse,
  type DiscoveryTriggerResponse,
  type DiscoveryStatus,
  type RedditDiscoveredPost,
  type RedditPostsFilterParams,
  type RedditPostUpdateRequest,
  type RedditBulkPostActionRequest,
  type RedditCommentResponse,
  type BatchGenerateResponse,
  type GenerationStatusResponse,
  type RedditCommentUpdateRequest,
  type CommentQueueParams,
  type CommentQueueResponse,
  type CrowdReplyBalanceResponse,
  type CommentSubmitResponse,
} from '@/lib/api';

// =============================================================================
// QUERY KEY FACTORY
// =============================================================================

export const redditKeys = {
  projects: () => ['reddit-projects'] as const,
  accounts: (params?: { niche?: string; status?: string; warmup_stage?: string }) =>
    ['reddit-accounts', params] as const,
  config: (projectId: string) =>
    ['reddit-config', projectId] as const,
  discoveryStatus: (projectId: string) =>
    ['reddit-discovery-status', projectId] as const,
  posts: (projectId: string, params?: RedditPostsFilterParams) =>
    ['reddit-posts', projectId, params] as const,
  comments: (projectId: string, filters?: { status?: string; post_id?: string }) =>
    ['reddit-comments', projectId, filters] as const,
  generationStatus: (projectId: string) =>
    ['reddit-generation-status', projectId] as const,
  commentQueue: (params?: CommentQueueParams) =>
    ['reddit-comment-queue', params] as const,
  balance: () => ['reddit-crowdreply-balance'] as const,
};

// =============================================================================
// REDDIT PROJECTS HOOK (dashboard)
// =============================================================================

/**
 * Fetch projects with Reddit configured (for the Reddit dashboard).
 */
export function useRedditProjects(
  options?: { enabled?: boolean }
): UseQueryResult<RedditProjectListResponse> {
  return useQuery({
    queryKey: redditKeys.projects(),
    queryFn: () => fetchRedditProjects(),
    enabled: options?.enabled,
  });
}

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

/**
 * Delete Reddit config (and associated posts/comments) for a project.
 * Does NOT delete the parent AI SEO project.
 */
export function useDeleteRedditConfig(projectId: string): UseMutationResult<
  void,
  Error,
  void
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => deleteRedditConfig(projectId),
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
  const queryClient = useQueryClient();
  const prevStatusRef = useRef<string>();

  const query = useQuery({
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

  // Auto-refresh posts when discovery transitions to "complete"
  useEffect(() => {
    const currentStatus = query.data?.status;
    if (
      prevStatusRef.current &&
      prevStatusRef.current !== 'complete' &&
      currentStatus === 'complete'
    ) {
      queryClient.invalidateQueries({ queryKey: ['reddit-posts', projectId] });
    }
    prevStatusRef.current = currentStatus;
  }, [query.data?.status, queryClient, projectId]);

  return query;
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

// =============================================================================
// COMMENT GENERATION HOOKS
// =============================================================================

/**
 * Fetch generated comments for a project with optional filters.
 */
export function useComments(
  projectId: string,
  filters?: { status?: string; post_id?: string },
  options?: { enabled?: boolean }
): UseQueryResult<RedditCommentResponse[]> {
  return useQuery({
    queryKey: redditKeys.comments(projectId, filters),
    queryFn: () => fetchComments(projectId, filters),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Poll batch generation status for a project.
 * Automatically polls every 2 seconds when status is "generating".
 * Invalidates comments query when generation transitions to "complete".
 */
export function useGenerationStatus(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<GenerationStatusResponse> {
  const queryClient = useQueryClient();
  const prevStatusRef = useRef<string>();

  const query = useQuery({
    queryKey: redditKeys.generationStatus(projectId),
    queryFn: () => fetchGenerationStatus(projectId),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'generating') {
        return 2000;
      }
      return false;
    },
  });

  // Auto-refresh comments when generation transitions to "complete"
  useEffect(() => {
    const currentStatus = query.data?.status;
    if (
      prevStatusRef.current &&
      prevStatusRef.current !== 'complete' &&
      currentStatus === 'complete'
    ) {
      queryClient.invalidateQueries({ queryKey: ['reddit-comments', projectId] });
    }
    prevStatusRef.current = currentStatus;
  }, [query.data?.status, queryClient, projectId]);

  return query;
}

/**
 * Generate a comment for a single Reddit post.
 * Invalidates comments query on success.
 */
export function useGenerateComment(projectId: string): UseMutationResult<
  RedditCommentResponse,
  Error,
  { postId: string; isPromotional?: boolean }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ postId, isPromotional }: { postId: string; isPromotional?: boolean }) =>
      generateComment(projectId, postId, isPromotional),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-comments', projectId],
      });
    },
  });
}

/**
 * Trigger batch comment generation for a project.
 * Invalidates generation status on success.
 */
export function useGenerateBatch(projectId: string): UseMutationResult<
  BatchGenerateResponse,
  Error,
  string[] | undefined
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (postIds?: string[]) =>
      generateBatch(projectId, postIds),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: redditKeys.generationStatus(projectId),
      });
    },
  });
}

/**
 * Update a comment's body text.
 * Invalidates comments query on success.
 */
export function useUpdateComment(projectId: string): UseMutationResult<
  RedditCommentResponse,
  Error,
  { commentId: string; data: RedditCommentUpdateRequest }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ commentId, data }: { commentId: string; data: RedditCommentUpdateRequest }) =>
      updateComment(projectId, commentId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-comments', projectId],
      });
    },
  });
}

/**
 * Delete a draft comment with optimistic removal.
 * Removes from cache immediately, rolls back on error.
 */
export function useDeleteComment(projectId: string): UseMutationResult<
  void,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (commentId: string) => deleteComment(projectId, commentId),
    onMutate: async (commentId) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-comments', projectId] });

      const previousQueries = queryClient.getQueriesData<RedditCommentResponse[]>({
        queryKey: ['reddit-comments', projectId],
      });

      queryClient.setQueriesData<RedditCommentResponse[]>(
        { queryKey: ['reddit-comments', projectId] },
        (old) => old?.filter((c) => c.id !== commentId),
      );

      return { previousQueries };
    },
    onError: (_err, _commentId, context) => {
      if (context?.previousQueries) {
        for (const [queryKey, data] of context.previousQueries) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-comments', projectId],
      });
    },
  });
}

/**
 * Revert an approved/rejected comment back to draft.
 */
export function useRevertComment(projectId: string): UseMutationResult<
  RedditCommentResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (commentId: string) => revertCommentToDraft(projectId, commentId),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: ['reddit-comments', projectId],
      });
    },
  });
}

// =============================================================================
// COMMENT QUEUE HOOKS (cross-project)
// =============================================================================

/**
 * Fetch the cross-project comment queue with optional filters.
 * Auto-polls every 5s when there are submitting comments.
 */
export function useCommentQueue(
  params?: CommentQueueParams,
  options?: { enabled?: boolean }
): UseQueryResult<CommentQueueResponse> {
  return useQuery({
    queryKey: redditKeys.commentQueue(params),
    queryFn: () => fetchCommentQueue(params),
    enabled: options?.enabled,
    refetchInterval: (query) => {
      const counts = query.state.data?.counts;
      if (counts && counts.submitting > 0) {
        return 5000;
      }
      return false;
    },
  });
}

/**
 * Approve a comment with optimistic removal from the queue cache.
 */
export function useApproveComment(): UseMutationResult<
  RedditCommentResponse,
  Error,
  { projectId: string; commentId: string; body?: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentId, body }) =>
      approveQueueComment(projectId, commentId, body),
    onMutate: async ({ commentId }) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-comment-queue'] });

      const previousQueries = queryClient.getQueriesData<CommentQueueResponse>({
        queryKey: ['reddit-comment-queue'],
      });

      queryClient.setQueriesData<CommentQueueResponse>(
        { queryKey: ['reddit-comment-queue'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.filter((c) => c.id !== commentId),
            total: old.total - 1,
            counts: {
              ...old.counts,
              draft: Math.max(0, old.counts.draft - 1),
              approved: old.counts.approved + 1,
            },
          };
        },
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
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
    },
  });
}

/**
 * Reject a comment with optimistic removal from the queue cache.
 */
export function useRejectComment(): UseMutationResult<
  RedditCommentResponse,
  Error,
  { projectId: string; commentId: string; reason: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentId, reason }) =>
      rejectQueueComment(projectId, commentId, reason),
    onMutate: async ({ commentId }) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-comment-queue'] });

      const previousQueries = queryClient.getQueriesData<CommentQueueResponse>({
        queryKey: ['reddit-comment-queue'],
      });

      queryClient.setQueriesData<CommentQueueResponse>(
        { queryKey: ['reddit-comment-queue'] },
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.filter((c) => c.id !== commentId),
            total: old.total - 1,
            counts: {
              ...old.counts,
              draft: Math.max(0, old.counts.draft - 1),
              rejected: old.counts.rejected + 1,
            },
          };
        },
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
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
    },
  });
}

/**
 * Bulk approve comments with optimistic removal from the queue cache.
 */
export function useBulkApprove(): UseMutationResult<
  { approved_count: number },
  Error,
  { projectId: string; commentIds: string[] }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentIds }) =>
      bulkApproveQueueComments(projectId, commentIds),
    onMutate: async ({ commentIds }) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-comment-queue'] });

      const previousQueries = queryClient.getQueriesData<CommentQueueResponse>({
        queryKey: ['reddit-comment-queue'],
      });

      const idSet = new Set(commentIds);
      queryClient.setQueriesData<CommentQueueResponse>(
        { queryKey: ['reddit-comment-queue'] },
        (old) => {
          if (!old) return old;
          const removed = old.items.filter((c) => idSet.has(c.id)).length;
          return {
            ...old,
            items: old.items.filter((c) => !idSet.has(c.id)),
            total: old.total - removed,
            counts: {
              ...old.counts,
              draft: Math.max(0, old.counts.draft - removed),
              approved: old.counts.approved + removed,
            },
          };
        },
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
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
    },
  });
}

/**
 * Bulk reject comments with optimistic removal from the queue cache.
 */
export function useBulkReject(): UseMutationResult<
  { rejected_count: number },
  Error,
  { projectId: string; commentIds: string[]; reason: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentIds, reason }) =>
      bulkRejectQueueComments(projectId, commentIds, reason),
    onMutate: async ({ commentIds }) => {
      await queryClient.cancelQueries({ queryKey: ['reddit-comment-queue'] });

      const previousQueries = queryClient.getQueriesData<CommentQueueResponse>({
        queryKey: ['reddit-comment-queue'],
      });

      const idSet = new Set(commentIds);
      queryClient.setQueriesData<CommentQueueResponse>(
        { queryKey: ['reddit-comment-queue'] },
        (old) => {
          if (!old) return old;
          const removed = old.items.filter((c) => idSet.has(c.id)).length;
          return {
            ...old,
            items: old.items.filter((c) => !idSet.has(c.id)),
            total: old.total - removed,
            counts: {
              ...old.counts,
              draft: Math.max(0, old.counts.draft - removed),
              rejected: old.counts.rejected + removed,
            },
          };
        },
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
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
    },
  });
}

// =============================================================================
// CROWDREPLY HOOKS
// =============================================================================

/**
 * Fetch the CrowdReply account balance.
 * Stale for 60s to avoid excessive polling.
 */
export function useCrowdReplyBalance(
  options?: { enabled?: boolean }
): UseQueryResult<CrowdReplyBalanceResponse> {
  return useQuery({
    queryKey: redditKeys.balance(),
    queryFn: () => fetchCrowdReplyBalance(),
    enabled: options?.enabled,
    staleTime: 60_000,
  });
}

/**
 * Revert a comment back to draft from the cross-project queue.
 */
export function useRevertQueueComment(): UseMutationResult<
  RedditCommentResponse,
  Error,
  { projectId: string; commentId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentId }) =>
      revertCommentToDraft(projectId, commentId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
    },
  });
}

/**
 * Submit approved comments to CrowdReply.
 * Invalidates comment queue and balance on success.
 */
export function useSubmitComments(): UseMutationResult<
  CommentSubmitResponse,
  Error,
  { projectId: string; commentIds?: string[]; upvotesPerComment?: number }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, commentIds, upvotesPerComment }) =>
      submitComments(projectId, commentIds, upvotesPerComment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reddit-comment-queue'] });
      queryClient.invalidateQueries({ queryKey: redditKeys.balance() });
    },
  });
}
