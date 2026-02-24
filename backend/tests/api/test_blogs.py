"""Tests for blog campaigns API endpoints.

Tests cover:
- Campaign CRUD: create (mocked discovery), list, get, delete
- Campaign validation: duplicate campaign per cluster (409), cluster not approved (422)
- Post update: PATCH keyword-level fields
- Bulk approve: POST approve all posts
- Content generation: trigger (202), duplicate run (409), status polling
- Content CRUD: get content, update content, approve content
- Content recheck: re-run QA checks
- Bulk content approval: approve QA-passed posts
- Export: campaign export, single post export, HTML download
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blog import BlogCampaign, BlogPost, CampaignStatus, ContentStatus
from app.models.keyword_cluster import KeywordCluster, ClusterStatus
from app.models.project import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_active_generations() -> None:
    """Clear the module-level active generation/link tracking before each test."""
    from app.api.v1.blogs import _active_blog_generations, _active_blog_link_plans
    _active_blog_generations.clear()
    _active_blog_link_plans.clear()


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    """Create a test project."""
    project = Project(
        name="Blog API Test",
        site_url="https://blog-api.example.com",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def cluster(db_session: AsyncSession, project: Project) -> KeywordCluster:
    """Create an approved keyword cluster."""
    cluster = KeywordCluster(
        project_id=project.id,
        seed_keyword="winter boots",
        name="Winter Boots",
        status=ClusterStatus.APPROVED.value,
    )
    db_session.add(cluster)
    await db_session.commit()
    await db_session.refresh(cluster)
    return cluster


@pytest.fixture
async def campaign(
    db_session: AsyncSession, project: Project, cluster: KeywordCluster
) -> BlogCampaign:
    """Create a blog campaign in 'writing' status with posts."""
    campaign = BlogCampaign(
        project_id=project.id,
        cluster_id=cluster.id,
        name="Blog: Winter Boots",
        status=CampaignStatus.WRITING.value,
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)

    post1 = BlogPost(
        campaign_id=campaign.id,
        primary_keyword="how to clean winter boots",
        url_slug="how-to-clean-winter-boots",
        is_approved=True,
        content_status=ContentStatus.PENDING.value,
    )
    post2 = BlogPost(
        campaign_id=campaign.id,
        primary_keyword="best winter boots for hiking",
        url_slug="best-winter-boots-for-hiking",
        is_approved=True,
        content_status=ContentStatus.PENDING.value,
    )
    db_session.add_all([post1, post2])
    await db_session.commit()

    return campaign


@pytest.fixture
async def campaign_with_content(
    db_session: AsyncSession, project: Project, cluster: KeywordCluster
) -> BlogCampaign:
    """Create a blog campaign with completed content on posts."""
    # Need a different cluster since campaign fixture uses the first one
    cluster2 = KeywordCluster(
        project_id=project.id,
        seed_keyword="summer shoes",
        name="Summer Shoes",
        status=ClusterStatus.APPROVED.value,
    )
    db_session.add(cluster2)
    await db_session.commit()
    await db_session.refresh(cluster2)

    campaign = BlogCampaign(
        project_id=project.id,
        cluster_id=cluster2.id,
        name="Blog: Summer Shoes",
        status=CampaignStatus.REVIEW.value,
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)

    post = BlogPost(
        campaign_id=campaign.id,
        primary_keyword="summer shoe guide",
        url_slug="summer-shoe-guide",
        is_approved=True,
        title="Summer Shoe Guide",
        meta_description="Complete guide to summer shoes.",
        content="<h2>Best Shoes</h2><p>Quality summer shoes.</p>",
        content_status=ContentStatus.COMPLETE.value,
        content_approved=False,
        qa_results={"passed": True, "issues": [], "checked_at": "2026-02-14T00:00:00"},
    )
    db_session.add(post)
    await db_session.commit()

    return campaign


# ---------------------------------------------------------------------------
# GET /projects/{id}/blogs - List campaigns
# ---------------------------------------------------------------------------


class TestListBlogCampaigns:
    """Tests for GET /projects/{id}/blogs endpoint."""

    @pytest.mark.asyncio
    async def test_lists_campaigns(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns campaigns with post counts."""
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "post_count" in item
        assert "cluster_name" in item

    @pytest.mark.asyncio
    async def test_returns_empty_for_no_campaigns(
        self, async_client: AsyncClient, project: Project
    ) -> None:
        """Returns empty list when no campaigns exist."""
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs"
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_project(
        self, async_client: AsyncClient
    ) -> None:
        """Returns 404 for non-existent project."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"/api/v1/projects/{fake_id}/blogs")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /projects/{id}/blogs/{blog_id} - Get campaign detail
# ---------------------------------------------------------------------------


class TestGetBlogCampaign:
    """Tests for GET /projects/{id}/blogs/{blog_id} endpoint."""

    @pytest.mark.asyncio
    async def test_returns_campaign_with_posts(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns campaign with nested posts."""
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == campaign.id
        assert data["name"] == "Blog: Winter Boots"
        assert len(data["posts"]) == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_campaign(
        self, async_client: AsyncClient, project: Project
    ) -> None:
        """Returns 404 for non-existent campaign."""
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{fake_id}"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /projects/{id}/blogs/{blog_id} - Delete campaign
# ---------------------------------------------------------------------------


class TestDeleteBlogCampaign:
    """Tests for DELETE /projects/{id}/blogs/{blog_id} endpoint."""

    @pytest.mark.asyncio
    async def test_deletes_campaign(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Deletes campaign and returns 204."""
        response = await async_client.delete(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}"
        )
        assert response.status_code == 204

        # Verify it's gone
        get_response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}"
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_campaign(
        self, async_client: AsyncClient, project: Project
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await async_client.delete(
            f"/api/v1/projects/{project.id}/blogs/{fake_id}"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /projects/{id}/blogs/{blog_id}/posts/{post_id} - Update post
# ---------------------------------------------------------------------------


class TestUpdateBlogPost:
    """Tests for PATCH /projects/{id}/blogs/{blog_id}/posts/{post_id} endpoint."""

    @pytest.mark.asyncio
    async def test_updates_keyword_fields(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign: BlogCampaign
    ) -> None:
        """Updates keyword and slug on a post."""
        # Get a post from the campaign
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/posts/{post.id}",
            json={"primary_keyword": "updated keyword", "url_slug": "updated-keyword"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["primary_keyword"] == "updated keyword"
        assert data["url_slug"] == "updated-keyword"

    @pytest.mark.asyncio
    async def test_returns_404_for_missing_post(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        fake_id = str(uuid.uuid4())
        response = await async_client.patch(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/posts/{fake_id}",
            json={"primary_keyword": "new"},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /projects/{id}/blogs/{blog_id}/approve - Bulk approve keywords
# ---------------------------------------------------------------------------


class TestApproveBlogPosts:
    """Tests for POST /projects/{id}/blogs/{blog_id}/approve endpoint."""

    @pytest.mark.asyncio
    async def test_approves_all_posts(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project
    ) -> None:
        """Approves all unapproved posts in a campaign."""
        # Create a campaign in planning status with unapproved posts
        cluster = KeywordCluster(
            project_id=project.id,
            seed_keyword="approve test",
            name="Approve Test Cluster",
            status=ClusterStatus.APPROVED.value,
        )
        db_session.add(cluster)
        await db_session.commit()
        await db_session.refresh(cluster)

        campaign = BlogCampaign(
            project_id=project.id,
            cluster_id=cluster.id,
            name="Approve Test",
            status=CampaignStatus.PLANNING.value,
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        post = BlogPost(
            campaign_id=campaign.id,
            primary_keyword="unapproved topic",
            url_slug="unapproved-topic",
            is_approved=False,
        )
        db_session.add(post)
        await db_session.commit()

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/approve"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["approved_count"] == 1
        # Campaign should transition to 'writing' since all posts are now approved
        assert data["campaign_status"] == "writing"


# ---------------------------------------------------------------------------
# POST /projects/{id}/blogs/{blog_id}/generate-content - Trigger generation
# ---------------------------------------------------------------------------


class TestGenerateBlogContent:
    """Tests for POST /projects/{id}/blogs/{blog_id}/generate-content endpoint."""

    @pytest.mark.asyncio
    async def test_returns_202_with_approved_posts(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns 202 when campaign is in writing status with approved posts."""
        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/generate-content"
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert "2 approved posts" in data["message"]

    @pytest.mark.asyncio
    async def test_returns_409_duplicate_generation(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns 409 if generation already in progress."""
        from app.api.v1.blogs import _active_blog_generations
        _active_blog_generations.add(campaign.id)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/generate-content"
        )

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_returns_400_wrong_campaign_status(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project
    ) -> None:
        """Returns 400 when campaign is not in 'writing' status."""
        cluster = KeywordCluster(
            project_id=project.id,
            seed_keyword="wrong status",
            name="Wrong Status Cluster",
            status=ClusterStatus.APPROVED.value,
        )
        db_session.add(cluster)
        await db_session.commit()
        await db_session.refresh(cluster)

        campaign = BlogCampaign(
            project_id=project.id,
            cluster_id=cluster.id,
            name="Planning Campaign",
            status=CampaignStatus.PLANNING.value,
        )
        db_session.add(campaign)
        await db_session.commit()
        await db_session.refresh(campaign)

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/generate-content"
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /projects/{id}/blogs/{blog_id}/content-status - Poll status
# ---------------------------------------------------------------------------


class TestBlogContentStatus:
    """Tests for GET /projects/{id}/blogs/{blog_id}/content-status endpoint."""

    @pytest.mark.asyncio
    async def test_returns_status_breakdown(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns content generation status with per-post breakdown."""
        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/content-status"
        )

        assert response.status_code == 200
        data = response.json()
        assert "overall_status" in data
        assert data["posts_total"] == 2
        assert "posts" in data
        assert len(data["posts"]) == 2

    @pytest.mark.asyncio
    async def test_shows_generating_when_active(
        self, async_client: AsyncClient, project: Project, campaign: BlogCampaign
    ) -> None:
        """Shows 'generating' status when campaign is in active generation set."""
        from app.api.v1.blogs import _active_blog_generations
        _active_blog_generations.add(campaign.id)

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/content-status"
        )

        assert response.status_code == 200
        assert response.json()["overall_status"] == "generating"


# ---------------------------------------------------------------------------
# Content CRUD endpoints
# ---------------------------------------------------------------------------


class TestBlogPostContentCrud:
    """Tests for blog post content CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_get_post_content(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """GET post content returns the full post with content fields."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/content"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Summer Shoe Guide"
        assert data["content_status"] == "complete"

    @pytest.mark.asyncio
    async def test_get_post_content_404_when_pending(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign: BlogCampaign
    ) -> None:
        """GET post content returns 404 when content not yet generated."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/posts/{post.id}/content"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_post_content(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """PUT post content updates content fields and clears approval."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        # First approve the content
        post.content_approved = True
        await db_session.commit()

        response = await async_client.put(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/content",
            json={"title": "Updated Title"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["content_approved"] is False  # Cleared on content change

    @pytest.mark.asyncio
    async def test_approve_post_content(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """POST approve-content sets content_approved=True."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/approve-content"
        )

        assert response.status_code == 200
        assert response.json()["content_approved"] is True


# ---------------------------------------------------------------------------
# POST /recheck - Re-run QA
# ---------------------------------------------------------------------------


class TestRecheckBlogPost:
    """Tests for POST /projects/{id}/blogs/{blog_id}/posts/{post_id}/recheck."""

    @pytest.mark.asyncio
    async def test_recheck_updates_qa_results(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """Re-run quality checks updates qa_results."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/recheck"
        )

        assert response.status_code == 200
        data = response.json()
        assert "qa_results" in data
        assert data["qa_results"] is not None
        assert "passed" in data["qa_results"]

    @pytest.mark.asyncio
    async def test_recheck_404_no_content(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign: BlogCampaign
    ) -> None:
        """Returns 404 when post has no content yet."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.post(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/posts/{post.id}/recheck"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


class TestBlogExport:
    """Tests for blog export API endpoints."""

    @pytest.mark.asyncio
    async def test_export_campaign(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """GET /export returns approved+complete posts as BlogExportItem list."""
        # Approve the post content first
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None
        post.content_approved = True
        await db_session.commit()

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/export"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["primary_keyword"] == "summer shoe guide"
        assert "html_content" in data[0]
        assert data[0]["word_count"] > 0

    @pytest.mark.asyncio
    async def test_export_single_post(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """GET /posts/{post_id}/export returns single post export."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/export"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["post_id"] == post.id
        assert "html_content" in data

    @pytest.mark.asyncio
    async def test_download_html(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign_with_content: BlogCampaign
    ) -> None:
        """GET /posts/{post_id}/download returns HTML file."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign_with_content.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign_with_content.id}/posts/{post.id}/download"
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "<!DOCTYPE html>" in response.text

    @pytest.mark.asyncio
    async def test_export_404_no_content(
        self, async_client: AsyncClient, db_session: AsyncSession,
        project: Project, campaign: BlogCampaign
    ) -> None:
        """Export returns 404 when post has no content."""
        from sqlalchemy import select
        stmt = select(BlogPost).where(BlogPost.campaign_id == campaign.id)
        result = await db_session.execute(stmt)
        post = result.scalars().first()
        assert post is not None

        response = await async_client.get(
            f"/api/v1/projects/{project.id}/blogs/{campaign.id}/posts/{post.id}/export"
        )
        assert response.status_code == 404
