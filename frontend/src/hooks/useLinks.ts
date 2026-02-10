/**
 * TanStack Query hooks for internal linking operations.
 *
 * Query keys:
 * - ['projects', projectId, 'links', 'plan-status', scope, clusterId?] for plan status polling
 * - ['projects', projectId, 'links', 'map', scope, clusterId?] for link map overview
 * - ['projects', projectId, 'links', 'page', pageId] for page link detail
 * - ['projects', projectId, 'links', 'suggestions', targetPageId] for anchor suggestions
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  planLinks,
  getPlanStatus,
  getLinkMap,
  getPageLinks,
  addLink,
  removeLink,
  editLink,
  getAnchorSuggestions,
  type PlanStatus,
  type LinkMap,
  type PageLinks,
  type InternalLink,
  type AddLinkRequest,
  type EditLinkRequest,
  type AnchorSuggestions,
} from '@/lib/api';

// Query keys factory
export const linkKeys = {
  planStatus: (projectId: string, scope: string, clusterId?: string) =>
    ['projects', projectId, 'links', 'plan-status', scope, clusterId] as const,
  map: (projectId: string, scope: string, clusterId?: string) =>
    ['projects', projectId, 'links', 'map', scope, clusterId] as const,
  page: (projectId: string, pageId: string) =>
    ['projects', projectId, 'links', 'page', pageId] as const,
  suggestions: (projectId: string, targetPageId: string) =>
    ['projects', projectId, 'links', 'suggestions', targetPageId] as const,
  allForProject: (projectId: string) =>
    ['projects', projectId, 'links'] as const,
};

// Mutation input types
interface PlanLinksInput {
  projectId: string;
  scope: 'onboarding' | 'cluster';
  clusterId?: string;
}

interface AddLinkInput {
  projectId: string;
  data: AddLinkRequest;
}

interface RemoveLinkInput {
  projectId: string;
  linkId: string;
}

interface EditLinkInput {
  projectId: string;
  linkId: string;
  data: EditLinkRequest;
}

/**
 * Trigger link planning for a project scope.
 * Invalidates plan status on success to start polling.
 */
export function usePlanLinks(): UseMutationResult<
  PlanStatus,
  Error,
  PlanLinksInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, scope, clusterId }: PlanLinksInput) =>
      planLinks(projectId, scope, clusterId),
    onSuccess: (_data, { projectId, scope, clusterId }) => {
      queryClient.invalidateQueries({
        queryKey: linkKeys.planStatus(projectId, scope, clusterId),
      });
    },
  });
}

/**
 * Poll link planning status for a project scope.
 * Refetches every 2 seconds while status is 'planning'.
 * Stops polling when status is 'complete' or 'failed'.
 */
export function usePlanStatus(
  projectId: string,
  scope: 'onboarding' | 'cluster',
  clusterId?: string,
  enabled?: boolean
): UseQueryResult<PlanStatus> {
  return useQuery({
    queryKey: linkKeys.planStatus(projectId, scope, clusterId),
    queryFn: () => getPlanStatus(projectId, scope, clusterId),
    enabled: enabled ?? !!projectId,
    refetchInterval: (query) => {
      const data = query.state.data as PlanStatus | undefined;
      if (data?.status === 'planning') {
        return 2000;
      }
      return false;
    },
  });
}

/**
 * Fetch the link map overview for a project scope.
 */
export function useLinkMap(
  projectId: string,
  scope: 'onboarding' | 'cluster' = 'onboarding',
  clusterId?: string
): UseQueryResult<LinkMap> {
  return useQuery({
    queryKey: linkKeys.map(projectId, scope, clusterId),
    queryFn: () => getLinkMap(projectId, scope, clusterId),
    enabled: !!projectId,
  });
}

/**
 * Fetch all links for a specific page with diversity metrics.
 */
export function usePageLinks(
  projectId: string,
  pageId: string
): UseQueryResult<PageLinks> {
  return useQuery({
    queryKey: linkKeys.page(projectId, pageId),
    queryFn: () => getPageLinks(projectId, pageId),
    enabled: !!projectId && !!pageId,
  });
}

/**
 * Manually add an internal link.
 * Invalidates link map and page links on success.
 */
export function useAddLink(): UseMutationResult<
  InternalLink,
  Error,
  AddLinkInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: AddLinkInput) =>
      addLink(projectId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: linkKeys.allForProject(projectId),
      });
    },
  });
}

/**
 * Remove a discretionary internal link.
 * Invalidates link map and page links on success.
 */
export function useRemoveLink(): UseMutationResult<
  void,
  Error,
  RemoveLinkInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, linkId }: RemoveLinkInput) =>
      removeLink(projectId, linkId),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: linkKeys.allForProject(projectId),
      });
    },
  });
}

/**
 * Edit an existing link's anchor text and type.
 * Invalidates page links on success.
 */
export function useEditLink(): UseMutationResult<
  InternalLink,
  Error,
  EditLinkInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, linkId, data }: EditLinkInput) =>
      editLink(projectId, linkId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: linkKeys.allForProject(projectId),
      });
    },
  });
}

/**
 * Fetch anchor text suggestions for a target page.
 */
export function useAnchorSuggestions(
  projectId: string,
  targetPageId: string
): UseQueryResult<AnchorSuggestions> {
  return useQuery({
    queryKey: linkKeys.suggestions(projectId, targetPageId),
    queryFn: () => getAnchorSuggestions(projectId, targetPageId),
    enabled: !!projectId && !!targetPageId,
  });
}
