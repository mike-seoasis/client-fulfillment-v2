"""CrawlSchedule model for managing scheduled crawl jobs.

The CrawlSchedule model represents a scheduled crawl configuration for a project:
- schedule_type: Type of schedule (manual, daily, weekly, monthly)
- cron_expression: Optional cron expression for custom schedules
- config: JSONB object for flexible schedule configuration (depth, selectors, etc.)
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CrawlSchedule(Base):
    """CrawlSchedule model for managing scheduled crawl jobs.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        schedule_type: Type of schedule ('manual', 'daily', 'weekly', 'monthly', 'cron')
        cron_expression: Cron expression for custom schedules (e.g., '0 2 * * *')
        start_url: The URL to start crawling from
        max_pages: Maximum number of pages to crawl per run
        max_depth: Maximum crawl depth from start URL
        config: JSONB object for additional configuration (selectors, exclusions, etc.)
        is_active: Whether the schedule is currently active
        last_run_at: When the schedule was last executed
        next_run_at: When the schedule is next expected to run
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example config structure:
        {
            "include_patterns": ["/**/products/*"],
            "exclude_patterns": ["/admin/*", "/api/*"],
            "respect_robots_txt": true,
            "follow_external_links": false,
            "extract_selectors": {"title": "h1", "price": ".product-price"}
        }
    """

    __tablename__ = "crawl_schedules"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )

    schedule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    cron_expression: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    start_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    max_pages: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=100,
    )

    max_depth: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=3,
    )

    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
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
        return f"<CrawlSchedule(id={self.id!r}, project_id={self.project_id!r}, type={self.schedule_type!r})>"
