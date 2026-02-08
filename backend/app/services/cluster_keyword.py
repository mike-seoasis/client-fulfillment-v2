"""Cluster keyword service for generating keyword clusters with brand context.

This service orchestrates keyword cluster generation by:
1. Building brand-aware context from BrandConfig v2_schema
2. Using Claude for cluster generation (Stages 1-3)
3. Using DataForSEO for search volume enrichment
"""

from typing import Any

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient
from app.integrations.dataforseo import DataForSEOClient

logger = get_logger(__name__)


class ClusterKeywordService:
    """Service for generating keyword clusters with brand context.

    Orchestrates cluster generation using:
    - Claude for intelligent cluster and page generation
    - DataForSEO for search volume enrichment
    - Brand config context for brand-aware prompts
    """

    def __init__(
        self,
        claude_client: ClaudeClient,
        dataforseo_client: DataForSEOClient,
    ) -> None:
        """Initialize the cluster keyword service.

        Args:
            claude_client: ClaudeClient for LLM cluster generation.
            dataforseo_client: DataForSEOClient for search volume data.
        """
        self._claude = claude_client
        self._dataforseo = dataforseo_client

        logger.info(
            "ClusterKeywordService initialized",
            extra={
                "claude_available": claude_client.available,
                "dataforseo_available": dataforseo_client.available,
            },
        )

    @staticmethod
    def _build_brand_context(brand_config: dict[str, Any]) -> str:
        """Build a brand context string from v2_schema for prompt injection.

        Extracts key brand information from the v2_schema JSON structure
        to provide relevant context for cluster generation prompts.

        Sections extracted:
        - brand_foundation: company name, primary products, price point, sales channels
        - target_audience: primary persona name and summary
        - competitor_context: competitor names

        Missing or incomplete sections are silently skipped.

        Args:
            brand_config: The v2_schema dict from BrandConfig model.

        Returns:
            Formatted string suitable for prompt injection. Returns empty
            string if no usable data is found.
        """
        parts: list[str] = []

        # Brand foundation
        brand_foundation = brand_config.get("brand_foundation")
        if isinstance(brand_foundation, dict):
            foundation_parts: list[str] = []

            company_overview = brand_foundation.get("company_overview")
            if isinstance(company_overview, dict):
                company_name = company_overview.get("company_name")
                if company_name:
                    foundation_parts.append(f"Company: {company_name}")

            what_they_sell = brand_foundation.get("what_they_sell")
            if isinstance(what_they_sell, dict):
                primary_products = what_they_sell.get("primary_products_services")
                if primary_products:
                    foundation_parts.append(f"Primary Products: {primary_products}")

                price_point = what_they_sell.get("price_point")
                if price_point:
                    foundation_parts.append(f"Price Point: {price_point}")

                sales_channels = what_they_sell.get("sales_channels")
                if sales_channels:
                    foundation_parts.append(f"Sales Channels: {sales_channels}")

            if foundation_parts:
                parts.append("## Brand\n" + "\n".join(foundation_parts))

        # Target audience — primary persona
        target_audience = brand_config.get("target_audience")
        if isinstance(target_audience, dict):
            personas = target_audience.get("personas")
            if isinstance(personas, list) and len(personas) > 0:
                primary_persona = personas[0]
                if isinstance(primary_persona, dict):
                    persona_parts: list[str] = []

                    persona_name = primary_persona.get("name")
                    if persona_name:
                        persona_parts.append(f"Primary Persona: {persona_name}")

                    summary = primary_persona.get("summary")
                    if summary:
                        persona_parts.append(f"Summary: {summary}")

                    if persona_parts:
                        parts.append(
                            "## Target Audience\n" + "\n".join(persona_parts)
                        )

        # Competitor context — competitor names
        competitor_context = brand_config.get("competitor_context")
        if isinstance(competitor_context, dict):
            direct_competitors = competitor_context.get("direct_competitors")
            if isinstance(direct_competitors, list) and len(direct_competitors) > 0:
                names: list[str] = []
                for comp in direct_competitors:
                    if isinstance(comp, dict):
                        name = comp.get("name")
                        if name:
                            names.append(name)
                if names:
                    parts.append("## Competitors\n" + ", ".join(names))

        return "\n\n".join(parts)
