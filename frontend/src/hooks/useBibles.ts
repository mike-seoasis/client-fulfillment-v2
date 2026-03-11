/**
 * TanStack Query hooks for vertical bible operations.
 *
 * Query keys:
 * - ['projects', projectId, 'bibles'] for the bible list
 * - ['projects', projectId, 'bibles', bibleId] for a single bible
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  getBibles,
  getBible,
  createBible,
  updateBible,
  deleteBible,
  importBible,
  exportBible,
  getBiblePreview,
  type VerticalBible,
  type BibleCreate,
  type BibleUpdate,
  type BibleExportResponse,
  type BiblePreviewResponse,
} from '@/lib/api';

// Query keys factory
export const bibleKeys = {
  list: (projectId: string) => ['projects', projectId, 'bibles'] as const,
  detail: (projectId: string, bibleId: string) =>
    ['projects', projectId, 'bibles', bibleId] as const,
  preview: (projectId: string, bibleId: string) =>
    ['projects', projectId, 'bibles', bibleId, 'preview'] as const,
};

// Mutation input types
interface CreateBibleInput {
  projectId: string;
  data: BibleCreate;
}

interface UpdateBibleInput {
  projectId: string;
  bibleId: string;
  data: BibleUpdate;
}

interface DeleteBibleInput {
  projectId: string;
  bibleId: string;
}

interface ImportBibleInput {
  projectId: string;
  markdown: string;
  isActive?: boolean;
}

interface ExportBibleInput {
  projectId: string;
  bibleId: string;
}

/**
 * Fetch all bibles for a project.
 * Returns the items array directly, matching useClusters/useBlogCampaigns pattern.
 */
export function useBibles(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<VerticalBible[]> {
  return useQuery({
    queryKey: bibleKeys.list(projectId),
    queryFn: () => getBibles(projectId).then((r) => r.items),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Fetch a single bible by ID.
 */
export function useBible(
  projectId: string,
  bibleId: string,
  options?: { enabled?: boolean }
): UseQueryResult<VerticalBible> {
  return useQuery({
    queryKey: bibleKeys.detail(projectId, bibleId),
    queryFn: () => getBible(projectId, bibleId),
    enabled: options?.enabled ?? (!!projectId && !!bibleId),
  });
}

/**
 * Create a new bible.
 * Invalidates the bible list on success.
 */
export function useCreateBible(): UseMutationResult<
  VerticalBible,
  Error,
  CreateBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, data }: CreateBibleInput) =>
      createBible(projectId, data),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Update an existing bible.
 * Optimistically updates the detail cache and invalidates list on settle.
 */
export function useUpdateBible(): UseMutationResult<
  VerticalBible,
  Error,
  UpdateBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, bibleId, data }: UpdateBibleInput) =>
      updateBible(projectId, bibleId, data),
    onMutate: async ({ projectId, bibleId, data }) => {
      const queryKey = bibleKeys.detail(projectId, bibleId);
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<VerticalBible>(queryKey);

      if (previous) {
        queryClient.setQueryData<VerticalBible>(queryKey, {
          ...previous,
          ...data,
        });
      }

      return { previous, queryKey };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(context.queryKey, context.previous);
      }
    },
    onSettled: (_data, _error, { projectId, bibleId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.detail(projectId, bibleId),
      });
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Delete a bible.
 * Removes detail cache and invalidates the list on success.
 */
export function useDeleteBible(): UseMutationResult<
  void,
  Error,
  DeleteBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, bibleId }: DeleteBibleInput) =>
      deleteBible(projectId, bibleId),
    onSuccess: (_data, { projectId, bibleId }) => {
      queryClient.removeQueries({
        queryKey: bibleKeys.detail(projectId, bibleId),
      });
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Import a bible from markdown.
 * Invalidates the bible list on success.
 */
export function useImportBible(): UseMutationResult<
  VerticalBible,
  Error,
  ImportBibleInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, markdown, isActive }: ImportBibleInput) =>
      importBible(projectId, markdown, isActive),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: bibleKeys.list(projectId),
      });
    },
  });
}

/**
 * Export a bible as markdown.
 */
export function useExportBible(): UseMutationResult<
  BibleExportResponse,
  Error,
  ExportBibleInput
> {
  return useMutation({
    mutationFn: ({ projectId, bibleId }: ExportBibleInput) =>
      exportBible(projectId, bibleId),
  });
}

/**
 * Fetch bible preview (prompt section + matching pages).
 */
export function useBiblePreview(
  projectId: string,
  bibleId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BiblePreviewResponse> {
  return useQuery({
    queryKey: bibleKeys.preview(projectId, bibleId),
    queryFn: () => getBiblePreview(projectId, bibleId),
    enabled: options?.enabled ?? (!!projectId && !!bibleId),
  });
}
