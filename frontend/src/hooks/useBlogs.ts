/**
 * TanStack Query hooks for blog campaign, content generation, link planning, and export.
 *
 * Query keys:
 * - ['projects', projectId, 'blogs'] for the blog campaign list
 * - ['projects', projectId, 'blogs', blogId] for a single campaign with posts
 * - ['projects', projectId, 'blogs', blogId, 'content-status'] for generation status
 * - ['projects', projectId, 'blogs', blogId, 'posts', postId, 'content'] for post content
 * - ['projects', projectId, 'blogs', blogId, 'posts', postId, 'link-status'] for link status
 * - ['projects', projectId, 'blogs', blogId, 'posts', postId, 'link-map'] for link map
 * - ['projects', projectId, 'blogs', blogId, 'export'] for campaign export
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  createBlogCampaign,
  getBlogCampaigns,
  getBlogCampaign,
  updateBlogPost,
  bulkApproveBlogPosts,
  deleteBlogCampaign,
  triggerBlogContentGeneration,
  getBlogContentStatus,
  getBlogPostContent,
  updateBlogPostContent,
  approveBlogPostContent,
  recheckBlogPostContent,
  bulkApproveBlogContent,
  triggerBlogLinkPlanning,
  getBlogLinkStatus,
  getBlogLinkMap,
  getBlogExport,
  downloadBlogPostHtml,
  type BlogCampaign,
  type BlogCampaignCreate,
  type BlogCampaignListItem,
  type BlogPost,
  type BlogPostUpdate,
  type BlogContentUpdate,
  type BlogContentGenerationStatus,
  type BlogContentTriggerResponse,
  type BlogBulkApproveResponse,
  type BlogLinkPlanTriggerResponse,
  type BlogExportItem,
  type BlogLinkStatusResponse,
  type BlogLinkMapResponse,
} from '@/lib/api';

// =============================================================================
// QUERY KEY FACTORY
// =============================================================================

export const blogKeys = {
  list: (projectId: string) =>
    ['projects', projectId, 'blogs'] as const,
  detail: (projectId: string, blogId: string) =>
    ['projects', projectId, 'blogs', blogId] as const,
  contentStatus: (projectId: string, blogId: string) =>
    ['projects', projectId, 'blogs', blogId, 'content-status'] as const,
  postContent: (projectId: string, blogId: string, postId: string) =>
    ['projects', projectId, 'blogs', blogId, 'posts', postId, 'content'] as const,
  linkStatus: (projectId: string, blogId: string, postId: string) =>
    ['projects', projectId, 'blogs', blogId, 'posts', postId, 'link-status'] as const,
  linkMap: (projectId: string, blogId: string, postId: string) =>
    ['projects', projectId, 'blogs', blogId, 'posts', postId, 'link-map'] as const,
  export: (projectId: string, blogId: string) =>
    ['projects', projectId, 'blogs', blogId, 'export'] as const,
};

// =============================================================================
// CAMPAIGN HOOKS
// =============================================================================

/**
 * Fetch all blog campaigns for a project (summary view with counts).
 */
export function useBlogCampaigns(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogCampaignListItem[]> {
  return useQuery({
    queryKey: blogKeys.list(projectId),
    queryFn: () => getBlogCampaigns(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Fetch a single blog campaign with all its posts.
 */
export function useBlogCampaign(
  projectId: string,
  blogId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogCampaign> {
  return useQuery({
    queryKey: blogKeys.detail(projectId, blogId),
    queryFn: () => getBlogCampaign(projectId, blogId),
    enabled: options?.enabled ?? (!!projectId && !!blogId),
  });
}

/**
 * Create a new blog campaign from a keyword cluster.
 * Invalidates the campaign list on success.
 */
export function useCreateBlogCampaign(): UseMutationResult<
  BlogCampaign,
  Error,
  { projectId: string; data: BlogCampaignCreate }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: { projectId: string; data: BlogCampaignCreate }) =>
      createBlogCampaign(projectId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.list(projectId),
      });
    },
  });
}

/**
 * Update keyword-level fields on a blog post.
 * Invalidates the campaign detail on success.
 */
export function useUpdateBlogPost(): UseMutationResult<
  BlogPost,
  Error,
  { projectId: string; blogId: string; postId: string; data: BlogPostUpdate }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
      data,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
      data: BlogPostUpdate;
    }) => updateBlogPost(projectId, blogId, postId, data),
    onMutate: async ({ projectId, blogId, postId, data }) => {
      // Cancel in-flight refetches so they don't overwrite our optimistic update
      const key = blogKeys.detail(projectId, blogId);
      await queryClient.cancelQueries({ queryKey: key });

      // Snapshot previous value for rollback
      const previous = queryClient.getQueryData<BlogCampaign>(key);

      // Optimistically update the post in the cached campaign
      if (previous) {
        queryClient.setQueryData<BlogCampaign>(key, {
          ...previous,
          posts: previous.posts.map((p) =>
            p.id === postId ? ({ ...p, ...data } as BlogPost) : p
          ),
        });
      }

      return { previous, key };
    },
    onError: (_err, _vars, context) => {
      // Roll back to snapshot on error
      if (context?.previous) {
        queryClient.setQueryData(context.key, context.previous);
      }
    },
    onSettled: (_data, _err, { projectId, blogId }) => {
      // Always refetch after mutation settles to sync with server
      queryClient.invalidateQueries({
        queryKey: blogKeys.detail(projectId, blogId),
      });
    },
  });
}

/**
 * Bulk approve all unapproved posts in a blog campaign.
 * Invalidates both the campaign detail and list on success.
 */
export function useBulkApproveBlogPosts(): UseMutationResult<
  { approved_count: number; campaign_status: string },
  Error,
  { projectId: string; blogId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, blogId }: { projectId: string; blogId: string }) =>
      bulkApproveBlogPosts(projectId, blogId),
    onSuccess: (_data, { projectId, blogId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.detail(projectId, blogId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.list(projectId),
      });
    },
  });
}

/**
 * Delete a blog campaign and all its posts.
 * Invalidates the campaign list on success.
 */
export function useDeleteBlogCampaign(): UseMutationResult<
  void,
  Error,
  { projectId: string; blogId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, blogId }: { projectId: string; blogId: string }) =>
      deleteBlogCampaign(projectId, blogId),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.list(projectId),
      });
    },
  });
}

// =============================================================================
// CONTENT GENERATION HOOKS
// =============================================================================

/**
 * Trigger blog content generation for all approved posts in a campaign.
 * Invalidates the content status query on success to start polling.
 */
export function useTriggerBlogContentGeneration(): UseMutationResult<
  BlogContentTriggerResponse,
  Error,
  { projectId: string; blogId: string; forceRefresh?: boolean }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, blogId, forceRefresh = false }: { projectId: string; blogId: string; forceRefresh?: boolean }) =>
      triggerBlogContentGeneration(projectId, blogId, forceRefresh),
    onSuccess: (_data, { projectId, blogId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.contentStatus(projectId, blogId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.detail(projectId, blogId),
      });
    },
  });
}

/**
 * Poll content generation status for a blog campaign.
 * Refetches every 3 seconds while overall_status is 'generating'.
 */
export function useBlogContentStatus(
  projectId: string,
  blogId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogContentGenerationStatus> {
  return useQuery({
    queryKey: blogKeys.contentStatus(projectId, blogId),
    queryFn: () => getBlogContentStatus(projectId, blogId),
    enabled: options?.enabled ?? (!!projectId && !!blogId),
    refetchInterval: (query) => {
      const data = query.state.data as BlogContentGenerationStatus | undefined;
      if (data?.overall_status === 'generating') {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Fetch full content for a specific blog post.
 */
export function useBlogPostContent(
  projectId: string,
  blogId: string,
  postId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogPost> {
  return useQuery({
    queryKey: blogKeys.postContent(projectId, blogId, postId),
    queryFn: () => getBlogPostContent(projectId, blogId, postId),
    enabled: options?.enabled ?? (!!projectId && !!blogId && !!postId),
  });
}

/**
 * Update content fields on a blog post.
 * Invalidates the post content and content status queries on success.
 */
export function useUpdateBlogPostContent(): UseMutationResult<
  BlogPost,
  Error,
  { projectId: string; blogId: string; postId: string; data: BlogContentUpdate }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
      data,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
      data: BlogContentUpdate;
    }) => updateBlogPostContent(projectId, blogId, postId, data),
    onSuccess: (_data, { projectId, blogId, postId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.postContent(projectId, blogId, postId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.contentStatus(projectId, blogId),
      });
    },
  });
}

/**
 * Approve or unapprove content for a blog post.
 * Invalidates post content, content status, and campaign detail on success.
 */
export function useApproveBlogPostContent(): UseMutationResult<
  BlogPost,
  Error,
  { projectId: string; blogId: string; postId: string; value?: boolean }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
      value = true,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
      value?: boolean;
    }) => approveBlogPostContent(projectId, blogId, postId, value),
    onSuccess: (_data, { projectId, blogId, postId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.postContent(projectId, blogId, postId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.contentStatus(projectId, blogId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.detail(projectId, blogId),
      });
    },
  });
}

/**
 * Re-run quality checks on current blog post content.
 * Invalidates the post content query on success.
 */
export function useRecheckBlogPostContent(): UseMutationResult<
  BlogPost,
  Error,
  { projectId: string; blogId: string; postId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
    }) => recheckBlogPostContent(projectId, blogId, postId),
    onSuccess: (_data, { projectId, blogId, postId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.postContent(projectId, blogId, postId),
      });
    },
  });
}

/**
 * Bulk approve all eligible blog posts (complete + QA passed) in a campaign.
 * Invalidates content status and campaign detail on success.
 */
export function useBulkApproveBlogContent(): UseMutationResult<
  BlogBulkApproveResponse,
  Error,
  { projectId: string; blogId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, blogId }: { projectId: string; blogId: string }) =>
      bulkApproveBlogContent(projectId, blogId),
    onSuccess: (_data, { projectId, blogId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.contentStatus(projectId, blogId),
      });
      queryClient.invalidateQueries({
        queryKey: blogKeys.detail(projectId, blogId),
      });
    },
  });
}

// =============================================================================
// LINK PLANNING HOOKS
// =============================================================================

/**
 * Trigger link planning for a blog post.
 * Invalidates the link status query on success to start polling.
 */
export function useTriggerBlogLinkPlanning(): UseMutationResult<
  BlogLinkPlanTriggerResponse,
  Error,
  { projectId: string; blogId: string; postId: string }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
    }) => triggerBlogLinkPlanning(projectId, blogId, postId),
    onSuccess: (_data, { projectId, blogId, postId }) => {
      queryClient.invalidateQueries({
        queryKey: blogKeys.linkStatus(projectId, blogId, postId),
      });
    },
  });
}

/**
 * Poll link planning status for a blog post.
 * Refetches every 3 seconds while status is 'planning'.
 */
export function useBlogLinkStatus(
  projectId: string,
  blogId: string,
  postId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogLinkStatusResponse> {
  return useQuery({
    queryKey: blogKeys.linkStatus(projectId, blogId, postId),
    queryFn: () => getBlogLinkStatus(projectId, blogId, postId),
    enabled: options?.enabled ?? (!!projectId && !!blogId && !!postId),
    refetchInterval: (query) => {
      const data = query.state.data as BlogLinkStatusResponse | undefined;
      if (data?.status === 'planning') {
        return 3000;
      }
      return false;
    },
  });
}

/**
 * Fetch the link map (all planned/injected links) for a blog post.
 */
export function useBlogLinkMap(
  projectId: string,
  blogId: string,
  postId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogLinkMapResponse> {
  return useQuery({
    queryKey: blogKeys.linkMap(projectId, blogId, postId),
    queryFn: () => getBlogLinkMap(projectId, blogId, postId),
    enabled: options?.enabled ?? (!!projectId && !!blogId && !!postId),
  });
}

// =============================================================================
// EXPORT HOOKS
// =============================================================================

/**
 * Fetch all approved blog posts formatted for export (clean HTML, metadata).
 */
export function useBlogExport(
  projectId: string,
  blogId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BlogExportItem[]> {
  return useQuery({
    queryKey: blogKeys.export(projectId, blogId),
    queryFn: () => getBlogExport(projectId, blogId),
    enabled: options?.enabled ?? (!!projectId && !!blogId),
  });
}

/**
 * Download a single blog post as an HTML file.
 */
export function useDownloadBlogPostHtml(): UseMutationResult<
  void,
  Error,
  { projectId: string; blogId: string; postId: string }
> {
  return useMutation({
    mutationFn: ({
      projectId,
      blogId,
      postId,
    }: {
      projectId: string;
      blogId: string;
      postId: string;
    }) => downloadBlogPostHtml(projectId, blogId, postId),
  });
}
