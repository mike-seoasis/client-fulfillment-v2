"""BrandConfig model with V2 schema JSONB field.

The BrandConfig model stores brand configuration for a project:
- Basic brand information (name, domain)
- V2 schema stored as JSONB for flexible brand settings
- Foreign key to projects table
- Timestamps for auditing
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BrandConfig(Base):
    """Brand configuration model for client onboarding.

    Attributes:
        id: UUID primary key
        project_id: Foreign key to projects table
        brand_name: Display name of the brand
        domain: Primary domain for the brand
        v2_schema: JSONB field storing V2 brand configuration schema
        created_at: Timestamp when config was created
        updated_at: Timestamp when config was last updated

    Example v2_schema structure:
        {
            "colors": {
                "primary": "#FF5733",
                "secondary": "#33C1FF",
                "accent": "#FFC300"
            },
            "typography": {
                "heading_font": "Inter",
                "body_font": "Open Sans",
                "base_size": 16
            },
            "logo": {
                "url": "https://cdn.example.com/logo.svg",
                "alt_text": "Brand Logo"
            },
            "voice": {
                "tone": "professional",
                "personality": ["helpful", "warm", "knowledgeable"]
            },
            "social": {
                "twitter": "@brand",
                "linkedin": "company/brand"
            },
            "version": "2.0"
        }
    """

    __tablename__ = "brand_configs"

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

    brand_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    domain: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        index=True,
    )

    v2_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
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
        return f"<BrandConfig(id={self.id!r}, brand_name={self.brand_name!r}, project_id={self.project_id!r})>"
