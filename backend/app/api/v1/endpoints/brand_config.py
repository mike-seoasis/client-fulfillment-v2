"""Brand Config API endpoints.

Provides endpoints for brand configuration synthesis and management:
- POST /api/v1/projects/{project_id}/brand-config/synthesize - Synthesize brand config from documents
- GET /api/v1/projects/{project_id}/brand-config - List brand configs for a project
- GET /api/v1/projects/{project_id}/brand-config/{brand_config_id} - Get a brand config
- PUT /api/v1/projects/{project_id}/brand-config/{brand_config_id} - Update a brand config
- DELETE /api/v1/projects/{project_id}/brand-config/{brand_config_id} - Delete a brand config

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.brand_config import (
    BrandConfigListResponse,
    BrandConfigResponse,
    BrandConfigSynthesisRequest,
    BrandConfigSynthesisResponse,
    BrandConfigUpdateRequest,
)
from app.services.brand_config import (
    BrandConfigNotFoundError,
    BrandConfigService,
    BrandConfigValidationError,
)

logger = get_logger(__name__)

router = APIRouter()


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


@router.post(
    "/synthesize",
    response_model=BrandConfigSynthesisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Synthesize brand config from documents",
    description="""
Synthesize a V2 brand configuration schema from provided source documents.

The synthesis process uses Claude to analyze uploaded documents (PDF, DOCX, TXT)
and extract brand identity elements including colors, typography, logo, voice/tone,
and social media handles.

**Document Requirements:**
- Documents should be base64-encoded
- Supported formats: PDF, DOCX, TXT
- Maximum 5 documents per request
- Maximum 50MB per document

**What gets extracted:**
- Colors (primary, secondary, accent, background, text)
- Typography (fonts, sizes, weights)
- Logo information
- Brand voice and tone
- Social media handles
""",
    responses={
        201: {"description": "Brand config synthesized successfully"},
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed for 'brand_name': cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def synthesize_brand_config(
    request: Request,
    project_id: str,
    data: BrandConfigSynthesisRequest,
    session: AsyncSession = Depends(get_session),
) -> BrandConfigSynthesisResponse | JSONResponse:
    """Synthesize brand config from documents using Claude LLM."""
    request_id = _get_request_id(request)
    logger.debug(
        "Synthesize brand config request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_name": data.brand_name[:50] if data.brand_name else "",
            "num_documents": len(data.source_documents),
            "num_urls": len(data.source_urls),
        },
    )

    service = BrandConfigService(session)
    try:
        result = await service.synthesize_and_save(project_id, data)

        if not result.success:
            logger.warning(
                "Brand config synthesis failed",
                extra={
                    "request_id": request_id,
                    "project_id": project_id,
                    "error": result.error,
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": result.error,
                    "code": "SYNTHESIS_FAILED",
                    "request_id": request_id,
                },
            )

        return result

    except BrandConfigValidationError as e:
        logger.warning(
            "Brand config validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field,
                "value": str(e.value)[:100] if e.value else None,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )


@router.get(
    "",
    response_model=BrandConfigListResponse,
    summary="List brand configs",
    description="Retrieve all brand configurations for a project.",
)
async def list_brand_configs(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> BrandConfigListResponse:
    """List all brand configs for a project."""
    request_id = _get_request_id(request)
    logger.debug(
        "List brand configs request",
        extra={"request_id": request_id, "project_id": project_id},
    )

    service = BrandConfigService(session)
    configs, total = await service.list_brand_configs(project_id)

    return BrandConfigListResponse(
        items=[BrandConfigResponse.model_validate(c) for c in configs],
        total=total,
    )


@router.get(
    "/{brand_config_id}",
    response_model=BrandConfigResponse,
    summary="Get a brand config",
    description="Retrieve a brand configuration by its ID.",
    responses={
        404: {
            "description": "Brand config not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Brand config not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def get_brand_config(
    request: Request,
    project_id: str,
    brand_config_id: str,
    session: AsyncSession = Depends(get_session),
) -> BrandConfigResponse | JSONResponse:
    """Get a brand config by ID."""
    request_id = _get_request_id(request)
    logger.debug(
        "Get brand config request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_config_id": brand_config_id,
        },
    )

    service = BrandConfigService(session)
    try:
        config = await service.get_brand_config(brand_config_id, project_id)
        return BrandConfigResponse.model_validate(config)

    except BrandConfigNotFoundError as e:
        logger.warning(
            "Brand config not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "brand_config_id": brand_config_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )


@router.put(
    "/{brand_config_id}",
    response_model=BrandConfigResponse,
    summary="Update a brand config",
    description="Update an existing brand configuration.",
    responses={
        404: {
            "description": "Brand config not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Brand config not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def update_brand_config(
    request: Request,
    project_id: str,
    brand_config_id: str,
    data: BrandConfigUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> BrandConfigResponse | JSONResponse:
    """Update a brand config."""
    request_id = _get_request_id(request)
    logger.debug(
        "Update brand config request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_config_id": brand_config_id,
            "update_fields": [
                k for k, v in data.model_dump().items() if v is not None
            ],
        },
    )

    service = BrandConfigService(session)
    try:
        v2_schema_dict = data.v2_schema.model_dump() if data.v2_schema else None

        config = await service.update_brand_config(
            brand_config_id=brand_config_id,
            brand_name=data.brand_name,
            domain=data.domain,
            v2_schema=v2_schema_dict,
            project_id=project_id,
        )
        return BrandConfigResponse.model_validate(config)

    except BrandConfigNotFoundError as e:
        logger.warning(
            "Brand config not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "brand_config_id": brand_config_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )

    except BrandConfigValidationError as e:
        logger.warning(
            "Brand config validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "brand_config_id": brand_config_id,
                "field": e.field,
                "value": str(e.value)[:100] if e.value else None,
                "message": e.message,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": str(e),
                "code": "VALIDATION_ERROR",
                "request_id": request_id,
            },
        )


@router.delete(
    "/{brand_config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a brand config",
    description="Delete an existing brand configuration.",
    responses={
        404: {
            "description": "Brand config not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Brand config not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        }
    },
)
async def delete_brand_config(
    request: Request,
    project_id: str,
    brand_config_id: str,
    session: AsyncSession = Depends(get_session),
) -> None | JSONResponse:
    """Delete a brand config."""
    request_id = _get_request_id(request)
    logger.debug(
        "Delete brand config request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "brand_config_id": brand_config_id,
        },
    )

    service = BrandConfigService(session)
    try:
        await service.delete_brand_config(brand_config_id, project_id)
        return None  # 204 No Content

    except BrandConfigNotFoundError as e:
        logger.warning(
            "Brand config not found",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "brand_config_id": brand_config_id,
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )
