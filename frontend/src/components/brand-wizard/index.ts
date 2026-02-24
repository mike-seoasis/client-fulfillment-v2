/**
 * Brand Wizard Components
 *
 * Components for the 7-step brand configuration wizard.
 */

// Layout components
export {
  WizardProgress,
  WizardProgressSkeleton,
  WIZARD_STEPS,
  type WizardProgressProps,
  type WizardStep,
} from './WizardProgress'

export {
  WizardNavigation,
  type WizardNavigationProps,
} from './WizardNavigation'

export {
  WizardContainer,
  WizardStepHeader,
  type WizardContainerProps,
  type WizardStepHeaderProps,
} from './WizardContainer'

// Form components
export {
  VoiceDimensionSlider,
  VOICE_DIMENSIONS,
  type VoiceDimensionSliderProps,
} from './VoiceDimensionSlider'

export {
  ChipInput,
  type ChipInputProps,
} from './ChipInput'

export {
  PersonaCard,
  type PersonaCardProps,
  type PersonaData,
} from './PersonaCard'

export {
  ExampleEditor,
  type ExampleEditorProps,
  type ExamplePair,
} from './ExampleEditor'

// Types
export type {
  WizardFormData,
  WizardState,
  WizardStepBaseProps,
  VoiceDimensions,
  VoiceCharacteristics,
  PersonaData as PersonaDataType,
  ExamplePair as ExamplePairType,
  WritingRules,
  Vocabulary,
  ProofElements,
  ExamplesBank,
  ResearchData,
} from './types'

// Step components
export {
  Step1BrandSetup,
  Step2Foundation,
  Step3Audience,
  Step4Voice,
  Step5WritingRules,
  Step6ProofExamples,
  Step7Review,
  type Step1BrandSetupProps,
  type Step7ReviewProps,
} from './steps'
