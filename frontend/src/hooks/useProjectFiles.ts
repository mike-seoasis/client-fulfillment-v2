/**
 * TanStack Query hooks for project file operations.
 *
 * Query keys:
 * - ['projects', projectId, 'files'] for file list
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiClient, ApiError } from "@/lib/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Types matching backend schemas

export interface ProjectFile {
  id: string;
  project_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  created_at: string;
}

export interface ProjectFileList {
  items: ProjectFile[];
  total: number;
}

// Query keys factory
export const projectFileKeys = {
  list: (projectId: string) => ["projects", projectId, "files"] as const,
};

/**
 * Fetch all files for a project.
 */
export function useProjectFiles(
  projectId: string
): UseQueryResult<ProjectFileList> {
  return useQuery({
    queryKey: projectFileKeys.list(projectId),
    queryFn: () =>
      apiClient.get<ProjectFileList>(`/projects/${projectId}/files`),
    enabled: !!projectId,
  });
}

/**
 * Upload a file to a project.
 * Uses multipart/form-data for file upload.
 * Invalidates the files list on success.
 */
export function useUploadFile(
  projectId: string
): UseMutationResult<ProjectFile, Error, File> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/files`,
        {
          method: "POST",
          body: formData,
          // Note: Don't set Content-Type header - browser sets it with boundary
        }
      );

      if (!response.ok) {
        let message: string | undefined;
        try {
          const data = await response.json();
          message = data.error || data.detail || data.message;
        } catch {
          // Response body is not JSON
        }
        throw new ApiError(response.status, response.statusText, message);
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectFileKeys.list(projectId) });
    },
  });
}

/**
 * Delete a file from a project.
 * Invalidates the files list on success.
 */
export function useDeleteFile(
  projectId: string
): UseMutationResult<void, Error, string> {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fileId: string) =>
      apiClient.delete<void>(`/projects/${projectId}/files/${fileId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectFileKeys.list(projectId) });
    },
  });
}
