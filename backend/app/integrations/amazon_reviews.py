"""Amazon store auto-detection and review fetching integration.

Uses Perplexity API to search for Amazon products and extract reviews,
avoiding direct Amazon scraping which would violate ToS.

Features:
- Auto-detect Amazon store presence for a brand
- Find top products on Amazon
- Extract customer reviews and insights
- Identify common praise/complaints
- Generate customer personas from review data

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second

RAILWAY DEPLOYMENT REQUIREMENTS:
- API base URL from environment variable (uses Perplexity settings)
- Handle API errors gracefully (show user-friendly messages)
- Implement retry logic for transient failures (via Perplexity client)
- Support both HTTP and HTTPS (Railway provides SSL)
"""

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.integrations.perplexity import PerplexityClient, get_perplexity

logger = get_logger(__name__)


@dataclass
class AmazonProduct:
    """An Amazon product found for a brand."""

    title: str
    asin: str | None = None
    url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    price: str | None = None


@dataclass
class AmazonReview:
    """A customer review from Amazon."""

    text: str
    rating: int  # 1-5
    title: str | None = None
    verified_purchase: bool = True
    helpful_votes: int = 0


@dataclass
class ReviewInsights:
    """Insights extracted from product reviews."""

    common_praise: list[str] = field(default_factory=list)
    common_complaints: list[str] = field(default_factory=list)
    best_quotes: list[dict[str, Any]] = field(default_factory=list)
    customer_types: list[str] = field(default_factory=list)
    product_strengths: list[str] = field(default_factory=list)
    average_sentiment: str = "neutral"


@dataclass
class AmazonStoreDetectionResult:
    """Result of Amazon store detection."""

    success: bool
    brand_name: str
    has_amazon_store: bool = False
    store_url: str | None = None
    products: list[AmazonProduct] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class FallbackPersona:
    """A customer persona generated from website analysis (fallback).

    Used when no reviews are available to generate personas from
    website content analysis via Perplexity.
    """

    name: str
    description: str
    source: str = "website_analysis"
    inferred: bool = True
    characteristics: list[str] = field(default_factory=list)


@dataclass
class AmazonReviewAnalysisResult:
    """Result of Amazon review analysis."""

    success: bool
    brand_name: str
    products_analyzed: int = 0
    reviews: list[AmazonReview] = field(default_factory=list)
    insights: ReviewInsights | None = None
    common_praise: list[str] = field(default_factory=list)
    common_complaints: list[str] = field(default_factory=list)
    customer_personas: list[dict[str, Any]] = field(default_factory=list)
    proof_stats: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    analyzed_at: str = ""
    # Fallback-related fields
    needs_review: bool = False
    fallback_used: bool = False
    fallback_source: str | None = None


# Prompts for Perplexity queries
AMAZON_STORE_DETECTION_PROMPT = """Search Amazon.com for products sold by or branded as "{brand_name}"{category_hint}.

Find their top 3-5 products that have customer reviews.

For each product found, provide:
1. Product title
2. ASIN (Amazon product ID) if visible
3. Approximate rating (e.g., 4.5 out of 5)
4. Approximate number of reviews
5. Price if visible

Format as JSON array:
```json
[
  {{
    "title": "Product Name",
    "asin": "B0XXXXXXXX",
    "rating": 4.5,
    "review_count": 1234,
    "price": "$29.99"
  }}
]
```

If no products are found for this brand on Amazon, return an empty array: []

Return ONLY the JSON, no explanation."""

REVIEW_ANALYSIS_PROMPT = """Analyze Amazon customer reviews for "{product_title}" by {brand_name}.

Look at both positive and negative reviews to understand:
1. What customers love about this product (common praise)
2. What customers complain about (common issues)
3. Key quotes that would make good testimonials
4. What type of customer buys this (persona hints)

Format as JSON:
```json
{{
  "common_praise": ["specific praise point 1", "specific praise point 2"],
  "common_complaints": ["specific complaint 1", "specific complaint 2"],
  "best_quotes": [
    {{"text": "Actual customer quote", "rating": 5, "context": "what they were praising"}},
    {{"text": "Another quote", "rating": 4, "context": "context"}}
  ],
  "customer_types": ["type of customer 1", "type of customer 2"],
  "product_strengths": ["strength 1", "strength 2"],
  "average_sentiment": "positive/mixed/negative"
}}
```

Return ONLY the JSON."""

FALLBACK_PERSONA_PROMPT = """Analyze the brand "{brand_name}" (website: {website_url}) and infer the likely customer personas based on the brand's positioning, products, and target market.

Since we don't have customer reviews to analyze, generate 2-3 customer personas based on:
1. The type of products/services the brand offers
2. The brand's positioning and messaging
3. Typical buyers for this product category
4. Price point and quality signals

For each persona, provide:
- A descriptive name (e.g., "Budget-Conscious Parent", "Professional Chef")
- A brief description of who they are
- Key characteristics that define their buying behavior

Format as JSON:
```json
{{
  "personas": [
    {{
      "name": "Persona Name",
      "description": "Brief description of this customer type",
      "characteristics": ["characteristic 1", "characteristic 2", "characteristic 3"]
    }}
  ],
  "confidence_note": "Brief note about the confidence level of these inferences"
}}
```

Return ONLY the JSON."""


def _parse_json_from_response(response: str) -> Any:
    """Parse JSON from a Perplexity response that may include markdown.

    Args:
        response: Raw response text, possibly with markdown code blocks

    Returns:
        Parsed JSON data

    Raises:
        ValueError: If JSON cannot be parsed
    """
    json_text = response

    # Try to extract JSON from markdown code blocks
    if "```json" in json_text:
        json_text = json_text.split("```json")[1].split("```")[0].strip()
    elif "```" in json_text:
        json_text = json_text.split("```")[1].split("```")[0].strip()

    return json.loads(json_text)


class AmazonReviewsClient:
    """Client for detecting Amazon stores and analyzing reviews.

    Uses Perplexity's web search capabilities to find Amazon products
    and extract review insights without direct Amazon scraping.
    """

    def __init__(
        self,
        perplexity_client: PerplexityClient | None = None,
    ) -> None:
        """Initialize Amazon reviews client.

        Args:
            perplexity_client: Optional Perplexity client instance.
                              If not provided, uses the global client.
        """
        self._perplexity = perplexity_client
        self._initialized = False

    async def _get_perplexity(self) -> PerplexityClient:
        """Get the Perplexity client, initializing if needed."""
        if self._perplexity is None:
            self._perplexity = await get_perplexity()
        return self._perplexity

    @property
    def available(self) -> bool:
        """Check if the client is available (Perplexity configured)."""
        if self._perplexity:
            return self._perplexity.available
        return True  # Will be checked when actually used

    async def detect_amazon_store(
        self,
        brand_name: str,
        product_category: str | None = None,
        project_id: str | None = None,
    ) -> AmazonStoreDetectionResult:
        """Detect if a brand has products on Amazon.

        Args:
            brand_name: The brand/company name to search for
            product_category: Optional product category to narrow search
            project_id: Optional project ID for logging context

        Returns:
            AmazonStoreDetectionResult with products found (if any)
        """
        logger.debug(
            "detect_amazon_store entry",
            extra={
                "brand_name": brand_name,
                "product_category": product_category,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        try:
            perplexity = await self._get_perplexity()

            if not perplexity.available:
                logger.warning(
                    "Perplexity not available for Amazon store detection",
                    extra={"project_id": project_id},
                )
                return AmazonStoreDetectionResult(
                    success=False,
                    brand_name=brand_name,
                    error="Perplexity API not configured",
                )

            # Build the prompt
            category_hint = (
                f" in the {product_category} category" if product_category else ""
            )
            prompt = AMAZON_STORE_DETECTION_PROMPT.format(
                brand_name=brand_name,
                category_hint=category_hint,
            )

            logger.info(
                "Searching Amazon for brand products",
                extra={
                    "brand_name": brand_name,
                    "product_category": product_category,
                    "project_id": project_id,
                },
            )

            # Query Perplexity
            result = await perplexity.complete(
                user_prompt=prompt,
                temperature=0.1,  # Low temperature for factual results
                return_citations=True,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success:
                logger.warning(
                    "Amazon store detection failed",
                    extra={
                        "brand_name": brand_name,
                        "error": result.error,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )
                return AmazonStoreDetectionResult(
                    success=False,
                    brand_name=brand_name,
                    error=result.error or "Failed to search Amazon",
                    duration_ms=duration_ms,
                )

            # Parse the response
            try:
                products_data = _parse_json_from_response(result.text or "[]")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Failed to parse Amazon products response",
                    extra={
                        "brand_name": brand_name,
                        "error": str(e),
                        "response_preview": (result.text or "")[:200],
                        "project_id": project_id,
                    },
                )
                products_data = []

            # Convert to AmazonProduct objects
            products: list[AmazonProduct] = []
            for p in products_data:
                if isinstance(p, dict):
                    products.append(
                        AmazonProduct(
                            title=p.get("title", ""),
                            asin=p.get("asin"),
                            rating=p.get("rating"),
                            review_count=p.get("review_count"),
                            price=p.get("price"),
                        )
                    )

            has_store = len(products) > 0

            logger.info(
                "Amazon store detection complete",
                extra={
                    "brand_name": brand_name,
                    "has_store": has_store,
                    "products_found": len(products),
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            if duration_ms > 1000:
                logger.info(
                    "Slow Amazon store detection",
                    extra={
                        "brand_name": brand_name,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.debug(
                "detect_amazon_store exit",
                extra={
                    "brand_name": brand_name,
                    "has_store": has_store,
                    "products_count": len(products),
                    "project_id": project_id,
                },
            )

            return AmazonStoreDetectionResult(
                success=True,
                brand_name=brand_name,
                has_amazon_store=has_store,
                products=products,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception during Amazon store detection",
                extra={
                    "brand_name": brand_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            return AmazonStoreDetectionResult(
                success=False,
                brand_name=brand_name,
                error=f"Error detecting Amazon store: {e}",
                duration_ms=duration_ms,
            )

    async def analyze_product_reviews(
        self,
        product: AmazonProduct,
        brand_name: str,
        project_id: str | None = None,
    ) -> ReviewInsights:
        """Analyze reviews for a specific Amazon product.

        Args:
            product: The Amazon product to analyze
            brand_name: The brand name
            project_id: Optional project ID for logging

        Returns:
            ReviewInsights with extracted review data
        """
        logger.debug(
            "analyze_product_reviews entry",
            extra={
                "product_title": product.title[:50],
                "brand_name": brand_name,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        try:
            perplexity = await self._get_perplexity()

            if not perplexity.available:
                logger.warning(
                    "Perplexity not available for review analysis",
                    extra={"project_id": project_id},
                )
                return ReviewInsights()

            # Build the prompt
            prompt = REVIEW_ANALYSIS_PROMPT.format(
                product_title=product.title,
                brand_name=brand_name,
            )

            logger.info(
                "Analyzing product reviews",
                extra={
                    "product_title": product.title[:50],
                    "brand_name": brand_name,
                    "project_id": project_id,
                },
            )

            # Query Perplexity
            result = await perplexity.complete(
                user_prompt=prompt,
                temperature=0.1,
                return_citations=True,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success:
                logger.warning(
                    "Product review analysis failed",
                    extra={
                        "product_title": product.title[:50],
                        "error": result.error,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )
                return ReviewInsights()

            # Parse the response
            try:
                analysis_data = _parse_json_from_response(result.text or "{}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Failed to parse review analysis response",
                    extra={
                        "product_title": product.title[:50],
                        "error": str(e),
                        "response_preview": (result.text or "")[:200],
                        "project_id": project_id,
                    },
                )
                return ReviewInsights()

            insights = ReviewInsights(
                common_praise=analysis_data.get("common_praise", []),
                common_complaints=analysis_data.get("common_complaints", []),
                best_quotes=analysis_data.get("best_quotes", []),
                customer_types=analysis_data.get("customer_types", []),
                product_strengths=analysis_data.get("product_strengths", []),
                average_sentiment=analysis_data.get("average_sentiment", "neutral"),
            )

            logger.info(
                "Product review analysis complete",
                extra={
                    "product_title": product.title[:50],
                    "praise_count": len(insights.common_praise),
                    "complaints_count": len(insights.common_complaints),
                    "quotes_count": len(insights.best_quotes),
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            if duration_ms > 1000:
                logger.info(
                    "Slow review analysis",
                    extra={
                        "product_title": product.title[:50],
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.debug(
                "analyze_product_reviews exit",
                extra={
                    "product_title": product.title[:50],
                    "insights_found": True,
                    "project_id": project_id,
                },
            )

            return insights

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception during review analysis",
                extra={
                    "product_title": product.title[:50],
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            return ReviewInsights()

    async def generate_fallback_personas(
        self,
        brand_name: str,
        website_url: str | None = None,
        project_id: str | None = None,
    ) -> list[FallbackPersona]:
        """Generate customer personas from website analysis when no reviews available.

        Uses Perplexity to analyze the brand's website and infer likely customer
        personas based on positioning, products, and target market.

        Args:
            brand_name: The brand/company name
            website_url: Optional website URL for analysis
            project_id: Optional project ID for logging

        Returns:
            List of FallbackPersona objects inferred from website analysis
        """
        logger.debug(
            "generate_fallback_personas entry",
            extra={
                "brand_name": brand_name,
                "website_url": website_url,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        try:
            perplexity = await self._get_perplexity()

            if not perplexity.available:
                logger.warning(
                    "Perplexity not available for fallback persona generation",
                    extra={"project_id": project_id},
                )
                return []

            # Build the prompt
            url_for_prompt = (
                website_url if website_url else f"{brand_name} official website"
            )
            prompt = FALLBACK_PERSONA_PROMPT.format(
                brand_name=brand_name,
                website_url=url_for_prompt,
            )

            logger.info(
                "Generating fallback personas from website analysis",
                extra={
                    "brand_name": brand_name,
                    "website_url": website_url,
                    "project_id": project_id,
                },
            )

            # Query Perplexity
            result = await perplexity.complete(
                user_prompt=prompt,
                temperature=0.3,  # Slightly higher for creative persona generation
                return_citations=True,
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success:
                logger.warning(
                    "Fallback persona generation failed",
                    extra={
                        "brand_name": brand_name,
                        "error": result.error,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )
                return []

            # Parse the response
            try:
                response_data = _parse_json_from_response(result.text or "{}")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(
                    "Failed to parse fallback persona response",
                    extra={
                        "brand_name": brand_name,
                        "error": str(e),
                        "response_preview": (result.text or "")[:200],
                        "project_id": project_id,
                    },
                )
                return []

            # Convert to FallbackPersona objects
            personas: list[FallbackPersona] = []
            personas_data = response_data.get("personas", [])

            for p in personas_data[:3]:  # Limit to 3 personas
                if isinstance(p, dict) and p.get("name"):
                    personas.append(
                        FallbackPersona(
                            name=p.get("name", ""),
                            description=p.get("description", ""),
                            source="website_analysis",
                            inferred=True,
                            characteristics=p.get("characteristics", []),
                        )
                    )

            logger.info(
                "Fallback persona generation complete",
                extra={
                    "brand_name": brand_name,
                    "personas_generated": len(personas),
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

            if duration_ms > 1000:
                logger.warning(
                    "Slow fallback persona generation",
                    extra={
                        "brand_name": brand_name,
                        "duration_ms": duration_ms,
                        "project_id": project_id,
                    },
                )

            logger.debug(
                "generate_fallback_personas exit",
                extra={
                    "brand_name": brand_name,
                    "personas_count": len(personas),
                    "project_id": project_id,
                },
            )

            return personas

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.exception(
                "Exception during fallback persona generation",
                extra={
                    "brand_name": brand_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )
            return []

    async def analyze_brand_reviews(
        self,
        brand_name: str,
        product_category: str | None = None,
        max_products: int = 3,
        project_id: str | None = None,
        website_url: str | None = None,
        use_fallback: bool = True,
    ) -> AmazonReviewAnalysisResult:
        """Perform complete Amazon review analysis for a brand.

        Steps:
        1. Detect Amazon store and find products
        2. Analyze reviews for top products
        3. Synthesize insights into personas and proof elements
        4. If no reviews available and use_fallback=True, generate fallback personas

        Args:
            brand_name: The brand/company name
            product_category: Optional product category hint
            max_products: Maximum number of products to analyze (default 3)
            project_id: Optional project ID for logging
            website_url: Optional website URL for fallback persona generation
            use_fallback: Whether to generate fallback personas when no reviews (default True)

        Returns:
            AmazonReviewAnalysisResult with comprehensive review data
        """
        logger.debug(
            "analyze_brand_reviews entry",
            extra={
                "brand_name": brand_name,
                "product_category": product_category,
                "max_products": max_products,
                "project_id": project_id,
            },
        )

        start_time = time.monotonic()

        # Step 1: Detect Amazon store
        detection_result = await self.detect_amazon_store(
            brand_name=brand_name,
            product_category=product_category,
            project_id=project_id,
        )

        if not detection_result.success:
            return AmazonReviewAnalysisResult(
                success=False,
                brand_name=brand_name,
                error=detection_result.error,
                duration_ms=detection_result.duration_ms,
                analyzed_at=datetime.now(UTC).isoformat(),
            )

        if not detection_result.has_amazon_store:
            logger.info(
                "No Amazon store found for brand, triggering fallback",
                extra={
                    "brand_name": brand_name,
                    "use_fallback": use_fallback,
                    "project_id": project_id,
                },
            )

            # Generate fallback personas if enabled
            fallback_personas: list[dict[str, Any]] = []
            fallback_used = False
            fallback_source: str | None = None

            if use_fallback:
                logger.warning(
                    "Fallback triggered: generating personas from website analysis",
                    extra={
                        "brand_name": brand_name,
                        "website_url": website_url,
                        "project_id": project_id,
                    },
                )

                generated_personas = await self.generate_fallback_personas(
                    brand_name=brand_name,
                    website_url=website_url,
                    project_id=project_id,
                )

                if generated_personas:
                    fallback_used = True
                    fallback_source = "website_analysis"
                    for p in generated_personas:
                        fallback_personas.append(
                            {
                                "name": p.name,
                                "description": p.description,
                                "source": p.source,
                                "inferred": p.inferred,
                                "characteristics": p.characteristics,
                            }
                        )

                    logger.info(
                        "Fallback personas generated successfully",
                        extra={
                            "brand_name": brand_name,
                            "personas_count": len(fallback_personas),
                            "project_id": project_id,
                        },
                    )

            duration_ms = (time.monotonic() - start_time) * 1000
            return AmazonReviewAnalysisResult(
                success=True,
                brand_name=brand_name,
                products_analyzed=0,
                customer_personas=fallback_personas,
                duration_ms=duration_ms,
                analyzed_at=datetime.now(UTC).isoformat(),
                needs_review=fallback_used,  # Flag for user validation
                fallback_used=fallback_used,
                fallback_source=fallback_source,
            )

        # Step 2: Analyze reviews for top products
        products_to_analyze = detection_result.products[:max_products]
        all_praise: list[str] = []
        all_complaints: list[str] = []
        all_quotes: list[dict[str, Any]] = []
        all_customer_types: list[str] = []

        logger.info(
            "Analyzing reviews for products",
            extra={
                "brand_name": brand_name,
                "products_count": len(products_to_analyze),
                "project_id": project_id,
            },
        )

        for product in products_to_analyze:
            insights = await self.analyze_product_reviews(
                product=product,
                brand_name=brand_name,
                project_id=project_id,
            )

            all_praise.extend(insights.common_praise)
            all_complaints.extend(insights.common_complaints)
            all_quotes.extend(insights.best_quotes)
            all_customer_types.extend(insights.customer_types)

        # Step 3: Deduplicate and synthesize
        # Use dict.fromkeys to preserve order while deduplicating
        common_praise = list(dict.fromkeys(all_praise))[:10]
        common_complaints = list(dict.fromkeys(all_complaints))[:5]

        # Convert quotes to reviews
        reviews: list[AmazonReview] = []
        for q in all_quotes[:10]:
            reviews.append(
                AmazonReview(
                    text=q.get("text", ""),
                    rating=q.get("rating", 5),
                    title=q.get("context", ""),
                )
            )

        # Build customer personas
        customer_types = list(dict.fromkeys(all_customer_types))
        personas: list[dict[str, Any]] = []
        for ct in customer_types[:3]:
            personas.append(
                {
                    "name": ct,
                    "source": "amazon_reviews",
                    "inferred": True,
                }
            )

        # Build proof stats
        proof_stats: list[dict[str, str]] = []
        products = detection_result.products
        total_reviews = sum(p.review_count or 0 for p in products)
        if total_reviews > 0:
            proof_stats.append(
                {
                    "stat": f"{total_reviews:,}+ Amazon reviews",
                    "context": "Social proof from Amazon customers",
                }
            )

        products_with_rating = [p for p in products if p.rating]
        if products_with_rating:
            avg_rating = sum(p.rating or 0 for p in products_with_rating) / len(
                products_with_rating
            )
            if avg_rating > 0:
                proof_stats.append(
                    {
                        "stat": f"{avg_rating:.1f}/5 average Amazon rating",
                        "context": "Customer satisfaction metric",
                    }
                )

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Brand review analysis complete",
            extra={
                "brand_name": brand_name,
                "products_analyzed": len(products_to_analyze),
                "reviews_extracted": len(reviews),
                "personas_generated": len(personas),
                "duration_ms": duration_ms,
                "project_id": project_id,
            },
        )

        if duration_ms > 1000:
            logger.info(
                "Slow brand review analysis",
                extra={
                    "brand_name": brand_name,
                    "duration_ms": duration_ms,
                    "project_id": project_id,
                },
            )

        logger.debug(
            "analyze_brand_reviews exit",
            extra={
                "brand_name": brand_name,
                "success": True,
                "project_id": project_id,
            },
        )

        return AmazonReviewAnalysisResult(
            success=True,
            brand_name=brand_name,
            products_analyzed=len(products_to_analyze),
            reviews=reviews,
            common_praise=common_praise,
            common_complaints=common_complaints,
            customer_personas=personas,
            proof_stats=proof_stats,
            duration_ms=duration_ms,
            analyzed_at=datetime.now(UTC).isoformat(),
        )


# Global client instance
_amazon_reviews_client: AmazonReviewsClient | None = None


async def init_amazon_reviews() -> AmazonReviewsClient:
    """Initialize the global Amazon reviews client.

    Returns:
        Initialized AmazonReviewsClient instance
    """
    global _amazon_reviews_client
    if _amazon_reviews_client is None:
        _amazon_reviews_client = AmazonReviewsClient()
        logger.info("Amazon reviews client initialized")
    return _amazon_reviews_client


async def get_amazon_reviews() -> AmazonReviewsClient:
    """Dependency for getting Amazon reviews client.

    Usage:
        @app.get("/amazon")
        async def get_reviews(
            brand_name: str,
            client: AmazonReviewsClient = Depends(get_amazon_reviews)
        ):
            result = await client.analyze_brand_reviews(brand_name)
            ...
    """
    global _amazon_reviews_client
    if _amazon_reviews_client is None:
        await init_amazon_reviews()
    return _amazon_reviews_client  # type: ignore[return-value]
