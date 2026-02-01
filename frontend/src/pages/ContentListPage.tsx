/**
 * ContentListPage - Main page for viewing and managing generated content
 *
 * Features:
 * - Search/filter content by title or type
 * - Status filtering (All, Pending Review, Approved, Rejected)
 * - Grid/list view of content items
 * - Loading states and error handling
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Log filter changes at debug level
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  FileText,
  Clock,
  CheckCircle2,
  XCircle,
  RefreshCw,
  ArrowLeft,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { addBreadcrumb } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/form-field'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Content status type matching backend */
type ContentStatus = 'pending_review' | 'approved' | 'rejected'

/** Content item matching backend GeneratedContent schema */
interface ContentItem {
  id: string
  project_id: string
  title: string
  content: string
  content_type: string
  status: ContentStatus
  tone: string
  word_count: number
  generated_at: string
  reviewed_at?: string | null
  reviewer_notes?: string | null
}

/** Content list response from API */
interface ContentListResponse {
  items: ContentItem[]
  total: number
  page: number
  per_page: number
}

// ============================================================================
// Constants
// ============================================================================

/** Status filter options */
const STATUS_FILTER_OPTIONS = [
  { value: 'all', label: 'All Content', icon: FileText },
  { value: 'pending_review', label: 'Pending Review', icon: Clock },
  { value: 'approved', label: 'Approved', icon: CheckCircle2 },
  { value: 'rejected', label: 'Rejected', icon: XCircle },
] as const

type StatusFilter = (typeof STATUS_FILTER_OPTIONS)[number]['value']

/** Status badge colors */
const STATUS_COLORS: Record<ContentStatus, { bg: string; text: string }> = {
  pending_review: { bg: 'bg-warning-100', text: 'text-warning-800' },
  approved: { bg: 'bg-success-100', text: 'text-success-800' },
  rejected: { bg: 'bg-error-100', text: 'text-error-800' },
}

/** Status display labels */
const STATUS_LABELS: Record<ContentStatus, string> = {
  pending_review: 'Pending Review',
  approved: 'Approved',
  rejected: 'Rejected',
}

/** Content type labels */
const CONTENT_TYPE_LABELS: Record<string, string> = {
  blog_post: 'Blog Post',
  landing_page: 'Landing Page',
  product_description: 'Product Description',
  email: 'Email Copy',
  social_post: 'Social Media Post',
  faq: 'FAQ Entry',
  collection: 'Collection',
  product: 'Product',
  blog: 'Blog',
  landing: 'Landing',
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a date string for display
 */
function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return dateString
  }
}

/**
 * Format a date with time for display
 */
function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Get display label for content type
 */
function getContentTypeLabel(type: string): string {
  return CONTENT_TYPE_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Empty state component shown when no content exists
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 bg-cream-200 rounded-2xl flex items-center justify-center mb-6">
        <FileText className="w-8 h-8 text-warmgray-400" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold text-warmgray-900 mb-2">
        No content yet
      </h3>
      <p className="text-warmgray-500 mb-6 max-w-sm">
        Content will appear here once you start generating. Use the Content Generation panel in your project to create content.
      </p>
    </div>
  )
}

/**
 * Empty search results component
 */
function NoSearchResults({ searchQuery, statusFilter }: { searchQuery: string; statusFilter: StatusFilter }) {
  const filterLabel = STATUS_FILTER_OPTIONS.find((o) => o.value === statusFilter)?.label || 'selected filter'

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-14 h-14 bg-cream-200 rounded-xl flex items-center justify-center mb-4">
        <Search className="w-6 h-6 text-warmgray-400" />
      </div>
      <h3 className="text-base font-semibold text-warmgray-900 mb-1">
        No results found
      </h3>
      <p className="text-warmgray-500 text-sm">
        {searchQuery
          ? `No content matches "${searchQuery}"${statusFilter !== 'all' ? ` in ${filterLabel.toLowerCase()}` : ''}.`
          : `No content with ${filterLabel.toLowerCase()} status.`}
      </p>
    </div>
  )
}

/**
 * Error state component for API failures
 */
function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-16 h-16 bg-error-100 rounded-2xl flex items-center justify-center mb-6">
        <XCircle className="w-8 h-8 text-error-500" aria-hidden="true" />
      </div>
      <h3 className="text-lg font-semibold text-warmgray-900 mb-2">
        Failed to load content
      </h3>
      <p className="text-warmgray-500 mb-6 max-w-sm">
        We couldn't load your content. Please check your connection and try again.
      </p>
      <Button onClick={onRetry} variant="outline">
        Try again
      </Button>
    </div>
  )
}

/**
 * Content card component
 */
function ContentCard({
  content,
  onClick,
  className,
}: {
  content: ContentItem
  onClick?: (content: ContentItem) => void
  className?: string
}) {
  const statusColors = STATUS_COLORS[content.status]

  const handleClick = () => {
    if (onClick) {
      addBreadcrumb(`Clicked content: ${content.title}`, 'user-action', {
        contentId: content.id,
        contentStatus: content.status,
      })
      onClick(content)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (onClick && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault()
      handleClick()
    }
  }

  return (
    <div
      className={cn(
        'card-hover cursor-pointer group',
        'focus-visible:ring-2 focus-visible:ring-primary-400 focus-visible:ring-offset-2 focus-visible:ring-offset-cream-50',
        className
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={onClick ? `View content: ${content.title}` : undefined}
    >
      {/* Header: Title and Status */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-warmgray-900 truncate group-hover:text-primary-700 transition-colors duration-200">
            {content.title}
          </h3>
          <p className="text-sm text-warmgray-500 truncate mt-0.5">
            {getContentTypeLabel(content.content_type)} · {content.word_count} words
          </p>
        </div>
        <span
          className={cn(
            'badge shrink-0',
            statusColors.bg,
            statusColors.text
          )}
        >
          {STATUS_LABELS[content.status]}
        </span>
      </div>

      {/* Content preview */}
      <div className="mb-4">
        <p className="text-sm text-warmgray-600 line-clamp-2">
          {content.content.substring(0, 150)}
          {content.content.length > 150 ? '...' : ''}
        </p>
      </div>

      {/* Metadata */}
      <div className="flex items-center gap-4 text-xs text-warmgray-400">
        <span className="flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" />
          {content.tone}
        </span>
        <span className="flex items-center gap-1.5">
          <Clock className="w-3.5 h-3.5" />
          {formatDateTime(content.generated_at)}
        </span>
      </div>

      {/* Review info if reviewed */}
      {content.reviewed_at && (
        <div className="mt-3 pt-3 border-t border-cream-200">
          <p className="text-xs text-warmgray-400">
            Reviewed {formatDate(content.reviewed_at)}
            {content.reviewer_notes && (
              <span className="block mt-1 text-warmgray-500 italic truncate">
                "{content.reviewer_notes}"
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  )
}

/**
 * Loading skeleton for ContentCard
 */
function ContentCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('card', className)}>
      {/* Header skeleton */}
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 space-y-2">
          <div className="h-5 bg-cream-200 rounded-lg w-3/4 animate-pulse-soft" />
          <div className="h-4 bg-cream-200 rounded-lg w-1/2 animate-pulse-soft" />
        </div>
        <div className="h-6 w-20 bg-cream-200 rounded-lg animate-pulse-soft" />
      </div>

      {/* Content skeleton */}
      <div className="space-y-2 mb-4">
        <div className="h-4 bg-cream-200 rounded-lg w-full animate-pulse-soft" />
        <div className="h-4 bg-cream-200 rounded-lg w-4/5 animate-pulse-soft" />
      </div>

      {/* Footer skeleton */}
      <div className="flex items-center gap-4">
        <div className="h-3 bg-cream-200 rounded w-16 animate-pulse-soft" />
        <div className="h-3 bg-cream-200 rounded w-24 animate-pulse-soft" />
      </div>
    </div>
  )
}

/**
 * Status count badge component
 */
function StatusCount({ status, count, isActive, onClick }: {
  status: StatusFilter
  count: number
  isActive: boolean
  onClick: () => void
}) {
  const option = STATUS_FILTER_OPTIONS.find((o) => o.value === status)
  if (!option) return null

  const Icon = option.icon

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-all',
        isActive
          ? 'bg-primary-100 text-primary-800 ring-1 ring-primary-200'
          : 'bg-cream-100 text-warmgray-600 hover:bg-cream-200'
      )}
    >
      <Icon className="w-4 h-4" />
      <span>{option.label}</span>
      <span className={cn(
        'px-1.5 py-0.5 rounded-md text-xs',
        isActive ? 'bg-primary-200 text-primary-900' : 'bg-cream-200 text-warmgray-700'
      )}>
        {count}
      </span>
    </button>
  )
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ContentListPage displays all generated content with search and status filtering
 */
export function ContentListPage() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')

  // Fetch all content across projects (or filter by project if needed)
  const {
    data: contentData,
    isLoading,
    isError,
    error,
    refetch,
  } = useApiQuery<ContentListResponse>({
    queryKey: ['content-list'],
    endpoint: '/api/v1/content',
    requestOptions: {
      userAction: 'Load content list',
      component: 'ContentListPage',
    },
  })

  // Get content items with fallback - memoized to avoid re-computation
  const allContent = useMemo(() => contentData?.items || [], [contentData?.items])

  // Filter content based on search query and status
  const filteredContent = useMemo(() => {
    let filtered = allContent

    // Status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter((item) => item.status === statusFilter)
    }

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim()
      filtered = filtered.filter(
        (item) =>
          item.title.toLowerCase().includes(query) ||
          item.content_type.toLowerCase().includes(query) ||
          item.tone.toLowerCase().includes(query)
      )
    }

    return filtered
  }, [allContent, searchQuery, statusFilter])

  // Compute status counts
  const statusCounts = useMemo(() => {
    return {
      all: allContent.length,
      pending_review: allContent.filter((c) => c.status === 'pending_review').length,
      approved: allContent.filter((c) => c.status === 'approved').length,
      rejected: allContent.filter((c) => c.status === 'rejected').length,
    }
  }, [allContent])

  // Handle content card click
  const handleContentClick = (content: ContentItem) => {
    addBreadcrumb(`Navigate to content: ${content.title}`, 'navigation', {
      contentId: content.id,
      projectId: content.project_id,
    })
    // Navigate to project detail with content context
    navigate(`/projects/${content.project_id}?tab=content&contentId=${content.id}`)
  }

  // Handle search input change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value)
    if (e.target.value) {
      addBreadcrumb(`Search content: ${e.target.value}`, 'user-action')
    }
  }

  // Handle status filter change
  const handleStatusFilterChange = (status: StatusFilter) => {
    setStatusFilter(status)
    addBreadcrumb(`Filter content by status: ${status}`, 'user-action')
  }

  // Handle retry after error
  const handleRetry = () => {
    addBreadcrumb('Retry loading content', 'user-action')
    refetch()
  }

  // Handle refresh
  const handleRefresh = () => {
    addBreadcrumb('Refresh content list', 'user-action')
    refetch()
  }

  // Log error when fetch fails
  if (isError && error) {
    console.error('[ContentListPage] Failed to load content:', {
      error: error.message,
      endpoint: '/api/v1/content',
      status: error.status,
    })
  }

  return (
    <div className="min-h-screen bg-cream-50">
      {/* Page container with max width */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header section */}
        <header className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate('/projects')}
                  className="text-warmgray-500 hover:text-warmgray-700 -ml-2"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Projects
                </Button>
              </div>
              <h1 className="text-2xl font-display font-semibold text-warmgray-900">
                Content
              </h1>
              <p className="mt-1 text-warmgray-500">
                View and manage all generated content
              </p>
            </div>

            {/* Refresh button */}
            <Button
              variant="outline"
              onClick={handleRefresh}
              disabled={isLoading}
              className="shrink-0"
            >
              <RefreshCw className={cn('w-4 h-4', isLoading && 'animate-spin')} />
              Refresh
            </Button>
          </div>

          {/* Status filter tabs */}
          {allContent.length > 0 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {STATUS_FILTER_OPTIONS.map((option) => (
                <StatusCount
                  key={option.value}
                  status={option.value}
                  count={statusCounts[option.value]}
                  isActive={statusFilter === option.value}
                  onClick={() => handleStatusFilterChange(option.value)}
                />
              ))}
            </div>
          )}

          {/* Search input */}
          {allContent.length > 0 && (
            <div className="mt-4 max-w-md">
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-warmgray-400 pointer-events-none"
                  aria-hidden="true"
                />
                <Input
                  type="search"
                  placeholder="Search content..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="pl-10"
                  aria-label="Search content by title or type"
                />
              </div>
            </div>
          )}
        </header>

        {/* Content area */}
        <main>
          {/* Loading state */}
          {isLoading && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <ContentCardSkeleton key={i} />
              ))}
            </div>
          )}

          {/* Error state */}
          {isError && !isLoading && <ErrorState onRetry={handleRetry} />}

          {/* Empty state - no content exists */}
          {!isLoading && !isError && allContent.length === 0 && <EmptyState />}

          {/* No search/filter results */}
          {!isLoading &&
            !isError &&
            allContent.length > 0 &&
            filteredContent.length === 0 && (
              <NoSearchResults searchQuery={searchQuery} statusFilter={statusFilter} />
            )}

          {/* Content grid */}
          {!isLoading && !isError && filteredContent.length > 0 && (
            <>
              {/* Results count */}
              {(searchQuery || statusFilter !== 'all') && (
                <p className="text-sm text-warmgray-500 mb-4">
                  {filteredContent.length}{' '}
                  {filteredContent.length === 1 ? 'item' : 'items'} found
                </p>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredContent.map((content) => (
                  <ContentCard
                    key={content.id}
                    content={content}
                    onClick={handleContentClick}
                  />
                ))}
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  )
}
