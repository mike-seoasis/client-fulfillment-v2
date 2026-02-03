"""ProjectFile model for storing uploaded brand documents.

The ProjectFile model represents files uploaded as part of brand configuration:
- File metadata (filename, content type, size)
- S3 storage reference
- Extracted text for AI processing
- Foreign key to projects table
- Timestamps for auditing
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectFile(Base):
    """Project file model for uploaded brand documents.

    Attributes:
        id: UUID primary key
        project_id: Foreign key to projects table (cascade delete)
        filename: Original filename as uploaded
        content_type: MIME type of the file (e.g., 'application/pdf')
        s3_key: Storage key for S3/compatible object storage
        extracted_text: Text extracted from the file for AI processing (nullable)
        file_size: Size of the file in bytes
        created_at: Timestamp when file was uploaded
    """

    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    s3_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    def __repr__(self) -> str:
        return f"<ProjectFile(id={self.id!r}, filename={self.filename!r}, project_id={self.project_id!r})>"
