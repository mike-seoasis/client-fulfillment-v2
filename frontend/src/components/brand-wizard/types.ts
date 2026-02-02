/**
 * Types for the Brand Wizard components
 *
 * Defines shared types used across wizard steps and components.
 */

/**
 * Voice dimension slider values (1-10 scale)
 */
export interface VoiceDimensions {
  formality: number
  humor: number
  reverence: number
  enthusiasm: number
}

/**
 * Voice characteristics ("We are" / "We are not")
 */
export interface VoiceCharacteristics {
  we_are: string[]
  we_are_not: string[]
  example_phrases?: string[]
}

/**
 * Customer persona data structure
 */
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

/**
 * Example pair for good/bad examples
 */
export interface ExamplePair {
  good: string
  bad?: string
  explanation?: string
}

/**
 * Writing rules configuration
 */
export interface WritingRules {
  sentence_length?: 'short' | 'medium' | 'long' | 'varied'
  paragraph_length?: 'short' | 'medium' | 'long'
  use_contractions?: boolean
  use_first_person?: boolean
  use_oxford_comma?: boolean
  use_exclamation_marks?: 'never' | 'sparingly' | 'freely'
  capitalization_style?: 'sentence' | 'title' | 'all_caps'
  formatting_preferences?: string[]
}

/**
 * Vocabulary configuration
 */
export interface Vocabulary {
  power_words: string[]
  banned_words: string[]
  preferred_terms: Record<string, string>
  industry_terms: string[]
  emojis_allowed?: boolean
  emoji_style?: string
}

/**
 * Proof elements (statistics, credentials, quotes)
 */
export interface ProofElements {
  statistics: Array<{
    stat: string
    context?: string
    source?: string
  }>
  credentials: string[]
  customer_quotes: Array<{
    quote: string
    attribution?: string
    context?: string
  }>
  guarantees: string[]
  certifications: string[]
}

/**
 * Examples bank for different content types
 */
export interface ExamplesBank {
  headlines: ExamplePair[]
  product_descriptions: ExamplePair[]
  ctas: ExamplePair[]
  email_subject_lines: ExamplePair[]
  social_posts: ExamplePair[]
}

/**
 * Complete wizard form data
 */
export interface WizardFormData {
  // Step 1: Brand Setup
  brand_name?: string
  domain?: string

  // Step 2: Foundation
  foundation?: {
    company_overview?: {
      name?: string
      founded?: string
      location?: string
      industry?: string
      business_model?: string
    }
    products_services?: {
      primary?: string[]
      secondary?: string[]
      price_point?: string
      sales_channels?: string[]
    }
    positioning?: {
      tagline?: string
      one_sentence?: string
      category_position?: string
    }
    mission_values?: {
      mission_statement?: string
      core_values?: string[]
      brand_promise?: string
    }
    differentiators?: {
      primary_usp?: string
      supporting?: string[]
      what_we_are_not?: string[]
    }
  }

  // Step 3: Audience
  personas?: PersonaData[]

  // Step 4: Voice
  voice_dimensions?: VoiceDimensions
  voice_characteristics?: VoiceCharacteristics

  // Step 5: Writing Rules
  writing_rules?: WritingRules
  vocabulary?: Vocabulary

  // Step 6: Proof & Examples
  proof_elements?: ProofElements
  examples_bank?: ExamplesBank

  // Step 7: Review (no additional data, just final review)
}

/**
 * Research data from Perplexity
 */
export interface ResearchData {
  raw_research?: string
  structured_data?: Partial<WizardFormData>
}

/**
 * Wizard state from backend
 */
export interface WizardState {
  project_id: string
  current_step: number
  steps_completed: number[]
  brand_name?: string
  domain?: string
  research_data?: ResearchData
  research_citations?: string[]
  research_cached_at?: string
  form_data: WizardFormData
  updated_at?: string
}

/**
 * Props common to all wizard steps
 */
export interface WizardStepBaseProps {
  /** Current form data */
  formData: WizardFormData
  /** Callback when form data changes */
  onChange: (data: Partial<WizardFormData>) => void
  /** Whether the step is disabled */
  disabled?: boolean
  /** Optional additional CSS classes */
  className?: string
}
