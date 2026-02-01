"""LLM QA Fix phase API endpoints for projects.

Provides Phase 5C LLM-powered content fixes for a project:
- POST /api/v1/projects/{project_id}/phases/llm_qa_fix/fix - Fix single content
- POST /api/v1/projects/{project_id}/phases/llm_qa_fix/batch - Fix multiple contents

The LLM QA Fix service handles patterns that regex might miss,
making minimal corrections while preserving structure and links.

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
from app.schemas.llm_qa_fix import (
    FixApplied,
    LLMQAFixBatchItemResponse,
    LLMQAFixBatchRequest,
    LLMQAFixBatchResponse,
    LLMQAFixRequest,
    LLMQAFixResponse,
)
from app.services.llm_qa_fix import (
    IssueToFix as ServiceIssueToFix,
)
from app.services.llm_qa_fix import (
    LLMQAFixInput,
    LLMQAFixResult,
    LLMQAFixValidationError,
    get_llm_qa_fix_service,
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


def _convert_result_to_response(
    result: LLMQAFixResult,
) -> LLMQAFixResponse:
    """Convert service result to API response schema."""
    return LLMQAFixResponse(
        success=result.success,
        fixed_bottom_description=result.fixed_bottom_description,
        issues_found=result.issues_found,
        fixes_applied=[
            FixApplied(
                issue_type=f.issue_type,
                original_text=f.original_text,
                fixed_text=f.fixed_text,
                explanation=f.explanation,
            )
            for f in result.fixes_applied
        ],
        fix_count=result.fix_count,
        content_id=result.content_id,
        page_id=result.page_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        error=result.error,
        duration_ms=round(result.duration_ms, 2),
    )


def _convert_request_to_input(
    data: LLMQAFixRequest,
    project_id: str,
) -> LLMQAFixInput:
    """Convert API request to service input."""
    return LLMQAFixInput(
        h1=data.h1,
        title_tag=data.title_tag,
        meta_description=data.meta_description,
        top_description=data.top_description,
        bottom_description=data.bottom_description,
        issues=[
            ServiceIssueToFix(
                issue_type=issue.issue_type,
                matched_text=issue.matched_text,
                position=issue.position,
                suggestion=issue.suggestion,
            )
            for issue in data.issues
        ],
        primary_keyword=data.primary_keyword,
        project_id=project_id,
        page_id=data.page_id,
        content_id=data.content_id,
    )


@router.post(
    "/fix",
    response_model=LLMQAFixResponse,
    summary="Fix content using LLM",
    description="Run Phase 5C LLM QA fix to correct AI trope patterns with minimal changes.",
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
                        "error": "Validation failed: bottom_description cannot be empty",
                        "code": "VALIDATION_ERROR",
                        "request_id": "<request_id>",
                    }
                }
            },
        },
    },
)
async def fix_content(
    request: Request,
    project_id: str,
    data: LLMQAFixRequest,
    session: AsyncSession = Depends(get_session),
) -> LLMQAFixResponse | JSONResponse:
    """Fix content issues using LLM.

    Phase 5C LLM QA fix for patterns that regex might miss:
    1. Receives content and specific issues to fix
    2. Uses Claude to make minimal corrections
    3. Preserves structure, links, and word count
    4. Returns fixed content with change details

    Common issues fixed:
    - Negation patterns ("aren't just X, they're Y")
    - Banned words (delve, unlock, journey, etc.)
    - Em dashes (—)
    - Triplet patterns ("Fast. Simple. Powerful.")
    - Rhetorical question openers
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "LLM QA fix request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "issue_count": len(data.issues),
            "bottom_description_length": len(data.bottom_description),
            "primary_keyword": data.primary_keyword[:50],
            "page_id": data.page_id,
            "content_id": data.content_id,
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_llm_qa_fix_service()
        input_data = _convert_request_to_input(data, project_id)
        result = await service.fix_content(input_data)

        duration_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "LLM QA fix complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "content_id": data.content_id,
                "success": result.success,
                "fix_count": result.fix_count,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return _convert_result_to_response(result)

    except LLMQAFixValidationError as e:
        logger.warning(
            "LLM QA fix validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
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
            "LLM QA fix failed",
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
    response_model=LLMQAFixBatchResponse,
    summary="Batch fix content using LLM",
    description="Fix multiple content items. Max 10 items per batch due to LLM costs.",
    responses={
        404: {"description": "Project not found"},
        400: {"description": "Validation error"},
    },
)
async def fix_content_batch(
    request: Request,
    project_id: str,
    data: LLMQAFixBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> LLMQAFixBatchResponse | JSONResponse:
    """Fix multiple content items using LLM.

    Runs Phase 5C LLM QA fix on each item with controlled concurrency.
    Returns aggregate statistics and individual results.

    Note: Limited to 10 items per batch due to LLM API costs.
    """
    request_id = _get_request_id(request)
    start_time = time.monotonic()

    logger.debug(
        "LLM QA fix batch request",
        extra={
            "request_id": request_id,
            "project_id": project_id,
            "item_count": len(data.items),
        },
    )

    # Verify project exists
    not_found = await _verify_project_exists(project_id, session, request_id)
    if not_found:
        return not_found

    try:
        service = get_llm_qa_fix_service()

        # Convert batch items to input data
        inputs: list[LLMQAFixInput] = []
        for item in data.items:
            inputs.append(
                LLMQAFixInput(
                    h1=item.h1,
                    title_tag=item.title_tag,
                    meta_description=item.meta_description,
                    top_description=item.top_description,
                    bottom_description=item.bottom_description,
                    issues=[
                        ServiceIssueToFix(
                            issue_type=issue.issue_type,
                            matched_text=issue.matched_text,
                            position=issue.position,
                            suggestion=issue.suggestion,
                        )
                        for issue in item.issues
                    ],
                    primary_keyword=item.primary_keyword,
                    project_id=project_id,
                    page_id=item.page_id,
                    content_id=item.content_id,
                )
            )

        results = await service.fix_content_batch(
            inputs=inputs,
            project_id=project_id,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        # Build response items and calculate stats
        items: list[LLMQAFixBatchItemResponse] = []
        success_count = 0
        error_count = 0
        total_fixes = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for result in results:
            items.append(
                LLMQAFixBatchItemResponse(
                    content_id=result.content_id,
                    page_id=result.page_id,
                    success=result.success,
                    fix_count=result.fix_count,
                    fixed_bottom_description=result.fixed_bottom_description,
                    error=result.error,
                )
            )

            if result.success:
                success_count += 1
                total_fixes += result.fix_count
            else:
                error_count += 1

            if result.input_tokens:
                total_input_tokens += result.input_tokens
            if result.output_tokens:
                total_output_tokens += result.output_tokens

        logger.info(
            "LLM QA fix batch complete",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "total_items": len(data.items),
                "success_count": success_count,
                "error_count": error_count,
                "total_fixes": total_fixes,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "duration_ms": round(duration_ms, 2),
            },
        )

        return LLMQAFixBatchResponse(
            success=True,
            results=items,
            total_items=len(data.items),
            success_count=success_count,
            error_count=error_count,
            total_fixes=total_fixes,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            error=None,
            duration_ms=round(duration_ms, 2),
        )

    except LLMQAFixValidationError as e:
        logger.warning(
            "LLM QA fix batch validation error",
            extra={
                "request_id": request_id,
                "project_id": project_id,
                "field": e.field_name,
                "value": str(e.value)[:100],
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
            "LLM QA fix batch failed",
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
