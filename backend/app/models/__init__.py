"""Models layer - SQLAlchemy ORM models.

Models define the database schema and relationships.
All models inherit from the Base class defined in core.database.
"""

from app.core.database import Base
from app.models.brand_config import BrandConfig
from app.models.crawl_history import CrawlHistory
from app.models.crawl_schedule import CrawlSchedule
from app.models.crawled_page import CrawledPage
from app.models.generated_content import GeneratedContent
from app.models.nlp_analysis_cache import NLPAnalysisCache
from app.models.page_keywords import PageKeywords
from app.models.page_paa import PagePAA
from app.models.project import Project

__all__ = [
    "Base",
    "BrandConfig",
    "CrawlHistory",
    "CrawlSchedule",
    "CrawledPage",
    "GeneratedContent",
    "NLPAnalysisCache",
    "PageKeywords",
    "PagePAA",
    "Project",
]
