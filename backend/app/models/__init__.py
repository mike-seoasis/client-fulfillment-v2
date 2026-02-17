"""Models layer - SQLAlchemy ORM models.

Models define the database schema and relationships.
All models inherit from the Base class defined in core.database.
"""

from app.core.database import Base
from app.models.blog import BlogCampaign, BlogPost
from app.models.brand_config import BrandConfig
from app.models.competitor import Competitor
from app.models.content_brief import ContentBrief
from app.models.content_score import ContentScore
from app.models.crawl_history import CrawlHistory
from app.models.crawl_schedule import CrawlSchedule
from app.models.crawled_page import CrawledPage
from app.models.crowdreply_task import (
    CrowdReplyTask,
    CrowdReplyTaskStatus,
    CrowdReplyTaskType,
)
from app.models.generated_content import GeneratedContent
from app.models.internal_link import InternalLink, LinkPlanSnapshot
from app.models.keyword_cluster import ClusterPage, KeywordCluster
from app.models.nlp_analysis_cache import NLPAnalysisCache
from app.models.notification import (
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    NotificationTemplate,
    WebhookConfig,
)
from app.models.page_content import PageContent
from app.models.page_keywords import PageKeywords
from app.models.page_paa import PagePAA
from app.models.project import Project
from app.models.project_file import ProjectFile
from app.models.prompt_log import PromptLog
from app.models.reddit_account import AccountStatus, RedditAccount, WarmupStage
from app.models.reddit_comment import CommentStatus, RedditComment
from app.models.reddit_config import RedditProjectConfig
from app.models.reddit_post import PostFilterStatus, PostIntent, RedditPost

__all__ = [
    "Base",
    "BlogCampaign",
    "BlogPost",
    "BrandConfig",
    "Competitor",
    "ContentBrief",
    "ContentScore",
    "CrowdReplyTask",
    "CrowdReplyTaskStatus",
    "CrowdReplyTaskType",
    "CrawlHistory",
    "CrawlSchedule",
    "ClusterPage",
    "CrawledPage",
    "GeneratedContent",
    "InternalLink",
    "LinkPlanSnapshot",
    "KeywordCluster",
    "NLPAnalysisCache",
    "NotificationChannel",
    "NotificationLog",
    "NotificationStatus",
    "NotificationTemplate",
    "PageContent",
    "PageKeywords",
    "PagePAA",
    "AccountStatus",
    "CommentStatus",
    "PostFilterStatus",
    "PostIntent",
    "Project",
    "ProjectFile",
    "RedditAccount",
    "RedditComment",
    "RedditPost",
    "RedditProjectConfig",
    "PromptLog",
    "WarmupStage",
    "WebhookConfig",
]
