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
  qa_passed: boolean | null;
  qa_issue_count: number;
  is_approved: boolean;
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

/**
 * Update generated content for a page (partial update).
 * Only provided fields are updated; omitted fields remain unchanged.
 * Clears approval on edit.
 */
export function updatePageContent(
  projectId: string,
  pageId: string,
  data: ContentUpdateRequest
): Promise<PageContentResponse> {
  return apiClient.put<PageContentResponse>(
    `/projects/${projectId}/pages/${pageId}/content`,
    data
  );
}

/**
 * Approve or unapprove generated content for a page.
 * Pass value=false to unapprove.
 */
export function approvePageContent(
  projectId: string,
  pageId: string,
  value: boolean = true
): Promise<PageContentResponse> {
  const queryParam = value ? '' : '?value=false';
  return apiClient.post<PageContentResponse>(
    `/projects/${projectId}/pages/${pageId}/approve-content${queryParam}`
  );
}

/**
 * Re-run quality checks on generated content for a page.
 * Returns updated content with fresh qa_results.
 */
export function recheckPageContent(
  projectId: string,
  pageId: string
): Promise<PageContentResponse> {
  return apiClient.post<PageContentResponse>(
    `/projects/${projectId}/pages/${pageId}/recheck-content`
  );
}

/**
 * Bulk approve all eligible content (complete + QA passed) for a project.
 * Returns count of newly approved pages.
 */
export function bulkApproveContent(
  projectId: string
): Promise<ContentBulkApproveResponse> {
  return apiClient.post<ContentBulkApproveResponse>(
    `/projects/${projectId}/bulk-approve-content`
  );
}

// =============================================================================
// KEYWORD CLUSTER API TYPES
// =============================================================================

/** Request to create a new keyword cluster. */
export interface ClusterCreate {
  seed_keyword: string;
  name?: string | null;
}

/** A single page within a keyword cluster. */
export interface ClusterPage {
  id: string;
  keyword: string;
  role: string;
  url_slug: string;
  expansion_strategy: string | null;
  reasoning: string | null;
  search_volume: number | null;
  cpc: number | null;
  competition: number | null;
  competition_level: string | null;
  composite_score: number | null;
  is_approved: boolean;
  crawled_page_id: string | null;
}

/** Full cluster with nested pages. */
export interface Cluster {
  id: string;
  project_id: string;
  seed_keyword: string;
  name: string;
  status: string;
  generation_metadata: Record<string, unknown> | null;
  pages: ClusterPage[];
  created_at: string;
  updated_at: string;
}

/** Summary cluster for list views. */
export interface ClusterListItem {
  id: string;
  seed_keyword: string;
  name: string;
  status: string;
  page_count: number;
  approved_count: number;
  created_at: string;
}

/** Request to update editable fields on a cluster page. */
export interface ClusterPageUpdate {
  is_approved?: boolean;
  keyword?: string;
  url_slug?: string;
  role?: string;
}

/** Response for bulk cluster approval. */
export interface ClusterBulkApproveResponse {
  bridged_count: number;
}

// =============================================================================
// KEYWORD CLUSTER API FUNCTIONS
// =============================================================================

/**
 * Create a new keyword cluster from a seed keyword.
 * Runs the 3-stage generation pipeline (~5-10s).
 */
export function createCluster(
  projectId: string,
  data: ClusterCreate
): Promise<Cluster> {
  return apiClient.post<Cluster>(
    `/projects/${projectId}/clusters`,
    data
  );
}

/**
 * List all keyword clusters for a project.
 * Returns summary data with page counts.
 */
export function getClusters(
  projectId: string
): Promise<ClusterListItem[]> {
  return apiClient.get<ClusterListItem[]>(
    `/projects/${projectId}/clusters`
  );
}

/**
 * Get a single cluster with all its pages.
 */
export function getCluster(
  projectId: string,
  clusterId: string
): Promise<Cluster> {
  return apiClient.get<Cluster>(
    `/projects/${projectId}/clusters/${clusterId}`
  );
}

/**
 * Update editable fields on a cluster page.
 * Only provided fields are updated.
 */
export function updateClusterPage(
  projectId: string,
  clusterId: string,
  pageId: string,
  data: ClusterPageUpdate
): Promise<ClusterPage> {
  return apiClient.patch<ClusterPage>(
    `/projects/${projectId}/clusters/${clusterId}/pages/${pageId}`,
    data
  );
}

/**
 * Bulk-approve a cluster, bridging approved pages into the content pipeline.
 */
export function bulkApproveCluster(
  projectId: string,
  clusterId: string
): Promise<ClusterBulkApproveResponse> {
  return apiClient.post<ClusterBulkApproveResponse>(
    `/projects/${projectId}/clusters/${clusterId}/approve`
  );
}

/**
 * Delete a cluster. Only allowed if status is before 'approved'.
 */
export function deleteCluster(
  projectId: string,
  clusterId: string
): Promise<void> {
  return apiClient.delete<void>(
    `/projects/${projectId}/clusters/${clusterId}`
  );
}

// =============================================================================
// EXPORT API FUNCTIONS
// =============================================================================

/**
 * Export approved pages as a Matrixify-compatible CSV and trigger browser download.
 * Uses fetch directly (not apiClient) to handle blob response.
 */
export async function exportProject(
  projectId: string,
  pageIds?: string[]
): Promise<void> {
  let url = `${API_BASE_URL}/projects/${projectId}/export`;
  if (pageIds && pageIds.length > 0) {
    url += `?page_ids=${pageIds.join(",")}`;
  }

  const response = await fetch(url);

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

  const blob = await response.blob();

  // Extract filename from Content-Disposition header
  const disposition = response.headers.get("Content-Disposition");
  let filename = "export.csv";
  if (disposition) {
    const match = disposition.match(/filename="?([^";\n]+)"?/);
    if (match) {
      filename = match[1];
    }
  }

  // Trigger browser download via hidden anchor
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(blobUrl);
}
