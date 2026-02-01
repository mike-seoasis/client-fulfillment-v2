"""Repositories layer - Data access and persistence.

Repositories handle all database operations using SQLAlchemy.
They abstract the database implementation from the service layer.
"""

from app.repositories.crawl import CrawlRepository
from app.repositories.project import ProjectRepository

__all__ = ["CrawlRepository", "ProjectRepository"]
