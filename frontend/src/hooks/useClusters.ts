/**
 * TanStack Query hooks for keyword cluster operations.
 *
 * Query keys:
 * - ['projects', projectId, 'clusters'] for the cluster list
 * - ['projects', projectId, 'clusters', clusterId] for a single cluster with pages
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  createCluster,
  getClusters,
  getCluster,
  updateClusterPage,
  bulkApproveCluster,
  deleteCluster,
  type Cluster,
  type ClusterCreate,
  type ClusterListItem,
  type ClusterPage,
  type ClusterPageUpdate,
  type ClusterBulkApproveResponse,
} from '@/lib/api';

// Query keys factory
export const clusterKeys = {
  list: (projectId: string) => ['projects', projectId, 'clusters'] as const,
  detail: (projectId: string, clusterId: string) =>
    ['projects', projectId, 'clusters', clusterId] as const,
};

// Mutation input types
interface CreateClusterInput {
  projectId: string;
  data: ClusterCreate;
}

interface UpdateClusterPageInput {
  projectId: string;
  clusterId: string;
  pageId: string;
  data: ClusterPageUpdate;
}

interface BulkApproveClusterInput {
  projectId: string;
  clusterId: string;
}

interface DeleteClusterInput {
  projectId: string;
  clusterId: string;
}

/**
 * Create a new keyword cluster from a seed keyword.
 * Invalidates the cluster list on success.
 */
export function useCreateCluster(): UseMutationResult<
  Cluster,
  Error,
  CreateClusterInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: CreateClusterInput) =>
      createCluster(projectId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: clusterKeys.list(projectId),
      });
    },
  });
}

/**
 * Fetch all clusters for a project (summary view with counts).
 */
export function useClusters(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<ClusterListItem[]> {
  return useQuery({
    queryKey: clusterKeys.list(projectId),
    queryFn: () => getClusters(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Fetch a single cluster with all its pages.
 */
export function useCluster(
  projectId: string,
  clusterId: string,
  options?: { enabled?: boolean }
): UseQueryResult<Cluster> {
  return useQuery({
    queryKey: clusterKeys.detail(projectId, clusterId),
    queryFn: () => getCluster(projectId, clusterId),
    enabled: options?.enabled ?? (!!projectId && !!clusterId),
  });
}

/**
 * Update editable fields on a cluster page.
 * Optimistically updates the cluster detail cache.
 */
export function useUpdateClusterPage(): UseMutationResult<
  ClusterPage,
  Error,
  UpdateClusterPageInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, clusterId, pageId, data }: UpdateClusterPageInput) =>
      updateClusterPage(projectId, clusterId, pageId, data),
    onMutate: async ({ projectId, clusterId, pageId, data }) => {
      const queryKey = clusterKeys.detail(projectId, clusterId);
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Cluster>(queryKey);

      if (previous) {
        queryClient.setQueryData<Cluster>(queryKey, {
          ...previous,
          pages: previous.pages.map((page) =>
            page.id === pageId ? { ...page, ...data } : page
          ),
        });
      }

      return { previous, queryKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
    },
    onSettled: (_data, _error, { projectId, clusterId }) => {
      queryClient.invalidateQueries({
        queryKey: clusterKeys.detail(projectId, clusterId),
      });
    },
  });
}

/**
 * Bulk-approve a cluster, bridging approved pages into the content pipeline.
 * Invalidates both the cluster detail and list on success.
 */
export function useBulkApproveCluster(): UseMutationResult<
  ClusterBulkApproveResponse,
  Error,
  BulkApproveClusterInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, clusterId }: BulkApproveClusterInput) =>
      bulkApproveCluster(projectId, clusterId),
    onSuccess: (_data, { projectId, clusterId }) => {
      queryClient.invalidateQueries({
        queryKey: clusterKeys.detail(projectId, clusterId),
      });
      queryClient.invalidateQueries({
        queryKey: clusterKeys.list(projectId),
      });
    },
  });
}

/**
 * Delete a cluster. Only allowed if status is before 'approved'.
 * Invalidates the cluster list on success.
 */
export function useDeleteCluster(): UseMutationResult<
  void,
  Error,
  DeleteClusterInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, clusterId }: DeleteClusterInput) =>
      deleteCluster(projectId, clusterId),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: clusterKeys.list(projectId),
      });
    },
  });
}
