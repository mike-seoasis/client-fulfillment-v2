/**
 * PersonaCard component for displaying/editing customer personas
 *
 * Displays all persona fields: name, demographics, psychographics,
 * behavioral insights, and communication preferences.
 *
 * Features:
 * - Expandable/collapsible sections
 * - Edit mode for all fields
 * - Primary persona indicator
 * - Delete confirmation
 */

import { cn } from '@/lib/utils'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ChipInput } from './ChipInput'
import {
  ChevronDown,
  ChevronUp,
  Star,
  Trash2,
  Edit2,
  Check,
  X,
  User,
} from 'lucide-react'

export interface PersonaData {
  name: string
  summary?: string
  is_primary?: boolean
  demographics: {
    age_range?: string
    gender?: string
    location?: string
    income_level?: string
    profession?: string
    education?: string
  }
  psychographics: {
    values?: string[]
    aspirations?: string[]
    fears?: string[]
    frustrations?: string[]
    identity?: string
  }
  behavioral: {
    discovery_channels?: string[]
    research_behavior?: string
    decision_factors?: string[]
    buying_triggers?: string[]
    common_objections?: string[]
  }
  communication: {
    preferred_tone?: string
    language_style?: string
    content_consumption?: string[]
    trust_signals?: string[]
  }
}

export interface PersonaCardProps {
  /** Persona data */
  persona: PersonaData
  /** Callback when persona is updated */
  onUpdate: (persona: PersonaData) => void
  /** Callback when persona is deleted */
  onDelete: () => void
  /** Callback when set as primary */
  onSetPrimary: () => void
  /** Whether this is the only persona (can't delete) */
  isOnlyPersona?: boolean
  /** Optional additional CSS classes */
  className?: string
}

/**
 * PersonaCard displays and allows editing of a customer persona
 *
 * @example
 * <PersonaCard
 *   persona={persona}
 *   onUpdate={(updated) => updatePersona(index, updated)}
 *   onDelete={() => deletePersona(index)}
 *   onSetPrimary={() => setPrimaryPersona(index)}
 * />
 */
export function PersonaCard({
  persona,
  onUpdate,
  onDelete,
  onSetPrimary,
  isOnlyPersona = false,
  className,
}: PersonaCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState<PersonaData>(persona)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleSave = () => {
    onUpdate(editData)
    setIsEditing(false)
  }

  const handleCancel = () => {
    setEditData(persona)
    setIsEditing(false)
  }

  const updateField = <K extends keyof PersonaData>(
    field: K,
    value: PersonaData[K]
  ) => {
    setEditData({ ...editData, [field]: value })
  }

  const updateNestedField = <
    K extends keyof PersonaData,
    NK extends keyof NonNullable<PersonaData[K]>
  >(
    field: K,
    nestedField: NK,
    value: NonNullable<PersonaData[K]>[NK]
  ) => {
    setEditData({
      ...editData,
      [field]: {
        ...(editData[field] as object || {}),
        [nestedField]: value,
      },
    })
  }

  return (
    <div
      className={cn(
        'bg-white border rounded-lg overflow-hidden',
        persona.is_primary ? 'border-primary-300 ring-1 ring-primary-100' : 'border-cream-200',
        className
      )}
    >
      {/* Header */}
      <div
        className={cn(
          'flex items-center gap-3 p-4 cursor-pointer',
          persona.is_primary && 'bg-primary-50'
        )}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
          <User className="w-5 h-5 text-primary-600" />
        </div>

        {/* Name and badges */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-warmgray-900 truncate">
              {persona.name || 'Unnamed Persona'}
            </h3>
            {persona.is_primary && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-primary-100 text-primary-700">
                <Star className="w-3 h-3" />
                Primary
              </span>
            )}
          </div>
          {persona.summary && (
            <p className="text-sm text-warmgray-500 truncate">
              {persona.summary}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {!isEditing && (
            <>
              {!persona.is_primary && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={onSetPrimary}
                  title="Set as primary"
                >
                  <Star className="w-4 h-4" />
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditData(persona)
                  setIsEditing(true)
                  setIsExpanded(true)
                }}
              >
                <Edit2 className="w-4 h-4" />
              </Button>
            </>
          )}
          {isExpanded ? (
            <ChevronUp className="w-5 h-5 text-warmgray-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-warmgray-400" />
          )}
        </div>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="p-4 border-t border-cream-200 space-y-6">
          {/* Basic info */}
          <section>
            <h4 className="text-sm font-medium text-warmgray-700 mb-3">Basic Info</h4>
            <div className="grid grid-cols-2 gap-4">
              <InputField
                label="Name"
                value={isEditing ? editData.name : persona.name}
                onChange={(v) => updateField('name', v)}
                disabled={!isEditing}
              />
              <InputField
                label="Summary"
                value={isEditing ? editData.summary : persona.summary}
                onChange={(v) => updateField('summary', v)}
                disabled={!isEditing}
                multiline
              />
            </div>
          </section>

          {/* Demographics */}
          <section>
            <h4 className="text-sm font-medium text-warmgray-700 mb-3">Demographics</h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              {(['age_range', 'gender', 'location', 'income_level', 'profession', 'education'] as const).map((field) => (
                <InputField
                  key={field}
                  label={field.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  value={isEditing ? editData.demographics[field] : persona.demographics[field]}
                  onChange={(v) => updateNestedField('demographics', field, v)}
                  disabled={!isEditing}
                />
              ))}
            </div>
          </section>

          {/* Psychographics */}
          <section>
            <h4 className="text-sm font-medium text-warmgray-700 mb-3">Psychographics</h4>
            <div className="space-y-4">
              {(['values', 'aspirations', 'fears', 'frustrations'] as const).map((field) => (
                <ChipInput
                  key={field}
                  label={field.replace(/\b\w/g, (c) => c.toUpperCase())}
                  values={(isEditing ? editData.psychographics[field] : persona.psychographics[field]) || []}
                  onChange={(v) => updateNestedField('psychographics', field, v)}
                  disabled={!isEditing}
                  placeholder={`Add ${field}...`}
                />
              ))}
              <InputField
                label="Identity"
                value={isEditing ? editData.psychographics.identity : persona.psychographics.identity}
                onChange={(v) => updateNestedField('psychographics', 'identity', v)}
                disabled={!isEditing}
              />
            </div>
          </section>

          {/* Behavioral */}
          <section>
            <h4 className="text-sm font-medium text-warmgray-700 mb-3">Behavioral Insights</h4>
            <div className="space-y-4">
              {(['discovery_channels', 'decision_factors', 'buying_triggers', 'common_objections'] as const).map((field) => (
                <ChipInput
                  key={field}
                  label={field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  values={(isEditing ? editData.behavioral[field] : persona.behavioral[field]) || []}
                  onChange={(v) => updateNestedField('behavioral', field, v)}
                  disabled={!isEditing}
                />
              ))}
              <InputField
                label="Research Behavior"
                value={isEditing ? editData.behavioral.research_behavior : persona.behavioral.research_behavior}
                onChange={(v) => updateNestedField('behavioral', 'research_behavior', v)}
                disabled={!isEditing}
                multiline
              />
            </div>
          </section>

          {/* Edit actions */}
          {isEditing && (
            <div className="flex items-center justify-between pt-4 border-t border-cream-200">
              <div>
                {!isOnlyPersona && (
                  showDeleteConfirm ? (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-error-600">Delete this persona?</span>
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={onDelete}
                      >
                        Yes, delete
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowDeleteConfirm(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="text-error-600 hover:text-error-700 hover:bg-error-50"
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                      Delete persona
                    </Button>
                  )
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleCancel}
                >
                  <X className="w-4 h-4 mr-1" />
                  Cancel
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSave}
                >
                  <Check className="w-4 h-4 mr-1" />
                  Save changes
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Simple text input field helper */
function InputField({
  label,
  value,
  onChange,
  disabled,
  multiline,
}: {
  label: string
  value?: string
  onChange: (value: string) => void
  disabled?: boolean
  multiline?: boolean
}) {
  const Component = multiline ? 'textarea' : 'input'
  return (
    <div>
      <label className="block text-xs text-warmgray-500 mb-1">{label}</label>
      <Component
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className={cn(
          'w-full px-3 py-2 text-sm border border-cream-200 rounded-md',
          'focus:border-primary-400 focus:ring-1 focus:ring-primary-400',
          disabled && 'bg-cream-50 cursor-default',
          multiline && 'min-h-[60px] resize-y'
        )}
      />
    </div>
  )
}
