/**
 * Step 3: Audience
 *
 * Customer personas with demographics, psychographics, and behavioral insights.
 *
 * Features:
 * - Add/edit/remove personas
 * - Primary persona indicator
 * - Expandable persona cards
 * - Pre-populated fields from research
 */

import { cn } from '@/lib/utils'
import { WizardStepHeader } from '../WizardContainer'
import { PersonaCard } from '../PersonaCard'
import { Button } from '@/components/ui/button'
import { Plus, Users } from 'lucide-react'
import type { WizardStepBaseProps, PersonaData } from '../types'

/** Default empty persona */
const createEmptyPersona = (name: string = 'New Persona', isPrimary: boolean = false): PersonaData => ({
  name,
  summary: '',
  is_primary: isPrimary,
  demographics: {},
  psychographics: {},
  behavioral: {},
  communication: {},
})

/**
 * Step3Audience - audience step for customer personas
 */
export function Step3Audience({
  formData,
  onChange,
  disabled = false,
  className,
}: WizardStepBaseProps) {
  const personas = formData.personas || []

  const updatePersonas = (newPersonas: PersonaData[]) => {
    onChange({ personas: newPersonas })
  }

  const addPersona = () => {
    const isFirst = personas.length === 0
    updatePersonas([
      ...personas,
      createEmptyPersona(`Persona ${personas.length + 1}`, isFirst),
    ])
  }

  const updatePersona = (index: number, updated: PersonaData) => {
    const newPersonas = [...personas]
    newPersonas[index] = updated
    updatePersonas(newPersonas)
  }

  const deletePersona = (index: number) => {
    const newPersonas = personas.filter((_, i) => i !== index)
    // If we deleted the primary persona and there are others, make the first one primary
    if (personas[index]?.is_primary && newPersonas.length > 0) {
      newPersonas[0] = { ...newPersonas[0], is_primary: true }
    }
    updatePersonas(newPersonas)
  }

  const setPrimaryPersona = (index: number) => {
    const newPersonas = personas.map((p, i) => ({
      ...p,
      is_primary: i === index,
    }))
    updatePersonas(newPersonas)
  }

  const canAddMore = personas.length < 5 && !disabled

  return (
    <div className={cn('space-y-8', className)}>
      <WizardStepHeader
        title="Target Audience"
        description="Define your ideal customers. Understanding who you're talking to helps shape your brand voice and messaging strategy."
      />

      {/* Personas list */}
      {personas.length === 0 ? (
        <div className="text-center py-12 bg-cream-50 rounded-xl border-2 border-dashed border-cream-300">
          <Users className="w-12 h-12 text-warmgray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-warmgray-700 mb-2">
            No personas yet
          </h3>
          <p className="text-warmgray-500 mb-6 max-w-md mx-auto">
            Create customer personas to help guide your brand voice and messaging.
            Start by adding your primary target audience.
          </p>
          <Button type="button" onClick={addPersona} disabled={disabled}>
            <Plus className="w-4 h-4 mr-2" />
            Add first persona
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          {personas.map((persona, index) => (
            <PersonaCard
              key={index}
              persona={persona}
              onUpdate={(updated) => updatePersona(index, updated)}
              onDelete={() => deletePersona(index)}
              onSetPrimary={() => setPrimaryPersona(index)}
              isOnlyPersona={personas.length === 1}
            />
          ))}

          {/* Add persona button */}
          {canAddMore && (
            <Button
              type="button"
              variant="outline"
              onClick={addPersona}
              className="w-full"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add another persona ({personas.length}/5)
            </Button>
          )}
        </div>
      )}

      {/* Help text */}
      <div className="text-sm text-warmgray-500 bg-warmgray-50 rounded-lg p-4">
        <p className="font-medium text-warmgray-700 mb-2">Tips for effective personas:</p>
        <ul className="space-y-1 list-disc list-inside">
          <li>Focus on 2-3 key personas rather than trying to cover everyone</li>
          <li>Mark your most important customer segment as "Primary"</li>
          <li>Include both demographic facts and psychographic motivations</li>
          <li>Think about their pain points, goals, and decision-making process</li>
        </ul>
      </div>
    </div>
  )
}
