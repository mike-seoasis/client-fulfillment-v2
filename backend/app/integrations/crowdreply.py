"""CrowdReply integration client for Reddit comment posting.

Submits approved comments to CrowdReply (~$5/comment third-party posting service)
and handles webhook-based status tracking.

3-layer mock strategy for development:
1. Mock Client (CROWDREPLY_USE_MOCK=true) - Fake responses, zero API calls
2. Dry Run (CROWDREPLY_DRY_RUN=true) - Logs real payloads without sending
3. Webhook Simulator (dev-only endpoint) - Simulates webhook callbacks

Follows the same integration pattern as serpapi.py / claude.py:
async httpx, circuit breaker, retry, global instance.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, cast

import httpx

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CrowdReplyError(Exception):
    """Base exception for CrowdReply errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class CrowdReplyTimeoutError(CrowdReplyError):
    """Raised when a CrowdReply request times out."""


class CrowdReplyRateLimitError(CrowdReplyError):
    """Raised when CrowdReply returns 429."""


class CrowdReplyAuthError(CrowdReplyError):
    """Raised when CrowdReply returns 401/403."""


class CrowdReplyCircuitOpenError(CrowdReplyError):
    """Raised when circuit breaker is open."""


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CreateTaskResult:
    """Result from creating a CrowdReply comment task."""

    success: bool
    status_code: int | None = None
    external_task_id: str | None = None
    request_payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class TaskInfo:
    """Info about a CrowdReply task."""

    id: str
    status: str
    thread_url: str = ""
    content: str = ""
    task_type: str = ""
    client_price: float | None = None
    task_submission: list[dict[str, Any]] = field(default_factory=list)
    published_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class BalanceInfo:
    """CrowdReply account balance."""

    balance: float
    currency: str = "USD"


# ---------------------------------------------------------------------------
# CrowdReplyClient (real API)
# ---------------------------------------------------------------------------


class CrowdReplyClient:
    """Async client for CrowdReply API.

    Features:
    - Circuit breaker for fault tolerance
    - Retry logic with exponential backoff
    - Dry-run mode (logs payloads without sending)
    - Lazy httpx client initialization
    """

    def __init__(self) -> None:
        settings = get_settings()

        self._api_key = settings.crowdreply_api_key
        self._base_url = settings.crowdreply_base_url.rstrip("/")
        self._project_id = settings.crowdreply_project_id
        self._timeout = settings.crowdreply_timeout
        self._dry_run = settings.crowdreply_dry_run
        self._reconcile_delay = settings.crowdreply_reconcile_delay
        self._max_retries = 3
        self._retry_delay = 1.0

        self._circuit_breaker = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0),
            name="crowdreply",
        )

        self._client: httpx.AsyncClient | None = None
        self._available = bool(self._api_key)

        logger.info(
            "CrowdReplyClient instantiated",
            extra={
                "available": self._available,
                "dry_run": self._dry_run,
                "base_url": self._base_url,
            },
        )

    @property
    def available(self) -> bool:
        return self._available

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout),
                headers={"x-api-key": self._api_key},
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("CrowdReply client closed")

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Execute HTTP request with retry and circuit breaker."""
        if not self._available:
            raise CrowdReplyError("CrowdReply not configured (missing API key)")

        if not await self._circuit_breaker.can_execute():
            raise CrowdReplyCircuitOpenError("CrowdReply circuit breaker is open")

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            attempt_start = time.monotonic()
            try:
                response = await client.request(
                    method, path, json=json, params=params
                )
                duration_ms = (time.monotonic() - attempt_start) * 1000

                if response.status_code == 429:
                    await self._circuit_breaker.record_failure()
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            "CrowdReply rate limited, retrying",
                            extra={"attempt": attempt + 1, "delay": delay},
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise CrowdReplyRateLimitError(
                        "Rate limited by CrowdReply", status_code=429
                    )

                if response.status_code in (401, 403):
                    await self._circuit_breaker.record_failure()
                    raise CrowdReplyAuthError(
                        "Authentication failed",
                        status_code=response.status_code,
                    )

                if response.status_code >= 500:
                    await self._circuit_breaker.record_failure()
                    if attempt < self._max_retries - 1:
                        delay = self._retry_delay * (2**attempt)
                        logger.warning(
                            "CrowdReply server error, retrying",
                            extra={
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                            },
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise CrowdReplyError(
                        f"Server error: {response.status_code}",
                        status_code=response.status_code,
                    )

                await self._circuit_breaker.record_success()

                logger.debug(
                    "CrowdReply request complete",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return response

            except httpx.TimeoutException:
                await self._circuit_breaker.record_failure()
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                last_error = CrowdReplyTimeoutError(
                    f"Request timed out after {self._timeout}s"
                )

            except httpx.RequestError as e:
                await self._circuit_breaker.record_failure()
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                last_error = CrowdReplyError(f"Request failed: {e}")

        raise last_error or CrowdReplyError("Request failed after all retries")

    async def create_comment_task(
        self,
        thread_url: str,
        content: str,
        project_id: str | None = None,
        schedule_at: str | None = None,
        upvotes: int | None = None,
    ) -> CreateTaskResult:
        """Create a comment task on CrowdReply.

        POST /tasks with taskData for a Reddit comment.
        CrowdReply returns no body on create, so we reconcile the task ID
        by polling GET /tasks after a short delay.
        """
        cr_project = project_id or self._project_id
        task_data: dict[str, Any] = {
            "taskType": "comment",
            "type": "RedditCommentTask",
            "platform": "reddit",
            "project": cr_project,
            "content": content,
            "threadUrl": thread_url,
        }
        payload: dict[str, Any] = {"taskData": task_data}
        if schedule_at:
            payload["taskData"]["scheduleAt"] = schedule_at
        if upvotes is not None:
            payload["taskData"]["upvotes"] = upvotes

        if self._dry_run:
            logger.info(
                "CrowdReply DRY RUN: create_comment_task",
                extra={"payload": payload, "thread_url": thread_url},
            )
            return CreateTaskResult(
                success=True,
                status_code=200,
                external_task_id=f"dryrun_{int(time.time())}",
                request_payload=payload,
            )

        try:
            response = await self._request("POST", "/tasks", json=payload)

            if response.status_code in (200, 201, 202):
                # CrowdReply often returns no body; reconcile task ID
                external_id = await self._reconcile_task_id(
                    cr_project, thread_url, content
                )
                return CreateTaskResult(
                    success=True,
                    status_code=response.status_code,
                    external_task_id=external_id,
                    request_payload=payload,
                )

            return CreateTaskResult(
                success=False,
                status_code=response.status_code,
                request_payload=payload,
                error=f"Unexpected status: {response.status_code}",
            )

        except CrowdReplyError as e:
            return CreateTaskResult(
                success=False,
                status_code=e.status_code,
                request_payload=payload,
                error=str(e),
            )

    async def _reconcile_task_id(
        self,
        project_id: str | None,
        thread_url: str,
        content: str,
    ) -> str | None:
        """Sleep briefly then GET /tasks to find the newly created task by matching content+URL."""
        await asyncio.sleep(self._reconcile_delay)

        try:
            params: dict[str, Any] = {}
            if project_id:
                params["project"] = project_id
            response = await self._request("GET", "/tasks", params=params)
            if response.status_code == 200:
                tasks = response.json()
                if isinstance(tasks, list):
                    for task in tasks:
                        if (
                            task.get("threadUrl") == thread_url
                            and task.get("content") == content
                        ):
                            return cast(str, task.get("_id"))
        except CrowdReplyError:
            logger.warning("Failed to reconcile CrowdReply task ID")

        return None

    async def list_tasks(
        self, filters: dict[str, Any] | None = None
    ) -> list[TaskInfo]:
        """GET /tasks with optional filters."""
        response = await self._request("GET", "/tasks", params=filters)
        tasks = response.json() if response.status_code == 200 else []
        return [
            TaskInfo(
                id=t.get("_id", ""),
                status=t.get("status", ""),
                thread_url=t.get("threadUrl", ""),
                content=t.get("content", ""),
                task_type=t.get("taskType", ""),
                client_price=t.get("clientPrice"),
                task_submission=t.get("taskSubmission", []),
                published_at=t.get("publishedAt"),
                raw=t,
            )
            for t in (tasks if isinstance(tasks, list) else [])
        ]

    async def get_task(self, task_id: str) -> TaskInfo | None:
        """GET /tasks/{id}."""
        response = await self._request("GET", f"/tasks/{task_id}")
        if response.status_code != 200:
            return None
        t = response.json()
        return TaskInfo(
            id=t.get("_id", ""),
            status=t.get("status", ""),
            thread_url=t.get("threadUrl", ""),
            content=t.get("content", ""),
            task_type=t.get("taskType", ""),
            client_price=t.get("clientPrice"),
            task_submission=t.get("taskSubmission", []),
            published_at=t.get("publishedAt"),
            raw=t,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """PUT /tasks/{id}/cancel-task."""
        response = await self._request("PUT", f"/tasks/{task_id}/cancel-task")
        return response.status_code in (200, 204)

    async def send_upvotes(
        self, task_id: str, quantity: int, delivery: str = "standard"
    ) -> bool:
        """POST /tasks/{id}/upvotes."""
        response = await self._request(
            "POST",
            f"/tasks/{task_id}/upvotes",
            json={"quantity": quantity, "delivery": delivery},
        )
        return response.status_code in (200, 201)

    async def get_balance(self) -> BalanceInfo:
        """GET /billing/balance. Always makes real call (bypasses dry_run)."""
        if not self._available:
            raise CrowdReplyError("CrowdReply not configured")

        # Balance check always hits the real API even in dry-run mode
        if not await self._circuit_breaker.can_execute():
            raise CrowdReplyCircuitOpenError("Circuit breaker is open")

        client = await self._get_client()
        response = await client.get("/billing/balance")

        if response.status_code == 200:
            data = response.json()
            return BalanceInfo(
                balance=float(data.get("balance", 0)),
                currency=data.get("currency", "USD"),
            )
        raise CrowdReplyError(
            f"Failed to fetch balance: {response.status_code}",
            status_code=response.status_code,
        )


# ---------------------------------------------------------------------------
# CrowdReplyMockClient
# ---------------------------------------------------------------------------


class CrowdReplyMockClient:
    """Mock CrowdReply client for development. No API calls made.

    Returns fake task IDs, decrements a fake balance ($250 start - $5/task).
    """

    def __init__(self) -> None:
        self._balance = 250.0
        self._task_counter = 0
        self._tasks: dict[str, TaskInfo] = {}
        logger.info("CrowdReplyMockClient instantiated (no API calls)")

    @property
    def available(self) -> bool:
        return True

    @property
    def dry_run(self) -> bool:
        return False

    async def close(self) -> None:
        logger.info("CrowdReply mock client closed")

    async def create_comment_task(
        self,
        thread_url: str,
        content: str,
        project_id: str | None = None,
        schedule_at: str | None = None,  # noqa: ARG002
        upvotes: int | None = None,  # noqa: ARG002
    ) -> CreateTaskResult:
        self._task_counter += 1
        task_id = f"mock_task_{self._task_counter}"
        self._balance -= 5.0

        self._tasks[task_id] = TaskInfo(
            id=task_id,
            status="assigned",
            thread_url=thread_url,
            content=content,
            task_type="comment",
            client_price=5.0,
        )

        payload = {
            "taskData": {
                "taskType": "comment",
                "type": "RedditCommentTask",
                "platform": "reddit",
                "project": project_id or "mock_project",
                "content": content,
                "threadUrl": thread_url,
            }
        }

        logger.info(
            "CrowdReply MOCK: create_comment_task",
            extra={"task_id": task_id, "thread_url": thread_url},
        )

        return CreateTaskResult(
            success=True,
            status_code=200,
            external_task_id=task_id,
            request_payload=payload,
        )

    async def list_tasks(
        self, _filters: dict[str, Any] | None = None
    ) -> list[TaskInfo]:
        return list(self._tasks.values())

    async def get_task(self, task_id: str) -> TaskInfo | None:
        return self._tasks.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self._tasks:
            self._tasks[task_id].status = "cancelled"
            return True
        return False

    async def send_upvotes(
        self, task_id: str, _quantity: int, _delivery: str = "standard"
    ) -> bool:
        return task_id in self._tasks

    async def get_balance(self) -> BalanceInfo:
        return BalanceInfo(balance=max(0, self._balance), currency="USD")


# ---------------------------------------------------------------------------
# Global instance + lifecycle
# ---------------------------------------------------------------------------

_crowdreply_client: CrowdReplyClient | CrowdReplyMockClient | None = None


async def init_crowdreply() -> CrowdReplyClient | CrowdReplyMockClient:
    """Initialize the global CrowdReply client.

    Creates MockClient if CROWDREPLY_USE_MOCK=true, else real client.
    """
    global _crowdreply_client
    if _crowdreply_client is None:
        settings = get_settings()
        if settings.crowdreply_use_mock:
            _crowdreply_client = CrowdReplyMockClient()
        else:
            _crowdreply_client = CrowdReplyClient()
    return _crowdreply_client


async def close_crowdreply() -> None:
    """Close the global CrowdReply client."""
    global _crowdreply_client
    if _crowdreply_client:
        await _crowdreply_client.close()
        _crowdreply_client = None


async def get_crowdreply() -> CrowdReplyClient | CrowdReplyMockClient:
    """FastAPI dependency for getting the CrowdReply client."""
    global _crowdreply_client
    if _crowdreply_client is None:
        await init_crowdreply()
    return _crowdreply_client  # type: ignore[return-value]
