"""NLPAnalysisCache model for caching NLP analysis results on competitor data.

The NLPAnalysisCache model stores cached NLP analysis results:
- competitor_url: The competitor URL that was analyzed
- analysis_type: Type of NLP analysis (sentiment, entities, keywords, topics, etc.)
- analysis_results: JSONB object containing the analysis output
- Foreign key relationship to Project
- TTL-based caching with expires_at timestamp
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NLPAnalysisCache(Base):
    """NLPAnalysisCache model for caching NLP analysis results on competitor data.

    Attributes:
        id: UUID primary key
        project_id: Reference to the parent project
        competitor_url: The competitor URL that was analyzed
        analysis_type: Type of NLP analysis performed (sentiment, entities, keywords, topics)
        analysis_results: JSONB object containing the cached analysis output
        model_version: Version of the NLP model used for analysis
        content_hash: Hash of the content that was analyzed (for cache invalidation)
        expires_at: Timestamp when the cache entry expires
        hit_count: Number of times this cache entry has been accessed
        created_at: Timestamp when record was created
        updated_at: Timestamp when record was last updated

    Example analysis_results structure:
        {
            "sentiment": {"score": 0.85, "label": "positive"},
            "entities": [{"text": "Acme Corp", "type": "ORG", "confidence": 0.95}],
            "keywords": ["product", "service", "quality"],
            "topics": [{"name": "pricing", "relevance": 0.8}],
            "summary": "Brief summary of the analyzed content"
        }
    """

    __tablename__ = "nlp_analysis_cache"

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

    competitor_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        index=True,
    )

    analysis_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    analysis_results: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    model_version: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    hit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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
        return f"<NLPAnalysisCache(id={self.id!r}, type={self.analysis_type!r}, url={self.competitor_url[:50]!r})>"
