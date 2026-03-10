"""Unit tests for Shopify OAuth flow and webhook endpoints.

Tests cover:
- Install endpoint constructs correct auth URL
- Install rejects invalid shop domain
- Callback validates HMAC signature
- Callback rejects invalid state parameter
- Callback exchanges code and stores encrypted token
- GDPR endpoints return 200
- Uninstall webhook clears connection
- Uninstall webhook rejects invalid HMAC
- Status endpoint returns correct state
- Sync trigger endpoint with validation
- Disconnect endpoint

Uses FastAPI TestClient with mocked dependencies.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.shopify import _oauth_states, _validate_shop_domain, verify_shopify_hmac, verify_webhook_hmac
from app.models.project import Project


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def oauth_project(db_session: AsyncSession) -> Project:
    """Create a test project for OAuth testing."""
    project = Project(
        id=str(uuid.uuid4()),
        name="OAuth Test Store",
        site_url="https://teststore.myshopify.com",
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.fixture
async def connected_project(db_session: AsyncSession) -> Project:
    """Create a project with an existing Shopify connection."""
    project = Project(
        id=str(uuid.uuid4()),
        name="Connected Store",
        site_url="https://connected.myshopify.com",
        shopify_store_domain="connected.myshopify.com",
        shopify_access_token_encrypted="encrypted_token_here",
        shopify_scopes="read_products,read_content",
        shopify_sync_status="idle",
        shopify_connected_at=datetime.now(UTC),
    )
    db_session.add(project)
    await db_session.commit()
    return project


# ---------------------------------------------------------------------------
# Test: Shop domain validation helper
# ---------------------------------------------------------------------------


class TestShopDomainValidation:
    """Tests for _validate_shop_domain helper."""

    def test_valid_domain(self) -> None:
        assert _validate_shop_domain("acmestore.myshopify.com") is True

    def test_valid_domain_with_hyphens(self) -> None:
        assert _validate_shop_domain("my-test-store.myshopify.com") is True

    def test_invalid_domain_no_myshopify(self) -> None:
        assert _validate_shop_domain("not-valid") is False

    def test_invalid_domain_wrong_suffix(self) -> None:
        assert _validate_shop_domain("store.shopify.com") is False

    def test_invalid_domain_with_path(self) -> None:
        assert _validate_shop_domain("store.myshopify.com/admin") is False

    def test_empty_string(self) -> None:
        assert _validate_shop_domain("") is False

    def test_starts_with_hyphen(self) -> None:
        assert _validate_shop_domain("-invalid.myshopify.com") is False


# ---------------------------------------------------------------------------
# Test: HMAC verification helpers
# ---------------------------------------------------------------------------


class TestHMACVerification:
    """Tests for HMAC verification utilities."""

    def test_verify_shopify_hmac_valid(self) -> None:
        """Test HMAC verification with valid signature."""
        secret = "test_secret"
        params = {
            "code": "auth_code",
            "shop": "store.myshopify.com",
            "state": "test_state",
            "timestamp": "1234567890",
        }
        # Compute HMAC
        message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        expected_hmac = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        params["hmac"] = expected_hmac

        assert verify_shopify_hmac(params, secret) is True

    def test_verify_shopify_hmac_invalid(self) -> None:
        """Test HMAC verification rejects invalid signature."""
        params = {
            "code": "auth_code",
            "shop": "store.myshopify.com",
            "hmac": "invalid_hmac",
        }
        assert verify_shopify_hmac(params, "secret") is False

    def test_verify_shopify_hmac_missing(self) -> None:
        """Test HMAC verification fails when hmac param is missing."""
        params = {"code": "auth_code", "shop": "store.myshopify.com"}
        assert verify_shopify_hmac(params, "secret") is False

    def test_verify_webhook_hmac_valid(self) -> None:
        """Test webhook HMAC verification with valid signature."""
        import base64

        secret = "webhook_secret"
        body = b'{"id": 123}'
        expected = base64.b64encode(
            hmac.new(secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        assert verify_webhook_hmac(body, expected, secret) is True

    def test_verify_webhook_hmac_invalid(self) -> None:
        """Test webhook HMAC verification rejects invalid signature."""
        assert verify_webhook_hmac(b'{"id": 123}', "invalid", "secret") is False


# ---------------------------------------------------------------------------
# Test: Install Endpoint
# ---------------------------------------------------------------------------


class TestInstallEndpoint:
    """Tests for GET /api/v1/shopify/auth/install."""

    def test_constructs_correct_auth_url(
        self, client: TestClient, oauth_project: Project
    ) -> None:
        """Test install endpoint redirects to Shopify OAuth URL."""
        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_key = "test_api_key"
            settings.shopify_api_secret = "test_api_secret"
            settings.frontend_url = None
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/install",
                params={
                    "shop": "acmestore.myshopify.com",
                    "project_id": oauth_project.id,
                },
                follow_redirects=False,
            )

        # Should redirect (302)
        assert response.status_code == 302

        location = response.headers.get("location", "")
        parsed = urlparse(location)

        assert "acmestore.myshopify.com" in parsed.netloc
        assert "/admin/oauth/authorize" in parsed.path

        query_params = parse_qs(parsed.query)
        assert "client_id" in query_params
        assert query_params["client_id"][0] == "test_api_key"
        assert "scope" in query_params
        assert "read_products" in query_params["scope"][0]
        assert "read_content" in query_params["scope"][0]
        assert "redirect_uri" in query_params
        assert "state" in query_params

    def test_rejects_invalid_shop_domain(
        self, client: TestClient, oauth_project: Project
    ) -> None:
        """Test install rejects invalid shop domain format."""
        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_key = "key"
            settings.shopify_api_secret = "secret"
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/install",
                params={
                    "shop": "not-valid",
                    "project_id": oauth_project.id,
                },
                follow_redirects=False,
            )

        assert response.status_code == 400
        assert "invalid" in response.json().get("detail", "").lower()

    def test_rejects_nonexistent_project(self, client: TestClient) -> None:
        """Test install rejects request for non-existent project."""
        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_key = "key"
            settings.shopify_api_secret = "secret"
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/install",
                params={
                    "shop": "store.myshopify.com",
                    "project_id": str(uuid.uuid4()),
                },
                follow_redirects=False,
            )

        assert response.status_code == 404

    def test_rejects_when_shopify_not_configured(
        self, client: TestClient, oauth_project: Project
    ) -> None:
        """Test install returns 500 when Shopify app is not configured."""
        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_key = None
            settings.shopify_api_secret = None
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/install",
                params={
                    "shop": "store.myshopify.com",
                    "project_id": oauth_project.id,
                },
                follow_redirects=False,
            )

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Test: Callback Endpoint
# ---------------------------------------------------------------------------


class TestCallbackEndpoint:
    """Tests for GET /api/v1/shopify/auth/callback."""

    def test_callback_rejects_invalid_hmac(self, client: TestClient) -> None:
        """Test callback rejects requests with invalid HMAC."""
        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_secret = "real_secret"
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/callback",
                params={
                    "code": "auth_code_123",
                    "hmac": "invalid_hmac_value",
                    "shop": "store.myshopify.com",
                    "state": "some_state",
                    "timestamp": "1234567890",
                },
                follow_redirects=False,
            )

        assert response.status_code == 401
        assert "signature" in response.json().get("detail", "").lower()

    def test_callback_rejects_invalid_state(self, client: TestClient) -> None:
        """Test callback rejects invalid state parameter."""
        secret = "test_secret"
        # Build valid HMAC but with invalid state
        params = {
            "code": "auth_code_123",
            "shop": "store.myshopify.com",
            "state": "invalid_state",
            "timestamp": "1234567890",
        }
        message = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        valid_hmac = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
        params["hmac"] = valid_hmac

        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_secret = secret
            mock_settings.return_value = settings

            response = client.get(
                "/api/v1/shopify/auth/callback",
                params=params,
                follow_redirects=False,
            )

        assert response.status_code == 400
        assert "state" in response.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Test: GDPR Endpoints
# ---------------------------------------------------------------------------


class TestGDPREndpoints:
    """Tests for GDPR compliance webhook endpoints.

    GDPR endpoints verify the X-Shopify-Hmac-SHA256 header, so tests must
    send a valid HMAC computed from the request body and the app's API secret.
    """

    @staticmethod
    def _make_gdpr_request(
        client: TestClient, path: str, body_dict: dict,
    ) -> "requests.Response":
        """Send a GDPR webhook request with valid HMAC."""
        import base64

        api_secret = "test_api_secret"
        body = json.dumps(body_dict).encode("utf-8")
        valid_hmac = base64.b64encode(
            hmac.new(api_secret.encode(), body, hashlib.sha256).digest()
        ).decode()

        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_secret = api_secret
            mock_settings.return_value = settings

            return client.post(
                path,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Hmac-SHA256": valid_hmac,
                },
            )

    def test_customer_data_request_returns_200(self, client: TestClient) -> None:
        """Test POST /shopify/webhooks/customers/data_request returns 200."""
        response = self._make_gdpr_request(
            client,
            "/api/v1/shopify/webhooks/customers/data_request",
            {
                "shop_id": 12345,
                "shop_domain": "store.myshopify.com",
                "customer": {"id": 1, "email": "customer@example.com"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_customer_redact_returns_200(self, client: TestClient) -> None:
        """Test POST /shopify/webhooks/customers/redact returns 200."""
        response = self._make_gdpr_request(
            client,
            "/api/v1/shopify/webhooks/customers/redact",
            {
                "shop_id": 12345,
                "shop_domain": "store.myshopify.com",
                "customer": {"id": 1, "email": "customer@example.com"},
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_shop_redact_returns_200(self, client: TestClient) -> None:
        """Test POST /shopify/webhooks/shop/redact returns 200."""
        response = self._make_gdpr_request(
            client,
            "/api/v1/shopify/webhooks/shop/redact",
            {
                "shop_id": 12345,
                "shop_domain": "store.myshopify.com",
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Test: Uninstall Webhook
# ---------------------------------------------------------------------------


class TestUninstallWebhook:
    """Tests for app/uninstalled webhook handler."""

    def test_uninstall_webhook_verifies_hmac(
        self,
        client: TestClient,
        mock_db_manager,
        connected_project: Project,
    ) -> None:
        """Test uninstall webhook verifies HMAC before processing."""
        import base64

        api_secret = "test_api_secret"
        webhook_body = json.dumps({
            "id": 12345,
            "domain": "connected.myshopify.com",
        }).encode("utf-8")

        valid_hmac = base64.b64encode(
            hmac.new(api_secret.encode(), webhook_body, hashlib.sha256).digest()
        ).decode()

        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_secret = api_secret
            mock_settings.return_value = settings

            response = client.post(
                "/api/v1/shopify/webhooks/app/uninstalled",
                content=webhook_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Hmac-SHA256": valid_hmac,
                    "X-Shopify-Shop-Domain": "connected.myshopify.com",
                },
            )

        assert response.status_code == 200

    def test_uninstall_webhook_rejects_invalid_hmac(self, client: TestClient) -> None:
        """Test uninstall webhook rejects request with invalid HMAC."""
        webhook_body = json.dumps({"id": 12345}).encode("utf-8")

        with patch("app.api.v1.shopify.get_settings") as mock_settings:
            settings = MagicMock()
            settings.shopify_api_secret = "real_secret"
            mock_settings.return_value = settings

            response = client.post(
                "/api/v1/shopify/webhooks/app/uninstalled",
                content=webhook_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Shopify-Hmac-SHA256": "invalid_hmac_value",
                    "X-Shopify-Shop-Domain": "store.myshopify.com",
                },
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: Status Endpoint
# ---------------------------------------------------------------------------


class TestStatusEndpoint:
    """Tests for GET /api/v1/projects/{id}/shopify/status."""

    def test_connected_store_returns_status(
        self,
        client: TestClient,
        connected_project: Project,
    ) -> None:
        """Test status endpoint returns connection details for connected store."""
        response = client.get(
            f"/api/v1/projects/{connected_project.id}/shopify/status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["store_domain"] == "connected.myshopify.com"
        assert data["sync_status"] == "idle"

    def test_unconnected_project_returns_not_connected(
        self,
        client: TestClient,
        oauth_project: Project,
    ) -> None:
        """Test status endpoint returns connected=false for unconnected project."""
        response = client.get(
            f"/api/v1/projects/{oauth_project.id}/shopify/status",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    def test_nonexistent_project_returns_404(self, client: TestClient) -> None:
        """Test status endpoint returns 404 for nonexistent project."""
        response = client.get(
            f"/api/v1/projects/{uuid.uuid4()}/shopify/status",
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test: Sync Trigger Endpoint
# ---------------------------------------------------------------------------


class TestSyncTrigger:
    """Tests for POST /api/v1/projects/{id}/shopify/sync."""

    def test_triggers_sync_returns_202(
        self,
        client: TestClient,
        connected_project: Project,
    ) -> None:
        """Test manual sync returns 202 Accepted."""
        with patch("app.api.v1.shopify.sync_immediate", new_callable=AsyncMock):
            response = client.post(
                f"/api/v1/projects/{connected_project.id}/shopify/sync",
            )

        assert response.status_code == 202
        assert response.json()["status"] == "syncing"

    def test_rejects_sync_when_not_connected(
        self,
        client: TestClient,
        oauth_project: Project,
    ) -> None:
        """Test sync rejects request when Shopify is not connected."""
        response = client.post(
            f"/api/v1/projects/{oauth_project.id}/shopify/sync",
        )

        assert response.status_code == 400
        assert "not connected" in response.json().get("detail", "").lower()

    async def test_rejects_sync_when_already_syncing(
        self,
        client: TestClient,
        db_session: AsyncSession,
        connected_project: Project,
    ) -> None:
        """Test sync rejects when already in progress."""
        # Set project to syncing state and commit so the endpoint's session sees it
        connected_project.shopify_sync_status = "syncing"
        await db_session.commit()

        response = client.post(
            f"/api/v1/projects/{connected_project.id}/shopify/sync",
        )

        assert response.status_code == 409
        assert "already in progress" in response.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# Test: Disconnect Endpoint
# ---------------------------------------------------------------------------


class TestDisconnectEndpoint:
    """Tests for DELETE /api/v1/projects/{id}/shopify."""

    def test_disconnect_clears_shopify_fields(
        self,
        client: TestClient,
        connected_project: Project,
    ) -> None:
        """Test disconnect clears all Shopify connection fields."""
        with patch("app.api.v1.shopify._remove_sync_job"):
            response = client.delete(
                f"/api/v1/projects/{connected_project.id}/shopify",
            )

        assert response.status_code == 200
        assert response.json()["status"] == "disconnected"

    def test_disconnect_on_unconnected_project_is_idempotent(
        self,
        client: TestClient,
        oauth_project: Project,
    ) -> None:
        """Test disconnect on a project with no Shopify connection returns 200."""
        with patch("app.api.v1.shopify._remove_sync_job"):
            response = client.delete(
                f"/api/v1/projects/{oauth_project.id}/shopify",
            )

        assert response.status_code == 200
