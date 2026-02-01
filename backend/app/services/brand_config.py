"""BrandConfigService for V2 brand config synthesis using Claude.

Synthesizes brand configuration from documents and URLs using Claude LLM,
generating a V2 schema with colors, typography, logo, voice/tone, and social media.

Features:
- Document parsing (PDF, DOCX, TXT) for brand extraction
- LLM-based synthesis via Claude
- Structured V2 schema output
- Comprehensive error logging per requirements

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, brand_config_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second
"""

import base64
import json
import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.integrations.claude import ClaudeClient, get_claude
from app.repositories.brand_config import BrandConfigRepository
from app.schemas.brand_config import (
    BrandConfigSynthesisRequest,
    BrandConfigSynthesisResponse,
    V2SchemaModel,
)
from app.utils.document_parser import DocumentParser, get_document_parser

logger = get_logger(__name__)

# Constants
SLOW_OPERATION_THRESHOLD_MS = 1000
MAX_CONTENT_LENGTH = 15000  # Max chars to send to Claude
MAX_CONTENT_PREVIEW_LENGTH = 200


# =============================================================================
# LLM PROMPT TEMPLATES FOR BRAND SYNTHESIS
# =============================================================================

BRAND_SYNTHESIS_SYSTEM_PROMPT = """You are a brand strategist expert specializing in extracting brand identity elements from documents and web content.

Your task is to analyze provided content and synthesize a comprehensive brand configuration schema.

## Output Requirements

You MUST respond with valid JSON only (no markdown, no explanation). The JSON must follow this exact structure:

{
  "colors": {
    "primary": "#HEXCODE",
    "secondary": "#HEXCODE",
    "accent": "#HEXCODE",
    "background": "#FFFFFF",
    "text": "#333333"
  },
  "typography": {
    "heading_font": "Font Name",
    "body_font": "Font Name",
    "base_size": 16,
    "heading_weight": "bold",
    "body_weight": "regular"
  },
  "logo": {
    "url": "URL if found",
    "alt_text": "Description of logo"
  },
  "voice": {
    "tone": "professional|friendly|playful|authoritative|warm|casual",
    "personality": ["trait1", "trait2", "trait3"],
    "writing_style": "conversational|formal|technical|inspirational",
    "target_audience": "Description of target audience",
    "value_proposition": "Core value proposition",
    "tagline": "Brand tagline if found"
  },
  "social": {
    "twitter": "@handle",
    "linkedin": "company/name",
    "instagram": "@handle",
    "facebook": "page name",
    "youtube": "channel",
    "tiktok": "@handle"
  },
  "version": "2.0"
}

## Guidelines

1. **Colors**: Extract actual colors if mentioned; otherwise infer from brand tone (warm brands = warm colors, tech = blues, etc.)
2. **Typography**: Use specific font names if mentioned; otherwise suggest appropriate fonts based on brand personality
3. **Voice**: Analyze tone, language patterns, and messaging to determine brand voice
4. **Social**: Include only handles that are explicitly mentioned
5. **Inference**: When information is missing, make reasonable inferences based on industry and brand positioning
6. **Hex Colors**: Always use 6-character hex codes with # prefix (e.g., #FF5733)
7. **Null Values**: Use null for fields with no information (don't guess social handles)

Respond with JSON only."""

BRAND_SYNTHESIS_USER_PROMPT_TEMPLATE = """Analyze the following brand content and synthesize a V2 brand configuration schema.

Brand Name: {brand_name}
Domain: {domain}

## Source Content:

{content}

{additional_context}

Extract brand identity elements and return a JSON object with colors, typography, logo, voice, and social media configuration.

Respond with JSON only:"""


# =============================================================================
# SERVICE EXCEPTIONS
# =============================================================================


class BrandConfigServiceError(Exception):
    """Base exception for BrandConfigService errors."""

    def __init__(
        self,
        message: str,
        project_id: str | None = None,
        brand_config_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.brand_config_id = brand_config_id


class BrandConfigValidationError(BrandConfigServiceError):
    """Raised when input validation fails."""

    def __init__(
        self,
        field: str,
        value: Any,
        message: str,
        project_id: str | None = None,
    ) -> None:
        super().__init__(
            f"Validation failed for '{field}': {message}",
            project_id=project_id,
        )
        self.field = field
        self.value = value
        self.message = message


class BrandConfigNotFoundError(BrandConfigServiceError):
    """Raised when brand config is not found."""

    def __init__(self, brand_config_id: str, project_id: str | None = None) -> None:
        super().__init__(
            f"Brand config not found: {brand_config_id}",
            project_id=project_id,
            brand_config_id=brand_config_id,
        )


class BrandConfigSynthesisError(BrandConfigServiceError):
    """Raised when synthesis fails."""

    pass


# =============================================================================
# SERVICE RESULT DATACLASS
# =============================================================================


@dataclass
class SynthesisResult:
    """Result of brand config synthesis."""

    success: bool
    v2_schema: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
    sources_used: list[str] = field(default_factory=list)


# =============================================================================
# BRAND CONFIG SERVICE
# =============================================================================


class BrandConfigService:
    """Service for brand config synthesis and management.

    Uses Claude LLM to synthesize brand configuration from documents and URLs,
    generating a V2 schema with colors, typography, logo, voice/tone, and social media.

    Example usage:
        service = BrandConfigService(session)

        result = await service.synthesize_brand_config(
            project_id="abc-123",
            request=BrandConfigSynthesisRequest(
                brand_name="Acme Corp",
                domain="acme.com",
                source_documents=[base64_encoded_pdf],
                document_filenames=["brand-guide.pdf"],
            ),
        )

        print(f"V2 Schema: {result.v2_schema}")
    """

    def __init__(
        self,
        session: AsyncSession,
        claude_client: ClaudeClient | None = None,
        document_parser: DocumentParser | None = None,
    ) -> None:
        """Initialize the brand config service.

        Args:
            session: Async SQLAlchemy session for database operations
            claude_client: Claude client for LLM synthesis (uses global if None)
            document_parser: Document parser for extracting text (uses global if None)
        """
        logger.debug(
            "BrandConfigService.__init__ called",
            extra={
                "has_custom_claude_client": claude_client is not None,
                "has_custom_document_parser": document_parser is not None,
            },
        )

        self._session = session
        self._repository = BrandConfigRepository(session)
        self._claude_client = claude_client
        self._document_parser = document_parser

        logger.debug("BrandConfigService initialized")

    async def _get_claude_client(self) -> ClaudeClient | None:
        """Get Claude client for LLM synthesis."""
        if self._claude_client is not None:
            return self._claude_client
        try:
            return await get_claude()
        except Exception as e:
            logger.warning(
                "Failed to get Claude client",
                extra={"error": str(e)},
            )
            return None

    def _get_document_parser(self) -> DocumentParser:
        """Get document parser for extracting text from files."""
        if self._document_parser is not None:
            return self._document_parser
        return get_document_parser()

    def _sanitize_content_for_log(self, content: str) -> str:
        """Sanitize content for logging (truncate if too long)."""
        if len(content) > MAX_CONTENT_PREVIEW_LENGTH:
            return content[:MAX_CONTENT_PREVIEW_LENGTH] + "..."
        return content

    async def _parse_documents(
        self,
        source_documents: list[str],
        document_filenames: list[str],
        project_id: str | None = None,
    ) -> tuple[list[str], list[str]]:
        """Parse base64-encoded documents and extract text.

        Args:
            source_documents: List of base64-encoded document content
            document_filenames: List of filenames for format detection
            project_id: Project ID for logging

        Returns:
            Tuple of (extracted_texts, successfully_parsed_filenames)
        """
        extracted_texts: list[str] = []
        parsed_filenames: list[str] = []
        parser = self._get_document_parser()

        for i, (doc_b64, filename) in enumerate(
            zip(source_documents, document_filenames, strict=False)
        ):
            if not doc_b64 or not filename:
                continue

            try:
                logger.debug(
                    "Parsing document",
                    extra={
                        "document_index": i,
                        "filename": filename[:50],
                        "project_id": project_id,
                    },
                )

                # Decode base64
                try:
                    file_bytes = base64.b64decode(doc_b64)
                except Exception as decode_error:
                    logger.warning(
                        "Failed to decode base64 document",
                        extra={
                            "filename": filename[:50],
                            "error": str(decode_error),
                            "project_id": project_id,
                        },
                    )
                    continue

                # Parse document
                result = parser.parse_bytes(file_bytes, filename, project_id)

                if result.success and result.content:
                    extracted_texts.append(
                        f"=== Document: {filename} ===\n{result.content}"
                    )
                    parsed_filenames.append(filename)
                    logger.debug(
                        "Document parsed successfully",
                        extra={
                            "filename": filename[:50],
                            "word_count": result.metadata.word_count if result.metadata else 0,
                            "project_id": project_id,
                        },
                    )
                else:
                    logger.warning(
                        "Document parsing returned no content",
                        extra={
                            "filename": filename[:50],
                            "error": result.error,
                            "project_id": project_id,
                        },
                    )

            except Exception as e:
                logger.warning(
                    "Failed to parse document",
                    extra={
                        "filename": filename[:50],
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "project_id": project_id,
                    },
                )
                continue

        return extracted_texts, parsed_filenames

    def _merge_v2_schemas(
        self,
        synthesized: dict[str, Any],
        partial: V2SchemaModel | None,
    ) -> dict[str, Any]:
        """Merge synthesized schema with partial user-provided schema.

        User-provided values take precedence over synthesized values.

        Args:
            synthesized: LLM-synthesized schema
            partial: User-provided partial schema

        Returns:
            Merged schema
        """
        if partial is None:
            return synthesized

        partial_dict = partial.model_dump(exclude_none=True, exclude_unset=True)

        # Deep merge: partial values override synthesized
        merged = synthesized.copy()

        for key, value in partial_dict.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # Merge nested dicts
                merged[key] = {**merged[key], **value}
            elif value:  # Only override if value is truthy
                merged[key] = value

        return merged

    async def synthesize_v2_schema(
        self,
        brand_name: str,
        domain: str | None = None,
        source_documents: list[str] | None = None,
        document_filenames: list[str] | None = None,
        source_urls: list[str] | None = None,
        additional_context: str | None = None,
        partial_v2_schema: V2SchemaModel | None = None,
        project_id: str | None = None,
    ) -> SynthesisResult:
        """Synthesize a V2 brand config schema from source materials.

        Uses Claude to analyze documents and URLs, extracting brand identity
        elements into a structured V2 schema.

        Args:
            brand_name: Name of the brand
            domain: Brand domain (optional)
            source_documents: Base64-encoded documents (optional)
            document_filenames: Filenames for documents (optional)
            source_urls: URLs to scrape (optional, not yet implemented)
            additional_context: Extra instructions/context (optional)
            partial_v2_schema: User-provided partial schema to merge (optional)
            project_id: Project ID for logging

        Returns:
            SynthesisResult with synthesized V2 schema
        """
        start_time = time.monotonic()

        logger.debug(
            "synthesize_v2_schema() called",
            extra={
                "project_id": project_id,
                "brand_name": brand_name[:50] if brand_name else "",
                "domain": domain,
                "num_documents": len(source_documents) if source_documents else 0,
                "num_urls": len(source_urls) if source_urls else 0,
                "has_additional_context": additional_context is not None,
                "has_partial_schema": partial_v2_schema is not None,
            },
        )

        # Validate inputs
        if not brand_name or not brand_name.strip():
            logger.warning(
                "Validation failed: empty brand_name",
                extra={
                    "project_id": project_id,
                    "field": "brand_name",
                    "rejected_value": repr(brand_name),
                },
            )
            return SynthesisResult(
                success=False,
                error="Brand name cannot be empty",
            )

        # Collect content from all sources
        content_parts: list[str] = []
        sources_used: list[str] = []

        # Parse documents
        if source_documents and document_filenames:
            extracted_texts, parsed_filenames = await self._parse_documents(
                source_documents,
                document_filenames,
                project_id,
            )
            content_parts.extend(extracted_texts)
            sources_used.extend(parsed_filenames)

        # TODO: Add URL scraping support
        if source_urls:
            logger.debug(
                "URL scraping not yet implemented, skipping URLs",
                extra={
                    "project_id": project_id,
                    "num_urls": len(source_urls),
                },
            )

        # Check if we have any content
        if not content_parts:
            logger.warning(
                "No content extracted from sources",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name[:50],
                },
            )
            # Create minimal schema if no content but partial schema provided
            if partial_v2_schema:
                return SynthesisResult(
                    success=True,
                    v2_schema=partial_v2_schema.model_dump(),
                    duration_ms=(time.monotonic() - start_time) * 1000,
                    sources_used=[],
                )
            return SynthesisResult(
                success=False,
                error="No content could be extracted from provided sources",
            )

        # Combine content
        combined_content = "\n\n".join(content_parts)

        # Truncate if too long
        if len(combined_content) > MAX_CONTENT_LENGTH:
            combined_content = combined_content[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated]"
            logger.debug(
                "Content truncated for prompt",
                extra={
                    "project_id": project_id,
                    "original_length": len("\n\n".join(content_parts)),
                    "truncated_to": MAX_CONTENT_LENGTH,
                },
            )

        # Get Claude client
        claude = await self._get_claude_client()
        if not claude or not claude.available:
            logger.warning(
                "Claude not available for brand synthesis",
                extra={
                    "project_id": project_id,
                    "reason": "client_unavailable",
                },
            )
            return SynthesisResult(
                success=False,
                error="Claude LLM not available (missing API key or service unavailable)",
            )

        # Build prompt
        additional_context_section = ""
        if additional_context:
            additional_context_section = f"\n## Additional Context:\n{additional_context}"

        user_prompt = BRAND_SYNTHESIS_USER_PROMPT_TEMPLATE.format(
            brand_name=brand_name,
            domain=domain or "(not specified)",
            content=combined_content,
            additional_context=additional_context_section,
        )

        try:
            # Log state transition: synthesis starting
            logger.info(
                "Brand config synthesis starting",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name[:50],
                    "sources_count": len(sources_used),
                    "content_length": len(combined_content),
                },
            )

            # Call Claude
            result = await claude.complete(
                system_prompt=BRAND_SYNTHESIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,  # Lower temperature for structured output
                max_tokens=2000,  # V2 schema is moderately sized
            )

            duration_ms = (time.monotonic() - start_time) * 1000

            if not result.success or not result.text:
                logger.warning(
                    "LLM brand synthesis failed",
                    extra={
                        "project_id": project_id,
                        "brand_name": brand_name[:50],
                        "error": result.error,
                        "status_code": result.status_code,
                        "request_id": result.request_id,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                return SynthesisResult(
                    success=False,
                    error=result.error or "LLM synthesis failed",
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                )

            # Parse JSON response
            response_text: str = result.text

            # Handle markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            response_text = response_text.strip()

            try:
                synthesized_schema = json.loads(response_text)

                if not isinstance(synthesized_schema, dict):
                    logger.warning(
                        "Validation failed: LLM response is not a dict",
                        extra={
                            "project_id": project_id,
                            "field": "response",
                            "rejected_value": type(synthesized_schema).__name__,
                        },
                    )
                    return SynthesisResult(
                        success=False,
                        error="LLM response is not a valid schema object",
                        duration_ms=round(duration_ms, 2),
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        request_id=result.request_id,
                    )

                # Ensure version is set
                synthesized_schema["version"] = "2.0"

                # Merge with partial schema if provided
                final_schema = self._merge_v2_schemas(synthesized_schema, partial_v2_schema)

                # Log state transition: synthesis complete
                logger.info(
                    "Brand config synthesis complete",
                    extra={
                        "project_id": project_id,
                        "brand_name": brand_name[:50],
                        "sources_count": len(sources_used),
                        "duration_ms": round(duration_ms, 2),
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "request_id": result.request_id,
                    },
                )

                if duration_ms > SLOW_OPERATION_THRESHOLD_MS:
                    logger.warning(
                        "Slow brand synthesis operation",
                        extra={
                            "project_id": project_id,
                            "brand_name": brand_name[:50],
                            "duration_ms": round(duration_ms, 2),
                            "threshold_ms": SLOW_OPERATION_THRESHOLD_MS,
                        },
                    )

                return SynthesisResult(
                    success=True,
                    v2_schema=final_schema,
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                    sources_used=sources_used,
                )

            except json.JSONDecodeError as e:
                logger.warning(
                    "Validation failed: LLM response is not valid JSON",
                    extra={
                        "project_id": project_id,
                        "field": "response",
                        "rejected_value": response_text[:200],
                        "error": str(e),
                        "error_position": e.pos if hasattr(e, "pos") else None,
                    },
                )
                return SynthesisResult(
                    success=False,
                    error=f"Failed to parse LLM response as JSON: {e}",
                    duration_ms=round(duration_ms, 2),
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    request_id=result.request_id,
                )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Brand synthesis exception",
                extra={
                    "project_id": project_id,
                    "brand_name": brand_name[:50] if brand_name else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return SynthesisResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                duration_ms=round(duration_ms, 2),
            )

    async def synthesize_and_save(
        self,
        project_id: str,
        request: BrandConfigSynthesisRequest,
    ) -> BrandConfigSynthesisResponse:
        """Synthesize brand config and save to database.

        Args:
            project_id: UUID of the project to associate the config with
            request: Synthesis request with sources and options

        Returns:
            BrandConfigSynthesisResponse with result and saved config ID
        """
        start_time = time.monotonic()

        logger.debug(
            "synthesize_and_save() called",
            extra={
                "project_id": project_id,
                "brand_name": request.brand_name[:50] if request.brand_name else "",
            },
        )

        # Synthesize V2 schema
        synthesis_result = await self.synthesize_v2_schema(
            brand_name=request.brand_name,
            domain=request.domain,
            source_documents=request.source_documents,
            document_filenames=request.document_filenames,
            source_urls=request.source_urls,
            additional_context=request.additional_context,
            partial_v2_schema=request.partial_v2_schema,
            project_id=project_id,
        )

        if not synthesis_result.success:
            return BrandConfigSynthesisResponse(
                success=False,
                project_id=project_id,
                brand_name=request.brand_name,
                domain=request.domain,
                v2_schema=V2SchemaModel(),
                error=synthesis_result.error,
                duration_ms=synthesis_result.duration_ms,
                input_tokens=synthesis_result.input_tokens,
                output_tokens=synthesis_result.output_tokens,
                request_id=synthesis_result.request_id,
            )

        try:
            # Check if brand config already exists for this project + brand name
            existing_config = await self._repository.get_by_project_and_brand(
                project_id, request.brand_name
            )

            if existing_config:
                # Update existing
                await self._repository.update(
                    existing_config.id,
                    domain=request.domain,
                    v2_schema=synthesis_result.v2_schema,
                )
                brand_config_id = existing_config.id
                logger.info(
                    "Brand config updated with synthesized schema",
                    extra={
                        "brand_config_id": brand_config_id,
                        "project_id": project_id,
                        "brand_name": request.brand_name[:50],
                    },
                )
            else:
                # Create new
                new_config = await self._repository.create(
                    project_id=project_id,
                    brand_name=request.brand_name,
                    domain=request.domain,
                    v2_schema=synthesis_result.v2_schema,
                )
                brand_config_id = new_config.id
                logger.info(
                    "Brand config created with synthesized schema",
                    extra={
                        "brand_config_id": brand_config_id,
                        "project_id": project_id,
                        "brand_name": request.brand_name[:50],
                    },
                )

            total_duration_ms = (time.monotonic() - start_time) * 1000

            return BrandConfigSynthesisResponse(
                success=True,
                brand_config_id=brand_config_id,
                project_id=project_id,
                brand_name=request.brand_name,
                domain=request.domain,
                v2_schema=V2SchemaModel.model_validate(synthesis_result.v2_schema),
                duration_ms=round(total_duration_ms, 2),
                input_tokens=synthesis_result.input_tokens,
                output_tokens=synthesis_result.output_tokens,
                request_id=synthesis_result.request_id,
                sources_used=synthesis_result.sources_used,
            )

        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "Failed to save synthesized brand config",
                extra={
                    "project_id": project_id,
                    "brand_name": request.brand_name[:50] if request.brand_name else "",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "stack_trace": traceback.format_exc(),
                },
                exc_info=True,
            )
            return BrandConfigSynthesisResponse(
                success=False,
                project_id=project_id,
                brand_name=request.brand_name,
                domain=request.domain,
                v2_schema=V2SchemaModel.model_validate(synthesis_result.v2_schema),
                error=f"Failed to save brand config: {str(e)}",
                duration_ms=round(duration_ms, 2),
                input_tokens=synthesis_result.input_tokens,
                output_tokens=synthesis_result.output_tokens,
                request_id=synthesis_result.request_id,
            )

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================

    async def get_brand_config(
        self,
        brand_config_id: str,
        project_id: str | None = None,
    ) -> Any:
        """Get a brand config by ID.

        Args:
            brand_config_id: UUID of the brand config
            project_id: Optional project ID for validation

        Returns:
            BrandConfig model instance

        Raises:
            BrandConfigNotFoundError: If brand config not found
        """
        logger.debug(
            "get_brand_config() called",
            extra={
                "brand_config_id": brand_config_id,
                "project_id": project_id,
            },
        )

        config = await self._repository.get_by_id(brand_config_id)

        if config is None:
            raise BrandConfigNotFoundError(brand_config_id, project_id)

        # Validate project ownership if project_id provided
        if project_id and config.project_id != project_id:
            logger.warning(
                "Brand config belongs to different project",
                extra={
                    "brand_config_id": brand_config_id,
                    "requested_project_id": project_id,
                    "actual_project_id": config.project_id,
                },
            )
            raise BrandConfigNotFoundError(brand_config_id, project_id)

        return config

    async def list_brand_configs(
        self,
        project_id: str,
    ) -> tuple[list[Any], int]:
        """List all brand configs for a project.

        Args:
            project_id: UUID of the project

        Returns:
            Tuple of (list of BrandConfig instances, total count)
        """
        logger.debug(
            "list_brand_configs() called",
            extra={"project_id": project_id},
        )

        configs = await self._repository.get_by_project_id(project_id)
        count = len(configs)

        return configs, count

    async def update_brand_config(
        self,
        brand_config_id: str,
        brand_name: str | None = None,
        domain: str | None = None,
        v2_schema: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> Any:
        """Update a brand config.

        Args:
            brand_config_id: UUID of the brand config
            brand_name: New brand name (optional)
            domain: New domain (optional)
            v2_schema: New V2 schema (optional)
            project_id: Optional project ID for validation

        Returns:
            Updated BrandConfig model instance

        Raises:
            BrandConfigNotFoundError: If brand config not found
        """
        logger.debug(
            "update_brand_config() called",
            extra={
                "brand_config_id": brand_config_id,
                "project_id": project_id,
                "update_fields": [
                    k
                    for k, v in [
                        ("brand_name", brand_name),
                        ("domain", domain),
                        ("v2_schema", v2_schema),
                    ]
                    if v is not None
                ],
            },
        )

        # Validate existence and ownership
        await self.get_brand_config(brand_config_id, project_id)

        config = await self._repository.update(
            brand_config_id,
            brand_name=brand_name,
            domain=domain,
            v2_schema=v2_schema,
        )

        if config is None:
            raise BrandConfigNotFoundError(brand_config_id, project_id)

        return config

    async def delete_brand_config(
        self,
        brand_config_id: str,
        project_id: str | None = None,
    ) -> bool:
        """Delete a brand config.

        Args:
            brand_config_id: UUID of the brand config
            project_id: Optional project ID for validation

        Returns:
            True if deleted

        Raises:
            BrandConfigNotFoundError: If brand config not found
        """
        logger.debug(
            "delete_brand_config() called",
            extra={
                "brand_config_id": brand_config_id,
                "project_id": project_id,
            },
        )

        # Validate existence and ownership
        await self.get_brand_config(brand_config_id, project_id)

        deleted = await self._repository.delete(brand_config_id)

        if not deleted:
            raise BrandConfigNotFoundError(brand_config_id, project_id)

        return deleted


# =============================================================================
# GLOBAL SERVICE ACCESSOR
# =============================================================================


def get_brand_config_service(session: AsyncSession) -> BrandConfigService:
    """Get BrandConfigService instance.

    Args:
        session: Async SQLAlchemy session

    Returns:
        BrandConfigService instance
    """
    return BrandConfigService(session)
