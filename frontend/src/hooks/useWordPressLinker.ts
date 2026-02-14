/**
 * TanStack Query hooks for WordPress blog linking wizard.
 *
 * Query keys:
 * - ['wp', 'progress', jobId] for polling background jobs
 * - ['wp', 'labels', projectId] for label review
 * - ['wp', 'review', projectId] for link review
 */

import {
  useMutation,
  useQuery,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import {
  wpConnect,
  wpImport,
  wpGetProgress,
  wpAnalyze,
  wpLabel,
  wpGetLabels,
  wpPlanLinks,
  wpGetReview,
  wpExport,
  type WPConnectResponse,
  type WPImportResponse,
  type WPProgressResponse,
  type WPLabelReviewResponse,
  type WPReviewResponse,
} from '@/lib/api';

// Query keys
export const wpKeys = {
  progress: (jobId: string) => ['wp', 'progress', jobId] as const,
  labels: (projectId: string) => ['wp', 'labels', projectId] as const,
  review: (projectId: string) => ['wp', 'review', projectId] as const,
};

// Mutation input types
interface ConnectInput {
  siteUrl: string;
  username: string;
  appPassword: string;
}

interface ImportInput extends ConnectInput {
  titleFilter?: string[];
  postStatus?: string;
}

interface ExportInput extends ConnectInput {
  projectId: string;
  titleFilter?: string[];
}

/**
 * Validate WordPress credentials.
 */
export function useWPConnect(): UseMutationResult<
  WPConnectResponse,
  Error,
  ConnectInput
> {
  return useMutation({
    mutationFn: ({ siteUrl, username, appPassword }: ConnectInput) =>
      wpConnect(siteUrl, username, appPassword),
  });
}

/**
 * Import WordPress posts. Returns job_id for progress polling.
 */
export function useWPImport(): UseMutationResult<
  WPImportResponse,
  Error,
  ImportInput
> {
  return useMutation({
    mutationFn: ({ siteUrl, username, appPassword, titleFilter, postStatus }: ImportInput) =>
      wpImport(siteUrl, username, appPassword, titleFilter, postStatus),
  });
}

/**
 * Poll progress for a background job.
 * Refetches every 2 seconds while status is 'running'.
 */
export function useWPProgress(
  jobId: string | null,
  enabled?: boolean
): UseQueryResult<WPProgressResponse> {
  return useQuery({
    queryKey: wpKeys.progress(jobId || ''),
    queryFn: () => wpGetProgress(jobId!),
    enabled: (enabled ?? true) && !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data as WPProgressResponse | undefined;
      if (data?.status === 'running') {
        return 2000;
      }
      return false;
    },
  });
}

/**
 * Start POP analysis. Returns job_id for progress polling.
 */
export function useWPAnalyze(): UseMutationResult<
  WPProgressResponse,
  Error,
  string
> {
  return useMutation({
    mutationFn: (projectId: string) => wpAnalyze(projectId),
  });
}

/**
 * Start blog labeling. Returns job_id for progress polling.
 */
export function useWPLabel(): UseMutationResult<
  WPProgressResponse,
  Error,
  string
> {
  return useMutation({
    mutationFn: (projectId: string) => wpLabel(projectId),
  });
}

/**
 * Fetch taxonomy and label assignments for review.
 */
export function useWPLabels(
  projectId: string | null,
  enabled?: boolean
): UseQueryResult<WPLabelReviewResponse> {
  return useQuery({
    queryKey: wpKeys.labels(projectId || ''),
    queryFn: () => wpGetLabels(projectId!),
    enabled: (enabled ?? true) && !!projectId,
  });
}

/**
 * Start link planning. Returns job_id for progress polling.
 */
export function useWPPlan(): UseMutationResult<
  WPProgressResponse,
  Error,
  string
> {
  return useMutation({
    mutationFn: (projectId: string) => wpPlanLinks(projectId),
  });
}

/**
 * Fetch link review stats.
 */
export function useWPReview(
  projectId: string | null,
  enabled?: boolean
): UseQueryResult<WPReviewResponse> {
  return useQuery({
    queryKey: wpKeys.review(projectId || ''),
    queryFn: () => wpGetReview(projectId!),
    enabled: (enabled ?? true) && !!projectId,
  });
}

/**
 * Export modified content back to WordPress.
 */
export function useWPExport(): UseMutationResult<
  WPProgressResponse,
  Error,
  ExportInput
> {
  return useMutation({
    mutationFn: ({
      projectId,
      siteUrl,
      username,
      appPassword,
      titleFilter,
    }: ExportInput) =>
      wpExport(projectId, siteUrl, username, appPassword, titleFilter),
  });
}
