/**
 * TanStack Query mutation hooks for keyword operations.
 *
 * All mutations invalidate the pages-with-keywords query on success
 * to ensure the UI stays in sync with the backend.
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query';
import {
  updatePrimaryKeyword,
  approveKeyword,
  approveAllKeywords,
  togglePriority,
  type PageKeywordsData,
  type BulkApproveResponse,
} from '@/lib/api';
import { pagesWithKeywordsKeys } from './usePagesWithKeywords';

// Types for mutation inputs
interface UpdatePrimaryKeywordInput {
  projectId: string;
  pageId: string;
  keyword: string;
}

interface ApproveKeywordInput {
  projectId: string;
  pageId: string;
}

interface TogglePriorityInput {
  projectId: string;
  pageId: string;
  value?: boolean;
}

/**
 * Mutation hook to update the primary keyword for a page.
 * Invalidates pages-with-keywords query on success.
 */
export function useUpdatePrimaryKeyword(): UseMutationResult<
  PageKeywordsData,
  Error,
  UpdatePrimaryKeywordInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, pageId, keyword }: UpdatePrimaryKeywordInput) =>
      updatePrimaryKeyword(projectId, pageId, keyword),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: pagesWithKeywordsKeys.list(projectId),
      });
    },
  });
}

/**
 * Mutation hook to approve a single keyword.
 * Invalidates pages-with-keywords query on success.
 */
export function useApproveKeyword(): UseMutationResult<
  PageKeywordsData,
  Error,
  ApproveKeywordInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, pageId }: ApproveKeywordInput) =>
      approveKeyword(projectId, pageId),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: pagesWithKeywordsKeys.list(projectId),
      });
    },
  });
}

/**
 * Mutation hook to approve all keywords in a project.
 * Invalidates pages-with-keywords query on success.
 */
export function useApproveAllKeywords(): UseMutationResult<
  BulkApproveResponse,
  Error,
  string
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (projectId: string) => approveAllKeywords(projectId),
    onSuccess: (_data, projectId) => {
      queryClient.invalidateQueries({
        queryKey: pagesWithKeywordsKeys.list(projectId),
      });
    },
  });
}

/**
 * Mutation hook to toggle the priority flag for a page's keyword.
 * Invalidates pages-with-keywords query on success.
 */
export function useTogglePriority(): UseMutationResult<
  PageKeywordsData,
  Error,
  TogglePriorityInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ projectId, pageId, value }: TogglePriorityInput) =>
      togglePriority(projectId, pageId, value),
    onSuccess: (_data, { projectId }) => {
      queryClient.invalidateQueries({
        queryKey: pagesWithKeywordsKeys.list(projectId),
      });
    },
  });
}
