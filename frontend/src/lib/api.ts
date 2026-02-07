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

/** Alternative keyword option with volume and score. */
export interface AlternativeKeyword {
  keyword: string;
  volume: number | null;
  composite_score: number | null;
}

/** Keyword data for a page. */
export interface PageKeywordsData {
  id: string;
  primary_keyword: string;
  secondary_keywords: string[];
  /** Alternative keywords - supports both old string[] and new AlternativeKeyword[] formats */
  alternative_keywords: (string | AlternativeKeyword)[];
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
 * Approve or unapprove the keyword for a specific page.
 * Pass value=false to unapprove (undo accidental approval).
 */
export function approveKeyword(
  projectId: string,
  pageId: string,
  value: boolean = true
): Promise<PageKeywordsData> {
  const queryParam = value ? "" : "?value=false";
  return apiClient.post<PageKeywordsData>(
    `/projects/${projectId}/pages/${pageId}/approve-keyword${queryParam}`
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

// =============================================================================
// CONTENT GENERATION API TYPES
// =============================================================================

/** Response when content generation pipeline is triggered. */
export interface ContentGenerationTriggerResponse {
  status: string;
  message: string;
}

/** Per-page status within the content generation pipeline. */
export interface PageGenerationStatusItem {
  page_id: string;
  url: string;
  keyword: string;
  status: string;
  error: string | null;
}

/** Overall content generation pipeline status for a project. */
export interface ContentGenerationStatus {
  overall_status: string;
  pages_total: number;
  pages_completed: number;
  pages_failed: number;
  pages_approved: number;
  pages: PageGenerationStatusItem[];
}

/** Lightweight summary of the content brief used during generation. */
export interface BriefSummary {
  keyword: string;
  lsi_terms_count: number;
}

/** Full content brief data for the review/editing UI. */
export interface ContentBriefData {
  keyword: string;
  lsi_terms: unknown[];
  heading_targets: unknown[];
  keyword_targets: unknown[];
}

/** Request for partial content updates during review/editing. */
export interface ContentUpdateRequest {
  page_title?: string | null;
  meta_description?: string | null;
  top_description?: string | null;
  bottom_description?: string | null;
}

/** Response for bulk content approval. */
export interface ContentBulkApproveResponse {
  approved_count: number;
}

/** Generated content for a single page. */
export interface PageContentResponse {
  page_title: string | null;
  meta_description: string | null;
  top_description: string | null;
  bottom_description: string | null;
  word_count: number | null;
  status: string;
  is_approved: boolean;
  approved_at: string | null;
  qa_results: Record<string, unknown> | null;
  brief_summary: BriefSummary | null;
  brief: ContentBriefData | null;
  generation_started_at: string | null;
  generation_completed_at: string | null;
}

/** A prompt/response exchange record. */
export interface PromptLogResponse {
  id: string;
  step: string;
  role: string;
  prompt_text: string;
  response_text: string | null;
  model: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  duration_ms: number | null;
  created_at: string;
}

// =============================================================================
// CONTENT GENERATION API FUNCTIONS
// =============================================================================

/**
 * Trigger content generation for all pages with approved keywords.
 * Returns 202 on success. Background task runs the pipeline.
 */
export function triggerContentGeneration(
  projectId: string,
  options?: { forceRefresh?: boolean; refreshBriefs?: boolean }
): Promise<ContentGenerationTriggerResponse> {
  const searchParams = new URLSearchParams();
  if (options?.forceRefresh) searchParams.set('force_refresh', 'true');
  if (options?.refreshBriefs) searchParams.set('refresh_briefs', 'true');
  const qs = searchParams.toString();
  return apiClient.post<ContentGenerationTriggerResponse>(
    `/projects/${projectId}/generate-content${qs ? `?${qs}` : ''}`
  );
}

/**
 * Poll content generation status for a project.
 * Returns overall status and per-page breakdown.
 */
export function pollContentGenerationStatus(
  projectId: string
): Promise<ContentGenerationStatus> {
  return apiClient.get<ContentGenerationStatus>(
    `/projects/${projectId}/content-generation-status`
  );
}

/**
 * Get generated content for a specific page.
 * Returns 404 if content has not been generated yet.
 */
export function getPageContent(
  projectId: string,
  pageId: string
): Promise<PageContentResponse> {
  return apiClient.get<PageContentResponse>(
    `/projects/${projectId}/pages/${pageId}/content`
  );
}

/**
 * Get all prompt logs for a specific page.
 * Returns empty array if no prompts exist.
 */
export function getPagePrompts(
  projectId: string,
  pageId: string
): Promise<PromptLogResponse[]> {
  return apiClient.get<PromptLogResponse[]>(
    `/projects/${projectId}/pages/${pageId}/prompts`
  );
}
