"""PagePAA model for storing People Also Ask (PAA) enrichment data.

The PagePAA model represents PAA questions related to a page's keywords:
- question: The PAA question from search results
- answer_snippet: Brief answer snippet if available
- related_questions: JSONB array of related follow-up questions
- Foreign key relationship to CrawledPage
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PagePAA(Base):
    """PagePAA model for storing People Also Ask enrichment data.

    Attributes:
        id: UUID primary key
        crawled_page_id: Reference to the parent crawled page
        question: The PAA question from search results
        answer_snippet: Brief answer snippet if available from search
        source_url: URL of the source providing the answer
        related_questions: JSONB array of related follow-up PAA questions
        position: Position in PAA results (1-based)
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example related_questions structure:
        ["Why is X important?", "How does X work?", "What are the benefits of X?"]
    """

    __tablename__ = "page_paa"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    crawled_page_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    answer_snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    related_questions: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )

    position: Mapped[int | None] = mapped_column(
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
        return f"<PagePAA(id={self.id!r}, question={self.question[:50]!r}...)>"
