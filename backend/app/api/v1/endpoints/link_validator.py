"""Link Validator phase API endpoints for projects.

Provides Phase 5C link validation against collection registry for a project:
- POST /api/v1/projects/{project_id}/phases/link_validator/validate - Validate links
- POST /api/v1/projects/{project_id}/phases/link_validator/batch - Batch validate links

Error Logging Requirements:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level

Railway Deployment Requirements:
- CORS must allow frontend domain (configure via FRONTEND_URL env var)
- Return proper error responses (Railway shows these in logs)
- Include request_id in all responses for debugging
- Health check endpoint at /health or /api/v1/health
"""

import time

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.schemas.link_validator import (
    BatchLinkValidationItemResponse,
    BatchLinkValidationRequest,
    BatchLinkValidationResponse,
    LinkValidationRequest,
    LinkValidationResponse,
    LinkValidationResultItem,
)
from app.services.link_validator import (
    CollectionRegistry,
    CollectionRegistryEntry,
    LinkToValidate,
    LinkValidationBatchResult,
    LinkValidatorInput,
    LinkValidatorValidationError,
    get_link_validator_service,
)
from app.services.project import ProjectNotFoundError, ProjectService

logger = get_logger(__name__)

router = APIRouter()


def _get_request_id(request: Request) -> str:
    """Get request_id from request state."""
    return getattr(request.state, "request_id", "unknown")


async def _verify_project_exists(
    project_id: str,
    session: AsyncSession,
    request_id: str,
) -> JSONResponse | None:
    """Verify that the project exists.

    Returns JSONResponse with 404 if not found, None if found.
    """
    service = ProjectService(session)
    try:
        await service.get_project(project_id)
        return None
    except ProjectNotFoundError as e:
        logger.warning(
            "Project not found",
            extra={"request_id": request_id, "project_id": project_id},
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": str(e),
                "code": "NOT_FOUND",
                "request_id": request_id,
            },
        )


def _convert_request_to_input(
    data: LinkValidationRequest,
    project_id: str,
) -> LinkValidatorInput:
    """Convert API request to service input."""
    # Build links
    links = [
        LinkToValidate(
            url=link.url,
            anchor_text=link.anchor_text,
            link_type=link.link_type,
        )
        for link in data.links
    ]

    # Build registry
    entries = [
        CollectionRegistryEntry(
            url=entry.url,
            name=entry.name,
            labels=set(entry.labels),
            page_id=entry.page_id,
        )
        for entry in data.registry
    ]
    registry = CollectionRegistry(entries=entries, project_id=project_id)

    return LinkValidatorInput(
        links=links,
        registry=registry,
        site_domain=data.site_domain,
        project_id=project_id,
        page_id=data.page_id,
        content_id=data.content_id,
    )


def _convert_result_to_response(
    result: LinkValidationBatchResult,
) -> LinkValidationResponse:
    """Convert service result to API response schema."""
    results = [
        LinkValidationResultItem(
            url=r.url,
            anchor_text=r.anchor_text,
            is_valid=r.is_valid,
            is_internal=r.is_internal,
            normalized_url=r.normalized_url,
            error=r.error,
            suggestion=r.suggestion,
        )
        for r in result.results
    ]

    return LinkValidationResponse(
        success=result.success,
        results=results,
        total_links=result.total_links,
        valid_count=result.valid_count,
        invalid_count=result.invalid_count,
        external_count=result.external_count,
        validation_score=round(result.validation_score, 2),
        passed_validation=result.passed_validation,
        error=result.error,
        duration_ms=round(result.duration_ms, 2),
    )


@router.post(
    "/validate",
    response_model=LinkValidationResponse,
    summary="Validate links against collection registry",
    description="Run Phase 5C link validation to ensure internal links point to valid collection pages.",
    responses={
        404: {
            "description": "Project not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Project not found: <uuid>",
                        "code": "NOT_FOUND",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
        400: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation failed: registry cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def validate_links(
    request: Request,
    project_id: str,
    data: LinkValidationRequest,
    session: AsyncSession = Depends(get_session),
) -> LinkValidationResponse | JSONResponse:
    """Validate links against the collection registry.

    Phase 5C link validation:
    1. Identify internal vs external links
    2. Normalize internal links for consistent comparison
    3. Check each internal link against the collection registry
    4. Calculate validation score (percentage of valid internal links)
    5. Generate suggestions for fixing invalid links

    Links pointing to pages in the collection registry are valid.
    External links are not validated against the registry.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Link validation request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "link_count": len(data.links),
            "registry_size": len(data.registry),
            "site_domain": data.site_domain,
            "page_id": data.page_id,
            "content_id": data.content_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_link_validator_service()
        input_data = _convert_request_to_input(data, project_id)
        result = await service.validate_links(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Link validation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
                "success": result.success,
                "valid_count": result.valid_count,
                "invalid_count": result.invalid_count,
                "validation_score": round(result.validation_score, 2),
                "passed_validation": result.passed_validation,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result)

    except LinkValidatorValidationError as e:
        logger.warning(
            "Link validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100] if e.value else "",
                "message": str(e),
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
    except Exception as e:
        logger.error(
            "Link validation failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )


@router.post(
    "/batch",
    response_model=BatchLinkValidationResponse,
    summary="Batch validate links against collection registry",
    description="Validate links for multiple content items against a shared collection registry.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def validate_links_batch(
    request: Request,
    project_id: str,
    data: BatchLinkValidationRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchLinkValidationResponse | JSONResponse:
    """Validate links for multiple content items.

    Runs Phase 5C link validation on each item using a shared registry.
    Returns aggregate statistics and individual results.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "Batch link validation request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
            "registry_size": len(data.registry),
            "site_domain": data.site_domain,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_link_validator_service()

        # Build shared registry
        entries = [
            CollectionRegistryEntry(
                url=entry.url,
                name=entry.name,
                labels=set(entry.labels),
                page_id=entry.page_id,
            )
            for entry in data.registry
        ]
        registry = CollectionRegistry(entries=entries, project_id=project_id)

        # Process each item
        results: list[BatchLinkValidationItemResponse] = []
        passed_count = 0
        failed_count = 0
        error_count = 0
        total_score = 0.0
        score_count = 0

        for item in data.items:
            # Build links for this item
            links = [
                LinkToValidate(
                    url=link.url,
                    anchor_text=link.anchor_text,
                    link_type=link.link_type,
                )
                for link in item.links
            ]

            input_data = LinkValidatorInput(
                links=links,
                registry=registry,
                site_domain=data.site_domain,
                project_id=project_id,
                page_id=item.page_id,
                content_id=item.content_id,
            )

            result = await service.validate_links(input_data)

            # Collect invalid URLs
            invalid_urls = [
                r.url for r in result.results
                if r.is_internal and not r.is_valid
            ]

            results.append(
                BatchLinkValidationItemResponse(
                    content_id=item.content_id,
                    page_id=item.page_id,
                    success=result.success,
                    valid_count=result.valid_count,
                    invalid_count=result.invalid_count,
                    external_count=result.external_count,
                    validation_score=round(result.validation_score, 2),
                    passed_validation=result.passed_validation,
                    invalid_urls=invalid_urls,
                    error=result.error,
                )
            )

            if not result.success:
                error_count += 1
            elif result.passed_validation:
                passed_count += 1
            else:
                failed_count += 1

            total_score += result.validation_score
            score_count += 1

        average_score = round(total_score / score_count, 2) if score_count > 0 else 0.0
        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "Batch link validation complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "passed_count": passed_count,
                "failed_count": failed_count,
                "error_count": error_count,
                "average_score": average_score,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return BatchLinkValidationResponse(
            success=True,
            results=results,
            total_items=len(data.items),
            passed_count=passed_count,
            failed_count=failed_count,
            error_count=error_count,
            average_score=average_score,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except LinkValidatorValidationError as e:
        logger.warning(
            "Batch link validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100] if e.value else "",
                "message": str(e),
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
    except Exception as e:
        logger.error(
            "Batch link validation failed",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "item_count": len(data.items),
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
                "request_id": request_id,
            },
        )
