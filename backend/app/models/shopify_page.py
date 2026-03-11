"""ShopifyPage model for synced Shopify store page inventory.

Stores collections, products, articles, and pages imported from a
connected Shopify store via the Admin GraphQL API.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShopifyPage(Base):
    """A single page/product/collection/article synced from Shopify."""

    __tablename__ = "shopify_pages"

    __table_args__ = (
        UniqueConstraint(
            "project_id", "shopify_id", name="uq_shopify_pages_project_shopify"
        ),
        Index(
            "ix_shopify_pages_project_type_deleted",
            "project_id",
            "page_type",
            "is_deleted",
        ),
    )

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
    )

    shopify_id: Mapped[str] = mapped_column(Text, nullable=False)
    page_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    handle: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Type-specific fields
    product_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blog_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)

    # Sync metadata
    shopify_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
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

    # Relationship
    project = relationship("Project", back_populates="shopify_pages")

    def __repr__(self) -> str:
        return (
            f"<ShopifyPage(id={self.id!r}, type={self.page_type!r}, "
            f"title={self.title!r})>"
        )
