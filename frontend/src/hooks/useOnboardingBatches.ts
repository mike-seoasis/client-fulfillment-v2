/**
 * TanStack Query hook for fetching onboarding batch summaries.
 *
 * Query keys:
 * - ['projects', projectId, 'onboarding-batches'] for batch list
 */

import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { getOnboardingBatches, type OnboardingBatchSummary } from '@/lib/api';

export const onboardingBatchesKeys = {
  list: (projectId: string) => ['projects', projectId, 'onboarding-batches'] as const,
};

export function useOnboardingBatches(
  projectId: string,
  options?: { enabled?: boolean }
): UseQueryResult<OnboardingBatchSummary[]> {
  return useQuery({
    queryKey: onboardingBatchesKeys.list(projectId),
    queryFn: () => getOnboardingBatches(projectId),
    enabled: options?.enabled ?? !!projectId,
  });
}
