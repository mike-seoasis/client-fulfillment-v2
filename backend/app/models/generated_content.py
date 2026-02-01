"""GeneratedContent model with QA results JSONB field.

The GeneratedContent model stores AI-generated content for crawled pages:
- Content text and type (meta description, heading, body copy, etc.)
- QA results stored as JSONB for flexible quality assessment tracking
- Foreign key to crawled_pages table
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GeneratedContent(Base):
    """Generated content model for AI-generated page content.

    Attributes:
        id: UUID primary key
        crawled_page_id: Foreign key to crawled_pages table
        content_type: Type of content (e.g., 'meta_description', 'heading', 'body_copy', 'alt_text')
        content_text: The generated content text
        prompt_used: The prompt template or identifier used to generate content
        model_version: AI model version used for generation
        qa_results: JSONB field storing QA check results
        status: Content status (e.g., 'draft', 'approved', 'rejected', 'published')
        created_at: Timestamp when content was generated
        updated_at: Timestamp when content was last updated

    Example qa_results structure:
        {
            "checks": [
                {
                    "name": "length_check",
                    "passed": true,
                    "message": "Content length within acceptable range",
                    "value": 155,
                    "threshold": {"min": 120, "max": 160}
                },
                {
                    "name": "keyword_presence",
                    "passed": true,
                    "message": "Primary keyword found in content",
                    "keyword": "client onboarding"
                },
                {
                    "name": "readability_score",
                    "passed": false,
                    "message": "Readability score below threshold",
                    "value": 45,
                    "threshold": 60
                }
            ],
            "overall_score": 0.67,
            "passed": false,
            "reviewed_by": null,
            "reviewed_at": null,
            "notes": "Needs readability improvement"
        }
    """

    __tablename__ = "generated_content"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    crawled_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("crawled_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    content_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    prompt_used: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    qa_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<GeneratedContent(id={self.id!r}, type={self.content_type!r}, status={self.status!r})>"
