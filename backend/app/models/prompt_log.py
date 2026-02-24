"""PromptLog model for persisting all prompts sent to Claude.

The PromptLog model stores each prompt/response exchange during content generation:
- page_content_id: FK to page_contents (many logs per page content)
- step: Pipeline step name (e.g. 'content_writing', 'qa_check')
- role: Message role ('system' or 'user')
- prompt_text: The prompt sent to Claude
- response_text: Claude's response (nullable, may be pending)
- model: Claude model identifier used
- input_tokens/output_tokens: Token usage tracking
- duration_ms: Time taken for the API call
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.page_content import PageContent


class PromptLog(Base):
    """PromptLog model for persisting all prompts sent to Claude.

    Attributes:
        id: UUID primary key
        page_content_id: FK to page_contents
        step: Pipeline step name (e.g. 'content_writing')
        role: Message role ('system' or 'user')
        prompt_text: The prompt text sent
        response_text: Claude's response text (nullable)
        model: Claude model identifier (nullable)
        input_tokens: Number of input tokens (nullable)
        output_tokens: Number of output tokens (nullable)
        duration_ms: API call duration in milliseconds (nullable)
        created_at: Timestamp when record was created
    """

    __tablename__ = "prompt_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )

    page_content_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("page_contents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    step: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    prompt_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    response_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    duration_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("now()"),
    )

    # Relationship to PageContent (many-to-one)
    page_content: Mapped["PageContent"] = relationship(
        "PageContent",
        back_populates="prompt_logs",
    )

    def __repr__(self) -> str:
        return f"<PromptLog(id={self.id!r}, step={self.step!r}, role={self.role!r})>"
