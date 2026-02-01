/**
 * CreateProjectModal - Modal dialog for creating new client onboarding projects
 *
 * Features:
 * - Project name input with validation
 * - Client website URL input with URL validation
 * - Form validation with real-time feedback
 * - Toast notifications for success/error
 * - Keyboard accessibility (Escape to close)
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log form validation failures with field names
 * - Log API errors with full context
 * - Log user actions (open, close, submit) as breadcrumbs
 */

import { useState, useCallback, useEffect, useRef, type FormEvent } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { FormField, Input } from '@/components/ui/form-field'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { api } from '@/lib/api'
import { addBreadcrumb } from '@/lib/errorReporting'
import { cn } from '@/lib/utils'

export interface CreateProjectModalProps {
  /** Whether the modal is open */
  isOpen: boolean
  /** Callback when the modal should close */
  onClose: () => void
  /** Callback when project is successfully created */
  onSuccess?: (project: CreatedProject) => void
}

interface CreatedProject {
  id: string
  name: string
  client_id: string
  status: string
}

interface CreateProjectInput {
  name: string
  client_id: string
}

interface FormErrors {
  name?: string
  clientUrl?: string
}

/**
 * Validates a URL string
 * Checks for valid HTTP/HTTPS URL format with a domain
 */
function validateUrl(url: string): { isValid: boolean; error?: string } {
  const trimmed = url.trim()

  if (!trimmed) {
    return { isValid: false, error: 'Website URL is required' }
  }

  // Add https:// if no protocol specified
  let urlToValidate = trimmed
  if (!urlToValidate.match(/^https?:\/\//i)) {
    urlToValidate = `https://${urlToValidate}`
  }

  try {
    const parsed = new URL(urlToValidate)

    // Must be http or https
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return { isValid: false, error: 'URL must use http or https protocol' }
    }

    // Must have a valid hostname with at least one dot (e.g., example.com)
    if (!parsed.hostname.includes('.') || parsed.hostname.startsWith('.') || parsed.hostname.endsWith('.')) {
      return { isValid: false, error: 'Please enter a valid domain (e.g., example.com)' }
    }

    // Basic hostname character validation
    const hostnameRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$/
    if (!hostnameRegex.test(parsed.hostname)) {
      return { isValid: false, error: 'Please enter a valid domain name' }
    }

    return { isValid: true }
  } catch {
    return { isValid: false, error: 'Please enter a valid URL' }
  }
}

/**
 * Normalizes a URL by adding https:// if missing and removing trailing slashes
 */
function normalizeUrl(url: string): string {
  let normalized = url.trim()

  if (!normalized.match(/^https?:\/\//i)) {
    normalized = `https://${normalized}`
  }

  // Remove trailing slash
  normalized = normalized.replace(/\/+$/, '')

  return normalized
}

/**
 * CreateProjectModal displays a dialog for creating new projects
 */
export function CreateProjectModal({ isOpen, onClose, onSuccess }: CreateProjectModalProps) {
  const [name, setName] = useState('')
  const [clientUrl, setClientUrl] = useState('')
  const [errors, setErrors] = useState<FormErrors>({})
  const [touched, setTouched] = useState<Record<string, boolean>>({})

  const modalRef = useRef<HTMLDivElement>(null)
  const nameInputRef = useRef<HTMLInputElement>(null)

  // Create project mutation with toast notifications
  const createMutation = useToastMutation<CreatedProject, Error, CreateProjectInput>({
    mutationFn: (data) => api.post<CreatedProject>('/api/projects', data, {
      userAction: 'Create project',
      component: 'CreateProjectModal',
    }),
    userAction: 'Create project',
    successMessage: 'Project created',
    successDescription: (data) => `"${data.name}" is ready for onboarding.`,
    onSuccess: (data) => {
      addBreadcrumb('Project created successfully', 'mutation', { projectId: data.id })
      handleClose()
      onSuccess?.(data)
    },
  })

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setName('')
      setClientUrl('')
      setErrors({})
      setTouched({})
      addBreadcrumb('Open create project modal', 'user-action')

      // Focus name input after animation
      setTimeout(() => {
        nameInputRef.current?.focus()
      }, 100)
    }
  }, [isOpen])

  // Handle escape key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        e.preventDefault()
        handleClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, handleClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  const handleClose = useCallback(() => {
    if (createMutation.isPending) return // Don't close while submitting
    addBreadcrumb('Close create project modal', 'user-action')
    onClose()
  }, [onClose, createMutation.isPending])

  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose()
    }
  }, [handleClose])

  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {}

    // Validate name
    const trimmedName = name.trim()
    if (!trimmedName) {
      newErrors.name = 'Project name is required'
    } else if (trimmedName.length > 255) {
      newErrors.name = 'Project name must be 255 characters or less'
    }

    // Validate URL
    const urlValidation = validateUrl(clientUrl)
    if (!urlValidation.isValid) {
      newErrors.clientUrl = urlValidation.error
    }

    setErrors(newErrors)

    if (Object.keys(newErrors).length > 0) {
      console.warn('[CreateProjectModal] Form validation failed', {
        errors: newErrors,
        name: trimmedName ? `${trimmedName.length} chars` : 'empty',
        clientUrl: clientUrl ? 'provided' : 'empty',
      })
    }

    return Object.keys(newErrors).length === 0
  }, [name, clientUrl])

  const handleSubmit = useCallback((e: FormEvent) => {
    e.preventDefault()

    // Mark all fields as touched
    setTouched({ name: true, clientUrl: true })

    if (!validateForm()) {
      return
    }

    addBreadcrumb('Submit create project form', 'user-action', {
      nameLength: name.trim().length,
    })

    const normalizedUrl = normalizeUrl(clientUrl)

    createMutation.mutate({
      name: name.trim(),
      client_id: normalizedUrl,
    })
  }, [name, clientUrl, validateForm, createMutation])

  const handleNameChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setName(e.target.value)
    if (touched.name) {
      // Clear error when user starts typing again
      setErrors((prev) => ({ ...prev, name: undefined }))
    }
  }, [touched.name])

  const handleUrlChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setClientUrl(e.target.value)
    if (touched.clientUrl) {
      // Clear error when user starts typing again
      setErrors((prev) => ({ ...prev, clientUrl: undefined }))
    }
  }, [touched.clientUrl])

  const handleNameBlur = useCallback(() => {
    setTouched((prev) => ({ ...prev, name: true }))
    const trimmedName = name.trim()
    if (!trimmedName) {
      setErrors((prev) => ({ ...prev, name: 'Project name is required' }))
    } else if (trimmedName.length > 255) {
      setErrors((prev) => ({ ...prev, name: 'Project name must be 255 characters or less' }))
    }
  }, [name])

  const handleUrlBlur = useCallback(() => {
    setTouched((prev) => ({ ...prev, clientUrl: true }))
    const urlValidation = validateUrl(clientUrl)
    if (!urlValidation.isValid) {
      setErrors((prev) => ({ ...prev, clientUrl: urlValidation.error }))
    }
  }, [clientUrl])

  if (!isOpen) {
    return null
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-project-title"
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-warmgray-900/40 backdrop-blur-sm animate-fade-in"
        onClick={handleOverlayClick}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        ref={modalRef}
        className={cn(
          'relative w-full max-w-md mx-4 bg-white rounded-2xl shadow-soft-xl',
          'animate-fade-in-up'
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-cream-200">
          <h2
            id="create-project-title"
            className="text-lg font-display font-semibold text-warmgray-900"
          >
            New Project
          </h2>
          <button
            type="button"
            onClick={handleClose}
            disabled={createMutation.isPending}
            className={cn(
              'p-2 rounded-lg text-warmgray-400 transition-colors',
              'hover:bg-cream-100 hover:text-warmgray-600',
              'focus:outline-none focus:ring-2 focus:ring-primary-300',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <FormField
            label="Project Name"
            required
            error={touched.name ? errors.name : undefined}
            helperText="A descriptive name for this client onboarding"
          >
            <Input
              ref={nameInputRef}
              type="text"
              placeholder="e.g., Acme Corp Website Refresh"
              value={name}
              onChange={handleNameChange}
              onBlur={handleNameBlur}
              disabled={createMutation.isPending}
              autoComplete="off"
              maxLength={255}
            />
          </FormField>

          <FormField
            label="Client Website"
            required
            error={touched.clientUrl ? errors.clientUrl : undefined}
            helperText="The client's website URL for content discovery"
          >
            <Input
              type="text"
              placeholder="e.g., acme.com or https://acme.com"
              value={clientUrl}
              onChange={handleUrlChange}
              onBlur={handleUrlBlur}
              disabled={createMutation.isPending}
              autoComplete="url"
            />
          </FormField>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={handleClose}
              disabled={createMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Project'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
