"""Pydantic schemas for Brand Config V3 - 11-part Brand Guidelines Bible framework.

Defines comprehensive brand configuration models aligned with the Brand Guidelines Bible:
1. Foundation - Company overview, positioning, mission/values, differentiators
2. Personas - Customer personas with demographics, psychographics, behavioral insights
3. Voice Dimensions - 4 sliders (formality, humor, reverence, enthusiasm)
4. Voice Characteristics - We are/We are not traits with examples
5. Writing Rules - Sentence/paragraph length, punctuation, formatting
6. Vocabulary - Power words, banned words, preferred terms, industry terms
7. Proof Elements - Statistics, credentials, quotes, guarantees
8. Examples Bank - Headlines, descriptions, CTAs with good/bad examples
9. Competitor Context - Competitive landscape, differentiators
10. AI Prompts - Snippets for AI writing tools
11. Quick Reference - Summary card for quick access
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# V3 SCHEMA VERSION CONSTANT
# =============================================================================

V3_SCHEMA_VERSION = "3.0"


# =============================================================================
# SECTION 1: FOUNDATION
# =============================================================================


class CompanyOverviewSchema(BaseModel):
    """Company overview details."""

    name: str | None = Field(None, description="Legal company name")
    founded: str | None = Field(None, description="Year founded")
    location: str | None = Field(None, description="HQ and other relevant locations")
    industry: str | None = Field(None, description="Primary industry/category")
    business_model: str | None = Field(
        None, description="Business model (B2B, B2C, DTC, Marketplace, etc.)"
    )

    model_config = ConfigDict(extra="allow")


class ProductsServicesSchema(BaseModel):
    """Products and services details."""

    primary: list[str] = Field(
        default_factory=list, description="Primary products/services"
    )
    secondary: list[str] = Field(
        default_factory=list, description="Secondary/supporting offerings"
    )
    price_point: str | None = Field(
        None, description="Price positioning (Budget/Mid-range/Premium/Luxury)"
    )
    sales_channels: list[str] = Field(
        default_factory=list,
        description="Sales channels (Online, retail, wholesale, etc.)",
    )

    model_config = ConfigDict(extra="allow")


class PositioningSchema(BaseModel):
    """Brand positioning details."""

    tagline: str | None = Field(None, description="Brand tagline or slogan")
    one_sentence: str | None = Field(
        None, description="One-sentence description of the company"
    )
    category_position: str | None = Field(
        None,
        description="Category position (Leader, challenger, specialist, disruptor)",
    )

    model_config = ConfigDict(extra="allow")


class MissionValuesSchema(BaseModel):
    """Mission and values details."""

    mission_statement: str | None = Field(None, description="Why the company exists")
    core_values: list[str] = Field(
        default_factory=list, description="3-5 guiding principles"
    )
    brand_promise: str | None = Field(
        None, description="What customers can always expect"
    )

    model_config = ConfigDict(extra="allow")


class DifferentiatorsSchema(BaseModel):
    """Brand differentiators."""

    primary_usp: str | None = Field(
        None, description="The #1 thing that makes them different"
    )
    supporting: list[str] = Field(
        default_factory=list, description="2-3 additional unique factors"
    )
    what_we_are_not: list[str] = Field(
        default_factory=list,
        description="Important distinctions/positioning they reject",
    )

    model_config = ConfigDict(extra="allow")


class FoundationSchema(BaseModel):
    """Section 1: Brand Foundation - non-negotiable facts about the brand."""

    company_overview: CompanyOverviewSchema = Field(
        default_factory=CompanyOverviewSchema
    )
    products_services: ProductsServicesSchema = Field(
        default_factory=ProductsServicesSchema
    )
    positioning: PositioningSchema = Field(default_factory=PositioningSchema)
    mission_values: MissionValuesSchema = Field(default_factory=MissionValuesSchema)
    differentiators: DifferentiatorsSchema = Field(
        default_factory=DifferentiatorsSchema
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 2: PERSONAS
# =============================================================================


class DemographicsSchema(BaseModel):
    """Demographics for a customer persona."""

    age_range: str | None = Field(None, description="Age range (e.g., 28-45)")
    gender: str | None = Field(None, description="Gender if relevant")
    location: str | None = Field(None, description="Geographic focus")
    income_level: str | None = Field(None, description="Income range or description")
    profession: str | None = Field(None, description="Profession/industry")
    education: str | None = Field(None, description="Education level if relevant")

    model_config = ConfigDict(extra="allow")


class PsychographicsSchema(BaseModel):
    """Psychographics for a customer persona."""

    values: list[str] = Field(
        default_factory=list, description="What matters most to them"
    )
    aspirations: list[str] = Field(
        default_factory=list, description="What they're working toward"
    )
    fears: list[str] = Field(
        default_factory=list, description="Pain points - what keeps them up at night"
    )
    frustrations: list[str] = Field(
        default_factory=list, description="What annoys them about current solutions"
    )
    identity: str | None = Field(None, description="How they see themselves")

    model_config = ConfigDict(extra="allow")


class BehavioralInsightsSchema(BaseModel):
    """Behavioral insights for a customer persona."""

    discovery_channels: list[str] = Field(
        default_factory=list,
        description="How they discover products (social, search, word of mouth)",
    )
    research_behavior: str | None = Field(
        None, description="How they research before buying"
    )
    decision_factors: list[str] = Field(
        default_factory=list,
        description="Decision factors (price, quality, brand, convenience)",
    )
    buying_triggers: list[str] = Field(
        default_factory=list, description="What pushes them to finally purchase"
    )
    common_objections: list[str] = Field(
        default_factory=list, description="What makes them hesitate"
    )

    model_config = ConfigDict(extra="allow")


class CommunicationPrefsSchema(BaseModel):
    """Communication preferences for a customer persona."""

    preferred_tone: str | None = Field(
        None, description="Tone they respond to (casual, professional, playful)"
    )
    language_style: str | None = Field(
        None, description="Language they use (jargon, plain speak, slang)"
    )
    content_consumption: list[str] = Field(
        default_factory=list,
        description="Content they consume (blogs, videos, podcasts)",
    )
    trust_signals: list[str] = Field(
        default_factory=list,
        description="Trust signals they need (reviews, certifications, guarantees)",
    )

    model_config = ConfigDict(extra="allow")


class PersonaSchema(BaseModel):
    """A single customer persona."""

    name: str = Field(..., description="Persona name (e.g., 'Studio Pro Sarah')")
    summary: str | None = Field(
        None, description="One paragraph describing this persona as a real person"
    )
    is_primary: bool = Field(
        default=False, description="Whether this is the primary persona"
    )
    demographics: DemographicsSchema = Field(default_factory=DemographicsSchema)
    psychographics: PsychographicsSchema = Field(default_factory=PsychographicsSchema)
    behavioral: BehavioralInsightsSchema = Field(
        default_factory=BehavioralInsightsSchema
    )
    communication: CommunicationPrefsSchema = Field(
        default_factory=CommunicationPrefsSchema
    )

    model_config = ConfigDict(extra="allow")


class PersonasSchema(BaseModel):
    """Section 2: Target Audience & Customer Personas."""

    personas: list[PersonaSchema] = Field(
        default_factory=list, description="List of customer personas"
    )

    model_config = ConfigDict(extra="allow")

    @property
    def primary_persona(self) -> PersonaSchema | None:
        """Get the primary persona if one exists."""
        for persona in self.personas:
            if persona.is_primary:
                return persona
        return self.personas[0] if self.personas else None


# =============================================================================
# SECTION 3: VOICE DIMENSIONS
# =============================================================================


class VoiceDimensionSchema(BaseModel):
    """A single voice dimension on a 1-10 scale."""

    value: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Position on 1-10 scale",
    )
    description: str | None = Field(
        None, description="How this manifests in actual writing"
    )
    example: str | None = Field(None, description="Sample sentence at this level")
    low_label: str | None = Field(
        None, description="What 1 means (e.g., 'Very Casual')"
    )
    high_label: str | None = Field(
        None, description="What 10 means (e.g., 'Very Formal')"
    )

    model_config = ConfigDict(extra="allow")


class VoiceDimensionsSchema(BaseModel):
    """Section 3: Voice Dimensions - 4 spectrums that define brand voice."""

    formality: VoiceDimensionSchema = Field(
        default_factory=lambda: VoiceDimensionSchema(
            low_label="Very Casual",
            high_label="Very Formal",
        ),
        description="Casual (1) to Formal (10)",
    )
    humor: VoiceDimensionSchema = Field(
        default_factory=lambda: VoiceDimensionSchema(
            low_label="Playful/Funny",
            high_label="Very Serious",
        ),
        description="Funny/Playful (1) to Serious (10)",
    )
    reverence: VoiceDimensionSchema = Field(
        default_factory=lambda: VoiceDimensionSchema(
            low_label="Irreverent/Edgy",
            high_label="Highly Respectful",
        ),
        description="Irreverent (1) to Respectful (10)",
    )
    enthusiasm: VoiceDimensionSchema = Field(
        default_factory=lambda: VoiceDimensionSchema(
            low_label="Very Enthusiastic",
            high_label="Matter-of-Fact",
        ),
        description="Enthusiastic (1) to Matter-of-Fact (10)",
    )
    summary: str | None = Field(
        None, description="2-3 sentence summary of overall voice"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 4: VOICE CHARACTERISTICS
# =============================================================================


class VoiceCharacteristicSchema(BaseModel):
    """A single voice characteristic (we are / we are not)."""

    trait: str = Field(
        ..., description="The characteristic trait (e.g., 'Knowledgeable')"
    )
    description: str | None = Field(None, description="What this means for writing")
    do_example: str | None = Field(None, description="Example of correct usage (DO)")
    dont_example: str | None = Field(
        None, description="Example of incorrect usage (DON'T)"
    )

    model_config = ConfigDict(extra="allow")


class VoiceCharacteristicsSchema(BaseModel):
    """Section 4: Voice Characteristics - We are / We are not traits."""

    we_are: list[VoiceCharacteristicSchema] = Field(
        default_factory=list, description="Characteristics that define our voice"
    )
    we_are_not: list[VoiceCharacteristicSchema] = Field(
        default_factory=list, description="Characteristics we explicitly avoid"
    )
    signature_phrases: list[str] = Field(
        default_factory=list, description="Phrases that capture our voice"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 5: WRITING RULES
# =============================================================================


class SentenceRulesSchema(BaseModel):
    """Sentence and paragraph structure rules."""

    avg_sentence_length: str | None = Field(
        None, description="Average sentence length guideline (e.g., '12-18 words')"
    )
    max_paragraph_sentences: int | None = Field(
        None, description="Maximum sentences per paragraph"
    )
    use_contractions: bool | None = Field(
        None, description="Whether to use contractions"
    )
    active_voice_percentage: int | None = Field(
        None, ge=0, le=100, description="Target percentage of active voice"
    )

    model_config = ConfigDict(extra="allow")


class CapitalizationRulesSchema(BaseModel):
    """Capitalization rules."""

    headlines: str | None = Field(
        None, description="Headlines format (Title Case / Sentence case)"
    )
    product_names: str | None = Field(
        None, description="How to capitalize product names"
    )
    feature_names: str | None = Field(
        None, description="How to capitalize feature names"
    )

    model_config = ConfigDict(extra="allow")


class PunctuationRulesSchema(BaseModel):
    """Punctuation rules."""

    serial_comma: bool | None = Field(None, description="Whether to use Oxford comma")
    em_dashes: str | None = Field(
        None, description="Em dash usage (Use / Avoid / When to use)"
    )
    exclamation_limit: int | None = Field(
        None, description="Max exclamation points per page"
    )
    ellipses: str | None = Field(None, description="Ellipsis usage (Use / Avoid)")

    model_config = ConfigDict(extra="allow")


class NumbersRulesSchema(BaseModel):
    """Number formatting rules."""

    spell_out_threshold: int | None = Field(
        None, description="Spell out numbers below this (e.g., 10)"
    )
    currency_format: str | None = Field(
        None, description="Currency format (e.g., '$XX' vs 'XX dollars')"
    )
    percentage_format: str | None = Field(
        None, description="Percentage format (e.g., '50%' vs '50 percent')"
    )

    model_config = ConfigDict(extra="allow")


class FormattingRulesSchema(BaseModel):
    """Text formatting rules."""

    bold_usage: str | None = Field(None, description="When to use bold")
    italics_usage: str | None = Field(None, description="When to use italics")
    bullet_points: str | None = Field(
        None, description="When to use bullets, max length"
    )
    header_max_words: int | None = Field(None, description="Max words in headers")

    model_config = ConfigDict(extra="allow")


class WritingRulesSchema(BaseModel):
    """Section 5: Writing Style Rules."""

    sentence_structure: SentenceRulesSchema = Field(default_factory=SentenceRulesSchema)
    capitalization: CapitalizationRulesSchema = Field(
        default_factory=CapitalizationRulesSchema
    )
    punctuation: PunctuationRulesSchema = Field(default_factory=PunctuationRulesSchema)
    numbers: NumbersRulesSchema = Field(default_factory=NumbersRulesSchema)
    formatting: FormattingRulesSchema = Field(default_factory=FormattingRulesSchema)

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 6: VOCABULARY
# =============================================================================


class PreferredTermSchema(BaseModel):
    """A preferred term mapping (instead of X, we say Y)."""

    instead_of: str = Field(..., description="The term to avoid")
    we_say: str = Field(..., description="The preferred alternative")

    model_config = ConfigDict(extra="allow")


class IndustryTermSchema(BaseModel):
    """An industry-specific term with usage guidance."""

    term: str = Field(..., description="The industry term")
    definition: str | None = Field(None, description="Definition or explanation")
    usage: str | None = Field(None, description="Usage guidance")

    model_config = ConfigDict(extra="allow")


class VocabularySchema(BaseModel):
    """Section 6: Vocabulary & Language."""

    power_words: list[str] = Field(
        default_factory=list,
        description="Words that align with brand voice and resonate with audience",
    )
    banned_words: list[str] = Field(
        default_factory=list,
        description="Words that feel off-brand, too generic, or AI-like",
    )
    preferred_terms: list[PreferredTermSchema] = Field(
        default_factory=list, description="Instead of X, we say Y"
    )
    industry_terms: list[IndustryTermSchema] = Field(
        default_factory=list, description="Industry-specific terminology"
    )
    brand_specific_terms: list[IndustryTermSchema] = Field(
        default_factory=list, description="Proprietary names and trademarked features"
    )
    shopify_placeholder_tag: str = Field(
        default="",
        description="Placeholder Shopify product tag used as the Rule: Condition in Matrixify exports. Set to a real tag from the store.",
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 7: PROOF ELEMENTS
# =============================================================================


class StatisticSchema(BaseModel):
    """A proof statistic."""

    stat: str = Field(..., description="The statistic (e.g., '47,000+ customers')")
    context: str | None = Field(None, description="Context or source for the stat")

    model_config = ConfigDict(extra="allow")


class CustomerQuoteSchema(BaseModel):
    """A customer testimonial quote."""

    quote: str = Field(..., description="The customer quote")
    attribution: str | None = Field(
        None, description="Attribution (e.g., 'Mike R., verified buyer')"
    )

    model_config = ConfigDict(extra="allow")


class ProofElementsSchema(BaseModel):
    """Section 7: Proof & Trust Elements."""

    statistics: list[StatisticSchema] = Field(
        default_factory=list, description="Hard numbers and metrics"
    )
    credentials: list[str] = Field(
        default_factory=list, description="Certifications, awards, memberships"
    )
    customer_quotes: list[CustomerQuoteSchema] = Field(
        default_factory=list, description="Customer testimonials"
    )
    guarantees: list[str] = Field(
        default_factory=list, description="Warranties, return policies, promises"
    )
    media_mentions: list[str] = Field(
        default_factory=list, description="Press and media coverage"
    )
    partnerships: list[str] = Field(
        default_factory=list, description="Notable partnerships or endorsements"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 8: EXAMPLES BANK
# =============================================================================


class ExamplePairSchema(BaseModel):
    """A good/bad example pair."""

    good: str = Field(..., description="Example of correct usage")
    bad: str | None = Field(None, description="Example of incorrect usage")
    explanation: str | None = Field(
        None, description="Why the good example works / bad doesn't"
    )

    model_config = ConfigDict(extra="allow")


class ContentExamplesSchema(BaseModel):
    """Examples for a specific content type."""

    content_type: str = Field(
        ..., description="Type of content (headlines, descriptions, CTAs, etc.)"
    )
    examples: list[ExamplePairSchema] = Field(
        default_factory=list, description="Good/bad example pairs"
    )

    model_config = ConfigDict(extra="allow")


class ExamplesBankSchema(BaseModel):
    """Section 8: Examples Bank."""

    headlines: list[ExamplePairSchema] = Field(
        default_factory=list, description="Headline examples"
    )
    product_descriptions: list[ExamplePairSchema] = Field(
        default_factory=list, description="Product description examples"
    )
    ctas: list[ExamplePairSchema] = Field(
        default_factory=list, description="Call-to-action examples"
    )
    email_subject_lines: list[ExamplePairSchema] = Field(
        default_factory=list, description="Email subject line examples"
    )
    social_posts: list[ExamplePairSchema] = Field(
        default_factory=list, description="Social media post examples"
    )
    additional: list[ContentExamplesSchema] = Field(
        default_factory=list, description="Additional content type examples"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 9: COMPETITOR CONTEXT
# =============================================================================


class CompetitorSchema(BaseModel):
    """A single competitor entry."""

    name: str = Field(..., description="Competitor name")
    positioning: str | None = Field(None, description="How they position themselves")
    our_difference: str | None = Field(
        None, description="How we differentiate from them"
    )

    model_config = ConfigDict(extra="allow")


class CompetitorContextSchema(BaseModel):
    """Section 9: Competitor Context."""

    competitors: list[CompetitorSchema] = Field(
        default_factory=list, description="Direct competitors"
    )
    competitive_advantages: list[str] = Field(
        default_factory=list, description="What we do better"
    )
    competitive_weaknesses: list[str] = Field(
        default_factory=list, description="Where we lag (internal only)"
    )
    positioning_statements: dict[str, str] = Field(
        default_factory=dict,
        description="Positioning statements by context (e.g., 'vs_premium', 'vs_budget')",
    )
    competitor_reference_rules: str | None = Field(
        None, description="Rules for mentioning competitors in copy"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 10: AI PROMPTS
# =============================================================================


class AIPromptSchema(BaseModel):
    """An AI prompt snippet for a specific use case."""

    use_case: str = Field(
        ..., description="Use case (product_description, email, social, etc.)"
    )
    prompt: str = Field(..., description="The prompt snippet to use before AI requests")

    model_config = ConfigDict(extra="allow")


class AIPromptsSchema(BaseModel):
    """Section 10: AI Prompt Snippets."""

    general: str | None = Field(
        None, description="General prompt snippet for any AI writing"
    )
    by_use_case: list[AIPromptSchema] = Field(
        default_factory=list, description="Use-case-specific prompt snippets"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# SECTION 11: QUICK REFERENCE
# =============================================================================


class QuickReferenceSchema(BaseModel):
    """Section 11: Quick Reference Card."""

    voice_in_three_words: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Voice in 3 words (e.g., ['Knowledgeable', 'Supportive', 'Direct'])",
    )
    we_sound_like: str | None = Field(
        None, description="1-sentence description of our voice"
    )
    we_never_sound_like: str | None = Field(
        None, description="1-sentence description of what we avoid"
    )
    primary_audience: str | None = Field(None, description="Primary audience summary")
    key_differentiator: str | None = Field(
        None, description="The #1 thing that makes us different"
    )
    default_cta: str | None = Field(None, description="Default call-to-action to use")
    avoid_list: list[str] = Field(
        default_factory=list, description="Top things to avoid (quick reference)"
    )

    model_config = ConfigDict(extra="allow")


# =============================================================================
# ROOT V3 SCHEMA
# =============================================================================


class V3BrandConfigSchema(BaseModel):
    """Complete V3 Brand Configuration Schema.

    This is the comprehensive brand configuration following the 11-part
    Brand Guidelines Bible framework.
    """

    # Version and metadata
    _version: Literal["3.0"] = Field(
        default="3.0",
        alias="_version",
        description="Schema version marker",
    )
    _generated_at: datetime | None = Field(
        default=None,
        alias="_generated_at",
        description="When this config was generated",
    )
    _sources_used: list[str] = Field(
        default_factory=list,
        alias="_sources_used",
        description="Sources used to generate this config",
    )

    # The 11 sections
    foundation: FoundationSchema = Field(
        default_factory=FoundationSchema,
        description="Section 1: Brand Foundation",
    )
    personas: PersonasSchema = Field(
        default_factory=PersonasSchema,
        description="Section 2: Target Audience & Customer Personas",
    )
    voice_dimensions: VoiceDimensionsSchema = Field(
        default_factory=VoiceDimensionsSchema,
        description="Section 3: Voice Dimensions (4 sliders)",
    )
    voice_characteristics: VoiceCharacteristicsSchema = Field(
        default_factory=VoiceCharacteristicsSchema,
        description="Section 4: Voice Characteristics (We are / We are not)",
    )
    writing_rules: WritingRulesSchema = Field(
        default_factory=WritingRulesSchema,
        description="Section 5: Writing Style Rules",
    )
    vocabulary: VocabularySchema = Field(
        default_factory=VocabularySchema,
        description="Section 6: Vocabulary & Language",
    )
    proof_elements: ProofElementsSchema = Field(
        default_factory=ProofElementsSchema,
        description="Section 7: Proof & Trust Elements",
    )
    examples_bank: ExamplesBankSchema = Field(
        default_factory=ExamplesBankSchema,
        description="Section 8: Examples Bank",
    )
    competitor_context: CompetitorContextSchema = Field(
        default_factory=CompetitorContextSchema,
        description="Section 9: Competitor Context",
    )
    ai_prompts: AIPromptsSchema = Field(
        default_factory=AIPromptsSchema,
        description="Section 10: AI Prompt Snippets",
    )
    quick_reference: QuickReferenceSchema = Field(
        default_factory=QuickReferenceSchema,
        description="Section 11: Quick Reference Card",
    )

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,  # Allow both _version and version as field names
    )


# =============================================================================
# VERSION DETECTION HELPERS
# =============================================================================


def is_v3_config(config: dict[str, Any]) -> bool:
    """Check if a config dict is a V3 schema.

    V3 configs have _version: "3.0" and the 11-section structure.
    """
    version = config.get("_version")
    if version == "3.0":
        return True
    # Also check for the v3-specific sections
    v3_sections = {"voice_dimensions", "voice_characteristics", "proof_elements"}
    return bool(v3_sections.intersection(config.keys()))


def is_v2_config(config: dict[str, Any]) -> bool:
    """Check if a config dict is a V2 schema.

    V2 configs have version: "2.0" (or no version) and the colors/typography structure.
    """
    version = config.get("version") or config.get("_version")
    if version == "3.0":
        return False
    # V2 has these specific sections
    v2_sections = {"colors", "typography", "logo", "voice", "social"}
    return bool(v2_sections.intersection(config.keys()))


def get_config_version(config: dict[str, Any]) -> str:
    """Get the version of a brand config.

    Returns "3.0", "2.0", or "unknown".
    """
    if is_v3_config(config):
        return "3.0"
    if is_v2_config(config):
        return "2.0"
    return "unknown"
