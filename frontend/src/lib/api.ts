/**
 * API client with fetch wrapper.
 *
 * Handles base URL configuration and JSON serialization for API requests.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message?: string
  ) {
    super(message || `${status} ${statusText}`);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message: string | undefined;
    try {
      const data = await response.json();
      // Backend uses {"error": ..., "code": ..., "request_id": ...} format
      message = data.error || data.detail || data.message;
    } catch {
      // Response body is not JSON
    }
    throw new ApiError(response.status, response.statusText, message);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export async function api<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { body, headers, ...rest } = options;

  const config: RequestInit = {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  if (body !== undefined) {
    config.body = JSON.stringify(body);
  }

  const url = endpoint.startsWith("/")
    ? `${API_BASE_URL}${endpoint}`
    : `${API_BASE_URL}/${endpoint}`;

  const response = await fetch(url, config);
  return handleResponse<T>(response);
}

// Convenience methods
export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    api<T>(endpoint, { ...options, method: "GET" }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    api<T>(endpoint, { ...options, method: "POST", body }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    api<T>(endpoint, { ...options, method: "PATCH", body }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    api<T>(endpoint, { ...options, method: "PUT", body }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    api<T>(endpoint, { ...options, method: "DELETE" }),
};
