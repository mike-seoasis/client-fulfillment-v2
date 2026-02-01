/**
 * ContentEditorPage - Edit content with live preview
 *
 * Features:
 * - Split-view layout with editor and live preview
 * - Auto-save with debounce
 * - Metadata editing (title, type, tone)
 * - Status management (approve/reject)
 * - Loading states and error handling
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Add breadcrumbs for navigation and editing actions
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Save,
  Eye,
  EyeOff,
  CheckCircle2,
  XCircle,
  Clock,
  FileText,
  RefreshCw,
  Loader2,
  AlertCircle,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { addBreadcrumb } from '@/lib/errorReporting'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input, Textarea, Select, Label, FormField } from '@/components/ui/form-field'
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

/** Content update request */
interface ContentUpdateRequest {
  title?: string
  content?: string
  content_type?: string
  tone?: string
  status?: ContentStatus
  reviewer_notes?: string
}

// ============================================================================
// Constants
// ============================================================================

/** Status badge colors */
const STATUS_COLORS: Record<ContentStatus, { bg: string; text: string; icon: typeof Clock }> = {
  pending_review: { bg: 'bg-warning-100', text: 'text-warning-800', icon: Clock },
  approved: { bg: 'bg-success-100', text: 'text-success-800', icon: CheckCircle2 },
  rejected: { bg: 'bg-error-100', text: 'text-error-800', icon: XCircle },
}

/** Status display labels */
const STATUS_LABELS: Record<ContentStatus, string> = {
  pending_review: 'Pending Review',
  approved: 'Approved',
  rejected: 'Rejected',
}

/** Content type options */
const CONTENT_TYPE_OPTIONS = [
  { value: 'blog_post', label: 'Blog Post' },
  { value: 'landing_page', label: 'Landing Page' },
  { value: 'product_description', label: 'Product Description' },
  { value: 'email', label: 'Email Copy' },
  { value: 'social_post', label: 'Social Media Post' },
  { value: 'faq', label: 'FAQ Entry' },
  { value: 'collection', label: 'Collection' },
  { value: 'product', label: 'Product' },
  { value: 'blog', label: 'Blog' },
  { value: 'landing', label: 'Landing' },
]

/** Tone options */
const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'casual', label: 'Casual' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'formal', label: 'Formal' },
  { value: 'persuasive', label: 'Persuasive' },
  { value: 'informative', label: 'Informative' },
]

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a date string for display
 */
function formatDateTime(dateString: string): string {
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

/**
 * Count words in text
 */
function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length
}

/**
 * Simple markdown-like preview renderer
 * Converts basic markdown to HTML for preview
 */
function renderPreview(content: string): string {
  if (!content) return '<p class="text-warmgray-400 italic">Start typing to see preview...</p>'

  return content
    // Headers
    .replace(/^### (.*$)/gm, '<h3 class="text-lg font-semibold text-warmgray-900 mt-4 mb-2">$1</h3>')
    .replace(/^## (.*$)/gm, '<h2 class="text-xl font-semibold text-warmgray-900 mt-5 mb-3">$1</h2>')
    .replace(/^# (.*$)/gm, '<h1 class="text-2xl font-bold text-warmgray-900 mt-6 mb-4">$1</h1>')
    // Bold and italic
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>')
    .replace(/\*(.*?)\*/g, '<em class="italic">$1</em>')
    // Lists
    .replace(/^- (.*$)/gm, '<li class="ml-4 list-disc text-warmgray-700">$1</li>')
    .replace(/^\d+\. (.*$)/gm, '<li class="ml-4 list-decimal text-warmgray-700">$1</li>')
    // Line breaks and paragraphs
    .replace(/\n\n/g, '</p><p class="text-warmgray-700 mb-3">')
    .replace(/\n/g, '<br/>')
    // Wrap in paragraph
    .replace(/^(.*)$/, '<p class="text-warmgray-700 mb-3">$1</p>')
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Loading skeleton for the editor page
 */
function EditorSkeleton() {
  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header skeleton */}
        <div className="mb-8">
          <div className="h-8 bg-cream-200 rounded-lg w-32 animate-pulse-soft mb-4" />
          <div className="h-10 bg-cream-200 rounded-lg w-64 animate-pulse-soft mb-2" />
          <div className="h-5 bg-cream-200 rounded-lg w-48 animate-pulse-soft" />
        </div>

        {/* Editor skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card space-y-4">
            <div className="h-10 bg-cream-200 rounded-xl animate-pulse-soft" />
            <div className="h-10 bg-cream-200 rounded-xl animate-pulse-soft" />
            <div className="h-64 bg-cream-200 rounded-xl animate-pulse-soft" />
          </div>
          <div className="card">
            <div className="h-full min-h-[400px] bg-cream-200 rounded-xl animate-pulse-soft" />
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Error state component for API failures
 */
function ErrorState({ onRetry, error }: { onRetry: () => void; error?: string }) {
  return (
    <div className="min-h-screen bg-cream-50 flex items-center justify-center">
      <div className="text-center px-4">
        <div className="w-16 h-16 bg-error-100 rounded-2xl flex items-center justify-center mb-6 mx-auto">
          <AlertCircle className="w-8 h-8 text-error-500" aria-hidden="true" />
        </div>
        <h2 className="text-lg font-semibold text-warmgray-900 mb-2">
          Failed to load content
        </h2>
        <p className="text-warmgray-500 mb-6 max-w-sm">
          {error || 'We couldn\'t load this content. Please check your connection and try again.'}
        </p>
        <Button onClick={onRetry} variant="outline">
          <RefreshCw className="w-4 h-4" />
          Try again
        </Button>
      </div>
    </div>
  )
}

/**
 * Status badge component
 */
function StatusBadge({ status }: { status: ContentStatus }) {
  const config = STATUS_COLORS[status]
  const Icon = config.icon

  return (
    <span className={cn('badge inline-flex items-center gap-1.5', config.bg, config.text)}>
      <Icon className="w-3.5 h-3.5" />
      {STATUS_LABELS[status]}
    </span>
  )
}

/**
 * Preview panel component
 */
function PreviewPanel({
  content,
  title,
  isVisible,
}: {
  content: string
  title: string
  isVisible: boolean
}) {
  const previewHtml = useMemo(() => renderPreview(content), [content])
  const wordCount = useMemo(() => countWords(content), [content])

  if (!isVisible) return null

  return (
    <div className="card h-full flex flex-col">
      {/* Preview header */}
      <div className="flex items-center justify-between pb-4 border-b border-cream-200 mb-4">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-warmgray-400" />
          <h3 className="font-medium text-warmgray-700">Preview</h3>
        </div>
        <span className="text-xs text-warmgray-400">{wordCount} words</span>
      </div>

      {/* Preview content */}
      <div className="flex-1 overflow-auto">
        {title && (
          <h1 className="text-2xl font-display font-bold text-warmgray-900 mb-4">
            {title}
          </h1>
        )}
        <div
          className="prose prose-warmgray max-w-none"
          dangerouslySetInnerHTML={{ __html: previewHtml }}
        />
      </div>
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ContentEditorPage - Edit content with split-view live preview
 */
export function ContentEditorPage() {
  const { contentId } = useParams<{ contentId: string }>()
  const navigate = useNavigate()

  // Editor state
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [contentType, setContentType] = useState('')
  const [tone, setTone] = useState('')
  const [reviewerNotes, setReviewerNotes] = useState('')
  const [showPreview, setShowPreview] = useState(true)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  // Fetch content data
  const {
    data: contentData,
    isLoading,
    isError,
    error,
    refetch,
  } = useApiQuery<ContentItem>({
    queryKey: ['content', contentId],
    endpoint: `/api/v1/content/${contentId}`,
    requestOptions: {
      userAction: 'Load content for editing',
      component: 'ContentEditorPage',
    },
    enabled: !!contentId,
  })

  // Initialize form state when data loads
  useEffect(() => {
    if (contentData) {
      setTitle(contentData.title)
      setContent(contentData.content)
      setContentType(contentData.content_type)
      setTone(contentData.tone)
      setReviewerNotes(contentData.reviewer_notes || '')
      setHasUnsavedChanges(false)
    }
  }, [contentData])

  // Track unsaved changes
  useEffect(() => {
    if (contentData) {
      const changed =
        title !== contentData.title ||
        content !== contentData.content ||
        contentType !== contentData.content_type ||
        tone !== contentData.tone ||
        reviewerNotes !== (contentData.reviewer_notes || '')

      setHasUnsavedChanges(changed)
    }
  }, [title, content, contentType, tone, reviewerNotes, contentData])

  // Save mutation
  const saveMutation = useToastMutation<ContentItem, Error, ContentUpdateRequest>({
    mutationFn: (data) =>
      api.patch<ContentItem>(`/api/v1/content/${contentId}`, data, {
        userAction: 'Save content changes',
        component: 'ContentEditorPage',
      }),
    userAction: 'Save content',
    successMessage: 'Changes saved',
    successDescription: 'Your content has been updated.',
    onSuccess: () => {
      setHasUnsavedChanges(false)
      refetch()
    },
  })

  // Status update mutation
  const statusMutation = useToastMutation<ContentItem, Error, { status: ContentStatus; reviewer_notes?: string }>({
    mutationFn: (data) =>
      api.patch<ContentItem>(`/api/v1/content/${contentId}`, data, {
        userAction: `Update content status to ${data.status}`,
        component: 'ContentEditorPage',
      }),
    userAction: 'Update content status',
    successMessage: (data) => `Content ${data.status === 'approved' ? 'approved' : 'rejected'}`,
    onSuccess: () => {
      refetch()
    },
  })

  // Handlers
  const handleSave = useCallback(() => {
    addBreadcrumb('Save content', 'user-action', { contentId })
    saveMutation.mutate({
      title,
      content,
      content_type: contentType,
      tone,
      reviewer_notes: reviewerNotes || undefined,
    })
  }, [contentId, title, content, contentType, tone, reviewerNotes, saveMutation])

  const handleApprove = useCallback(() => {
    addBreadcrumb('Approve content', 'user-action', { contentId })
    statusMutation.mutate({ status: 'approved', reviewer_notes: reviewerNotes || undefined })
  }, [contentId, reviewerNotes, statusMutation])

  const handleReject = useCallback(() => {
    addBreadcrumb('Reject content', 'user-action', { contentId })
    statusMutation.mutate({ status: 'rejected', reviewer_notes: reviewerNotes || undefined })
  }, [contentId, reviewerNotes, statusMutation])

  const handleBack = useCallback(() => {
    addBreadcrumb('Navigate back from editor', 'navigation', { contentId })
    if (hasUnsavedChanges) {
      if (window.confirm('You have unsaved changes. Are you sure you want to leave?')) {
        navigate(-1)
      }
    } else {
      navigate(-1)
    }
  }, [contentId, hasUnsavedChanges, navigate])

  const handleRetry = useCallback(() => {
    addBreadcrumb('Retry loading content', 'user-action', { contentId })
    refetch()
  }, [contentId, refetch])

  const togglePreview = useCallback(() => {
    setShowPreview((prev) => !prev)
    addBreadcrumb(`Toggle preview: ${!showPreview ? 'show' : 'hide'}`, 'user-action')
  }, [showPreview])

  // Loading state
  if (isLoading) {
    return <EditorSkeleton />
  }

  // Error state
  if (isError) {
    console.error('[ContentEditorPage] Failed to load content:', {
      error: error?.message,
      endpoint: `/api/v1/content/${contentId}`,
      status: error?.status,
    })
    return <ErrorState onRetry={handleRetry} error={error?.message} />
  }

  // No content found
  if (!contentData) {
    return <ErrorState onRetry={handleRetry} error="Content not found" />
  }

  const isSaving = saveMutation.isPending
  const isUpdatingStatus = statusMutation.isPending
  const isBusy = isSaving || isUpdatingStatus

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            {/* Left: Back button and title */}
            <div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleBack}
                className="text-warmgray-500 hover:text-warmgray-700 -ml-2 mb-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </Button>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-display font-semibold text-warmgray-900">
                  Edit Content
                </h1>
                <StatusBadge status={contentData.status} />
                {hasUnsavedChanges && (
                  <span className="text-xs text-warning-600 bg-warning-100 px-2 py-0.5 rounded-lg">
                    Unsaved changes
                  </span>
                )}
              </div>
              <p className="mt-1 text-warmgray-500 text-sm">
                Generated {formatDateTime(contentData.generated_at)}
              </p>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-3">
              {/* Preview toggle */}
              <Button
                variant="ghost"
                size="sm"
                onClick={togglePreview}
                className="text-warmgray-600"
              >
                {showPreview ? (
                  <>
                    <EyeOff className="w-4 h-4" />
                    Hide Preview
                  </>
                ) : (
                  <>
                    <Eye className="w-4 h-4" />
                    Show Preview
                  </>
                )}
              </Button>

              {/* Save button */}
              <Button
                onClick={handleSave}
                disabled={isBusy || !hasUnsavedChanges}
              >
                {isSaving ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Save
              </Button>
            </div>
          </div>
        </header>

        {/* Main content area */}
        <div className={cn(
          'grid gap-6',
          showPreview ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1 max-w-3xl'
        )}>
          {/* Editor panel */}
          <div className="card space-y-6">
            {/* Metadata section */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Title" required>
                <Input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter content title"
                  disabled={isBusy}
                />
              </FormField>

              <FormField label="Content Type">
                <Select
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value)}
                  disabled={isBusy}
                >
                  {CONTENT_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </FormField>

              <FormField label="Tone">
                <Select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={isBusy}
                >
                  {TONE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </FormField>

              <div className="flex items-end">
                <div className="flex items-center gap-2 text-sm text-warmgray-500 pb-2">
                  <FileText className="w-4 h-4" />
                  <span>{countWords(content)} words</span>
                </div>
              </div>
            </div>

            {/* Content editor */}
            <div>
              <Label htmlFor="content-editor">Content</Label>
              <Textarea
                id="content-editor"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Enter your content here..."
                rows={16}
                className="font-mono text-sm leading-relaxed"
                disabled={isBusy}
              />
              <p className="text-xs text-warmgray-400 mt-2">
                Supports basic markdown: **bold**, *italic*, # headers, - lists
              </p>
            </div>

            {/* Review section */}
            <div className="pt-4 border-t border-cream-200">
              <FormField label="Reviewer Notes" optional>
                <Textarea
                  value={reviewerNotes}
                  onChange={(e) => setReviewerNotes(e.target.value)}
                  placeholder="Add notes about this content..."
                  rows={3}
                  disabled={isBusy}
                />
              </FormField>

              {/* Review actions */}
              <div className="flex flex-wrap items-center gap-3 mt-4">
                <Button
                  variant="outline"
                  onClick={handleApprove}
                  disabled={isBusy || contentData.status === 'approved'}
                  className="text-success-700 border-success-300 hover:bg-success-50"
                >
                  {isUpdatingStatus && statusMutation.variables?.status === 'approved' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-4 h-4" />
                  )}
                  Approve
                </Button>
                <Button
                  variant="outline"
                  onClick={handleReject}
                  disabled={isBusy || contentData.status === 'rejected'}
                  className="text-error-700 border-error-300 hover:bg-error-50"
                >
                  {isUpdatingStatus && statusMutation.variables?.status === 'rejected' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <XCircle className="w-4 h-4" />
                  )}
                  Reject
                </Button>

                {contentData.reviewed_at && (
                  <span className="text-xs text-warmgray-400 ml-auto">
                    Last reviewed {formatDateTime(contentData.reviewed_at)}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Preview panel */}
          <PreviewPanel
            content={content}
            title={title}
            isVisible={showPreview}
          />
        </div>
      </div>
    </div>
  )
}
