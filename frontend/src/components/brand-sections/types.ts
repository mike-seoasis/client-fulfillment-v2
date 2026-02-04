/**
 * Type definitions for brand configuration section components.
 * These types match the v2_schema structure from the backend.
 */

// Brand Foundation types
export interface BrandFoundationData {
  company_overview?: {
    company_name?: string;
    founded?: string;
    location?: string;
    industry?: string;
    business_model?: string;
  };
  what_they_sell?: {
    primary_products?: string;
    secondary_offerings?: string;
    price_point?: string;
    sales_channels?: string;
  };
  brand_positioning?: {
    tagline?: string;
    one_sentence_description?: string;
    category_position?: string;
  };
  mission_and_values?: {
    mission_statement?: string;
    core_values?: string[];
    brand_promise?: string;
  };
  differentiators?: {
    primary_usp?: string;
    supporting_differentiators?: string[];
    what_we_are_not?: string[];
  };
}

// Target Audience types
export interface PersonaData {
  name: string;
  percentage?: string;
  demographics?: {
    age_range?: string;
    gender?: string;
    location?: string;
    income_level?: string;
    profession?: string;
    education?: string;
  };
  psychographics?: {
    values?: string[];
    aspirations?: string[];
    fears?: string[];
    frustrations?: string[];
    identity?: string;
  };
  behavioral?: {
    discovery_channels?: string[];
    research_behavior?: string;
    decision_factors?: string[];
    buying_triggers?: string[];
    objections?: string[];
  };
  communication?: {
    tone_preference?: string;
    language_style?: string;
    content_consumed?: string[];
    trust_signals?: string[];
  };
  summary?: string;
}

export interface TargetAudienceData {
  personas?: PersonaData[];
  audience_overview?: {
    primary_persona?: string;
    secondary_persona?: string;
    tertiary_persona?: string;
  };
}

// Voice Dimensions types
export interface VoiceDimensionScale {
  position: number; // 1-10
  description?: string;
  example?: string;
}

export interface VoiceDimensionsData {
  formality?: VoiceDimensionScale;
  humor?: VoiceDimensionScale;
  reverence?: VoiceDimensionScale;
  enthusiasm?: VoiceDimensionScale;
  voice_summary?: string;
}

// Voice Characteristics types
export interface VoiceTraitExample {
  trait_name: string;
  description?: string;
  do_example?: string;
  dont_example?: string;
}

export interface VoiceCharacteristicsData {
  we_are?: VoiceTraitExample[];
  we_are_not?: string[];
}

// Writing Style types
export interface WritingStyleData {
  sentence_structure?: {
    average_sentence_length?: string;
    paragraph_length?: string;
    use_contractions?: string;
    active_vs_passive?: string;
  };
  capitalization?: {
    headlines?: string;
    product_names?: string;
    feature_names?: string;
  };
  punctuation?: {
    serial_comma?: string;
    em_dashes?: string;
    exclamation_points?: string;
    ellipses?: string;
  };
  numbers_formatting?: {
    spell_out_rules?: string;
    currency?: string;
    percentages?: string;
    bold_usage?: string;
    bullet_usage?: string;
  };
}

// Vocabulary types
export interface WordSubstitution {
  instead_of: string;
  we_say: string;
}

export interface IndustryTerm {
  term: string;
  usage: string;
}

export interface VocabularyData {
  power_words?: string[];
  word_substitutions?: WordSubstitution[];
  banned_words?: string[];
  industry_terms?: IndustryTerm[];
  signature_phrases?: string[];
}

// Trust Elements types
export interface CustomerQuote {
  quote: string;
  attribution: string;
}

export interface TrustElementsData {
  hard_numbers?: {
    customer_count?: string;
    years_in_business?: string;
    products_sold?: string;
    average_store_rating?: string;
    review_count?: string;
  };
  credentials?: string[];
  media_press?: string[];
  endorsements?: string[];
  guarantees?: {
    return_policy?: string;
    warranty?: string;
    satisfaction_guarantee?: string;
  };
  customer_quotes?: CustomerQuote[];
}

// Examples Bank types
export interface ProductDescriptionItem {
  product_name: string;
  description: string;
}

export interface ExamplesBankData {
  headlines?: string[];
  /** @deprecated Use product_descriptions instead */
  product_description_example?: string;
  product_descriptions?: ProductDescriptionItem[];
  email_subject_lines?: string[];
  social_media_examples?: Array<{
    platform?: string;
    content?: string;
  }>;
  ctas?: string[];
  off_brand_examples?: Array<{
    example: string;
    reason?: string;
  }>;
}

// Competitor Context types
export interface CompetitorEntry {
  name: string;
  positioning?: string;
  our_difference?: string;
}

export interface CompetitorContextData {
  direct_competitors?: CompetitorEntry[];
  competitive_advantages?: string[];
  competitive_weaknesses?: string[];
  positioning_statements?: Array<{
    context?: string;
    statement: string;
  }>;
  rules?: string[];
}

// AI Prompt Snippet type
export interface AIPromptSnippetData {
  snippet: string;
  voice_in_three_words?: string[];
  we_sound_like?: string;
  we_never_sound_like?: string;
  primary_audience_summary?: string;
  key_differentiators?: string[];
  never_use_words?: string[];
  always_include?: string[];
}

// Base props for all section components
export interface BaseSectionProps {
  isEditing?: boolean;
  onUpdate?: (data: unknown) => void;
}
