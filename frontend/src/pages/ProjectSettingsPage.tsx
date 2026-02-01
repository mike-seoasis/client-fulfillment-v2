/**
 * ProjectSettingsPage - Configuration page for individual project settings
 *
 * Features:
 * - Project name and description editing
 * - Status management (active, on_hold, completed, cancelled)
 * - Danger zone with archive/delete options
 * - Form validation with real-time feedback
 * - Error handling with ErrorBoundary integration
 * - Loading states with skeletons
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log form validation failures with field names
 * - Log API errors with full context (endpoint, status, response body)
 * - Log user actions as breadcrumbs
 * - Include project_id in all logs
 */

import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Settings,
  AlertTriangle,
  Save,
  Archive,
  Trash2,
  Loader2,
  CheckCircle2,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { useOptimisticMutation } from '@/lib/hooks/useOptimisticMutation'
import { api } from '@/lib/api'
import { addBreadcrumb, reportError } from '@/lib/errorReporting'
import { Button } from '@/components/ui/button'
import { FormField, Input, Textarea, Select } from '@/components/ui/form-field'
import { cn } from '@/lib/utils'

/** Valid project statuses */
type ProjectStatus = 'active' | 'completed' | 'on_hold' | 'cancelled' | 'archived'

/** Project data structure matching backend schema */
interface ProjectDetail {
  id: string
  name: string
  client_id: string
  description?: string
  status: ProjectStatus
  phase_status: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** Update project input */
interface UpdateProjectInput {
  name?: string
  description?: string
  status?: ProjectStatus
}

/** Form errors */
interface FormErrors {
  name?: string
  description?: string
}

/** Status options for the select */
const statusOptions: { value: ProjectStatus; label: string; description: string }[] = [
  { value: 'active', label: 'Active', description: 'Project is in progress' },
  { value: 'on_hold', label: 'On Hold', description: 'Project is temporarily paused' },
  { value: 'completed', label: 'Completed', description: 'Project has been finished' },
  { value: 'cancelled', label: 'Cancelled', description: 'Project has been stopped' },
]


/**
 * Loading skeleton for the settings page
 */
function SettingsSkeleton() {
  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb skeleton */}
        <div className="h-5 bg-cream-200 rounded w-32 mb-6 animate-pulse-soft" />

        {/* Header skeleton */}
        <div className="mb-8">
          <div className="h-8 bg-cream-200 rounded-lg w-48 mb-2 animate-pulse-soft" />
          <div className="h-5 bg-cream-200 rounded w-64 animate-pulse-soft" />
        </div>

        {/* Form skeleton */}
        <div className="card space-y-6">
          <div className="space-y-2">
            <div className="h-5 bg-cream-200 rounded w-24 animate-pulse-soft" />
            <div className="h-11 bg-cream-200 rounded-xl animate-pulse-soft" />
          </div>
          <div className="space-y-2">
            <div className="h-5 bg-cream-200 rounded w-20 animate-pulse-soft" />
            <div className="h-24 bg-cream-200 rounded-xl animate-pulse-soft" />
          </div>
          <div className="space-y-2">
            <div className="h-5 bg-cream-200 rounded w-16 animate-pulse-soft" />
            <div className="h-11 bg-cream-200 rounded-xl animate-pulse-soft" />
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Error state component
 */
function ErrorState({
  error,
  onRetry,
  onGoBack,
}: {
  error: Error & { status?: number }
  onRetry: () => void
  onGoBack: () => void
}) {
  const isNotFound = error.status === 404

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
          <div
            className={cn(
              'w-16 h-16 rounded-2xl flex items-center justify-center mb-6',
              isNotFound ? 'bg-warning-100' : 'bg-error-100'
            )}
          >
            <AlertTriangle
              className={cn('w-8 h-8', isNotFound ? 'text-warning-500' : 'text-error-500')}
            />
          </div>
          <h2 className="text-xl font-semibold text-warmgray-900 mb-2">
            {isNotFound ? 'Project not found' : 'Failed to load settings'}
          </h2>
          <p className="text-warmgray-500 mb-6 max-w-sm">
            {isNotFound
              ? "The project you're looking for doesn't exist or has been deleted."
              : "We couldn't load the project settings. Please check your connection and try again."}
          </p>
          <div className="flex gap-3">
            <Button variant="outline" onClick={onGoBack}>
              <ArrowLeft className="w-4 h-4" />
              Back to project
            </Button>
            {!isNotFound && <Button onClick={onRetry}>Try again</Button>}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Danger zone section for destructive actions
 */
function DangerZone({
  projectId,
  projectName,
  isArchived,
  onArchive,
  isArchiving,
}: {
  projectId: string
  projectName: string
  isArchived: boolean
  onArchive: () => void
  isArchiving: boolean
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const deleteMutation = useToastMutation<void, Error, void>({
    mutationFn: () =>
      api.delete(`/api/projects/${projectId}`, {
        userAction: 'Delete project',
        component: 'ProjectSettingsPage',
      }),
    userAction: 'Delete project',
    successMessage: 'Project deleted',
    successDescription: `"${projectName}" has been permanently deleted.`,
    onSuccess: () => {
      addBreadcrumb('Project deleted successfully', 'mutation', { projectId })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate('/projects')
    },
  })

  const handleDeleteClick = useCallback(() => {
    addBreadcrumb('Open delete confirmation', 'user-action', { projectId })
    setShowDeleteConfirm(true)
    setDeleteConfirmText('')
  }, [projectId])

  const handleDeleteCancel = useCallback(() => {
    addBreadcrumb('Cancel delete confirmation', 'user-action', { projectId })
    setShowDeleteConfirm(false)
    setDeleteConfirmText('')
  }, [projectId])

  const handleDeleteConfirm = useCallback(() => {
    if (deleteConfirmText !== projectName) {
      console.warn('[ProjectSettingsPage] Delete confirmation mismatch', {
        projectId,
        expected: projectName,
        received: deleteConfirmText,
      })
      return
    }

    addBreadcrumb('Confirm delete project', 'user-action', { projectId })
    deleteMutation.mutate()
  }, [deleteConfirmText, projectName, projectId, deleteMutation])

  const canDelete = deleteConfirmText === projectName

  return (
    <div className="card border-error-200 bg-error-50/30">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-xl bg-error-100 flex items-center justify-center">
          <AlertTriangle className="w-5 h-5 text-error-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-warmgray-900">Danger Zone</h3>
          <p className="text-sm text-warmgray-500">
            Irreversible and destructive actions
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Archive action */}
        <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-cream-200">
          <div>
            <h4 className="font-medium text-warmgray-900">
              {isArchived ? 'Unarchive project' : 'Archive project'}
            </h4>
            <p className="text-sm text-warmgray-500">
              {isArchived
                ? 'Restore this project to active status'
                : 'Hide this project from the main list'}
            </p>
          </div>
          <Button
            variant="outline"
            onClick={onArchive}
            disabled={isArchiving}
          >
            {isArchiving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Archive className="w-4 h-4" />
            )}
            {isArchived ? 'Unarchive' : 'Archive'}
          </Button>
        </div>

        {/* Delete action */}
        <div className="p-4 bg-white rounded-xl border border-error-200">
          {!showDeleteConfirm ? (
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-warmgray-900">Delete project</h4>
                <p className="text-sm text-warmgray-500">
                  Permanently delete this project and all its data
                </p>
              </div>
              <Button variant="destructive" onClick={handleDeleteClick}>
                <Trash2 className="w-4 h-4" />
                Delete
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-error-700">
                  Are you sure you want to delete this project?
                </h4>
                <p className="text-sm text-warmgray-500 mt-1">
                  This action cannot be undone. Type{' '}
                  <span className="font-mono font-medium text-warmgray-700">
                    {projectName}
                  </span>{' '}
                  to confirm.
                </p>
              </div>
              <Input
                type="text"
                placeholder="Type project name to confirm"
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                variant={canDelete ? 'success' : 'default'}
              />
              <div className="flex gap-3">
                <Button
                  variant="ghost"
                  onClick={handleDeleteCancel}
                  disabled={deleteMutation.isPending}
                >
                  Cancel
                </Button>
                <Button
                  variant="destructive"
                  onClick={handleDeleteConfirm}
                  disabled={!canDelete || deleteMutation.isPending}
                >
                  {deleteMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                  Delete permanently
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * ProjectSettingsPage displays and allows editing of project configuration
 */
export function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [status, setStatus] = useState<ProjectStatus>('active')
  const [errors, setErrors] = useState<FormErrors>({})
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [hasChanges, setHasChanges] = useState(false)

  // Fetch project details
  const {
    data: project,
    isLoading,
    isError,
    error,
    refetch,
  } = useApiQuery<ProjectDetail>({
    queryKey: ['project', projectId],
    endpoint: `/api/projects/${projectId}`,
    requestOptions: {
      userAction: 'Load project settings',
      component: 'ProjectSettingsPage',
    },
    enabled: !!projectId,
  })

  // Initialize form with project data
  useEffect(() => {
    if (project) {
      setName(project.name)
      setDescription(project.description || '')
      setStatus(project.status)
      setHasChanges(false)
      addBreadcrumb('Project settings loaded', 'data', { projectId })
    }
  }, [project, projectId])

  // Track changes
  useEffect(() => {
    if (project) {
      const nameChanged = name !== project.name
      const descriptionChanged = description !== (project.description || '')
      const statusChanged = status !== project.status
      setHasChanges(nameChanged || descriptionChanged || statusChanged)
    }
  }, [name, description, status, project])

  // Update project mutation with optimistic updates
  const updateMutation = useOptimisticMutation<ProjectDetail, UpdateProjectInput, ProjectDetail>({
    mutationFn: (data) =>
      api.patch<ProjectDetail>(`/api/projects/${projectId}`, data, {
        userAction: 'Update project settings',
        component: 'ProjectSettingsPage',
      }),
    queryKey: ['project', projectId],
    getOptimisticData: (currentData, data) => {
      // Current data should always exist since we only render when project is loaded
      if (!currentData) {
        console.warn('[ProjectSettingsPage] Optimistic update called without current data')
        return currentData as unknown as ProjectDetail
      }
      return {
        ...currentData,
        ...(data.name !== undefined ? { name: data.name } : {}),
        ...(data.description !== undefined ? { description: data.description } : {}),
        ...(data.status !== undefined ? { status: data.status } : {}),
        updated_at: new Date().toISOString(),
      }
    },
    invalidateKeys: [['projects']],
    userAction: 'Update project',
    component: 'ProjectSettingsPage',
    entityIds: { projectId },
    successMessage: 'Settings saved',
    successDescription: 'Your changes have been saved successfully.',
    onSuccess: () => {
      setHasChanges(false)
    },
  })

  // Archive mutation with optimistic updates
  const archiveMutation = useOptimisticMutation<ProjectDetail, void, ProjectDetail>({
    mutationFn: () => {
      const newStatus = project?.status === 'archived' ? 'active' : 'archived'
      return api.patch<ProjectDetail>(
        `/api/projects/${projectId}`,
        { status: newStatus },
        {
          userAction: project?.status === 'archived' ? 'Unarchive project' : 'Archive project',
          component: 'ProjectSettingsPage',
        }
      )
    },
    queryKey: ['project', projectId],
    getOptimisticData: (currentData) => {
      // Current data should always exist since we only render when project is loaded
      if (!currentData) {
        console.warn('[ProjectSettingsPage] Optimistic update called without current data')
        return currentData as unknown as ProjectDetail
      }
      const newStatus = currentData.status === 'archived' ? 'active' : 'archived'
      return {
        ...currentData,
        status: newStatus,
        updated_at: new Date().toISOString(),
      }
    },
    invalidateKeys: [['projects']],
    userAction: project?.status === 'archived' ? 'Unarchive project' : 'Archive project',
    component: 'ProjectSettingsPage',
    entityIds: { projectId },
    successMessage: project?.status === 'archived' ? 'Project unarchived' : 'Project archived',
    successDescription: project?.status === 'archived'
      ? 'Project has been restored.'
      : 'Project has been archived.',
  })

  // Validation
  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {}

    const trimmedName = name.trim()
    if (!trimmedName) {
      newErrors.name = 'Project name is required'
    } else if (trimmedName.length > 255) {
      newErrors.name = 'Project name must be 255 characters or less'
    }

    if (description.length > 1000) {
      newErrors.description = 'Description must be 1000 characters or less'
    }

    setErrors(newErrors)

    if (Object.keys(newErrors).length > 0) {
      console.warn('[ProjectSettingsPage] Form validation failed', {
        errors: newErrors,
        projectId,
      })
      reportError(new Error('Form validation failed'), {
        component: 'ProjectSettingsPage',
        userAction: 'Save settings',
        extra: { errors: newErrors, projectId },
      })
    }

    return Object.keys(newErrors).length === 0
  }, [name, description, projectId])

  // Handlers
  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault()

      setTouched({ name: true, description: true })

      if (!validateForm()) {
        return
      }

      addBreadcrumb('Submit project settings', 'user-action', { projectId })

      const updates: UpdateProjectInput = {}
      if (name !== project?.name) updates.name = name.trim()
      if (description !== (project?.description || '')) updates.description = description
      if (status !== project?.status) updates.status = status

      updateMutation.mutate(updates)
    },
    [name, description, status, project, validateForm, projectId, updateMutation]
  )

  const handleNameChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setName(e.target.value)
      if (touched.name) {
        setErrors((prev) => ({ ...prev, name: undefined }))
      }
    },
    [touched.name]
  )

  const handleDescriptionChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setDescription(e.target.value)
      if (touched.description) {
        setErrors((prev) => ({ ...prev, description: undefined }))
      }
    },
    [touched.description]
  )

  const handleStatusChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatus(e.target.value as ProjectStatus)
  }, [])

  const handleNameBlur = useCallback(() => {
    setTouched((prev) => ({ ...prev, name: true }))
    const trimmedName = name.trim()
    if (!trimmedName) {
      setErrors((prev) => ({ ...prev, name: 'Project name is required' }))
    } else if (trimmedName.length > 255) {
      setErrors((prev) => ({ ...prev, name: 'Project name must be 255 characters or less' }))
    }
  }, [name])

  const handleDescriptionBlur = useCallback(() => {
    setTouched((prev) => ({ ...prev, description: true }))
    if (description.length > 1000) {
      setErrors((prev) => ({
        ...prev,
        description: 'Description must be 1000 characters or less',
      }))
    }
  }, [description])

  const handleGoBack = useCallback(() => {
    addBreadcrumb('Navigate back to project', 'navigation', { projectId })
    navigate(`/projects/${projectId}`)
  }, [navigate, projectId])

  const handleRetry = useCallback(() => {
    addBreadcrumb('Retry loading project settings', 'user-action', { projectId })
    refetch()
  }, [refetch, projectId])

  const handleArchive = useCallback(() => {
    addBreadcrumb('Archive/unarchive project', 'user-action', { projectId })
    archiveMutation.mutate()
  }, [archiveMutation, projectId])

  // Computed values
  const isArchived = project?.status === 'archived'
  const isSaving = updateMutation.isPending

  // Log errors
  if (isError && error) {
    console.error('[ProjectSettingsPage] Failed to load project settings:', {
      error: error.message,
      endpoint: `/api/projects/${projectId}`,
      status: error.status,
      projectId,
    })
  }

  // Loading state
  if (isLoading) {
    return <SettingsSkeleton />
  }

  // Error state
  if (isError) {
    return <ErrorState error={error} onRetry={handleRetry} onGoBack={handleGoBack} />
  }

  // No data (shouldn't happen but handle gracefully)
  if (!project) {
    return <ErrorState error={new Error('No data')} onRetry={handleRetry} onGoBack={handleGoBack} />
  }

  return (
    <div className="min-h-screen bg-cream-50">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Breadcrumb navigation */}
        <nav className="mb-6">
          <Link
            to={`/projects/${projectId}`}
            className="inline-flex items-center gap-1.5 text-sm text-warmgray-500 hover:text-warmgray-700 transition-colors"
            onClick={() => addBreadcrumb('Click breadcrumb to project', 'navigation')}
          >
            <ArrowLeft className="w-4 h-4" />
            Back to project
          </Link>
        </nav>

        {/* Header */}
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Settings className="w-5 h-5 text-primary-600" />
            </div>
            <h1 className="text-2xl font-display font-semibold text-warmgray-900">
              Project Settings
            </h1>
          </div>
          <p className="text-warmgray-500 ml-13">
            Configure settings for "{project.name}"
          </p>
        </header>

        {/* Settings form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-warmgray-900 mb-5">
              General Settings
            </h2>

            <div className="space-y-5">
              <FormField
                label="Project Name"
                required
                error={touched.name ? errors.name : undefined}
                helperText="A descriptive name for this client onboarding"
              >
                <Input
                  type="text"
                  placeholder="e.g., Acme Corp Website Refresh"
                  value={name}
                  onChange={handleNameChange}
                  onBlur={handleNameBlur}
                  disabled={isSaving}
                  maxLength={255}
                />
              </FormField>

              <FormField
                label="Description"
                optional
                error={touched.description ? errors.description : undefined}
                helperText={`${description.length}/1000 characters`}
              >
                <Textarea
                  placeholder="Add notes or context about this project..."
                  value={description}
                  onChange={handleDescriptionChange}
                  onBlur={handleDescriptionBlur}
                  disabled={isSaving}
                  rows={4}
                  maxLength={1000}
                />
              </FormField>

              <FormField
                label="Status"
                helperText="The current state of this project"
              >
                <Select
                  value={status}
                  onChange={handleStatusChange}
                  disabled={isSaving || isArchived}
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </FormField>

              {isArchived && (
                <div className="flex items-center gap-2 p-3 bg-warning-50 rounded-xl border border-warning-200">
                  <AlertTriangle className="w-4 h-4 text-warning-600 shrink-0" />
                  <p className="text-sm text-warning-700">
                    This project is archived. Unarchive it to change the status.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Client info (read-only) */}
          <div className="card">
            <h2 className="text-lg font-semibold text-warmgray-900 mb-5">
              Client Information
            </h2>

            <div className="space-y-4">
              <div>
                <label className="label">Client Website</label>
                <div className="px-4 py-2.5 bg-cream-100 rounded-xl text-warmgray-600 text-sm">
                  {project.client_id}
                </div>
                <p className="text-xs text-warmgray-400 mt-1.5">
                  The client website cannot be changed after project creation
                </p>
              </div>
            </div>
          </div>

          {/* Save button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {hasChanges && (
                <span className="text-sm text-warmgray-500">
                  You have unsaved changes
                </span>
              )}
              {updateMutation.isSuccess && !hasChanges && (
                <span className="flex items-center gap-1.5 text-sm text-success-600">
                  <CheckCircle2 className="w-4 h-4" />
                  Changes saved
                </span>
              )}
            </div>
            <Button type="submit" disabled={!hasChanges || isSaving}>
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>

        {/* Danger zone */}
        <div className="mt-8">
          <DangerZone
            projectId={projectId || ''}
            projectName={project.name}
            isArchived={isArchived}
            onArchive={handleArchive}
            isArchiving={archiveMutation.isPending}
          />
        </div>
      </div>
    </div>
  )
}
