/**
 * TanStack Query hook for fetching crawl status.
 *
 * Query keys:
 * - ['projects', id, 'crawl-status'] for crawl status
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

// Types matching backend CrawlStatusResponse
export interface PageSummary {
  id: string;
  url: string;
  status: 'pending' | 'crawling' | 'completed' | 'failed';
  title: string | null;
  word_count: number | null;
  headings: { h1?: string[]; h2?: string[]; h3?: string[] } | null;
  product_count: number | null;
  labels: string[];
  crawl_error: string | null;
}

export interface ProgressCounts {
  total: number;
  completed: number;
  failed: number;
  pending: number;
}

export interface CrawlStatusResponse {
  project_id: string;
  status: 'crawling' | 'labeling' | 'complete';
  progress: ProgressCounts;
  pages: PageSummary[];
}

// Query keys factory
export const crawlStatusKeys = {
  detail: (projectId: string) => ["projects", projectId, "crawl-status"] as const,
};

/**
 * Fetch crawl status for a project.
 * Returns null if no pages exist (404 response).
 */
export function useCrawlStatus(
  projectId: string,
  options?: { enabled?: boolean; refetchInterval?: number | false }
): UseQueryResult<CrawlStatusResponse | null> {
  return useQuery({
    queryKey: crawlStatusKeys.detail(projectId),
    queryFn: async () => {
      try {
        return await apiClient.get<CrawlStatusResponse>(`/projects/${projectId}/crawl-status`);
      } catch (error) {
        // Return null for 404 (no pages exist yet)
        if (error instanceof Error && error.message.includes("404")) {
          return null;
        }
        throw error;
      }
    },
    enabled: options?.enabled ?? !!projectId,
    refetchInterval: options?.refetchInterval,
  });
}

/**
 * Determine which onboarding step the user should navigate to based on progress.
 */
export function getOnboardingStep(crawlStatus: CrawlStatusResponse | null | undefined): {
  currentStep: 'upload' | 'crawl' | 'keywords' | 'content' | 'export';
  stepIndex: number;
  hasStarted: boolean;
  isComplete: boolean;
} {
  // No crawl status means no pages uploaded yet
  if (!crawlStatus || crawlStatus.progress.total === 0) {
    return {
      currentStep: 'upload',
      stepIndex: 0,
      hasStarted: false,
      isComplete: false,
    };
  }

  // Has pages but still crawling or labeling
  if (crawlStatus.status === 'crawling' || crawlStatus.status === 'labeling') {
    return {
      currentStep: 'crawl',
      stepIndex: 1,
      hasStarted: true,
      isComplete: false,
    };
  }

  // Crawl complete - would be on keywords step
  // For now, keywords is Phase 4 (not implemented), so we show crawl as complete
  return {
    currentStep: 'keywords',
    stepIndex: 2,
    hasStarted: true,
    isComplete: crawlStatus.status === 'complete',
  };
}
