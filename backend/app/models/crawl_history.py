"""CrawlHistory model for tracking crawl job execution history.

The CrawlHistory model represents a single crawl job execution:
- status: Job status (pending, running, completed, failed, cancelled)
- stats: JSONB object for crawl statistics (pages crawled, errors, timing)
- error_log: JSONB array for storing error details
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CrawlHistory(Base):
    """CrawlHistory model for tracking crawl job execution history.

    Attributes:
        id: UUID primary key
        schedule_id: Reference to the parent crawl schedule (nullable for manual runs)
        project_id: Reference to the project being crawled
        status: Job status ('pending', 'running', 'completed', 'failed', 'cancelled')
        trigger_type: How the crawl was triggered ('scheduled', 'manual', 'webhook')
        started_at: When the crawl job started
        completed_at: When the crawl job finished (success or failure)
        pages_crawled: Total number of pages successfully crawled
        pages_failed: Number of pages that failed to crawl
        stats: JSONB object for detailed crawl statistics
        error_log: JSONB array of error entries during crawl
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example stats structure:
        {
            "total_requests": 150,
            "successful_requests": 145,
            "failed_requests": 5,
            "avg_response_time_ms": 250,
            "total_bytes_downloaded": 15728640,
            "new_pages": 10,
            "updated_pages": 90,
            "unchanged_pages": 45
        }

    Example error_log structure:
        [
            {"url": "https://example.com/broken", "error": "404 Not Found", "timestamp": "2026-02-01T12:00:00Z"},
            {"url": "https://example.com/timeout", "error": "Connection timeout", "timestamp": "2026-02-01T12:01:00Z"}
        ]
    """

    __tablename__ = "crawl_history"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    schedule_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    trigger_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="manual",
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    pages_crawled: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    pages_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    error_log: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
        return f"<CrawlHistory(id={self.id!r}, project_id={self.project_id!r}, status={self.status!r})>"
