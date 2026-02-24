/**
 * BrandConfigPanel - Brand configuration with document upload and editor
 *
 * Features:
 * - Document upload with drag-and-drop support (PDF, DOCX, TXT)
 * - Brand guidelines text editor with additional context
 * - V2 schema display with color palette, typography, voice/tone
 * - Synthesis from uploaded documents via Claude LLM
 * - Manual editing of brand configuration
 * - Real-time validation and error feedback
 *
 * ERROR LOGGING REQUIREMENTS:
 * - Log API errors with endpoint, status, response body
 * - Include user action context in error logs
 * - Log form validation errors at debug level
 * - Log file upload errors with file details
 *
 * RAILWAY DEPLOYMENT REQUIREMENTS:
 * - API URL via VITE_API_URL environment variable
 * - All API calls use relative paths or env-configured URLs
 */

import { useState, useCallback, useRef, useMemo } from 'react'
import { Link } from 'react-router-dom'
import {
  Palette,
  Type,
  MessageSquare,
  Upload,
  FileText,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  AlertCircle,
  X,
  Sparkles,
  Edit3,
  Save,
  ExternalLink,
  Wand2,
} from 'lucide-react'
import { useApiQuery } from '@/lib/hooks/useApiQuery'
import { useToastMutation } from '@/lib/hooks/useToastMutation'
import { addBreadcrumb } from '@/lib/errorReporting'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { FormField, Input, Textarea, Select } from '@/components/ui/form-field'
import { LoadingSpinner, ButtonSpinner } from '@/components/ui/loading-spinner'
import { cn } from '@/lib/utils'

// ============================================================================
// Types
// ============================================================================

/** Color schema from backend */
interface ColorsSchema {
  primary: string | null
  secondary: string | null
  accent: string | null
  background: string | null
  text: string | null
}

/** Typography schema from backend */
interface TypographySchema {
  heading_font: string | null
  body_font: string | null
  base_size: number | null
  heading_weight: string | null
  body_weight: string | null
}

/** Logo schema from backend */
interface LogoSchema {
  url: string | null
  alt_text: string | null
  dark_url: string | null
  favicon_url: string | null
}

/** Voice schema from backend */
interface VoiceSchema {
  tone: string | null
  personality: string[]
  writing_style: string | null
  target_audience: string | null
  value_proposition: string | null
  tagline: string | null
}

/** Social schema from backend */
interface SocialSchema {
  twitter: string | null
  linkedin: string | null
  instagram: string | null
  facebook: string | null
  youtube: string | null
  tiktok: string | null
}

/** V2 schema structure */
interface V2Schema {
  colors: ColorsSchema
  typography: TypographySchema
  logo: LogoSchema
  voice: VoiceSchema
  social: SocialSchema
  version: string
}

/** Brand config response from API */
interface BrandConfigResponse {
  id: string
  project_id: string
  brand_name: string
  domain: string | null
  v2_schema: V2Schema
  created_at: string
  updated_at: string
}

/** Brand config list response */
interface BrandConfigListResponse {
  items: BrandConfigResponse[]
  total: number
}

/** Synthesis request */
interface SynthesisRequest {
  brand_name: string
  domain?: string
  source_documents: string[]
  document_filenames: string[]
  additional_context?: string
}

/** Synthesis response */
interface SynthesisResponse {
  success: boolean
  brand_config_id: string | null
  project_id: string
  brand_name: string
  domain: string | null
  v2_schema: V2Schema
  error: string | null
  duration_ms: number
  sources_used: string[]
}

/** Uploaded file state */
interface UploadedFile {
  id: string
  file: File
  name: string
  size: number
  base64: string | null
  status: 'pending' | 'processing' | 'ready' | 'error'
  error?: string
}

// ============================================================================
// Constants
// ============================================================================

/** Accepted file types */
const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
}

/** Max file size (50MB) */
const MAX_FILE_SIZE = 50 * 1024 * 1024

/** Max files */
const MAX_FILES = 5

/** Tone options */
const TONE_OPTIONS = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'playful', label: 'Playful' },
  { value: 'authoritative', label: 'Authoritative' },
  { value: 'conversational', label: 'Conversational' },
  { value: 'formal', label: 'Formal' },
]

/** Writing style options */
const WRITING_STYLE_OPTIONS = [
  { value: 'conversational', label: 'Conversational' },
  { value: 'formal', label: 'Formal' },
  { value: 'technical', label: 'Technical' },
  { value: 'casual', label: 'Casual' },
  { value: 'academic', label: 'Academic' },
]

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Stats card component
 */
function StatsCard({
  label,
  value,
  icon: Icon,
  variant = 'default',
}: {
  label: string
  value: number | string
  icon: React.ElementType
  variant?: 'default' | 'success' | 'warning'
}) {
  const variantStyles = {
    default: 'bg-cream-50 border-cream-200',
    success: 'bg-success-50 border-success-200',
    warning: 'bg-gold-50 border-gold-200',
  }

  const iconStyles = {
    default: 'text-warmgray-500',
    success: 'text-success-600',
    warning: 'text-gold-600',
  }

  return (
    <div className={cn('p-4 rounded-xl border', variantStyles[variant])}>
      <div className="flex items-center gap-3">
        <Icon className={cn('w-5 h-5', iconStyles[variant])} />
        <div>
          <p className="text-2xl font-semibold text-warmgray-900">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </p>
          <p className="text-sm text-warmgray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}

/**
 * Color swatch component
 */
function ColorSwatch({
  color,
  label,
  onChange,
  disabled,
}: {
  color: string | null
  label: string
  onChange?: (color: string) => void
  disabled?: boolean
}) {
  const displayColor = color || '#E5E5E5'
  const hasColor = !!color

  return (
    <div className="flex items-center gap-3">
      <div className="relative">
        <div
          className={cn(
            'w-10 h-10 rounded-lg border-2 shadow-sm transition-all',
            hasColor ? 'border-cream-300' : 'border-dashed border-cream-400'
          )}
          style={{ backgroundColor: displayColor }}
        />
        {onChange && !disabled && (
          <input
            type="color"
            value={displayColor}
            onChange={(e) => onChange(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer"
            title={`Change ${label} color`}
          />
        )}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-warmgray-700 capitalize">{label}</p>
        <p className="text-xs text-warmgray-500 font-mono">
          {color || 'Not set'}
        </p>
      </div>
    </div>
  )
}

/**
 * File drop zone component
 */
function FileDropZone({
  files,
  onFilesAdded,
  onFileRemove,
  disabled,
  maxFiles = MAX_FILES,
}: {
  files: UploadedFile[]
  onFilesAdded: (files: File[]) => void
  onFileRemove: (id: string) => void
  disabled?: boolean
  maxFiles?: number
}) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!disabled) {
      setIsDragging(true)
    }
  }, [disabled])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      e.stopPropagation()
      setIsDragging(false)

      if (disabled) return

      const droppedFiles = Array.from(e.dataTransfer.files)
      onFilesAdded(droppedFiles)
    },
    [disabled, onFilesAdded]
  )

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        onFilesAdded(Array.from(e.target.files))
      }
      // Reset input to allow selecting the same file again
      if (inputRef.current) {
        inputRef.current.value = ''
      }
    },
    [onFilesAdded]
  )

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const canAddMore = files.length < maxFiles

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      {canAddMore && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
          className={cn(
            'relative border-2 border-dashed rounded-xl p-6 transition-all cursor-pointer',
            isDragging
              ? 'border-primary-400 bg-primary-50'
              : 'border-cream-300 hover:border-cream-400 hover:bg-cream-50/50',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            multiple
            onChange={handleFileSelect}
            className="hidden"
            disabled={disabled}
          />
          <div className="flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-xl bg-cream-100 flex items-center justify-center mb-3">
              <Upload className="w-6 h-6 text-warmgray-500" />
            </div>
            <p className="text-sm font-medium text-warmgray-700">
              {isDragging ? 'Drop files here' : 'Drop files or click to upload'}
            </p>
            <p className="text-xs text-warmgray-500 mt-1">
              PDF, DOCX, or TXT files up to 50MB each
            </p>
            <p className="text-xs text-warmgray-400 mt-1">
              {files.length}/{maxFiles} files
            </p>
          </div>
        </div>
      )}

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((file) => (
            <div
              key={file.id}
              className={cn(
                'flex items-center gap-3 p-3 rounded-lg border',
                file.status === 'ready' && 'bg-success-50 border-success-200',
                file.status === 'processing' && 'bg-cream-50 border-cream-200',
                file.status === 'error' && 'bg-error-50 border-error-200',
                file.status === 'pending' && 'bg-cream-50 border-cream-200'
              )}
            >
              <div
                className={cn(
                  'w-8 h-8 rounded-lg flex items-center justify-center shrink-0',
                  file.status === 'ready' && 'bg-success-100',
                  file.status === 'processing' && 'bg-cream-200',
                  file.status === 'error' && 'bg-error-100',
                  file.status === 'pending' && 'bg-cream-200'
                )}
              >
                {file.status === 'processing' ? (
                  <LoadingSpinner size="sm" />
                ) : file.status === 'ready' ? (
                  <CheckCircle2 className="w-4 h-4 text-success-600" />
                ) : file.status === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-error-600" />
                ) : (
                  <FileText className="w-4 h-4 text-warmgray-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-warmgray-700 truncate">
                  {file.name}
                </p>
                <p className="text-xs text-warmgray-500">
                  {file.error || formatFileSize(file.size)}
                </p>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onFileRemove(file.id)}
                disabled={disabled || file.status === 'processing'}
                className="shrink-0"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Personality tag input component
 */
function PersonalityTags({
  tags,
  onChange,
  disabled,
}: {
  tags: string[]
  onChange: (tags: string[]) => void
  disabled?: boolean
}) {
  const [inputValue, setInputValue] = useState('')

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault()
        const value = inputValue.trim()
        if (value && !tags.includes(value)) {
          onChange([...tags, value])
          setInputValue('')
        }
      } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
        onChange(tags.slice(0, -1))
      }
    },
    [inputValue, tags, onChange]
  )

  const handleRemove = useCallback(
    (tag: string) => {
      onChange(tags.filter((t) => t !== tag))
    },
    [tags, onChange]
  )

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span
            key={tag}
            className={cn(
              'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm',
              'bg-primary-100 text-primary-700'
            )}
          >
            {tag}
            {!disabled && (
              <button
                type="button"
                onClick={() => handleRemove(tag)}
                className="hover:text-primary-900 transition-colors"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </span>
        ))}
      </div>
      {!disabled && (
        <Input
          type="text"
          placeholder="Add personality trait (press Enter)"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          size="sm"
        />
      )}
    </div>
  )
}

// ============================================================================
// Main Component
// ============================================================================

export interface BrandConfigPanelProps {
  /** Project ID to manage brand config for */
  projectId: string
  /** Optional CSS classes */
  className?: string
}

/**
 * BrandConfigPanel provides brand configuration management with document upload
 *
 * @example
 * <BrandConfigPanel projectId="abc-123" />
 */
export function BrandConfigPanel({ projectId, className }: BrandConfigPanelProps) {
  // UI state
  const [showUpload, setShowUpload] = useState(true)
  const [showColors, setShowColors] = useState(true)
  const [showTypography, setShowTypography] = useState(false)
  const [showVoice, setShowVoice] = useState(false)
  const [showSocial, setShowSocial] = useState(false)
  const [isEditing, setIsEditing] = useState(false)

  // Upload state
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [brandName, setBrandName] = useState('')
  const [domain, setDomain] = useState('')
  const [additionalContext, setAdditionalContext] = useState('')

  // Edit state
  const [editedSchema, setEditedSchema] = useState<V2Schema | null>(null)

  // Fetch brand configs
  const {
    data: brandConfigs,
    isLoading: isLoadingConfigs,
    refetch: refetchConfigs,
  } = useApiQuery<BrandConfigListResponse>({
    queryKey: ['brand-configs', projectId],
    endpoint: `/api/v1/projects/${projectId}/phases/brand_config`,
    requestOptions: {
      userAction: 'Load brand configs',
      component: 'BrandConfigPanel',
    },
  })

  // Get the active brand config (first one)
  const activeConfig = useMemo(() => {
    return brandConfigs?.items?.[0] || null
  }, [brandConfigs])

  // Synthesize mutation
  const synthesizeMutation = useToastMutation<SynthesisResponse, Error, SynthesisRequest>({
    mutationFn: (data) =>
      api.post<SynthesisResponse>(
        `/api/v1/projects/${projectId}/phases/brand_config/synthesize`,
        data,
        {
          userAction: 'Synthesize brand config',
          component: 'BrandConfigPanel',
        }
      ),
    userAction: 'Synthesize brand config',
    successMessage: 'Brand config synthesized',
    successDescription: 'Brand guidelines extracted from documents.',
    onSuccess: () => {
      addBreadcrumb('Brand config synthesized', 'mutation', { projectId })
      refetchConfigs()
      setUploadedFiles([])
      setBrandName('')
      setDomain('')
      setAdditionalContext('')
    },
  })

  // Update mutation
  const updateMutation = useToastMutation<BrandConfigResponse, Error, { id: string; v2_schema: V2Schema }>({
    mutationFn: ({ id, v2_schema }) =>
      api.put<BrandConfigResponse>(
        `/api/v1/projects/${projectId}/phases/brand_config/${id}`,
        { v2_schema },
        {
          userAction: 'Update brand config',
          component: 'BrandConfigPanel',
        }
      ),
    userAction: 'Update brand config',
    successMessage: 'Brand config updated',
    onSuccess: () => {
      addBreadcrumb('Brand config updated', 'mutation', { projectId })
      refetchConfigs()
      setIsEditing(false)
      setEditedSchema(null)
    },
  })

  // File handling
  const handleFilesAdded = useCallback(
    async (files: File[]) => {
      const validFiles: UploadedFile[] = []

      for (const file of files) {
        // Check file count
        if (uploadedFiles.length + validFiles.length >= MAX_FILES) {
          console.warn('[BrandConfigPanel] Max files reached', { maxFiles: MAX_FILES })
          break
        }

        // Validate file type
        const isValidType = Object.keys(ACCEPTED_FILE_TYPES).includes(file.type) ||
          ['.pdf', '.docx', '.txt'].some((ext) => file.name.toLowerCase().endsWith(ext))

        if (!isValidType) {
          console.warn('[BrandConfigPanel] Invalid file type', {
            fileName: file.name,
            fileType: file.type,
          })
          validFiles.push({
            id: crypto.randomUUID(),
            file,
            name: file.name,
            size: file.size,
            base64: null,
            status: 'error',
            error: 'Invalid file type',
          })
          continue
        }

        // Validate file size
        if (file.size > MAX_FILE_SIZE) {
          console.warn('[BrandConfigPanel] File too large', {
            fileName: file.name,
            fileSize: file.size,
            maxSize: MAX_FILE_SIZE,
          })
          validFiles.push({
            id: crypto.randomUUID(),
            file,
            name: file.name,
            size: file.size,
            base64: null,
            status: 'error',
            error: 'File too large (max 50MB)',
          })
          continue
        }

        // Add file with pending status
        const uploadedFile: UploadedFile = {
          id: crypto.randomUUID(),
          file,
          name: file.name,
          size: file.size,
          base64: null,
          status: 'processing',
        }
        validFiles.push(uploadedFile)
      }

      setUploadedFiles((prev) => [...prev, ...validFiles])

      // Process files to base64
      for (const uploadedFile of validFiles.filter((f) => f.status === 'processing')) {
        try {
          const base64 = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              const result = reader.result as string
              // Extract base64 part from data URL
              const base64Data = result.split(',')[1]
              resolve(base64Data)
            }
            reader.onerror = () => reject(new Error('Failed to read file'))
            reader.readAsDataURL(uploadedFile.file)
          })

          setUploadedFiles((prev) =>
            prev.map((f) =>
              f.id === uploadedFile.id
                ? { ...f, base64, status: 'ready' as const }
                : f
            )
          )

          addBreadcrumb('File processed', 'file_upload', {
            fileName: uploadedFile.name,
            fileSize: uploadedFile.size,
          })
        } catch (error) {
          console.error('[BrandConfigPanel] Failed to process file', {
            fileName: uploadedFile.name,
            error,
          })
          setUploadedFiles((prev) =>
            prev.map((f) =>
              f.id === uploadedFile.id
                ? { ...f, status: 'error' as const, error: 'Failed to read file' }
                : f
            )
          )
        }
      }
    },
    [uploadedFiles.length]
  )

  const handleFileRemove = useCallback((id: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.id !== id))
    addBreadcrumb('File removed', 'file_upload', { fileId: id })
  }, [])

  // Synthesis handler
  const handleSynthesize = useCallback(() => {
    if (!brandName.trim()) {
      console.warn('[BrandConfigPanel] Brand name required for synthesis')
      return
    }

    const readyFiles = uploadedFiles.filter((f) => f.status === 'ready' && f.base64)
    if (readyFiles.length === 0 && !additionalContext.trim()) {
      console.warn('[BrandConfigPanel] At least one document or context required')
      return
    }

    addBreadcrumb('Starting synthesis', 'user_action', {
      brandName,
      domain,
      fileCount: readyFiles.length,
      hasContext: !!additionalContext.trim(),
    })

    synthesizeMutation.mutate({
      brand_name: brandName.trim(),
      domain: domain.trim() || undefined,
      source_documents: readyFiles.map((f) => f.base64!),
      document_filenames: readyFiles.map((f) => f.name),
      additional_context: additionalContext.trim() || undefined,
    })
  }, [brandName, domain, uploadedFiles, additionalContext, synthesizeMutation])

  // Edit handlers
  const handleStartEdit = useCallback(() => {
    if (activeConfig) {
      setEditedSchema(activeConfig.v2_schema)
      setIsEditing(true)
      addBreadcrumb('Start editing brand config', 'user_action', { configId: activeConfig.id })
    }
  }, [activeConfig])

  const handleCancelEdit = useCallback(() => {
    setIsEditing(false)
    setEditedSchema(null)
    addBreadcrumb('Cancel editing brand config', 'user_action')
  }, [])

  const handleSaveEdit = useCallback(() => {
    if (activeConfig && editedSchema) {
      updateMutation.mutate({
        id: activeConfig.id,
        v2_schema: editedSchema,
      })
    }
  }, [activeConfig, editedSchema, updateMutation])

  // Schema update helpers
  const updateColor = useCallback((key: keyof ColorsSchema, value: string) => {
    if (!editedSchema) return
    setEditedSchema({
      ...editedSchema,
      colors: { ...editedSchema.colors, [key]: value },
    })
  }, [editedSchema])

  const updateTypography = useCallback((key: keyof TypographySchema, value: string | number) => {
    if (!editedSchema) return
    setEditedSchema({
      ...editedSchema,
      typography: { ...editedSchema.typography, [key]: value },
    })
  }, [editedSchema])

  const updateVoice = useCallback((key: keyof VoiceSchema, value: string | string[]) => {
    if (!editedSchema) return
    setEditedSchema({
      ...editedSchema,
      voice: { ...editedSchema.voice, [key]: value },
    })
  }, [editedSchema])

  const updateSocial = useCallback((key: keyof SocialSchema, value: string) => {
    if (!editedSchema) return
    setEditedSchema({
      ...editedSchema,
      social: { ...editedSchema.social, [key]: value || null },
    })
  }, [editedSchema])

  // Current schema to display
  const displaySchema = isEditing && editedSchema ? editedSchema : activeConfig?.v2_schema

  // Calculate stats
  const colorCount = useMemo(() => {
    if (!displaySchema?.colors) return 0
    return Object.values(displaySchema.colors).filter((v) => v).length
  }, [displaySchema?.colors])

  const hasTypography = useMemo(() => {
    if (!displaySchema?.typography) return false
    return Object.values(displaySchema.typography).some((v) => v)
  }, [displaySchema?.typography])

  const hasVoice = useMemo(() => {
    if (!displaySchema?.voice) return false
    const { personality, ...rest } = displaySchema.voice
    return personality?.length > 0 || Object.values(rest).some((v) => v)
  }, [displaySchema?.voice])

  const readyFilesCount = uploadedFiles.filter((f) => f.status === 'ready').length
  const canSynthesize = brandName.trim() && (readyFilesCount > 0 || additionalContext.trim())

  return (
    <div className={cn('space-y-6', className)}>
      {/* Stats Overview */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
              <Palette className="w-5 h-5 text-primary-600" />
            </div>
            <div>
              <h3 className="font-semibold text-warmgray-900">Brand Configuration</h3>
              <p className="text-sm text-warmgray-500">Visual identity and voice guidelines</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => refetchConfigs()}
            disabled={isLoadingConfigs}
          >
            <RefreshCw
              className={cn('w-4 h-4', isLoadingConfigs && 'animate-spin')}
            />
            Refresh
          </Button>
        </div>

        {isLoadingConfigs ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" label="Loading brand config..." showLabel />
          </div>
        ) : activeConfig ? (
          <div className="space-y-6">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <StatsCard
                label="Brand Colors"
                value={colorCount}
                icon={Palette}
                variant={colorCount > 0 ? 'success' : 'warning'}
              />
              <StatsCard
                label="Typography"
                value={hasTypography ? 'Configured' : 'Not set'}
                icon={Type}
                variant={hasTypography ? 'success' : 'warning'}
              />
              <StatsCard
                label="Voice & Tone"
                value={hasVoice ? 'Defined' : 'Not set'}
                icon={MessageSquare}
                variant={hasVoice ? 'success' : 'warning'}
              />
            </div>

            {/* Brand info */}
            <div className="flex items-center justify-between p-3 bg-cream-50 rounded-lg">
              <div>
                <p className="text-sm font-medium text-warmgray-700">
                  {activeConfig.brand_name}
                </p>
                {activeConfig.domain && (
                  <p className="text-xs text-warmgray-500">
                    {activeConfig.domain}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {!isEditing ? (
                  <>
                    <Link to={`/projects/${projectId}/brand-wizard`}>
                      <Button variant="outline" size="sm">
                        <Wand2 className="w-4 h-4" />
                        Wizard
                      </Button>
                    </Link>
                    <Button variant="outline" size="sm" onClick={handleStartEdit}>
                      <Edit3 className="w-4 h-4" />
                      Edit
                    </Button>
                  </>
                ) : (
                  <>
                    <Button variant="ghost" size="sm" onClick={handleCancelEdit}>
                      Cancel
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      onClick={handleSaveEdit}
                      disabled={updateMutation.isPending}
                    >
                      {updateMutation.isPending ? <ButtonSpinner /> : <Save className="w-4 h-4" />}
                      Save
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-6">
            <Palette className="w-12 h-12 text-warmgray-300 mx-auto mb-3" />
            <p className="text-warmgray-500">No brand configuration yet</p>
            <p className="text-sm text-warmgray-400 mt-1 mb-4">
              Use the wizard to configure your brand identity, or upload documents below.
            </p>
            <Link to={`/projects/${projectId}/brand-wizard`}>
              <Button>
                <Wand2 className="w-4 h-4" />
                Launch Brand Wizard
              </Button>
            </Link>
          </div>
        )}
      </div>

      {/* Document Upload Section */}
      {!activeConfig && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowUpload(!showUpload)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <Upload className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Upload Brand Documents</h3>
                <p className="text-sm text-warmgray-500">
                  PDF, DOCX, or TXT brand guidelines
                </p>
              </div>
            </div>
            {showUpload ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showUpload && (
            <div className="mt-6 space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Brand Name" required helperText="The name of the brand">
                  <Input
                    type="text"
                    placeholder="e.g., Acme Corporation"
                    value={brandName}
                    onChange={(e) => setBrandName(e.target.value)}
                    disabled={synthesizeMutation.isPending}
                  />
                </FormField>

                <FormField label="Domain" optional helperText="Primary website domain">
                  <Input
                    type="text"
                    placeholder="e.g., acme.com"
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    disabled={synthesizeMutation.isPending}
                  />
                </FormField>
              </div>

              <FileDropZone
                files={uploadedFiles}
                onFilesAdded={handleFilesAdded}
                onFileRemove={handleFileRemove}
                disabled={synthesizeMutation.isPending}
              />

              <FormField
                label="Additional Context"
                optional
                helperText="Extra information to help with synthesis"
              >
                <Textarea
                  placeholder="Add any additional brand guidelines, notes, or context..."
                  value={additionalContext}
                  onChange={(e) => setAdditionalContext(e.target.value)}
                  disabled={synthesizeMutation.isPending}
                  rows={4}
                />
              </FormField>

              <div className="flex items-center justify-end pt-2">
                <Button
                  type="button"
                  disabled={!canSynthesize || synthesizeMutation.isPending}
                  onClick={handleSynthesize}
                >
                  {synthesizeMutation.isPending ? (
                    <ButtonSpinner />
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Synthesize Brand Config
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Colors Section */}
      {displaySchema && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowColors(!showColors)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <Palette className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Color Palette</h3>
                <p className="text-sm text-warmgray-500">
                  {colorCount} colors defined
                </p>
              </div>
            </div>
            {showColors ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showColors && (
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <ColorSwatch
                color={displaySchema.colors.primary}
                label="Primary"
                onChange={isEditing ? (c) => updateColor('primary', c) : undefined}
                disabled={!isEditing}
              />
              <ColorSwatch
                color={displaySchema.colors.secondary}
                label="Secondary"
                onChange={isEditing ? (c) => updateColor('secondary', c) : undefined}
                disabled={!isEditing}
              />
              <ColorSwatch
                color={displaySchema.colors.accent}
                label="Accent"
                onChange={isEditing ? (c) => updateColor('accent', c) : undefined}
                disabled={!isEditing}
              />
              <ColorSwatch
                color={displaySchema.colors.background}
                label="Background"
                onChange={isEditing ? (c) => updateColor('background', c) : undefined}
                disabled={!isEditing}
              />
              <ColorSwatch
                color={displaySchema.colors.text}
                label="Text"
                onChange={isEditing ? (c) => updateColor('text', c) : undefined}
                disabled={!isEditing}
              />
            </div>
          )}
        </div>
      )}

      {/* Typography Section */}
      {displaySchema && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowTypography(!showTypography)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <Type className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Typography</h3>
                <p className="text-sm text-warmgray-500">
                  {displaySchema.typography.heading_font || displaySchema.typography.body_font
                    ? 'Font settings configured'
                    : 'No fonts configured'}
                </p>
              </div>
            </div>
            {showTypography ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showTypography && (
            <div className="mt-6 space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Heading Font" optional>
                  <Input
                    type="text"
                    placeholder="e.g., Inter"
                    value={displaySchema.typography.heading_font || ''}
                    onChange={(e) => updateTypography('heading_font', e.target.value)}
                    disabled={!isEditing}
                  />
                </FormField>
                <FormField label="Body Font" optional>
                  <Input
                    type="text"
                    placeholder="e.g., Open Sans"
                    value={displaySchema.typography.body_font || ''}
                    onChange={(e) => updateTypography('body_font', e.target.value)}
                    disabled={!isEditing}
                  />
                </FormField>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <FormField label="Base Size (px)" optional>
                  <Input
                    type="number"
                    placeholder="16"
                    value={displaySchema.typography.base_size || ''}
                    onChange={(e) => updateTypography('base_size', parseInt(e.target.value) || 0)}
                    disabled={!isEditing}
                    min={10}
                    max={24}
                  />
                </FormField>
                <FormField label="Heading Weight" optional>
                  <Input
                    type="text"
                    placeholder="bold"
                    value={displaySchema.typography.heading_weight || ''}
                    onChange={(e) => updateTypography('heading_weight', e.target.value)}
                    disabled={!isEditing}
                  />
                </FormField>
                <FormField label="Body Weight" optional>
                  <Input
                    type="text"
                    placeholder="regular"
                    value={displaySchema.typography.body_weight || ''}
                    onChange={(e) => updateTypography('body_weight', e.target.value)}
                    disabled={!isEditing}
                  />
                </FormField>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Voice & Tone Section */}
      {displaySchema && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowVoice(!showVoice)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Voice & Tone</h3>
                <p className="text-sm text-warmgray-500">
                  {displaySchema.voice.tone || 'Brand voice not defined'}
                </p>
              </div>
            </div>
            {showVoice ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showVoice && (
            <div className="mt-6 space-y-5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <FormField label="Tone" optional helperText="Overall brand tone">
                  <Select
                    value={displaySchema.voice.tone || ''}
                    onChange={(e) => updateVoice('tone', e.target.value)}
                    disabled={!isEditing}
                  >
                    <option value="">Select tone...</option>
                    {TONE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
                <FormField label="Writing Style" optional helperText="Content writing style">
                  <Select
                    value={displaySchema.voice.writing_style || ''}
                    onChange={(e) => updateVoice('writing_style', e.target.value)}
                    disabled={!isEditing}
                  >
                    <option value="">Select style...</option>
                    {WRITING_STYLE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </Select>
                </FormField>
              </div>

              <FormField label="Personality Traits" optional helperText="Press Enter to add">
                <PersonalityTags
                  tags={displaySchema.voice.personality || []}
                  onChange={(tags) => updateVoice('personality', tags)}
                  disabled={!isEditing}
                />
              </FormField>

              <FormField label="Target Audience" optional>
                <Textarea
                  placeholder="Describe the target audience..."
                  value={displaySchema.voice.target_audience || ''}
                  onChange={(e) => updateVoice('target_audience', e.target.value)}
                  disabled={!isEditing}
                  rows={2}
                />
              </FormField>

              <FormField label="Value Proposition" optional>
                <Textarea
                  placeholder="Core value proposition statement..."
                  value={displaySchema.voice.value_proposition || ''}
                  onChange={(e) => updateVoice('value_proposition', e.target.value)}
                  disabled={!isEditing}
                  rows={2}
                />
              </FormField>

              <FormField label="Tagline" optional>
                <Input
                  type="text"
                  placeholder="Brand tagline or slogan..."
                  value={displaySchema.voice.tagline || ''}
                  onChange={(e) => updateVoice('tagline', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
            </div>
          )}
        </div>
      )}

      {/* Social Media Section */}
      {displaySchema && (
        <div className="card">
          <button
            type="button"
            className="w-full flex items-center justify-between"
            onClick={() => setShowSocial(!showSocial)}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-cream-100 flex items-center justify-center">
                <ExternalLink className="w-5 h-5 text-warmgray-600" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-warmgray-900">Social Media</h3>
                <p className="text-sm text-warmgray-500">
                  Brand social handles
                </p>
              </div>
            </div>
            {showSocial ? (
              <ChevronUp className="w-5 h-5 text-warmgray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-warmgray-400" />
            )}
          </button>

          {showSocial && (
            <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Twitter/X" optional>
                <Input
                  type="text"
                  placeholder="@handle"
                  value={displaySchema.social.twitter || ''}
                  onChange={(e) => updateSocial('twitter', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
              <FormField label="LinkedIn" optional>
                <Input
                  type="text"
                  placeholder="company/handle"
                  value={displaySchema.social.linkedin || ''}
                  onChange={(e) => updateSocial('linkedin', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
              <FormField label="Instagram" optional>
                <Input
                  type="text"
                  placeholder="@handle"
                  value={displaySchema.social.instagram || ''}
                  onChange={(e) => updateSocial('instagram', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
              <FormField label="Facebook" optional>
                <Input
                  type="text"
                  placeholder="Page name"
                  value={displaySchema.social.facebook || ''}
                  onChange={(e) => updateSocial('facebook', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
              <FormField label="YouTube" optional>
                <Input
                  type="text"
                  placeholder="Channel"
                  value={displaySchema.social.youtube || ''}
                  onChange={(e) => updateSocial('youtube', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
              <FormField label="TikTok" optional>
                <Input
                  type="text"
                  placeholder="@handle"
                  value={displaySchema.social.tiktok || ''}
                  onChange={(e) => updateSocial('tiktok', e.target.value)}
                  disabled={!isEditing}
                />
              </FormField>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
