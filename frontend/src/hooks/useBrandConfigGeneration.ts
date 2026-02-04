/**
 * TanStack Query hooks for brand config generation operations.
 *
 * Query keys:
 * - ['projects', projectId, 'brand-config', 'status'] for generation status
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

// Types matching backend schemas
export interface GenerationStatus {
  status: 'pending' | 'generating' | 'complete' | 'failed';
  current_step: string | null;
  steps_completed: number;
  steps_total: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

// Generation step display names
export const GENERATION_STEP_LABELS: Record<string, string> = {
  brand_foundation: 'Extracting brand foundation...',
  target_audience: 'Building target audience personas...',
  voice_dimensions: 'Analyzing voice dimensions (4 scales)...',
  voice_characteristics: 'Defining voice characteristics...',
  writing_style: 'Setting writing style rules...',
  vocabulary: 'Building vocabulary guide...',
  trust_elements: 'Compiling trust elements...',
  competitor_context: 'Analyzing competitor context...',
  ai_prompt_snippet: 'Generating AI prompt snippet...',
};

// Query keys factory
export const brandConfigKeys = {
  status: (projectId: string) => ['projects', projectId, 'brand-config', 'status'] as const,
};

/**
 * Fetch the current generation status for a project.
 * Supports polling when generation is in progress.
 */
export function useBrandConfigStatus(
  projectId: string,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<GenerationStatus> {
  return useQuery({
    queryKey: brandConfigKeys.status(projectId),
    queryFn: () =>
      apiClient.get<GenerationStatus>(`/projects/${projectId}/brand-config/status`),
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: options?.refetchInterval,
  });
}

/**
 * Start brand config generation for a project.
 * Returns the initial generation status.
 */
export function useStartBrandConfigGeneration(
  projectId: string
): UseMutationResult<GenerationStatus, Error, void> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiClient.post<GenerationStatus>(`/projects/${projectId}/brand-config/generate`),
    onSuccess: (data) => {
      // Update the status cache with the returned status
      queryClient.setQueryData(brandConfigKeys.status(projectId), data);
    },
  });
}

/**
 * Helper hook that manages the full generation flow.
 * - Starts generation when triggered
 * - Polls for status while generating
 * - Returns status and control functions
 */
export function useBrandConfigGeneration(projectId: string) {
  const queryClient = useQueryClient();

  // Poll status when generating
  const status = useQuery({
    queryKey: brandConfigKeys.status(projectId),
    queryFn: () =>
      apiClient.get<GenerationStatus>(`/projects/${projectId}/brand-config/status`),
    enabled: !!projectId,
    // Poll every 2 seconds while generating, stop polling when complete/failed
    refetchInterval: (query) => {
      const data = query.state.data as GenerationStatus | undefined;
      if (data?.status === 'generating') {
        return 2000;
      }
      return false;
    },
  });

  const startGeneration = useStartBrandConfigGeneration(projectId);

  // Calculate progress percentage
  const stepsTotal = status.data?.steps_total ?? 0;
  const stepsCompleted = status.data?.steps_completed ?? 0;
  const progress = stepsTotal > 0 ? Math.round((stepsCompleted / stepsTotal) * 100) : 0;

  // Get display label for current step
  const currentStepLabel = status.data?.current_step
    ? GENERATION_STEP_LABELS[status.data.current_step] || status.data.current_step
    : null;

  return {
    // Status data
    status: status.data?.status ?? 'pending',
    currentStep: status.data?.current_step,
    currentStepLabel,
    stepsCompleted,
    stepsTotal,
    progress,
    error: status.data?.error,
    startedAt: status.data?.started_at,
    completedAt: status.data?.completed_at,

    // Query states
    isLoading: status.isLoading,
    isError: status.isError,
    isGenerating: status.data?.status === 'generating',
    isComplete: status.data?.status === 'complete',
    isFailed: status.data?.status === 'failed',

    // Actions
    startGeneration: startGeneration.mutate,
    startGenerationAsync: startGeneration.mutateAsync,
    isStarting: startGeneration.isPending,
    startError: startGeneration.error,

    // Refetch
    refetch: status.refetch,
    invalidate: () =>
      queryClient.invalidateQueries({ queryKey: brandConfigKeys.status(projectId) }),
  };
}
