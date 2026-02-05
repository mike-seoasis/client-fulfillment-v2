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

// =============================================================================
// PRIMARY KEYWORD API TYPES
// =============================================================================

/** A keyword candidate with volume metrics and AI scoring. */
export interface KeywordCandidate {
  keyword: string;
  volume: number | null;
  cpc: number | null;
  competition: number | null;
  relevance_score: number | null;
  composite_score: number | null;
}

/** Keyword data for a page. */
export interface PageKeywordsData {
  id: string;
  primary_keyword: string;
  secondary_keywords: string[];
  alternative_keywords: KeywordCandidate[];
  is_approved: boolean;
  is_priority: boolean;
  composite_score: number | null;
  relevance_score: number | null;
  ai_reasoning: string | null;
  search_volume: number | null;
  difficulty_score: number | null;
}

/** Combined view of a crawled page with its keyword data. */
export interface PageWithKeywords {
  id: string;
  url: string;
  title: string | null;
  labels: string[];
  product_count: number | null;
  keywords: PageKeywordsData | null;
}

/** Status of primary keyword generation for a project. */
export interface PrimaryKeywordGenerationStatus {
  status: "pending" | "generating" | "completed" | "failed";
  total: number;
  completed: number;
  failed: number;
  current_page: string | null;
  error: string | null;
}

/** Response for generate-primary-keywords endpoint. */
export interface GeneratePrimaryKeywordsResponse {
  task_id: string;
  status: string;
  page_count: number;
}

/** Response for bulk keyword approval. */
export interface BulkApproveResponse {
  approved_count: number;
}

// =============================================================================
// PRIMARY KEYWORD API FUNCTIONS
// =============================================================================

/**
 * Start generating primary keywords for all completed pages in a project.
 * Returns immediately with a task_id for polling progress.
 */
export function generatePrimaryKeywords(
  projectId: string
): Promise<GeneratePrimaryKeywordsResponse> {
  return apiClient.post<GeneratePrimaryKeywordsResponse>(
    `/projects/${projectId}/generate-primary-keywords`
  );
}

/**
 * Get the status of primary keyword generation for a project.
 * Use this to poll for progress during generation.
 */
export function getPrimaryKeywordsStatus(
  projectId: string
): Promise<PrimaryKeywordGenerationStatus> {
  return apiClient.get<PrimaryKeywordGenerationStatus>(
    `/projects/${projectId}/primary-keywords-status`
  );
}

/**
 * Get all pages with their keyword data for the approval interface.
 * Only returns completed pages.
 */
export function getPagesWithKeywords(
  projectId: string
): Promise<PageWithKeywords[]> {
  return apiClient.get<PageWithKeywords[]>(
    `/projects/${projectId}/pages-with-keywords`
  );
}

/**
 * Update the primary keyword for a specific page.
 * If the keyword matches an alternative, volume data is preserved.
 * Otherwise, volume data is cleared for custom keywords.
 */
export function updatePrimaryKeyword(
  projectId: string,
  pageId: string,
  keyword: string
): Promise<PageKeywordsData> {
  return apiClient.put<PageKeywordsData>(
    `/projects/${projectId}/pages/${pageId}/primary-keyword`,
    { keyword }
  );
}

/**
 * Approve the keyword for a specific page.
 * Sets is_approved=true. Idempotent.
 */
export function approveKeyword(
  projectId: string,
  pageId: string
): Promise<PageKeywordsData> {
  return apiClient.post<PageKeywordsData>(
    `/projects/${projectId}/pages/${pageId}/approve-keyword`
  );
}

/**
 * Approve all keywords for completed pages in a project.
 * Returns the count of newly approved keywords.
 */
export function approveAllKeywords(
  projectId: string
): Promise<BulkApproveResponse> {
  return apiClient.post<BulkApproveResponse>(
    `/projects/${projectId}/approve-all-keywords`
  );
}

/**
 * Toggle the priority flag for a page's keyword.
 * Can optionally set an explicit value instead of toggling.
 */
export function togglePriority(
  projectId: string,
  pageId: string,
  value?: boolean
): Promise<PageKeywordsData> {
  const queryParam = value !== undefined ? `?value=${value}` : "";
  return apiClient.put<PageKeywordsData>(
    `/projects/${projectId}/pages/${pageId}/priority${queryParam}`
  );
}
