/**
 * TanStack Query hooks for brand config operations.
 *
 * Query keys:
 * - ['projects', projectId, 'brand-config'] for the full brand config
 *
 * For generation status and polling, use useBrandConfigGeneration.ts instead.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { brandConfigKeys, type GenerationStatus } from './useBrandConfigGeneration';

// Types matching backend schemas

export interface BrandConfig {
  id: string;
  project_id: string;
  brand_name: string;
  domain: string | null;
  v2_schema: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SectionUpdateInput {
  sections: Record<string, Record<string, unknown>>;
}

export interface RegenerateInput {
  section?: string;
  sections?: string[];
}

// Query keys factory
export const brandConfigDataKeys = {
  config: (projectId: string) => ['projects', projectId, 'brand-config'] as const,
};

/**
 * Fetch the full brand config for a project.
 * Returns null if the brand config hasn't been generated yet.
 */
export function useBrandConfig(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<BrandConfig> {
  return useQuery({
    queryKey: brandConfigDataKeys.config(projectId),
    queryFn: () => apiClient.get<BrandConfig>(`/projects/${projectId}/brand-config`),
    enabled: options?.enabled ?? !!projectId,
  });
}

/**
 * Re-export useBrandConfigStatus for convenience.
 * Supports refetchInterval for polling during generation.
 */
export { useBrandConfigStatus, brandConfigKeys } from './useBrandConfigGeneration';

/**
 * Update specific sections of a brand config.
 * Invalidates both the config and status caches on success.
 */
export function useUpdateBrandConfig(
  projectId: string
): UseMutationResult<BrandConfig, Error, SectionUpdateInput> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SectionUpdateInput) =>
      apiClient.patch<BrandConfig>(`/projects/${projectId}/brand-config`, data),
    onSuccess: (updatedConfig) => {
      // Update the config cache with the returned config
      queryClient.setQueryData(brandConfigDataKeys.config(projectId), updatedConfig);
      // Invalidate status in case it's affected
      queryClient.invalidateQueries({ queryKey: brandConfigKeys.status(projectId) });
    },
  });
}

/**
 * Regenerate all or specific sections of a brand config.
 * This re-runs the research and synthesis phases as a background task.
 * Returns 202 with generation status; the frontend should poll for completion.
 *
 * Pass undefined or {} to regenerate all sections.
 * Pass { section: 'name' } to regenerate a single section.
 * Pass { sections: ['name1', 'name2'] } to regenerate multiple sections.
 */
export function useRegenerateBrandConfig(
  projectId: string
): UseMutationResult<GenerationStatus, Error, RegenerateInput | undefined> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RegenerateInput | undefined) =>
      apiClient.post<GenerationStatus>(`/projects/${projectId}/brand-config/regenerate`, data ?? {}),
    onSuccess: (statusData) => {
      // Update the status cache to trigger polling in the UI
      queryClient.setQueryData(brandConfigKeys.status(projectId), statusData);
      // Invalidate status to start fresh polling
      queryClient.invalidateQueries({ queryKey: brandConfigKeys.status(projectId) });
    },
  });
}

/**
 * Helper hook that manages brand config with loading/error states.
 * Combines the config fetch with convenient derived state.
 */
export function useBrandConfigWithStatus(projectId: string) {
  const queryClient = useQueryClient();
  const config = useBrandConfig(projectId);
  const updateMutation = useUpdateBrandConfig(projectId);
  const regenerateMutation = useRegenerateBrandConfig(projectId);

  return {
    // Config data
    config: config.data,
    isLoading: config.isLoading,
    isError: config.isError,
    error: config.error,

    // Update mutation
    updateSections: updateMutation.mutate,
    updateSectionsAsync: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error,

    // Regenerate mutation
    regenerate: regenerateMutation.mutate,
    regenerateAsync: regenerateMutation.mutateAsync,
    isRegenerating: regenerateMutation.isPending,
    regenerateError: regenerateMutation.error,

    // Refetch
    refetch: config.refetch,
    invalidate: () =>
      queryClient.invalidateQueries({ queryKey: brandConfigDataKeys.config(projectId) }),
  };
}
