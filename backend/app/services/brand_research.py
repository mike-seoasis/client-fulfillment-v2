"""Brand Research Service - Perplexity→Claude synthesis pipeline.

Two-stage pipeline for brand research:
1. Perplexity researches the brand from their website URL
2. Claude synthesizes the research into V3 brand config schema

Features:
- Caching (24hr TTL) via BrandResearchCacheService
- Rate limiting (5/hr/project)
- Cache bypass for force refresh
- Graceful fallback when services unavailable
"""

import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import get_claude
from app.integrations.perplexity import get_perplexity
from app.schemas.brand_config_v3 import V3BrandConfigSchema, V3_SCHEMA_VERSION
from app.services.brand_research_cache import (
    BrandResearchCacheResult,
    RateLimitResult,
    get_brand_research_cache_service,
)

logger = get_logger(__name__)


# Claude prompt for synthesizing research into V3 schema
V3_SYNTHESIS_SYSTEM_PROMPT = """You are a brand strategist AI. Your task is to synthesize brand research into a structured V3 brand configuration schema.

You will receive research about a brand from their website and online presence. Transform this into a comprehensive brand configuration following the 11-part Brand Guidelines Bible framework.

## Output Format

Return a valid JSON object with this exact structure. Use null for any fields where data is not available.

```json
{
  "_version": "3.0",
  "_generated_at": "<ISO timestamp>",
  "_sources_used": ["<list of sources>"],

  "foundation": {
    "company_overview": {
      "name": "<company name>",
      "founded": "<year or null>",
      "location": "<HQ location or null>",
      "industry": "<industry>",
      "business_model": "<B2B/B2C/DTC/etc.>"
    },
    "products_services": {
      "primary": ["<main offerings>"],
      "secondary": ["<supporting offerings>"],
      "price_point": "<Budget/Mid-range/Premium/Luxury>",
      "sales_channels": ["<channels>"]
    },
    "positioning": {
      "tagline": "<tagline or null>",
      "one_sentence": "<one-sentence description>",
      "category_position": "<Leader/Challenger/Specialist/Disruptor>"
    },
    "mission_values": {
      "mission_statement": "<mission or null>",
      "core_values": ["<values>"],
      "brand_promise": "<promise or null>"
    },
    "differentiators": {
      "primary_usp": "<main differentiator>",
      "supporting": ["<other differentiators>"],
      "what_we_are_not": ["<what they reject>"]
    }
  },

  "personas": {
    "personas": [
      {
        "name": "<persona name>",
        "summary": "<one paragraph description>",
        "is_primary": true,
        "demographics": {
          "age_range": "<range>",
          "gender": "<if relevant>",
          "location": "<geographic focus>",
          "income_level": "<range>",
          "profession": "<profession>",
          "education": "<if relevant>"
        },
        "psychographics": {
          "values": ["<values>"],
          "aspirations": ["<aspirations>"],
          "fears": ["<pain points>"],
          "frustrations": ["<frustrations>"],
          "identity": "<how they see themselves>"
        },
        "behavioral": {
          "discovery_channels": ["<channels>"],
          "research_behavior": "<how they research>",
          "decision_factors": ["<factors>"],
          "buying_triggers": ["<triggers>"],
          "common_objections": ["<objections>"]
        },
        "communication": {
          "preferred_tone": "<tone>",
          "language_style": "<style>",
          "content_consumption": ["<content types>"],
          "trust_signals": ["<trust signals needed>"]
        }
      }
    ]
  },

  "voice_dimensions": {
    "formality": {
      "value": 5,
      "description": "<how this manifests>",
      "example": "<sample sentence>",
      "low_label": "Very Casual",
      "high_label": "Very Formal"
    },
    "humor": {
      "value": 5,
      "description": "<how this manifests>",
      "example": "<sample sentence>",
      "low_label": "Playful/Funny",
      "high_label": "Very Serious"
    },
    "reverence": {
      "value": 5,
      "description": "<how this manifests>",
      "example": "<sample sentence>",
      "low_label": "Irreverent/Edgy",
      "high_label": "Highly Respectful"
    },
    "enthusiasm": {
      "value": 5,
      "description": "<how this manifests>",
      "example": "<sample sentence>",
      "low_label": "Very Enthusiastic",
      "high_label": "Matter-of-Fact"
    },
    "summary": "<2-3 sentence voice summary>"
  },

  "voice_characteristics": {
    "we_are": [
      {
        "trait": "<trait>",
        "description": "<what this means>",
        "do_example": "<DO example>",
        "dont_example": "<DON'T example>"
      }
    ],
    "we_are_not": [
      {
        "trait": "<trait>",
        "description": "<what to avoid>",
        "do_example": null,
        "dont_example": "<example of what to avoid>"
      }
    ],
    "signature_phrases": ["<phrases that capture the voice>"]
  },

  "writing_rules": {
    "sentence_structure": {
      "avg_sentence_length": "<e.g., 12-18 words>",
      "max_paragraph_sentences": 4,
      "use_contractions": true,
      "active_voice_percentage": 90
    },
    "capitalization": {
      "headlines": "Title Case",
      "product_names": "<guidance>",
      "feature_names": "<guidance>"
    },
    "punctuation": {
      "serial_comma": true,
      "em_dashes": "<Use/Avoid/guidance>",
      "exclamation_limit": 1,
      "ellipses": "Avoid"
    },
    "numbers": {
      "spell_out_threshold": 10,
      "currency_format": "$XX",
      "percentage_format": "50%"
    },
    "formatting": {
      "bold_usage": "<guidance>",
      "italics_usage": "<guidance>",
      "bullet_points": "<guidance>",
      "header_max_words": 7
    }
  },

  "vocabulary": {
    "power_words": ["<on-brand words>"],
    "banned_words": ["<off-brand words>"],
    "preferred_terms": [
      {"instead_of": "<avoid>", "we_say": "<prefer>"}
    ],
    "industry_terms": [
      {"term": "<term>", "definition": "<definition>", "usage": "<usage>"}
    ],
    "brand_specific_terms": []
  },

  "proof_elements": {
    "statistics": [
      {"stat": "<statistic>", "context": "<context>"}
    ],
    "credentials": ["<certifications, awards>"],
    "customer_quotes": [
      {"quote": "<quote>", "attribution": "<attribution>"}
    ],
    "guarantees": ["<warranties, policies>"],
    "media_mentions": ["<press mentions>"],
    "partnerships": ["<partnerships>"]
  },

  "examples_bank": {
    "headlines": [
      {"good": "<on-brand headline>", "bad": "<off-brand version>", "explanation": "<why>"}
    ],
    "product_descriptions": [],
    "ctas": [
      {"good": "<on-brand CTA>", "bad": null, "explanation": null}
    ],
    "email_subject_lines": [],
    "social_posts": [],
    "additional": []
  },

  "competitor_context": {
    "competitors": [
      {"name": "<competitor>", "positioning": "<their position>", "our_difference": "<differentiation>"}
    ],
    "competitive_advantages": ["<advantages>"],
    "competitive_weaknesses": [],
    "positioning_statements": {},
    "competitor_reference_rules": "Never mention competitors by name in customer-facing copy"
  },

  "ai_prompts": {
    "general": "<general prompt snippet for AI writing>",
    "by_use_case": []
  },

  "quick_reference": {
    "voice_in_three_words": ["<word1>", "<word2>", "<word3>"],
    "we_sound_like": "<1-sentence description>",
    "we_never_sound_like": "<1-sentence anti-description>",
    "primary_audience": "<primary audience summary>",
    "key_differentiator": "<#1 differentiator>",
    "default_cta": "<default CTA>",
    "avoid_list": ["<top things to avoid>"]
  }
}
```

## Guidelines

1. Fill in as much as possible from the research. Use null for truly unknown fields.
2. Make reasonable inferences based on available data, but don't invent facts.
3. For voice dimensions, analyze the brand's existing content to determine appropriate 1-10 values.
4. Include examples where the research provides them.
5. The quick_reference should summarize the most important points.
6. Return ONLY the JSON object, no markdown code blocks or explanatory text."""


@dataclass
class BrandResearchServiceResult:
    """Result of a brand research operation."""

    success: bool
    project_id: str
    domain: str
    v3_config: V3BrandConfigSchema | None = None
    raw_research: str | None = None
    citations: list[str] = field(default_factory=list)
    from_cache: bool = False
    cached_at: datetime | None = None
    error: str | None = None
    duration_ms: float = 0.0
    perplexity_tokens: dict[str, int | None] = field(default_factory=dict)
    claude_tokens: dict[str, int | None] = field(default_factory=dict)


@dataclass
class ResearchOnlyResult:
    """Result of research-only operation (no synthesis)."""

    success: bool
    project_id: str
    domain: str
    raw_research: str | None = None
    citations: list[str] = field(default_factory=list)
    from_cache: bool = False
    cached_at: datetime | None = None
    error: str | None = None
    rate_limit: RateLimitResult | None = None
    duration_ms: float = 0.0


class BrandResearchService:
    """Service for researching brands and synthesizing into V3 config.

    Two-stage pipeline:
    1. research_brand() - Call Perplexity to research the brand
    2. synthesize_to_v3() - Call Claude to structure into V3 schema
    3. research_and_synthesize() - Combined operation
    """

    def __init__(self) -> None:
        """Initialize the brand research service."""
        self._cache = get_brand_research_cache_service()
        logger.info("BrandResearchService initialized")

    async def check_rate_limit(self, project_id: str) -> RateLimitResult:
        """Check rate limit for a project.

        Args:
            project_id: The project ID

        Returns:
            RateLimitResult with allowed status and remaining requests
        """
        return await self._cache.check_rate_limit(project_id)

    async def research_brand(
        self,
        project_id: str,
        domain: str,
        brand_name: str | None = None,
        force_refresh: bool = False,
    ) -> ResearchOnlyResult:
        """Research a brand using Perplexity (stage 1 only).

        This method performs only the Perplexity research, without Claude synthesis.
        Useful for getting raw research data that can be edited before synthesis.

        Args:
            project_id: Project ID for rate limiting and caching
            domain: Website domain to research
            brand_name: Optional brand name
            force_refresh: Bypass cache and force new research

        Returns:
            ResearchOnlyResult with raw research text and citations
        """
        start_time = time.monotonic()

        logger.info(
            "Starting brand research (stage 1)",
            extra={
                "project_id": project_id,
                "domain": domain,
                "brand_name": brand_name,
                "force_refresh": force_refresh,
            },
        )

        # Check cache first (unless force refresh)
        if not force_refresh:
            cache_result = await self._cache.get(project_id, domain)
            if cache_result.cache_hit and cache_result.data:
                logger.info(
                    "Brand research cache hit",
                    extra={"project_id": project_id, "domain": domain},
                )
                return ResearchOnlyResult(
                    success=True,
                    project_id=project_id,
                    domain=domain,
                    raw_research=cache_result.data.raw_text,
                    citations=cache_result.data.citations,
                    from_cache=True,
                    cached_at=cache_result.cached_at,
                    duration_ms=(time.monotonic() - start_time) * 1000,
                )

        # Check rate limit
        rate_limit = await self._cache.check_rate_limit(project_id)
        if not rate_limit.allowed:
            logger.warning(
                "Brand research rate limited",
                extra={
                    "project_id": project_id,
                    "requests_used": rate_limit.requests_used,
                    "reset_at": rate_limit.reset_at,
                },
            )
            return ResearchOnlyResult(
                success=False,
                project_id=project_id,
                domain=domain,
                error=f"Rate limit exceeded. {rate_limit.requests_used}/{5} requests used. "
                f"Resets at {rate_limit.reset_at.isoformat() if rate_limit.reset_at else 'unknown'}",
                rate_limit=rate_limit,
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        # Delete cache entry if force refresh
        if force_refresh:
            await self._cache.delete(project_id, domain)

        # Get Perplexity client
        perplexity = await get_perplexity()
        if not perplexity.available:
            logger.warning(
                "Perplexity not available for brand research",
                extra={"project_id": project_id, "domain": domain},
            )
            return ResearchOnlyResult(
                success=False,
                project_id=project_id,
                domain=domain,
                error="Perplexity API not configured. Manual brand entry required.",
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        # Call Perplexity research
        research_result = await perplexity.research_brand(domain, brand_name)

        if not research_result.success:
            logger.error(
                "Perplexity brand research failed",
                extra={
                    "project_id": project_id,
                    "domain": domain,
                    "error": research_result.error,
                },
            )
            return ResearchOnlyResult(
                success=False,
                project_id=project_id,
                domain=domain,
                error=f"Research failed: {research_result.error}",
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        # Increment rate limit counter
        await self._cache.increment_rate_limit(project_id)

        # Cache the research result
        await self._cache.set(
            project_id=project_id,
            domain=domain,
            raw_text=research_result.raw_text,
            citations=research_result.citations,
        )

        total_duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Brand research completed",
            extra={
                "project_id": project_id,
                "domain": domain,
                "duration_ms": total_duration_ms,
                "citations": len(research_result.citations),
            },
        )

        return ResearchOnlyResult(
            success=True,
            project_id=project_id,
            domain=domain,
            raw_research=research_result.raw_text,
            citations=research_result.citations,
            from_cache=False,
            rate_limit=rate_limit,
            duration_ms=total_duration_ms,
        )

    async def synthesize_to_v3(
        self,
        research_text: str,
        brand_name: str | None = None,
        domain: str | None = None,
        citations: list[str] | None = None,
    ) -> tuple[V3BrandConfigSchema | None, str | None, dict[str, int | None]]:
        """Synthesize research text into V3 brand config using Claude (stage 2).

        Args:
            research_text: Raw research text from Perplexity
            brand_name: Optional brand name for context
            domain: Optional domain for context
            citations: Optional list of citation URLs

        Returns:
            Tuple of (V3BrandConfigSchema or None, error message or None, token usage dict)
        """
        logger.info(
            "Starting V3 synthesis (stage 2)",
            extra={"brand_name": brand_name, "domain": domain},
        )

        # Get Claude client
        claude = await get_claude()
        if not claude.available:
            logger.warning("Claude not available for V3 synthesis")
            return None, "Claude API not configured. Manual V3 configuration required.", {}

        # Build user prompt
        context_parts = []
        if brand_name:
            context_parts.append(f"Brand Name: {brand_name}")
        if domain:
            context_parts.append(f"Domain: {domain}")
        if citations:
            context_parts.append(f"Sources: {', '.join(citations[:5])}")

        context_str = "\n".join(context_parts) if context_parts else ""

        user_prompt = f"""## Brand Research Data

{context_str}

## Research Findings

{research_text}

---

Transform this research into a complete V3 brand configuration JSON following the schema in your instructions. Return only valid JSON."""

        # Call Claude for synthesis
        try:
            result = await claude.complete(
                user_prompt=user_prompt,
                system_prompt=V3_SYNTHESIS_SYSTEM_PROMPT,
                max_tokens=8192,  # V3 schema can be large
                temperature=0.1,  # Low temperature for structured output
            )

            token_usage = {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            if not result.success:
                logger.error(
                    "Claude V3 synthesis failed",
                    extra={"error": result.error},
                )
                return None, f"Synthesis failed: {result.error}", token_usage

            # Parse the JSON response
            response_text = result.text or ""

            # Try to extract JSON from the response (handle potential markdown)
            json_text = response_text.strip()
            if json_text.startswith("```"):
                # Remove markdown code blocks
                lines = json_text.split("\n")
                json_lines = []
                in_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_block = not in_block
                        continue
                    if in_block or not json_text.startswith("```"):
                        json_lines.append(line)
                json_text = "\n".join(json_lines)

            try:
                config_data = json.loads(json_text)
            except json.JSONDecodeError as e:
                logger.error(
                    "Failed to parse V3 JSON from Claude",
                    extra={
                        "error": str(e),
                        "response_preview": response_text[:500],
                    },
                )
                return None, f"Failed to parse V3 JSON: {e}", token_usage

            # Add/update metadata
            config_data["_version"] = V3_SCHEMA_VERSION
            config_data["_generated_at"] = datetime.utcnow().isoformat()
            if citations:
                config_data["_sources_used"] = citations

            # Validate against schema
            try:
                v3_config = V3BrandConfigSchema.model_validate(config_data)
            except Exception as e:
                logger.error(
                    "V3 schema validation failed",
                    extra={"error": str(e)},
                )
                return None, f"Schema validation failed: {e}", token_usage

            logger.info(
                "V3 synthesis completed",
                extra={
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                },
            )

            return v3_config, None, token_usage

        except Exception as e:
            logger.error(
                "V3 synthesis error",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return None, f"Synthesis error: {e}", {}

    async def research_and_synthesize(
        self,
        project_id: str,
        domain: str,
        brand_name: str | None = None,
        force_refresh: bool = False,
    ) -> BrandResearchServiceResult:
        """Research a brand and synthesize into V3 config (both stages).

        This is the main entry point for complete brand research.

        Args:
            project_id: Project ID for rate limiting and caching
            domain: Website domain to research
            brand_name: Optional brand name
            force_refresh: Bypass cache and force new research

        Returns:
            BrandResearchServiceResult with V3 config or error
        """
        start_time = time.monotonic()

        logger.info(
            "Starting brand research and synthesis",
            extra={
                "project_id": project_id,
                "domain": domain,
                "brand_name": brand_name,
                "force_refresh": force_refresh,
            },
        )

        # Stage 1: Research
        research_result = await self.research_brand(
            project_id=project_id,
            domain=domain,
            brand_name=brand_name,
            force_refresh=force_refresh,
        )

        if not research_result.success:
            return BrandResearchServiceResult(
                success=False,
                project_id=project_id,
                domain=domain,
                error=research_result.error,
                duration_ms=(time.monotonic() - start_time) * 1000,
            )

        # Stage 2: Synthesis
        v3_config, synthesis_error, claude_tokens = await self.synthesize_to_v3(
            research_text=research_result.raw_research or "",
            brand_name=brand_name,
            domain=domain,
            citations=research_result.citations,
        )

        if synthesis_error:
            return BrandResearchServiceResult(
                success=False,
                project_id=project_id,
                domain=domain,
                raw_research=research_result.raw_research,
                citations=research_result.citations,
                from_cache=research_result.from_cache,
                cached_at=research_result.cached_at,
                error=synthesis_error,
                duration_ms=(time.monotonic() - start_time) * 1000,
                claude_tokens=claude_tokens,
            )

        total_duration_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "Brand research and synthesis completed",
            extra={
                "project_id": project_id,
                "domain": domain,
                "duration_ms": total_duration_ms,
                "from_cache": research_result.from_cache,
            },
        )

        return BrandResearchServiceResult(
            success=True,
            project_id=project_id,
            domain=domain,
            v3_config=v3_config,
            raw_research=research_result.raw_research,
            citations=research_result.citations,
            from_cache=research_result.from_cache,
            cached_at=research_result.cached_at,
            duration_ms=total_duration_ms,
            claude_tokens=claude_tokens,
        )


# Global singleton instance
_brand_research_service: BrandResearchService | None = None


def get_brand_research_service() -> BrandResearchService:
    """Get the global brand research service instance.

    Usage:
        from app.services.brand_research import get_brand_research_service
        service = get_brand_research_service()
        result = await service.research_and_synthesize("project-123", "acme.com")
    """
    global _brand_research_service
    if _brand_research_service is None:
        _brand_research_service = BrandResearchService()
    return _brand_research_service
