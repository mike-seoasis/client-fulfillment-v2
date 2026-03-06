/**
 * TanStack Query hooks for Shopify integration.
 *
 * Query keys:
 * - ['shopify-status', projectId] for connection status
 * - ['shopify-pages', projectId, type, page, search] for paginated pages
 * - ['shopify-page-counts', projectId] for category counts
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
  type UseMutationResult,
} from '@tanstack/react-query';
import {
  getShopifyStatus,
  getShopifyPages,
  getShopifyPageCounts,
  triggerShopifySync,
  disconnectShopify,
  type ShopifyStatus,
  type ShopifyPagesResponse,
  type ShopifyPageCounts,
} from '@/lib/api';

// Query keys factory
export const shopifyKeys = {
  status: (projectId: string) => ['shopify-status', projectId] as const,
  pages: (projectId: string, type: string, page: number, search: string) =>
    ['shopify-pages', projectId, type, page, search] as const,
  pageCounts: (projectId: string) => ['shopify-page-counts', projectId] as const,
};

/**
 * Fetch Shopify connection status for a project.
 */
export function useShopifyStatus(
  projectId: string,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<ShopifyStatus> {
  return useQuery({
    queryKey: shopifyKeys.status(projectId),
    queryFn: () => getShopifyStatus(projectId),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: options?.refetchInterval,
  });
}

/**
 * Fetch paginated Shopify pages for a project, filtered by type.
 */
export function useShopifyPages(
  projectId: string,
  type: string,
  page: number = 1,
  search: string = '',
  options?: { enabled?: boolean }
): UseQueryResult<ShopifyPagesResponse> {
  return useQuery({
    queryKey: shopifyKeys.pages(projectId, type, page, search),
    queryFn: () => getShopifyPages(projectId, { type, page, per_page: 25, search }),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Fetch page counts per category for a project.
 */
export function useShopifyPageCounts(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<ShopifyPageCounts> {
  return useQuery({
    queryKey: shopifyKeys.pageCounts(projectId),
    queryFn: () => getShopifyPageCounts(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Trigger an immediate Shopify sync. Invalidates status, pages, and counts on success.
 */
export function useShopifySync(
  projectId: string
): UseMutationResult<{ status: string }, Error, void> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => triggerShopifySync(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: shopifyKeys.status(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: ['shopify-pages', projectId],
      });
      queryClient.invalidateQueries({
        queryKey: shopifyKeys.pageCounts(projectId),
      });
    },
  });
}

/**
 * Disconnect Shopify from a project. Invalidates all Shopify queries on success.
 */
export function useDisconnectShopify(
  projectId: string
): UseMutationResult<void, Error, void> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => disconnectShopify(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: shopifyKeys.status(projectId),
      });
      queryClient.invalidateQueries({
        queryKey: ['shopify-pages', projectId],
      });
      queryClient.invalidateQueries({
        queryKey: shopifyKeys.pageCounts(projectId),
      });
    },
  });
}
