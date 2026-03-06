import { useMutation, useQueryClient } from '@tanstack/react-query';
import { deleteCrawledPage, deleteCrawledPagesBulk, resetOnboarding } from '@/lib/api';

/** Delete a single crawled page and invalidate crawl-status. */
export function useDeletePage(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (pageId: string) => deleteCrawledPage(projectId, pageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
    },
  });
}

/** Bulk-delete crawled pages and invalidate crawl-status. */
export function useDeletePagesBulk(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (pageIds: string[]) => deleteCrawledPagesBulk(projectId, pageIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
    },
  });
}

/** Reset all onboarding pages and invalidate both crawl-status and project queries. */
export function useResetOnboarding(projectId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => resetOnboarding(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crawl-status', projectId] });
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });
}
