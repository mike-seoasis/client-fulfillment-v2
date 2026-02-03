"""Pydantic schemas for ProjectFile validation.

Defines response models for file upload API endpoints.
No Create schema needed - files come as multipart/form-data, not JSON.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectFileResponse(BaseModel):
    """Schema for project file response."""

    id: str = Field(..., description="File UUID")
    project_id: str = Field(..., description="Parent project UUID")
    filename: str = Field(..., description="Original filename as uploaded")
    content_type: str = Field(..., description="MIME type of the file")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")

    model_config = ConfigDict(from_attributes=True)


class ProjectFileList(BaseModel):
    """Schema for list of project files."""

    items: list[ProjectFileResponse] = Field(..., description="List of project files")
    total: int = Field(..., ge=0, description="Total count of files")
