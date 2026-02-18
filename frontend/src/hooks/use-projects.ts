/**
 * TanStack Query hooks for project data fetching and mutations.
 *
 * Query keys:
 * - ['projects'] for list
 * - ['projects', id] for single project
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

// Types matching backend schemas

export interface PhaseStatusEntry {
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  blocked_reason?: string | null;
  [key: string]: unknown; // Allow additional metadata
}

export interface Project {
  id: string;
  name: string;
  site_url: string;
  client_id: string | null;
  additional_info: string | null;
  status: string;
  phase_status: Record<string, PhaseStatusEntry | unknown>;
  brand_config_status: 'pending' | 'generating' | 'complete' | 'failed';
  has_brand_config: boolean;
  reddit_only: boolean;
  uploaded_files_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProjectCreateInput {
  name: string;
  site_url: string;
  client_id?: string | null;
  status?: string;
  reddit_only?: boolean;
  phase_status?: Record<string, unknown>;
}

export interface ProjectUpdateInput {
  name?: string;
  site_url?: string;
  status?: string;
  reddit_only?: boolean;
  phase_status?: Record<string, unknown>;
}

// Query keys factory
export const projectKeys = {
  all: ["projects"] as const,
  detail: (id: string) => ["projects", id] as const,
};

/**
 * Fetch all projects.
 */
export function useProjects(): UseQueryResult<ProjectListResponse> {
  return useQuery({
    queryKey: projectKeys.all,
    queryFn: () => apiClient.get<ProjectListResponse>("/projects"),
  });
}

/**
 * Fetch a single project by ID.
 */
export function useProject(
  id: string,
  options?: { enabled?: boolean }
): UseQueryResult<Project> {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: () => apiClient.get<Project>(`/projects/${id}`),
    enabled: options?.enabled ?? !!id,
  });
}

/**
 * Create a new project.
 * Invalidates the projects list on success.
 */
export function useCreateProject(): UseMutationResult<
  Project,
  Error,
  ProjectCreateInput
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ProjectCreateInput) =>
      apiClient.post<Project>("/projects", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}

/**
 * Update an existing project.
 * Invalidates both the projects list and the specific project on success.
 */
export function useUpdateProject(): UseMutationResult<
  Project,
  Error,
  { id: string; data: ProjectUpdateInput }
> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) =>
      apiClient.patch<Project>(`/projects/${id}`, data),
    onSuccess: (updatedProject) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
      queryClient.setQueryData(
        projectKeys.detail(updatedProject.id),
        updatedProject
      );
    },
  });
}

/**
 * Delete a project.
 * Uses optimistic update to remove from cache immediately.
 */
export function useDeleteProject(): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => apiClient.delete<void>(`/projects/${id}`),
    onMutate: async (deletedId) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: projectKeys.all });

      // Snapshot previous value
      const previousProjects =
        queryClient.getQueryData<ProjectListResponse>(projectKeys.all);

      // Optimistically remove from cache
      if (previousProjects) {
        queryClient.setQueryData<ProjectListResponse>(projectKeys.all, {
          ...previousProjects,
          items: previousProjects.items.filter((p) => p.id !== deletedId),
          total: previousProjects.total - 1,
        });
      }

      // Remove the detail cache
      queryClient.removeQueries({ queryKey: projectKeys.detail(deletedId) });

      return { previousProjects };
    },
    onError: (_err, _deletedId, context) => {
      // Rollback on error
      if (context?.previousProjects) {
        queryClient.setQueryData(projectKeys.all, context.previousProjects);
      }
    },
    onSettled: () => {
      // Refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
    },
  });
}
