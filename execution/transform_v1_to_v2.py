#!/usr/bin/env python3
"""V1 to V2 Schema Transformation Script.

Transforms data from V1 (old app) schema to V2 (new app) schema with
comprehensive error logging as per requirements:

ERROR LOGGING REQUIREMENTS:
- Log method entry/exit at DEBUG level with parameters (sanitized)
- Log all exceptions with full stack trace and context
- Include entity IDs (project_id, page_id) in all service logs
- Log validation failures with field names and rejected values
- Log state transitions (phase changes) at INFO level
- Add timing logs for operations >1 second

V1 Schema (old app):
- projects table with phase1_status, phase2_status, etc.
- project_files table for file path tracking
- JSON files for crawl results, pages, keywords, content

V2 Schema (new app):
- projects table with phase_status JSONB
- crawled_pages table
- page_keywords table
- generated_content table
"""

import json
import logging
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

# Configure logging for standalone script
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("transform_v1_to_v2")

# Slow operation threshold in seconds
SLOW_OPERATION_THRESHOLD_S = 1.0


# =============================================================================
# Helper Functions for Logging
# =============================================================================


def sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Sanitize parameters for logging by masking sensitive values."""
    sensitive_keys = {"password", "secret", "token", "api_key", "credentials"}
    sanitized = {}
    for key, value in params.items():
        if any(s in key.lower() for s in sensitive_keys):
            sanitized[key] = "****"
        elif isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:200] + f"... (truncated, {len(value)} chars)"
        else:
            sanitized[key] = value
    return sanitized


def log_method_entry(method_name: str, **params: Any) -> None:
    """Log method entry at DEBUG level with sanitized parameters."""
    logger.debug(
        f"ENTRY: {method_name}",
        extra={"method": method_name, "params": sanitize_params(params)},
    )


def log_method_exit(method_name: str, success: bool, result_summary: str = "") -> None:
    """Log method exit at DEBUG level."""
    logger.debug(
        f"EXIT: {method_name} (success={success})",
        extra={"method": method_name, "success": success, "result": result_summary},
    )


def log_exception_with_context(
    error: Exception,
    context: dict[str, Any],
    operation: str,
) -> None:
    """Log exception with full stack trace and context."""
    logger.error(
        f"Exception in {operation}: {type(error).__name__}: {error}",
        extra={
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "stack_trace": traceback.format_exc(),
        },
    )


def log_slow_operation(operation: str, duration_s: float, **context: Any) -> None:
    """Log slow operation at WARNING level if duration exceeds threshold."""
    if duration_s > SLOW_OPERATION_THRESHOLD_S:
        logger.warning(
            f"Slow operation: {operation} took {duration_s:.2f}s",
            extra={
                "operation": operation,
                "duration_seconds": round(duration_s, 2),
                "threshold_seconds": SLOW_OPERATION_THRESHOLD_S,
                **context,
            },
        )


def log_validation_failure(
    entity_type: str,
    entity_id: str | None,
    field_name: str,
    rejected_value: Any,
    reason: str,
) -> None:
    """Log validation failure with field names and rejected values."""
    # Truncate large values for logging
    if isinstance(rejected_value, str) and len(rejected_value) > 100:
        rejected_value = rejected_value[:100] + "..."

    logger.warning(
        f"Validation failed for {entity_type}: {field_name}",
        extra={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "field_name": field_name,
            "rejected_value": rejected_value,
            "reason": reason,
        },
    )


def log_phase_transition(
    project_id: str,
    phase_name: str,
    old_status: str | None,
    new_status: str,
) -> None:
    """Log state transitions (phase changes) at INFO level."""
    logger.info(
        f"Phase transition for project {project_id}: {phase_name} {old_status} -> {new_status}",
        extra={
            "project_id": project_id,
            "phase_name": phase_name,
            "old_status": old_status,
            "new_status": new_status,
        },
    )


# =============================================================================
# V2 Schema Definitions (Pydantic models for validation)
# =============================================================================

VALID_PROJECT_STATUSES = frozenset(
    {"active", "completed", "on_hold", "cancelled", "archived"}
)
VALID_PHASE_STATUSES = frozenset(
    {"pending", "in_progress", "completed", "blocked", "skipped"}
)
VALID_PHASES = frozenset(
    {"discovery", "requirements", "implementation", "review", "launch"}
)


class V2ProjectSchema(BaseModel):
    """V2 Project schema for validation."""

    id: str = Field(..., min_length=36, max_length=36)
    name: str = Field(..., min_length=1, max_length=255)
    client_id: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="active")
    phase_status: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_PROJECT_STATUSES:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(VALID_PROJECT_STATUSES))}"
            )
        return v

    @field_validator("phase_status")
    @classmethod
    def validate_phase_status(cls, v: dict[str, Any]) -> dict[str, Any]:
        for phase, data in v.items():
            if phase not in VALID_PHASES:
                raise ValueError(f"Invalid phase '{phase}'")
            if isinstance(data, dict) and "status" in data:
                if data["status"] not in VALID_PHASE_STATUSES:
                    raise ValueError(
                        f"Invalid phase status '{data['status']}' for phase '{phase}'"
                    )
        return v


class V2CrawledPageSchema(BaseModel):
    """V2 CrawledPage schema for validation."""

    id: str = Field(..., min_length=36, max_length=36)
    project_id: str = Field(..., min_length=36, max_length=36)
    normalized_url: str = Field(..., min_length=1)
    raw_url: str | None = None
    category: str | None = None
    labels: list[str] = Field(default_factory=list)
    title: str | None = None
    content_hash: str | None = None
    last_crawled_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("normalized_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL format: {v[:50]}")
        return v


class V2PageKeywordsSchema(BaseModel):
    """V2 PageKeywords schema for validation."""

    id: str = Field(..., min_length=36, max_length=36)
    crawled_page_id: str = Field(..., min_length=36, max_length=36)
    primary_keyword: str = Field(..., min_length=1)
    secondary_keywords: list[str] = Field(default_factory=list)
    search_volume: int | None = None
    difficulty_score: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("difficulty_score")
    @classmethod
    def validate_difficulty(cls, v: int | None) -> int | None:
        if v is not None and (v < 0 or v > 100):
            raise ValueError(f"Difficulty score must be 0-100, got {v}")
        return v


class V2GeneratedContentSchema(BaseModel):
    """V2 GeneratedContent schema for validation."""

    id: str = Field(..., min_length=36, max_length=36)
    crawled_page_id: str = Field(..., min_length=36, max_length=36)
    content_type: str = Field(..., min_length=1)
    content_text: str = Field(..., min_length=1)
    prompt_used: str | None = None
    model_version: str | None = None
    qa_results: dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="draft")
    created_at: str | None = None
    updated_at: str | None = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        valid_types = {"meta_description", "heading", "body_copy", "alt_text"}
        if v not in valid_types:
            raise ValueError(f"Invalid content type '{v}'")
        return v


# =============================================================================
# Transformation Result Tracking
# =============================================================================


@dataclass
class TransformationResult:
    """Track results of transformation operations."""

    entity_type: str
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skipped_count: int = 0
    errors: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def add_error(
        self, entity_id: str, error: str, context: dict[str, Any] | None = None
    ) -> None:
        self.failure_count += 1
        if self.errors is None:
            self.errors = []
        self.errors.append(
            {"entity_id": entity_id, "error": error, "context": context or {}}
        )


# =============================================================================
# V1 to V2 Transformers
# =============================================================================


class SchemaTransformer:
    """Transform V1 schema data to V2 schema."""

    # Mapping from V1 phase names to V2 phase names
    V1_TO_V2_PHASE_MAPPING = {
        "phase1": "discovery",
        "phase2": "requirements",
        "phase3": "implementation",
        "phase4": "review",
        "phase45": "review",  # Sub-phase of review
        "phase46": "review",  # Sub-phase of review
        "phase5": "launch",
        "phase5a": "launch",  # Sub-phase of launch
        "phase5b": "launch",  # Sub-phase of launch
        "phase5c": "launch",  # Sub-phase of launch
    }

    def __init__(self, v1_data_dir: Path, output_dir: Path):
        """Initialize transformer with data directories.

        Args:
            v1_data_dir: Path to V1 data directory
            output_dir: Path to output directory for V2 data
        """
        log_method_entry(
            "SchemaTransformer.__init__",
            v1_data_dir=str(v1_data_dir),
            output_dir=str(output_dir),
        )

        self.v1_data_dir = v1_data_dir
        self.output_dir = output_dir
        self.results: dict[str, TransformationResult] = {}

        log_method_exit("SchemaTransformer.__init__", success=True)

    def transform_all(self) -> dict[str, TransformationResult]:
        """Transform all V1 data to V2 format.

        Returns:
            Dictionary of transformation results by entity type
        """
        log_method_entry("SchemaTransformer.transform_all")
        start_time = time.monotonic()

        try:
            # Transform each entity type
            self.results["projects"] = self.transform_projects()
            self.results["crawled_pages"] = self.transform_crawled_pages()
            self.results["page_keywords"] = self.transform_page_keywords()
            self.results["generated_content"] = self.transform_generated_content()

            duration_s = time.monotonic() - start_time
            log_slow_operation("transform_all", duration_s)

            # Log summary
            total_success = sum(r.success_count for r in self.results.values())
            total_failures = sum(r.failure_count for r in self.results.values())
            logger.info(
                f"Transformation complete: {total_success} successes, {total_failures} failures",
                extra={
                    "total_success": total_success,
                    "total_failures": total_failures,
                    "duration_seconds": round(duration_s, 2),
                    "results_by_type": {
                        k: {
                            "success": v.success_count,
                            "failures": v.failure_count,
                            "skipped": v.skipped_count,
                        }
                        for k, v in self.results.items()
                    },
                },
            )

            log_method_exit(
                "SchemaTransformer.transform_all",
                success=True,
                result_summary=f"{total_success} successes, {total_failures} failures",
            )
            return self.results

        except Exception as e:
            log_exception_with_context(
                e,
                {"v1_data_dir": str(self.v1_data_dir)},
                "SchemaTransformer.transform_all",
            )
            log_method_exit("SchemaTransformer.transform_all", success=False)
            raise

    def transform_projects(self) -> TransformationResult:
        """Transform V1 projects to V2 format.

        Returns:
            TransformationResult with success/failure counts
        """
        log_method_entry("SchemaTransformer.transform_projects")
        start_time = time.monotonic()
        result = TransformationResult(entity_type="projects")

        try:
            # Load V1 projects
            v1_projects_path = self.v1_data_dir / "projects.json"
            if not v1_projects_path.exists():
                logger.warning(
                    f"V1 projects file not found: {v1_projects_path}",
                    extra={"path": str(v1_projects_path)},
                )
                log_method_exit(
                    "SchemaTransformer.transform_projects",
                    success=True,
                    result_summary="No projects file found",
                )
                return result

            with open(v1_projects_path) as f:
                v1_data = json.load(f)

            projects = v1_data.get("projects", [])
            result.total_count = len(projects)

            logger.info(
                f"Transforming {len(projects)} projects",
                extra={"total_projects": len(projects)},
            )

            v2_projects = []
            for v1_project in projects:
                project_id = v1_project.get("id", "unknown")

                try:
                    v2_project = self._transform_single_project(v1_project)
                    v2_projects.append(v2_project)
                    result.success_count += 1

                except ValidationError as e:
                    for error in e.errors():
                        log_validation_failure(
                            entity_type="project",
                            entity_id=project_id,
                            field_name=".".join(str(loc) for loc in error["loc"]),
                            rejected_value=error.get("input"),
                            reason=error["msg"],
                        )
                    result.add_error(project_id, str(e), {"v1_data": v1_project})

                except Exception as e:
                    log_exception_with_context(
                        e,
                        {"project_id": project_id, "v1_data": v1_project},
                        "transform_single_project",
                    )
                    result.add_error(project_id, str(e), {"v1_data": v1_project})

            # Write V2 projects
            self._write_output("projects.json", {"projects": v2_projects})

            duration_s = time.monotonic() - start_time
            log_slow_operation(
                "transform_projects",
                duration_s,
                total_count=result.total_count,
                success_count=result.success_count,
            )

            log_method_exit(
                "SchemaTransformer.transform_projects",
                success=True,
                result_summary=f"{result.success_count}/{result.total_count} succeeded",
            )
            return result

        except Exception as e:
            log_exception_with_context(
                e, {"v1_data_dir": str(self.v1_data_dir)}, "transform_projects"
            )
            log_method_exit("SchemaTransformer.transform_projects", success=False)
            raise

    def _transform_single_project(self, v1_project: dict[str, Any]) -> dict[str, Any]:
        """Transform a single V1 project to V2 format.

        Args:
            v1_project: V1 project data

        Returns:
            V2 project data (validated)
        """
        project_id = v1_project.get("id", "unknown")
        log_method_entry(
            "_transform_single_project",
            project_id=project_id,
            name=v1_project.get("name"),
        )

        # Extract phase statuses from V1 flat fields
        phase_status = self._extract_phase_status(v1_project, project_id)

        # Determine overall status
        status = self._determine_project_status(v1_project, phase_status)

        # Build V2 project
        v2_data = {
            "id": v1_project["id"],
            "name": v1_project.get("name", "Untitled Project"),
            "client_id": v1_project.get("name", "unknown"),  # V1 didn't have client_id
            "status": status,
            "phase_status": phase_status,
            "created_at": v1_project.get("created_at"),
            "updated_at": v1_project.get("updated_at"),
        }

        # Validate with Pydantic
        validated = V2ProjectSchema(**v2_data)

        log_method_exit(
            "_transform_single_project",
            success=True,
            result_summary=f"status={status}",
        )
        return validated.model_dump()

    def _extract_phase_status(
        self, v1_project: dict[str, Any], project_id: str
    ) -> dict[str, Any]:
        """Extract and transform phase statuses from V1 project.

        Args:
            v1_project: V1 project data
            project_id: Project ID for logging

        Returns:
            V2 phase_status JSONB structure
        """
        phase_status: dict[str, dict[str, Any]] = {}

        for v1_phase, v2_phase in self.V1_TO_V2_PHASE_MAPPING.items():
            v1_status_key = f"{v1_phase}_status"
            v1_status = v1_project.get(v1_status_key)

            if v1_status:
                old_status = phase_status.get(v2_phase, {}).get("status")

                # If phase already exists, keep the "best" status
                if v2_phase in phase_status:
                    # Completed > in_progress > pending
                    if v1_status == "completed" or old_status == "completed":
                        new_status = "completed"
                    elif v1_status == "in_progress" or old_status == "in_progress":
                        new_status = "in_progress"
                    else:
                        new_status = v1_status

                    if new_status != old_status:
                        log_phase_transition(
                            project_id, v2_phase, old_status, new_status
                        )
                        phase_status[v2_phase]["status"] = new_status
                else:
                    # Map V1 status to V2 status
                    v2_status = self._map_status(v1_status)
                    phase_status[v2_phase] = {"status": v2_status}
                    log_phase_transition(project_id, v2_phase, None, v2_status)

        return phase_status

    def _map_status(self, v1_status: str) -> str:
        """Map V1 status value to V2 status value."""
        status_mapping = {
            "pending": "pending",
            "in_progress": "in_progress",
            "complete": "completed",
            "completed": "completed",
            "done": "completed",
            "blocked": "blocked",
            "skipped": "skipped",
            "skip": "skipped",
        }
        mapped = status_mapping.get(v1_status.lower(), "pending")
        return mapped

    def _determine_project_status(
        self, v1_project: dict[str, Any], phase_status: dict[str, Any]
    ) -> str:
        """Determine overall project status based on phase statuses."""
        # Check if all phases are completed
        if phase_status:
            all_completed = all(
                p.get("status") == "completed" for p in phase_status.values()
            )
            if all_completed:
                return "completed"

            any_in_progress = any(
                p.get("status") == "in_progress" for p in phase_status.values()
            )
            if any_in_progress:
                return "active"

        return "active"

    def transform_crawled_pages(self) -> TransformationResult:
        """Transform V1 crawled pages to V2 format.

        Returns:
            TransformationResult with success/failure counts
        """
        log_method_entry("SchemaTransformer.transform_crawled_pages")
        start_time = time.monotonic()
        result = TransformationResult(entity_type="crawled_pages")

        try:
            all_pages = []

            # Find all project directories
            projects_dir = self.v1_data_dir / "projects"
            if not projects_dir.exists():
                logger.warning(
                    "No projects directory found",
                    extra={"path": str(projects_dir)},
                )
                return result

            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                project_id = project_dir.name
                pages = self._transform_project_pages(project_id, project_dir, result)
                all_pages.extend(pages)

            # Write V2 crawled pages
            self._write_output("crawled_pages.json", {"pages": all_pages})

            duration_s = time.monotonic() - start_time
            log_slow_operation(
                "transform_crawled_pages",
                duration_s,
                total_count=result.total_count,
                success_count=result.success_count,
            )

            log_method_exit(
                "SchemaTransformer.transform_crawled_pages",
                success=True,
                result_summary=f"{result.success_count}/{result.total_count} succeeded",
            )
            return result

        except Exception as e:
            log_exception_with_context(
                e, {"v1_data_dir": str(self.v1_data_dir)}, "transform_crawled_pages"
            )
            log_method_exit("SchemaTransformer.transform_crawled_pages", success=False)
            raise

    def _transform_project_pages(
        self, project_id: str, project_dir: Path, result: TransformationResult
    ) -> list[dict[str, Any]]:
        """Transform pages for a single project.

        Args:
            project_id: Project ID
            project_dir: Path to project directory
            result: TransformationResult to update

        Returns:
            List of V2 crawled page data
        """
        log_method_entry(
            "_transform_project_pages",
            project_id=project_id,
            project_dir=str(project_dir),
        )

        v2_pages = []

        # Try different V1 page file names
        page_files = [
            "crawl_results.json",
            "categorized_pages.json",
            "labeled_pages.json",
        ]

        for page_file in page_files:
            page_path = project_dir / page_file
            if page_path.exists():
                try:
                    with open(page_path) as f:
                        v1_pages = json.load(f)

                    if isinstance(v1_pages, dict):
                        v1_pages = v1_pages.get("pages", [])

                    for v1_page in v1_pages:
                        result.total_count += 1
                        page_id = v1_page.get("id", f"page_{result.total_count}")

                        try:
                            v2_page = self._transform_single_page(
                                v1_page, project_id, page_id
                            )
                            v2_pages.append(v2_page)
                            result.success_count += 1

                        except ValidationError as e:
                            for error in e.errors():
                                log_validation_failure(
                                    entity_type="crawled_page",
                                    entity_id=page_id,
                                    field_name=".".join(
                                        str(loc) for loc in error["loc"]
                                    ),
                                    rejected_value=error.get("input"),
                                    reason=error["msg"],
                                )
                            result.add_error(
                                page_id, str(e), {"project_id": project_id}
                            )

                        except Exception as e:
                            log_exception_with_context(
                                e,
                                {"project_id": project_id, "page_id": page_id},
                                "_transform_single_page",
                            )
                            result.add_error(
                                page_id, str(e), {"project_id": project_id}
                            )

                    # Only process first found file
                    break

                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to parse {page_path}: {e}",
                        extra={
                            "project_id": project_id,
                            "file": str(page_path),
                            "error": str(e),
                        },
                    )

        log_method_exit(
            "_transform_project_pages",
            success=True,
            result_summary=f"{len(v2_pages)} pages transformed",
        )
        return v2_pages

    def _transform_single_page(
        self, v1_page: dict[str, Any], project_id: str, page_id: str
    ) -> dict[str, Any]:
        """Transform a single V1 page to V2 format.

        Args:
            v1_page: V1 page data
            project_id: Parent project ID
            page_id: Page ID

        Returns:
            V2 crawled page data (validated)
        """
        import uuid

        # Normalize URL
        url = v1_page.get("url", v1_page.get("normalized_url", ""))
        if not url:
            raise ValueError("Page has no URL")

        # Generate UUID if not present
        if not v1_page.get("id") or len(str(v1_page.get("id", ""))) < 36:
            page_id = str(uuid.uuid4())
        else:
            page_id = str(v1_page["id"])

        # Extract labels from V1 data
        labels = []
        if v1_page.get("label"):
            labels.append(v1_page["label"])
        if v1_page.get("labels"):
            labels.extend(v1_page["labels"])

        v2_data = {
            "id": page_id,
            "project_id": project_id,
            "normalized_url": url,
            "raw_url": v1_page.get("original_url"),
            "category": v1_page.get("category"),
            "labels": labels,
            "title": v1_page.get("title"),
            "content_hash": v1_page.get("content_hash"),
            "last_crawled_at": v1_page.get("crawled_at"),
            "created_at": v1_page.get("created_at"),
            "updated_at": v1_page.get("updated_at"),
        }

        validated = V2CrawledPageSchema(**v2_data)
        return validated.model_dump()

    def transform_page_keywords(self) -> TransformationResult:
        """Transform V1 keyword data to V2 format.

        Returns:
            TransformationResult with success/failure counts
        """
        log_method_entry("SchemaTransformer.transform_page_keywords")
        start_time = time.monotonic()
        result = TransformationResult(entity_type="page_keywords")

        try:
            all_keywords = []

            projects_dir = self.v1_data_dir / "projects"
            if not projects_dir.exists():
                return result

            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                project_id = project_dir.name
                keywords = self._transform_project_keywords(
                    project_id, project_dir, result
                )
                all_keywords.extend(keywords)

            self._write_output("page_keywords.json", {"keywords": all_keywords})

            duration_s = time.monotonic() - start_time
            log_slow_operation(
                "transform_page_keywords",
                duration_s,
                total_count=result.total_count,
            )

            log_method_exit(
                "SchemaTransformer.transform_page_keywords",
                success=True,
                result_summary=f"{result.success_count}/{result.total_count} succeeded",
            )
            return result

        except Exception as e:
            log_exception_with_context(
                e, {"v1_data_dir": str(self.v1_data_dir)}, "transform_page_keywords"
            )
            log_method_exit("SchemaTransformer.transform_page_keywords", success=False)
            raise

    def _transform_project_keywords(
        self, project_id: str, project_dir: Path, result: TransformationResult
    ) -> list[dict[str, Any]]:
        """Transform keywords for a single project."""
        import uuid

        v2_keywords = []
        keyword_path = project_dir / "keyword_enriched.json"

        if not keyword_path.exists():
            keyword_path = project_dir / "keyword_with_paa.json"

        if not keyword_path.exists():
            return []

        try:
            with open(keyword_path) as f:
                v1_data = json.load(f)

            pages_with_keywords = (
                v1_data if isinstance(v1_data, list) else v1_data.get("pages", [])
            )

            for page in pages_with_keywords:
                result.total_count += 1
                page_id = page.get("page_id", page.get("id"))

                if not page_id:
                    result.skipped_count += 1
                    continue

                try:
                    keyword_id = str(uuid.uuid4())
                    primary = page.get("primary_keyword", page.get("keyword", ""))
                    secondary = page.get("secondary_keywords", [])
                    if isinstance(secondary, str):
                        secondary = [secondary]

                    v2_data = {
                        "id": keyword_id,
                        "crawled_page_id": page_id,
                        "primary_keyword": primary or "unknown",
                        "secondary_keywords": secondary,
                        "search_volume": page.get("search_volume"),
                        "difficulty_score": page.get(
                            "difficulty", page.get("keyword_difficulty")
                        ),
                    }

                    validated = V2PageKeywordsSchema(**v2_data)
                    v2_keywords.append(validated.model_dump())
                    result.success_count += 1

                except ValidationError as e:
                    for error in e.errors():
                        log_validation_failure(
                            entity_type="page_keywords",
                            entity_id=page_id,
                            field_name=".".join(str(loc) for loc in error["loc"]),
                            rejected_value=error.get("input"),
                            reason=error["msg"],
                        )
                    result.add_error(page_id, str(e), {"project_id": project_id})

                except Exception as e:
                    log_exception_with_context(
                        e,
                        {"project_id": project_id, "page_id": page_id},
                        "_transform_project_keywords",
                    )
                    result.add_error(page_id, str(e), {"project_id": project_id})

        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse {keyword_path}: {e}",
                extra={
                    "project_id": project_id,
                    "file": str(keyword_path),
                    "error": str(e),
                },
            )

        return v2_keywords

    def transform_generated_content(self) -> TransformationResult:
        """Transform V1 generated content to V2 format.

        Returns:
            TransformationResult with success/failure counts
        """
        log_method_entry("SchemaTransformer.transform_generated_content")
        start_time = time.monotonic()
        result = TransformationResult(entity_type="generated_content")

        try:
            all_content = []

            projects_dir = self.v1_data_dir / "projects"
            if not projects_dir.exists():
                return result

            for project_dir in projects_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                project_id = project_dir.name
                content = self._transform_project_content(
                    project_id, project_dir, result
                )
                all_content.extend(content)

            self._write_output("generated_content.json", {"content": all_content})

            duration_s = time.monotonic() - start_time
            log_slow_operation(
                "transform_generated_content",
                duration_s,
                total_count=result.total_count,
            )

            log_method_exit(
                "SchemaTransformer.transform_generated_content",
                success=True,
                result_summary=f"{result.success_count}/{result.total_count} succeeded",
            )
            return result

        except Exception as e:
            log_exception_with_context(
                e, {"v1_data_dir": str(self.v1_data_dir)}, "transform_generated_content"
            )
            log_method_exit(
                "SchemaTransformer.transform_generated_content", success=False
            )
            raise

    def _transform_project_content(
        self, project_id: str, project_dir: Path, result: TransformationResult
    ) -> list[dict[str, Any]]:
        """Transform generated content for a single project."""
        import uuid

        v2_content = []
        content_files = [
            ("draft_content.json", "draft"),
            ("validated_content.json", "approved"),
            ("collection_content.json", "draft"),
        ]

        for filename, default_status in content_files:
            content_path = project_dir / filename

            if not content_path.exists():
                continue

            try:
                with open(content_path) as f:
                    v1_data = json.load(f)

                items = (
                    v1_data if isinstance(v1_data, list) else v1_data.get("content", [])
                )

                for item in items:
                    result.total_count += 1
                    page_id = item.get("page_id", item.get("id"))

                    if not page_id:
                        result.skipped_count += 1
                        continue

                    # Extract content fields
                    content_types = [
                        ("meta_description", item.get("meta_description")),
                        ("heading", item.get("h1", item.get("heading"))),
                        ("body_copy", item.get("body", item.get("content"))),
                    ]

                    for content_type, content_text in content_types:
                        if not content_text:
                            continue

                        try:
                            content_id = str(uuid.uuid4())
                            v2_data = {
                                "id": content_id,
                                "crawled_page_id": page_id,
                                "content_type": content_type,
                                "content_text": content_text,
                                "prompt_used": item.get("prompt_id"),
                                "model_version": item.get("model"),
                                "qa_results": item.get("qa_results", {}),
                                "status": item.get("status", default_status),
                            }

                            validated = V2GeneratedContentSchema(**v2_data)
                            v2_content.append(validated.model_dump())
                            result.success_count += 1

                        except ValidationError as e:
                            for error in e.errors():
                                log_validation_failure(
                                    entity_type="generated_content",
                                    entity_id=page_id,
                                    field_name=".".join(
                                        str(loc) for loc in error["loc"]
                                    ),
                                    rejected_value=error.get("input"),
                                    reason=error["msg"],
                                )
                            result.add_error(
                                page_id, str(e), {"project_id": project_id}
                            )

                        except Exception as e:
                            log_exception_with_context(
                                e,
                                {"project_id": project_id, "page_id": page_id},
                                "_transform_project_content",
                            )
                            result.add_error(
                                page_id, str(e), {"project_id": project_id}
                            )

            except json.JSONDecodeError as e:
                logger.error(
                    f"Failed to parse {content_path}: {e}",
                    extra={
                        "project_id": project_id,
                        "file": str(content_path),
                        "error": str(e),
                    },
                )

        return v2_content

    def _write_output(self, filename: str, data: dict[str, Any]) -> None:
        """Write output file with logging."""
        log_method_entry("_write_output", filename=filename)
        start_time = time.monotonic()

        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_path = self.output_dir / filename

            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, default=str)

            duration_s = time.monotonic() - start_time
            log_slow_operation("_write_output", duration_s, filename=filename)

            logger.info(
                f"Wrote output file: {output_path}",
                extra={
                    "filename": filename,
                    "path": str(output_path),
                    "size_bytes": output_path.stat().st_size,
                },
            )
            log_method_exit("_write_output", success=True)

        except Exception as e:
            log_exception_with_context(
                e,
                {"filename": filename, "output_dir": str(self.output_dir)},
                "_write_output",
            )
            raise


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """Main entry point for V1 to V2 transformation.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    log_method_entry("main")
    start_time = time.monotonic()

    # Default paths (can be overridden via command line args)
    v1_data_dir = Path(".tmp")
    output_dir = Path(".tmp/v2_export")

    # Parse command line args if provided
    if len(sys.argv) > 1:
        v1_data_dir = Path(sys.argv[1])
    if len(sys.argv) > 2:
        output_dir = Path(sys.argv[2])

    logger.info(
        "Starting V1 to V2 schema transformation",
        extra={
            "v1_data_dir": str(v1_data_dir),
            "output_dir": str(output_dir),
        },
    )

    try:
        transformer = SchemaTransformer(v1_data_dir, output_dir)
        results = transformer.transform_all()

        # Check for failures
        total_failures = sum(r.failure_count for r in results.values())
        if total_failures > 0:
            logger.warning(
                f"Transformation completed with {total_failures} failures",
                extra={
                    "total_failures": total_failures,
                    "results": {k: v.failure_count for k, v in results.items()},
                },
            )

        duration_s = time.monotonic() - start_time
        log_slow_operation("main", duration_s)

        log_method_exit(
            "main",
            success=True,
            result_summary=f"Completed in {duration_s:.2f}s",
        )
        return 0

    except Exception as e:
        log_exception_with_context(
            e,
            {"v1_data_dir": str(v1_data_dir), "output_dir": str(output_dir)},
            "main",
        )
        log_method_exit("main", success=False)
        return 1


if __name__ == "__main__":
    sys.exit(main())
