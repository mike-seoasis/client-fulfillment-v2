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
  source: string;
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
 * Regenerate unapproved keywords in a cluster.
 * Keeps approved pages and replaces unapproved ones with fresh suggestions.
 */
export function regenerateCluster(
  projectId: string,
  clusterId: string
): Promise<Cluster> {
  return apiClient.post<Cluster>(
    `/projects/${projectId}/clusters/${clusterId}/regenerate`
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
// INTERNAL LINKING API TYPES
// =============================================================================

/** A single internal link between two pages. */
export interface InternalLink {
  id: string;
  source_page_id: string;
  target_page_id: string;
  target_url: string;
  target_title: string;
  target_keyword: string;
  anchor_text: string;
  anchor_type: string;
  position_in_content: number | null;
  is_mandatory: boolean;
  placement_method: string;
  status: string;
}

/** A single outbound link from a page in the link map. */
export interface LinkMapOutboundLink {
  anchor_text: string;
  target_url: string;
  target_title: string;
  anchor_type: string;
  placement_method: string;
}

/** Summary of a page within the link map overview. */
export interface LinkMapPage {
  page_id: string;
  url: string;
  title: string;
  is_priority: boolean;
  role: string | null;
  labels: string[] | null;
  outbound_count: number;
  inbound_count: number;
  outbound_links: LinkMapOutboundLink[];
  methods: Record<string, number>;
  validation_status: string;
}

/** Full link map overview for a project scope. */
export interface LinkMap {
  scope: string;
  total_links: number;
  total_pages: number;
  avg_links_per_page: number;
  validation_pass_rate: number;
  method_breakdown: Record<string, number>;
  anchor_diversity: Record<string, number>;
  pages: LinkMapPage[];
  hierarchy: Record<string, unknown> | null;
}

/** All links for a specific page with diversity metrics. */
export interface PageLinks {
  outbound_links: InternalLink[];
  inbound_links: InternalLink[];
  anchor_diversity: Record<string, number>;
  diversity_score: string;
}

/** Status of the link planning pipeline. */
export interface PlanStatus {
  status: "idle" | "planning" | "complete" | "failed";
  current_step: number | null;
  step_label: string | null;
  pages_processed: number;
  total_pages: number;
  total_links: number | null;
  error: string | null;
}

/** Anchor text suggestions for a target page. */
export interface AnchorSuggestions {
  primary_keyword: string;
  pop_variations: string[];
  usage_counts: Record<string, number>;
}

/** Request to manually add an internal link. */
export interface AddLinkRequest {
  source_page_id: string;
  target_page_id: string;
  anchor_text: string;
  anchor_type: "exact_match" | "partial_match" | "natural";
}

/** Request to edit an existing link's anchor. */
export interface EditLinkRequest {
  anchor_text: string;
  anchor_type: "exact_match" | "partial_match" | "natural";
}

// =============================================================================
// INTERNAL LINKING API FUNCTIONS
// =============================================================================

/**
 * Trigger link planning for a project scope.
 * Returns 202 with initial status. Poll with getPlanStatus for progress.
 */
export function planLinks(
  projectId: string,
  scope: "onboarding" | "cluster",
  clusterId?: string
): Promise<PlanStatus> {
  return apiClient.post<PlanStatus>(
    `/projects/${projectId}/links/plan`,
    { scope, cluster_id: clusterId ?? null }
  );
}

/**
 * Get link planning pipeline status for a project scope.
 * Returns idle if no pipeline has run.
 */
export function getPlanStatus(
  projectId: string,
  scope: "onboarding" | "cluster",
  clusterId?: string
): Promise<PlanStatus> {
  const params = new URLSearchParams({ scope });
  if (clusterId) params.set("cluster_id", clusterId);
  return apiClient.get<PlanStatus>(
    `/projects/${projectId}/links/plan/status?${params.toString()}`
  );
}

/**
 * Get the link map overview for a project scope.
 * Returns aggregate stats, per-page summaries, and optional hierarchy.
 */
export function getLinkMap(
  projectId: string,
  scope: "onboarding" | "cluster" = "onboarding",
  clusterId?: string
): Promise<LinkMap> {
  const params = new URLSearchParams({ scope });
  if (clusterId) params.set("cluster_id", clusterId);
  return apiClient.get<LinkMap>(
    `/projects/${projectId}/links?${params.toString()}`
  );
}

/**
 * Get all links for a specific page with diversity metrics.
 * Returns outbound/inbound links and anchor diversity score.
 */
export function getPageLinks(
  projectId: string,
  pageId: string
): Promise<PageLinks> {
  return apiClient.get<PageLinks>(
    `/projects/${projectId}/links/page/${pageId}`
  );
}

/**
 * Manually add an internal link.
 * Validates silo integrity and injects the link into content.
 */
export function addLink(
  projectId: string,
  data: AddLinkRequest
): Promise<InternalLink> {
  return apiClient.post<InternalLink>(
    `/projects/${projectId}/links`,
    data
  );
}

/**
 * Remove a discretionary internal link.
 * Strips the anchor tag from content and marks the link as removed.
 */
export function removeLink(
  projectId: string,
  linkId: string
): Promise<void> {
  return apiClient.delete<void>(
    `/projects/${projectId}/links/${linkId}`
  );
}

/**
 * Edit an existing link's anchor text and type.
 * Updates both the InternalLink record and the HTML content.
 */
export function editLink(
  projectId: string,
  linkId: string,
  data: EditLinkRequest
): Promise<InternalLink> {
  return apiClient.put<InternalLink>(
    `/projects/${projectId}/links/${linkId}`,
    data
  );
}

/**
 * Get anchor text suggestions for a target page.
 * Returns primary keyword, POP variations, and usage counts.
 */
export function getAnchorSuggestions(
  projectId: string,
  targetPageId: string
): Promise<AnchorSuggestions> {
  return apiClient.get<AnchorSuggestions>(
    `/projects/${projectId}/links/suggestions/${targetPageId}`
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
  pageIds?: string[],
  exportLabel?: string
): Promise<void> {
  const params = new URLSearchParams();
  if (pageIds && pageIds.length > 0) {
    params.set("page_ids", pageIds.join(","));
  }
  if (exportLabel) {
    params.set("export_label", exportLabel);
  }
  const qs = params.toString();
  let url = `${API_BASE_URL}/projects/${projectId}/export`;
  if (qs) {
    url += `?${qs}`;
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

// =============================================================================
// BLOG CAMPAIGN API TYPES
// =============================================================================

/** Request to create a new blog campaign from a keyword cluster. */
export interface BlogCampaignCreate {
  cluster_id: string;
  name?: string | null;
}

/** A single blog post within a campaign. */
export interface BlogPost {
  id: string;
  campaign_id: string;
  primary_keyword: string;
  url_slug: string;
  search_volume: number | null;
  source_page_id: string | null;
  title: string | null;
  meta_description: string | null;
  content: string | null;
  is_approved: boolean;
  content_status: string;
  content_approved: boolean;
  pop_brief: Record<string, unknown> | null;
  qa_results: Record<string, unknown> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

/** Full blog campaign with nested posts. */
export interface BlogCampaign {
  id: string;
  project_id: string;
  cluster_id: string;
  name: string;
  status: string;
  generation_metadata: Record<string, unknown> | null;
  posts: BlogPost[];
  created_at: string;
  updated_at: string;
}

/** Summary campaign for list views. */
export interface BlogCampaignListItem {
  id: string;
  name: string;
  status: string;
  cluster_name: string;
  post_count: number;
  approved_count: number;
  content_complete_count: number;
  created_at: string;
}

/** Request to update keyword-level fields on a blog post. */
export interface BlogPostUpdate {
  primary_keyword?: string | null;
  url_slug?: string | null;
  is_approved?: boolean | null;
  title?: string | null;
}

/** Request to update content fields on a blog post. */
export interface BlogContentUpdate {
  title?: string | null;
  meta_description?: string | null;
  content?: string | null;
}

/** Per-post status within a content generation run. */
export interface BlogPostGenerationStatusItem {
  post_id: string;
  primary_keyword: string;
  content_status: string;
}

/** Status of content generation across a blog campaign. */
export interface BlogContentGenerationStatus {
  overall_status: string;
  posts_total: number;
  posts_completed: number;
  posts_failed: number;
  posts: BlogPostGenerationStatusItem[];
}

/** Response when blog content generation is triggered. */
export interface BlogContentTriggerResponse {
  status: string;
  message: string;
}

/** Response for bulk blog content approval. */
export interface BlogBulkApproveResponse {
  approved_count: number;
}

/** Single post export with full HTML content and metadata. */
export interface BlogExportItem {
  post_id: string;
  primary_keyword: string;
  url_slug: string;
  title: string | null;
  meta_description: string | null;
  html_content: string | null;
  word_count: number;
}

/** Response when blog link planning is triggered. */
export interface BlogLinkPlanTriggerResponse {
  status: string;
  message: string;
}

/** Status of blog link planning for a post. */
export interface BlogLinkStatusResponse {
  status: string;
  step: string | null;
  links_planned: number;
  error: string | null;
}

/** A single planned/injected link for a blog post. */
export interface BlogLinkMapItem {
  target_page_id: string;
  anchor_text: string;
  anchor_type: string;
  target_keyword: string | null;
  target_url: string | null;
  placement_method: string;
  status: string;
}

/** Full link map for a blog post. */
export interface BlogLinkMapResponse {
  blog_post_id: string;
  crawled_page_id: string | null;
  total_links: number;
  links: BlogLinkMapItem[];
}

// =============================================================================
// BLOG CAMPAIGN API FUNCTIONS
// =============================================================================

/**
 * Create a new blog campaign from a keyword cluster.
 * Runs the 4-stage topic discovery pipeline (~5-10s).
 */
export function createBlogCampaign(
  projectId: string,
  data: BlogCampaignCreate
): Promise<BlogCampaign> {
  return apiClient.post<BlogCampaign>(
    `/projects/${projectId}/blogs`,
    data
  );
}

/**
 * List all blog campaigns for a project.
 * Returns summary data with post counts.
 */
export function getBlogCampaigns(
  projectId: string
): Promise<BlogCampaignListItem[]> {
  return apiClient.get<BlogCampaignListItem[]>(
    `/projects/${projectId}/blogs`
  );
}

/**
 * Get a single blog campaign with all its posts.
 */
export function getBlogCampaign(
  projectId: string,
  blogId: string
): Promise<BlogCampaign> {
  return apiClient.get<BlogCampaign>(
    `/projects/${projectId}/blogs/${blogId}`
  );
}

/**
 * Update keyword-level fields on a blog post.
 * Only provided fields are updated.
 */
export function updateBlogPost(
  projectId: string,
  blogId: string,
  postId: string,
  data: BlogPostUpdate
): Promise<BlogPost> {
  return apiClient.patch<BlogPost>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}`,
    data
  );
}

/**
 * Bulk approve all unapproved posts in a blog campaign.
 * Returns approved count and campaign status.
 */
export function bulkApproveBlogPosts(
  projectId: string,
  blogId: string
): Promise<{ approved_count: number; campaign_status: string }> {
  return apiClient.post<{ approved_count: number; campaign_status: string }>(
    `/projects/${projectId}/blogs/${blogId}/approve`
  );
}

/**
 * Delete a blog campaign and all its posts.
 */
export function deleteBlogCampaign(
  projectId: string,
  blogId: string
): Promise<void> {
  return apiClient.delete<void>(
    `/projects/${projectId}/blogs/${blogId}`
  );
}

// =============================================================================
// BLOG CONTENT API FUNCTIONS
// =============================================================================

/**
 * Trigger blog content generation for all approved posts in a campaign.
 * Returns 202 on success. Background task runs the pipeline.
 */
export function triggerBlogContentGeneration(
  projectId: string,
  blogId: string,
  forceRefresh: boolean = false
): Promise<BlogContentTriggerResponse> {
  const params = forceRefresh ? '?force_refresh=true' : '';
  return apiClient.post<BlogContentTriggerResponse>(
    `/projects/${projectId}/blogs/${blogId}/generate-content${params}`
  );
}

/**
 * Poll content generation status for a blog campaign.
 * Returns overall status and per-post breakdown.
 */
export function getBlogContentStatus(
  projectId: string,
  blogId: string
): Promise<BlogContentGenerationStatus> {
  return apiClient.get<BlogContentGenerationStatus>(
    `/projects/${projectId}/blogs/${blogId}/content-status`
  );
}

/**
 * Get full content for a specific blog post.
 * Returns 404 if content has not been generated yet.
 */
export function getBlogPostContent(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogPost> {
  return apiClient.get<BlogPost>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/content`
  );
}

/**
 * Update content fields on a blog post (partial update).
 * Clears content approval when content changes.
 */
export function updateBlogPostContent(
  projectId: string,
  blogId: string,
  postId: string,
  data: BlogContentUpdate
): Promise<BlogPost> {
  return apiClient.put<BlogPost>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/content`,
    data
  );
}

/**
 * Approve or unapprove content for a blog post.
 * Pass value=false to unapprove.
 */
export function approveBlogPostContent(
  projectId: string,
  blogId: string,
  postId: string,
  value: boolean = true
): Promise<BlogPost> {
  const queryParam = value ? "" : "?value=false";
  return apiClient.post<BlogPost>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/approve-content${queryParam}`
  );
}

/**
 * Re-run quality checks on current blog post content.
 * Returns updated post with fresh qa_results.
 */
export function recheckBlogPostContent(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogPost> {
  return apiClient.post<BlogPost>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/recheck`
  );
}

/**
 * Bulk approve all eligible blog posts (complete + QA passed) in a campaign.
 * Returns count of newly approved posts.
 */
export function bulkApproveBlogContent(
  projectId: string,
  blogId: string
): Promise<BlogBulkApproveResponse> {
  return apiClient.post<BlogBulkApproveResponse>(
    `/projects/${projectId}/blogs/${blogId}/bulk-approve-content`
  );
}

// =============================================================================
// BLOG LINK API FUNCTIONS
// =============================================================================

/**
 * Trigger link planning for a blog post.
 * Returns 202 Accepted. Poll with getBlogLinkStatus for progress.
 */
export function triggerBlogLinkPlanning(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogLinkPlanTriggerResponse> {
  return apiClient.post<BlogLinkPlanTriggerResponse>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/plan-links`
  );
}

/**
 * Poll link planning status for a blog post.
 */
export function getBlogLinkStatus(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogLinkStatusResponse> {
  return apiClient.get<BlogLinkStatusResponse>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/link-status`
  );
}

/**
 * Get the link map (all planned/injected links) for a blog post.
 */
export function getBlogLinkMap(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogLinkMapResponse> {
  return apiClient.get<BlogLinkMapResponse>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/link-map`
  );
}

// =============================================================================
// BLOG EXPORT API FUNCTIONS
// =============================================================================

/**
 * Export all approved posts in a blog campaign as clean HTML.
 * Returns JSON array of export items.
 */
export function getBlogExport(
  projectId: string,
  blogId: string
): Promise<BlogExportItem[]> {
  return apiClient.get<BlogExportItem[]>(
    `/projects/${projectId}/blogs/${blogId}/export`
  );
}

/**
 * Export a single blog post as clean HTML.
 */
export function getBlogPostExport(
  projectId: string,
  blogId: string,
  postId: string
): Promise<BlogExportItem> {
  return apiClient.get<BlogExportItem>(
    `/projects/${projectId}/blogs/${blogId}/posts/${postId}/export`
  );
}

/**
 * Download a blog post as an HTML file.
 * Triggers browser download via hidden anchor (same pattern as exportProject).
 */
export async function downloadBlogPostHtml(
  projectId: string,
  blogId: string,
  postId: string
): Promise<void> {
  const url = `${API_BASE_URL}/projects/${projectId}/blogs/${blogId}/posts/${postId}/download`;

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
  let filename = "blog-post.html";
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

// =============================================================================
// REDDIT COMMENT GENERATION API TYPES
// =============================================================================

/** Response from single comment generation (POST). */
export interface RedditCommentResponse {
  id: string;
  post_id: string;
  project_id: string;
  account_id: string | null;
  body: string;
  original_body: string;
  is_promotional: boolean;
  approach_type: string | null;
  status: string;
  reject_reason: string | null;
  crowdreply_task_id: string | null;
  posted_url: string | null;
  posted_at: string | null;
  generation_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  post: RedditDiscoveredPost | null;
}

/** Request body for single comment generation. */
export interface GenerateCommentRequest {
  is_promotional?: boolean;
}

/** Request body for batch comment generation. */
export interface BatchGenerateRequest {
  post_ids?: string[];
}

/** Response from batch generation trigger (202). */
export interface BatchGenerateResponse {
  message: string;
}

/** Polling response for generation progress. */
export interface GenerationStatusResponse {
  status: "idle" | "generating" | "complete" | "failed";
  total_posts: number;
  posts_generated: number;
  error: string | null;
}

/** Request body for updating a comment. */
export interface RedditCommentUpdateRequest {
  body?: string;
}

// =============================================================================
// REDDIT COMMENT GENERATION API FUNCTIONS
// =============================================================================

/**
 * Generate a comment for a single Reddit post.
 * Synchronous - returns the created comment (201).
 */
export function generateComment(
  projectId: string,
  postId: string,
  isPromotional?: boolean
): Promise<RedditCommentResponse> {
  const body: GenerateCommentRequest = {};
  if (isPromotional !== undefined) body.is_promotional = isPromotional;
  return apiClient.post<RedditCommentResponse>(
    `/projects/${projectId}/reddit/posts/${postId}/generate`,
    Object.keys(body).length > 0 ? body : undefined
  );
}

/**
 * Trigger batch comment generation for a project.
 * Returns 202. Poll with fetchGenerationStatus for progress.
 */
export function generateBatch(
  projectId: string,
  postIds?: string[]
): Promise<BatchGenerateResponse> {
  const body: BatchGenerateRequest = {};
  if (postIds && postIds.length > 0) body.post_ids = postIds;
  return apiClient.post<BatchGenerateResponse>(
    `/projects/${projectId}/reddit/generate-batch`,
    Object.keys(body).length > 0 ? body : undefined
  );
}

/**
 * Poll batch generation status for a project.
 * Returns "idle" if no generation is active.
 */
export function fetchGenerationStatus(
  projectId: string
): Promise<GenerationStatusResponse> {
  return apiClient.get<GenerationStatusResponse>(
    `/projects/${projectId}/reddit/generate/status`
  );
}

/**
 * List generated comments for a project with optional filters.
 */
export function fetchComments(
  projectId: string,
  filters?: { status?: string; post_id?: string }
): Promise<RedditCommentResponse[]> {
  const searchParams = new URLSearchParams();
  if (filters?.status) searchParams.set("status", filters.status);
  if (filters?.post_id) searchParams.set("post_id", filters.post_id);
  const qs = searchParams.toString();
  return apiClient.get<RedditCommentResponse[]>(
    `/projects/${projectId}/reddit/comments${qs ? `?${qs}` : ""}`
  );
}

/**
 * Update a comment's body text (PATCH).
 */
export function updateComment(
  projectId: string,
  commentId: string,
  data: RedditCommentUpdateRequest
): Promise<RedditCommentResponse> {
  return apiClient.patch<RedditCommentResponse>(
    `/projects/${projectId}/reddit/comments/${commentId}`,
    data
  );
}

/**
 * Delete a draft comment (DELETE).
 */
export function deleteComment(
  projectId: string,
  commentId: string
): Promise<void> {
  return apiClient.delete<void>(
    `/projects/${projectId}/reddit/comments/${commentId}`
  );
}

// =============================================================================
// WORDPRESS LINKER API TYPES & FUNCTIONS
// =============================================================================

/** WordPress connect response. */
export interface WPConnectResponse {
  site_name: string;
  site_url: string;
  total_posts: number;
  valid: boolean;
}

/** WordPress import response (202 with job_id). */
export interface WPImportResponse {
  project_id: string;
  posts_imported: number;
  job_id: string;
}

/** Progress response for any WP background operation. */
export interface WPProgressResponse {
  job_id: string;
  step: string;
  step_label: string;
  status: "running" | "complete" | "failed";
  current: number;
  total: number;
  error?: string;
  result?: Record<string, unknown>;
}

/** Single taxonomy label. */
export interface WPTaxonomyLabel {
  name: string;
  description: string;
  post_count: number;
}

/** Label assignment for a single post. */
export interface WPLabelAssignment {
  page_id: string;
  title: string;
  url: string;
  labels: string[];
  primary_label: string;
}

/** Label review response with taxonomy and assignments. */
export interface WPLabelReviewResponse {
  taxonomy: WPTaxonomyLabel[];
  assignments: WPLabelAssignment[];
  total_groups: number;
}

/** Silo group stats for review. */
export interface WPReviewGroup {
  group_name: string;
  post_count: number;
  link_count: number;
  avg_links_per_post: number;
  collection_link_count: number;
}

/** A project available for importing WP posts into. */
export interface WPProjectOption {
  id: string;
  name: string;
  site_url: string;
  collection_page_count: number;
}

/** Link review response. */
export interface WPReviewResponse {
  total_posts: number;
  total_links: number;
  avg_links_per_post: number;
  groups: WPReviewGroup[];
  validation_pass_rate: number;
}

// =============================================================================
// REDDIT API TYPES
// =============================================================================

/** A Reddit account used for engagement. */
export interface RedditAccount {
  id: string;
  username: string;
  status: string;
  warmup_stage: string;
  niche_tags: string[];
  karma_post: number;
  karma_comment: number;
  account_age_days: number | null;
  cooldown_until: string | null;
  last_used_at: string | null;
  notes: string | null;
  extra_metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** Request to create a new Reddit account. */
export interface RedditAccountCreate {
  username: string;
  niche_tags?: string[];
  warmup_stage?: string;
  notes?: string | null;
}

/** Request to update a Reddit account (all fields optional). */
export interface RedditAccountUpdate {
  username?: string;
  status?: string;
  warmup_stage?: string;
  niche_tags?: string[];
  karma_post?: number;
  karma_comment?: number;
  account_age_days?: number | null;
  cooldown_until?: string | null;
  last_used_at?: string | null;
  notes?: string | null;
}

/** Per-project Reddit configuration. */
export interface RedditProjectConfig {
  id: string;
  project_id: string;
  search_keywords: string[];
  target_subreddits: string[];
  banned_subreddits: string[];
  competitors: string[];
  comment_instructions: string | null;
  niche_tags: string[];
  discovery_settings: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Request to create/update a project's Reddit config. */
export interface RedditProjectConfigCreate {
  search_keywords?: string[];
  target_subreddits?: string[];
  banned_subreddits?: string[];
  competitors?: string[];
  comment_instructions?: string | null;
  niche_tags?: string[];
  discovery_settings?: Record<string, unknown> | null;
  is_active?: boolean;
}

// =============================================================================
// REDDIT API FUNCTIONS
// =============================================================================

/**
 * List all Reddit accounts with optional filters.
 */
export function fetchRedditAccounts(params?: {
  niche?: string;
  status?: string;
  warmup_stage?: string;
}): Promise<RedditAccount[]> {
  const searchParams = new URLSearchParams();
  if (params?.niche) searchParams.set("niche", params.niche);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.warmup_stage) searchParams.set("warmup_stage", params.warmup_stage);
  const qs = searchParams.toString();
  return apiClient.get<RedditAccount[]>(
    `/reddit/accounts${qs ? `?${qs}` : ""}`
  );
}

/**
 * Create a new Reddit account. Returns 409 if username already exists.
 */
export function createRedditAccount(
  data: RedditAccountCreate
): Promise<RedditAccount> {
  return apiClient.post<RedditAccount>("/reddit/accounts", data);
}

/**
 * Update a Reddit account. Only provided fields are updated.
 */
export function updateRedditAccount(
  accountId: string,
  data: RedditAccountUpdate
): Promise<RedditAccount> {
  return apiClient.patch<RedditAccount>(
    `/reddit/accounts/${accountId}`,
    data
  );
}

/**
 * Delete a Reddit account.
 */
export function deleteRedditAccount(accountId: string): Promise<void> {
  return apiClient.delete<void>(`/reddit/accounts/${accountId}`);
}

/**
 * Get Reddit config for a project. Returns null if none exists (404).
 */
export async function fetchRedditConfig(
  projectId: string
): Promise<RedditProjectConfig | null> {
  try {
    return await apiClient.get<RedditProjectConfig>(
      `/projects/${projectId}/reddit/config`
    );
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null;
    }
    throw err;
  }
}

/**
 * Create or update Reddit config for a project (upsert).
 * Returns 201 if created, 200 if updated.
 */
export function upsertRedditConfig(
  projectId: string,
  data: RedditProjectConfigCreate
): Promise<RedditProjectConfig> {
  return apiClient.post<RedditProjectConfig>(
    `/projects/${projectId}/reddit/config`,
    data
  );
}

// =============================================================================
// REDDIT DISCOVERY API TYPES
// =============================================================================

/** Response when discovery is triggered (202 Accepted). */
export interface DiscoveryTriggerResponse {
  message: string;
}

/** Progress status for a running discovery pipeline. */
export interface DiscoveryStatus {
  status: "searching" | "scoring" | "storing" | "complete" | "failed" | "idle";
  total_keywords: number;
  keywords_searched: number;
  total_posts_found: number;
  posts_scored: number;
  posts_stored: number;
  error: string | null;
}

/** A discovered Reddit post. */
export interface RedditDiscoveredPost {
  id: string;
  project_id: string;
  reddit_post_id: string | null;
  subreddit: string;
  title: string;
  url: string;
  snippet: string | null;
  keyword: string | null;
  intent: string | null;
  intent_categories: string[] | null;
  relevance_score: number | null;
  matched_keywords: string[] | null;
  ai_evaluation: Record<string, unknown> | null;
  filter_status: string;
  serp_position: number | null;
  discovered_at: string;
  created_at: string;
  updated_at: string;
}

/** Params for filtering Reddit posts. */
export interface RedditPostsFilterParams {
  filter_status?: string;
  intent?: string;
  subreddit?: string;
}

/** Request to update a post's filter status. */
export interface RedditPostUpdateRequest {
  filter_status: string;
}

/** Request for bulk post status updates. */
export interface RedditBulkPostActionRequest {
  post_ids: string[];
  filter_status: string;
}

// =============================================================================
// REDDIT DISCOVERY API FUNCTIONS
// =============================================================================

/**
 * Trigger Reddit post discovery for a project.
 * Returns 202 Accepted. Poll with fetchDiscoveryStatus for progress.
 */
export function triggerRedditDiscovery(
  projectId: string,
  timeRange?: string
): Promise<DiscoveryTriggerResponse> {
  return apiClient.post<DiscoveryTriggerResponse>(
    `/projects/${projectId}/reddit/discover`,
    timeRange ? { time_range: timeRange } : undefined
  );
}

/**
 * Poll discovery pipeline status for a project.
 * Returns idle if no discovery has been triggered.
 */
export function fetchDiscoveryStatus(
  projectId: string
): Promise<DiscoveryStatus> {
  return apiClient.get<DiscoveryStatus>(
    `/projects/${projectId}/reddit/discover/status`
  );
}

/**
 * List discovered Reddit posts for a project with optional filters.
 */
export function fetchRedditPosts(
  projectId: string,
  params?: RedditPostsFilterParams
): Promise<RedditDiscoveredPost[]> {
  const searchParams = new URLSearchParams();
  if (params?.filter_status) searchParams.set("filter_status", params.filter_status);
  if (params?.intent) searchParams.set("intent", params.intent);
  if (params?.subreddit) searchParams.set("subreddit", params.subreddit);
  const qs = searchParams.toString();
  return apiClient.get<RedditDiscoveredPost[]>(
    `/projects/${projectId}/reddit/posts${qs ? `?${qs}` : ""}`
  );
}

/**
 * Update a post's filter status (approve/reject).
 */
export function updateRedditPostStatus(
  projectId: string,
  postId: string,
  data: RedditPostUpdateRequest
): Promise<RedditDiscoveredPost> {
  return apiClient.patch<RedditDiscoveredPost>(
    `/projects/${projectId}/reddit/posts/${postId}`,
    data
  );
}

/**
 * Bulk update filter status for multiple posts.
 */
export function bulkUpdateRedditPosts(
  projectId: string,
  data: RedditBulkPostActionRequest
): Promise<{ updated_count: number }> {
  return apiClient.post<{ updated_count: number }>(
    `/projects/${projectId}/reddit/posts/bulk-action`,
    data
  );
}

// =============================================================================
// WORDPRESS LINKER API TYPES & FUNCTIONS
// =============================================================================

/** Validate WP credentials. */
export function wpConnect(
  siteUrl: string,
  username: string,
  appPassword: string
): Promise<WPConnectResponse> {
  return apiClient.post<WPConnectResponse>("/wordpress/connect", {
    site_url: siteUrl,
    username,
    app_password: appPassword,
  });
}

/** List projects with onboarding pages (for project picker). */
export function wpListLinkableProjects(): Promise<WPProjectOption[]> {
  return apiClient.get<WPProjectOption[]>("/wordpress/projects");
}

/** Import WP posts (returns 202 with job_id). */
export function wpImport(
  siteUrl: string,
  username: string,
  appPassword: string,
  titleFilter?: string[],
  postStatus: string = "publish",
  existingProjectId?: string | null,
): Promise<WPImportResponse> {
  return apiClient.post<WPImportResponse>("/wordpress/import", {
    site_url: siteUrl,
    username,
    app_password: appPassword,
    title_filter: titleFilter || null,
    post_status: postStatus,
    existing_project_id: existingProjectId || null,
  });
}

/** Poll progress for a background job. */
export function wpGetProgress(jobId: string): Promise<WPProgressResponse> {
  return apiClient.get<WPProgressResponse>(`/wordpress/progress/${jobId}`);
}

/** Start POP analysis (returns 202 with job_id). */
export function wpAnalyze(projectId: string): Promise<WPProgressResponse> {
  return apiClient.post<WPProgressResponse>("/wordpress/analyze", {
    project_id: projectId,
  });
}

/** Start blog labeling (returns 202 with job_id). */
export function wpLabel(projectId: string): Promise<WPProgressResponse> {
  return apiClient.post<WPProgressResponse>("/wordpress/label", {
    project_id: projectId,
  });
}

/** Get taxonomy + label assignments for review. */
export function wpGetLabels(projectId: string): Promise<WPLabelReviewResponse> {
  return apiClient.get<WPLabelReviewResponse>(
    `/wordpress/labels/${projectId}`
  );
}

/** Start link planning (returns 202 with job_id). */
export function wpPlanLinks(projectId: string): Promise<WPProgressResponse> {
  return apiClient.post<WPProgressResponse>("/wordpress/plan", {
    project_id: projectId,
  });
}

/** Get link review stats. */
export function wpGetReview(projectId: string): Promise<WPReviewResponse> {
  return apiClient.get<WPReviewResponse>(`/wordpress/review/${projectId}`);
}

/** Start export to WordPress (returns 202 with job_id). */
export function wpExport(
  projectId: string,
  siteUrl: string,
  username: string,
  appPassword: string,
  titleFilter?: string[]
): Promise<WPProgressResponse> {
  return apiClient.post<WPProgressResponse>("/wordpress/export", {
    project_id: projectId,
    site_url: siteUrl,
    username,
    app_password: appPassword,
    title_filter: titleFilter || null,
  });
}
