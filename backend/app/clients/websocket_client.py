"""WebSocket client for real-time updates from the server.

Features:
- Async WebSocket client using websockets library
- Connection state management
- Heartbeat/ping mechanism for keepalive
- Automatic reconnection with exponential backoff
- Circuit breaker for fault tolerance
- Polling fallback when WebSocket unavailable
- Comprehensive error logging per requirements

ERROR LOGGING REQUIREMENTS:
- Log all outbound API calls with endpoint, method, timing
- Log request/response bodies at DEBUG level (truncate large responses)
- Log and handle: timeouts, rate limits (429), auth failures (401/403)
- Include retry attempt number in logs
- Log API quota/credit usage if available
- Mask API keys and tokens in all logs
- Log circuit breaker state changes

RAILWAY DEPLOYMENT REQUIREMENTS:
- Railway supports WebSocket connections
- Implement heartbeat/ping to keep connections alive
- Handle reconnection gracefully (deploys will disconnect clients)
- Consider fallback to polling for reliability
"""

import asyncio
import contextlib
import json
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
import websockets
from websockets.client import WebSocketClientProtocol  # type: ignore[attr-defined]
from websockets.exceptions import (  # type: ignore[attr-defined]
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidStatusCode,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionState(Enum):
    """WebSocket client connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CLOSING = "closing"
    CLOSED = "closed"
    FALLBACK_POLLING = "fallback_polling"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0


@dataclass
class ReconnectConfig:
    """Reconnection configuration with exponential backoff."""

    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0
    max_attempts: int = 0  # 0 = infinite

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (in seconds)."""
        delay_ms = min(
            self.initial_delay_ms * (self.backoff_multiplier ** attempt),
            self.max_delay_ms,
        )
        return delay_ms / 1000.0


@dataclass
class WebSocketClientConfig:
    """WebSocket client configuration."""

    url: str
    heartbeat_interval: float = 30.0
    heartbeat_timeout: float = 90.0
    connect_timeout: float = 30.0
    message_timeout: float = 60.0
    reconnect: ReconnectConfig = field(default_factory=ReconnectConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    polling_interval: float = 5.0
    polling_enabled: bool = True


@dataclass
class WebSocketMessage:
    """Incoming WebSocket message."""

    type: str
    data: dict[str, Any]
    timestamp: float
    raw: str


class CircuitBreaker:
    """Circuit breaker for WebSocket operations."""

    def __init__(self, config: CircuitBreakerConfig) -> None:
        self._config = config
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self._state == CircuitState.OPEN

    async def can_execute(self) -> bool:
        """Check if operation can be executed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._last_failure_time is not None:
                    elapsed = time.monotonic() - self._last_failure_time
                    if elapsed >= self._config.recovery_timeout:
                        logger.info(
                            "WebSocket circuit breaker transitioning to half-open",
                            extra={
                                "from_state": self._state.value,
                                "failure_count": self._failure_count,
                            },
                        )
                        self._state = CircuitState.HALF_OPEN
                        return True
                return False

            return True  # HALF_OPEN

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    "WebSocket circuit breaker closed after recovery",
                    extra={"failure_count": self._failure_count},
                )
                self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None

    async def record_failure(self) -> None:
        """Record failed operation."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "WebSocket circuit breaker reopened after failed recovery",
                    extra={"failure_count": self._failure_count},
                )
                self._state = CircuitState.OPEN
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._config.failure_threshold
            ):
                logger.warning(
                    "WebSocket circuit breaker opened",
                    extra={
                        "failure_count": self._failure_count,
                        "recovery_timeout": self._config.recovery_timeout,
                    },
                )
                self._state = CircuitState.OPEN


class WebSocketClientLogger:
    """Logger for WebSocket client operations with required error logging."""

    def __init__(self) -> None:
        self._logger = get_logger("websocket_client")

    def _mask_url(self, url: str) -> str:
        """Mask sensitive parts of URL (tokens, keys)."""
        # Simple masking for common patterns
        import re
        masked = re.sub(r'(token|key|secret|password)=([^&]+)', r'\1=***', url, flags=re.I)
        return masked[:200]  # Truncate for logging

    def connection_attempt(
        self, url: str, attempt: int, max_attempts: int | None
    ) -> None:
        """Log connection attempt."""
        self._logger.info(
            "WebSocket connection attempt",
            extra={
                "url": self._mask_url(url),
                "retry_attempt": attempt,
                "max_attempts": max_attempts,
            },
        )

    def connection_established(
        self, url: str, connection_id: str | None, duration_ms: float
    ) -> None:
        """Log successful connection."""
        self._logger.info(
            "WebSocket connection established",
            extra={
                "url": self._mask_url(url),
                "connection_id": connection_id,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def connection_closed(
        self, url: str, reason: str | None, code: int | None
    ) -> None:
        """Log connection closed."""
        self._logger.info(
            "WebSocket connection closed",
            extra={
                "url": self._mask_url(url),
                "close_reason": reason,
                "close_code": code,
            },
        )

    def connection_error(
        self, url: str, error: Exception, context: str, attempt: int = 0
    ) -> None:
        """Log connection error."""
        self._logger.error(
            "WebSocket connection error",
            extra={
                "url": self._mask_url(url),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "retry_attempt": attempt,
                "stack_trace": traceback.format_exc(),
            },
        )

    def auth_failure(self, url: str, status_code: int) -> None:
        """Log authentication failure (401/403)."""
        self._logger.error(
            "WebSocket authentication failed",
            extra={
                "url": self._mask_url(url),
                "status_code": status_code,
            },
        )

    def timeout_error(
        self, url: str, timeout: float, context: str, attempt: int = 0
    ) -> None:
        """Log timeout error."""
        self._logger.warning(
            "WebSocket timeout",
            extra={
                "url": self._mask_url(url),
                "timeout_seconds": timeout,
                "context": context,
                "retry_attempt": attempt,
            },
        )

    def message_received(
        self, message_type: str, payload_size: int
    ) -> None:
        """Log incoming message at DEBUG level."""
        self._logger.debug(
            "WebSocket message received",
            extra={
                "message_type": message_type,
                "payload_size": payload_size,
            },
        )

    def message_sent(
        self, message_type: str, payload_size: int
    ) -> None:
        """Log outgoing message at DEBUG level."""
        self._logger.debug(
            "WebSocket message sent",
            extra={
                "message_type": message_type,
                "payload_size": payload_size,
            },
        )

    def heartbeat_sent(self) -> None:
        """Log heartbeat ping sent."""
        self._logger.debug("WebSocket heartbeat sent")

    def heartbeat_received(self) -> None:
        """Log heartbeat pong received."""
        self._logger.debug("WebSocket heartbeat received")

    def heartbeat_timeout(self, last_pong_seconds_ago: float) -> None:
        """Log heartbeat timeout."""
        self._logger.warning(
            "WebSocket heartbeat timeout",
            extra={"last_pong_seconds_ago": round(last_pong_seconds_ago, 2)},
        )

    def reconnection_scheduled(self, delay: float, attempt: int) -> None:
        """Log scheduled reconnection."""
        self._logger.info(
            "WebSocket reconnection scheduled",
            extra={
                "delay_seconds": round(delay, 2),
                "retry_attempt": attempt,
            },
        )

    def circuit_state_change(self, from_state: str, to_state: str) -> None:
        """Log circuit breaker state change."""
        self._logger.warning(
            "WebSocket circuit breaker state change",
            extra={
                "from_state": from_state,
                "to_state": to_state,
            },
        )

    def fallback_to_polling(self, url: str, reason: str) -> None:
        """Log fallback to polling mode."""
        self._logger.warning(
            "WebSocket falling back to polling",
            extra={
                "url": self._mask_url(url),
                "reason": reason,
            },
        )

    def polling_request(
        self, url: str, method: str, duration_ms: float, status_code: int
    ) -> None:
        """Log polling HTTP request."""
        self._logger.debug(
            "Polling request completed",
            extra={
                "url": self._mask_url(url),
                "method": method,
                "duration_ms": round(duration_ms, 2),
                "status_code": status_code,
            },
        )

    def polling_error(self, url: str, error: Exception) -> None:
        """Log polling error."""
        self._logger.warning(
            "Polling request failed",
            extra={
                "url": self._mask_url(url),
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )


# Type for message handlers
MessageHandler = Callable[[WebSocketMessage], Any]


class WebSocketClient:
    """Async WebSocket client for real-time updates.

    Provides WebSocket client capabilities with:
    - Automatic reconnection with exponential backoff
    - Heartbeat/ping mechanism for keepalive
    - Circuit breaker for fault tolerance
    - Polling fallback when WebSocket unavailable
    - Comprehensive logging
    """

    def __init__(self, config: WebSocketClientConfig) -> None:
        """Initialize WebSocket client.

        Args:
            config: Client configuration
        """
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._ws: WebSocketClientProtocol | None = None
        self._connection_id: str | None = None
        self._subscribed_projects: set[str] = set()

        # Timing
        self._connected_at: float | None = None
        self._last_ping: float = 0.0
        self._last_pong: float = 0.0

        # Reconnection tracking
        self._reconnect_attempt = 0
        self._should_reconnect = True

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(config.circuit_breaker)

        # Tasks
        self._receive_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._polling_task: asyncio.Task[None] | None = None

        # Message handlers
        self._handlers: dict[str, list[MessageHandler]] = {}

        # HTTP client for polling fallback
        self._http_client: httpx.AsyncClient | None = None

        # Logger
        self._log = WebSocketClientLogger()

        logger.debug(
            "WebSocketClient initialized",
            extra={"url": self._log._mask_url(config.url)},
        )

    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected to WebSocket."""
        return self._state == ConnectionState.CONNECTED

    @property
    def connection_id(self) -> str | None:
        """Get current connection ID."""
        return self._connection_id

    def on_message(self, message_type: str, handler: MessageHandler) -> None:
        """Register a handler for a specific message type.

        Args:
            message_type: Type of message to handle (e.g., "project_update")
            handler: Callback function to handle the message
        """
        if message_type not in self._handlers:
            self._handlers[message_type] = []
        self._handlers[message_type].append(handler)

    def off_message(self, message_type: str, handler: MessageHandler) -> None:
        """Unregister a message handler.

        Args:
            message_type: Type of message
            handler: Handler to remove
        """
        if message_type in self._handlers:
            with contextlib.suppress(ValueError):
                self._handlers[message_type].remove(handler)

    async def connect(self) -> bool:
        """Connect to the WebSocket server.

        Returns:
            True if connected successfully
        """
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            return self._state == ConnectionState.CONNECTED

        if not await self._circuit_breaker.can_execute():
            self._log.circuit_state_change(
                self._circuit_breaker.state.value, "blocked"
            )
            if self._config.polling_enabled:
                await self._start_polling("circuit_breaker_open")
            return False

        self._state = ConnectionState.CONNECTING
        self._should_reconnect = True
        start_time = time.monotonic()

        try:
            self._log.connection_attempt(
                self._config.url, self._reconnect_attempt, self._config.reconnect.max_attempts or None
            )

            # Connect with timeout
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self._config.url,
                    close_timeout=10,
                ),
                timeout=self._config.connect_timeout,
            )

            self._state = ConnectionState.CONNECTED
            self._connected_at = time.monotonic()
            self._last_pong = time.monotonic()
            self._reconnect_attempt = 0

            await self._circuit_breaker.record_success()

            duration_ms = (time.monotonic() - start_time) * 1000
            self._log.connection_established(
                self._config.url, self._connection_id, duration_ms
            )

            # Start background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Stop polling if it was running
            await self._stop_polling()

            return True

        except TimeoutError:
            self._log.timeout_error(
                self._config.url,
                self._config.connect_timeout,
                "connect",
                self._reconnect_attempt,
            )
            await self._circuit_breaker.record_failure()
            self._state = ConnectionState.DISCONNECTED
            return False

        except InvalidStatusCode as e:
            if e.status_code in (401, 403):
                self._log.auth_failure(self._config.url, e.status_code)
            else:
                self._log.connection_error(
                    self._config.url, e, "connect", self._reconnect_attempt
                )
            await self._circuit_breaker.record_failure()
            self._state = ConnectionState.DISCONNECTED
            return False

        except Exception as e:
            self._log.connection_error(
                self._config.url, e, "connect", self._reconnect_attempt
            )
            await self._circuit_breaker.record_failure()
            self._state = ConnectionState.DISCONNECTED
            return False

    async def disconnect(self, reason: str = "client_disconnect") -> None:
        """Disconnect from the WebSocket server.

        Args:
            reason: Reason for disconnection
        """
        self._should_reconnect = False
        self._state = ConnectionState.CLOSING

        # Cancel background tasks
        for task in [self._receive_task, self._heartbeat_task]:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        self._receive_task = None
        self._heartbeat_task = None

        # Stop polling
        await self._stop_polling()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        # Close WebSocket
        if self._ws:
            with contextlib.suppress(Exception):
                await self._ws.close(1000, reason)

        self._ws = None
        self._connection_id = None
        self._subscribed_projects.clear()
        self._state = ConnectionState.CLOSED

        self._log.connection_closed(self._config.url, reason, 1000)

    async def subscribe(self, project_id: str) -> bool:
        """Subscribe to updates for a project.

        Args:
            project_id: Project ID to subscribe to

        Returns:
            True if subscription was sent successfully
        """
        if self._state != ConnectionState.CONNECTED:
            # Track for re-subscription on reconnect
            self._subscribed_projects.add(project_id)
            return False

        success = await self._send_message({
            "type": "subscribe",
            "project_id": project_id,
        })

        if success:
            self._subscribed_projects.add(project_id)

        return success

    async def unsubscribe(self, project_id: str) -> bool:
        """Unsubscribe from updates for a project.

        Args:
            project_id: Project ID to unsubscribe from

        Returns:
            True if unsubscription was sent successfully
        """
        self._subscribed_projects.discard(project_id)

        if self._state != ConnectionState.CONNECTED:
            return True

        return await self._send_message({
            "type": "unsubscribe",
            "project_id": project_id,
        })

    async def _send_message(self, message: dict[str, Any]) -> bool:
        """Send a message to the server.

        Args:
            message: Message dict to send

        Returns:
            True if message was sent successfully
        """
        if self._state != ConnectionState.CONNECTED or not self._ws:
            return False

        try:
            message_str = json.dumps(message)
            await self._ws.send(message_str)
            self._log.message_sent(message.get("type", "unknown"), len(message_str))
            return True
        except Exception as e:
            self._log.connection_error(self._config.url, e, "send_message")
            return False

    async def _receive_loop(self) -> None:
        """Main loop for receiving WebSocket messages."""
        if not self._ws:
            return

        try:
            async for raw_message in self._ws:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")

                await self._handle_message(raw_message)

        except ConnectionClosedOK:
            self._log.connection_closed(self._config.url, "closed_ok", 1000)
        except ConnectionClosedError as e:
            self._log.connection_closed(self._config.url, str(e), e.code)
        except ConnectionClosed as e:
            self._log.connection_closed(self._config.url, str(e), e.code)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._log.connection_error(self._config.url, e, "receive_loop")
        finally:
            if self._should_reconnect:
                asyncio.create_task(self._schedule_reconnect())

    async def _handle_message(self, raw_message: str) -> None:
        """Handle an incoming WebSocket message.

        Args:
            raw_message: Raw JSON message string
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError as e:
            self._log.connection_error(self._config.url, e, "parse_message")
            return

        message_type = data.get("type", "unknown")
        self._log.message_received(message_type, len(raw_message))

        # Handle internal message types
        if message_type == "connected":
            self._connection_id = data.get("connection_id")
            # Re-subscribe to projects after reconnect
            for project_id in list(self._subscribed_projects):
                await self._send_message({
                    "type": "subscribe",
                    "project_id": project_id,
                })

        elif message_type == "ping":
            # Server ping - respond with pong
            await self._send_message({
                "type": "pong",
                "timestamp": data.get("timestamp"),
            })
            self._last_pong = time.monotonic()
            self._log.heartbeat_received()

        elif message_type == "pong":
            # Response to our ping
            self._last_pong = time.monotonic()
            self._log.heartbeat_received()

        elif message_type == "shutdown":
            # Server shutdown notice - prepare for reconnect
            self._log.connection_closed(
                self._config.url, data.get("reason", "server_shutdown"), None
            )

        # Create message object for handlers
        message = WebSocketMessage(
            type=message_type,
            data=data,
            timestamp=data.get("timestamp", time.time()),
            raw=raw_message,
        )

        # Call registered handlers
        handlers = self._handlers.get(message_type, [])
        for handler in handlers:
            try:
                result = handler(message)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(
                    "Message handler error",
                    extra={
                        "message_type": message_type,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat pings to keep connection alive."""
        while self._state == ConnectionState.CONNECTED:
            try:
                await asyncio.sleep(self._config.heartbeat_interval)

                if self._state != ConnectionState.CONNECTED:
                    break

                # Check for heartbeat timeout
                time_since_pong = time.monotonic() - self._last_pong
                if time_since_pong > self._config.heartbeat_timeout:
                    self._log.heartbeat_timeout(time_since_pong)
                    # Force reconnection
                    if self._ws:
                        await self._ws.close(1002, "heartbeat_timeout")
                    break

                # Send ping
                await self._send_message({
                    "type": "ping",
                    "timestamp": time.time(),
                })
                self._last_ping = time.monotonic()
                self._log.heartbeat_sent()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.connection_error(self._config.url, e, "heartbeat_loop")
                break

    async def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if not self._should_reconnect:
            return

        self._state = ConnectionState.RECONNECTING
        self._reconnect_attempt += 1

        # Check max attempts
        max_attempts = self._config.reconnect.max_attempts
        if max_attempts > 0 and self._reconnect_attempt > max_attempts:
            logger.warning(
                "Max reconnection attempts reached",
                extra={
                    "max_attempts": max_attempts,
                    "url": self._log._mask_url(self._config.url),
                },
            )
            self._state = ConnectionState.DISCONNECTED
            if self._config.polling_enabled:
                await self._start_polling("max_reconnect_attempts")
            return

        # Calculate delay with exponential backoff
        delay = self._config.reconnect.get_delay(self._reconnect_attempt - 1)
        self._log.reconnection_scheduled(delay, self._reconnect_attempt)

        await asyncio.sleep(delay)

        if self._should_reconnect:
            await self.connect()

    async def _start_polling(self, reason: str) -> None:
        """Start polling fallback mode.

        Args:
            reason: Reason for falling back to polling
        """
        if self._state == ConnectionState.FALLBACK_POLLING:
            return

        self._log.fallback_to_polling(self._config.url, reason)
        self._state = ConnectionState.FALLBACK_POLLING

        if self._polling_task is None or self._polling_task.done():
            self._polling_task = asyncio.create_task(self._polling_loop())

    async def _stop_polling(self) -> None:
        """Stop polling fallback mode."""
        if self._polling_task:
            self._polling_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._polling_task
            self._polling_task = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for polling."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._config.message_timeout),
            )
        return self._http_client

    async def _polling_loop(self) -> None:
        """Polling loop for fallback mode."""
        # Convert WebSocket URL to HTTP for polling
        poll_url = self._config.url.replace("ws://", "http://").replace("wss://", "https://")
        # Assume there's a polling endpoint at /api/v1/projects/{id}/status
        base_url = poll_url.rsplit("/ws/", 1)[0] if "/ws/" in poll_url else poll_url

        client = await self._get_http_client()

        while self._state == ConnectionState.FALLBACK_POLLING:
            try:
                await asyncio.sleep(self._config.polling_interval)

                if self._state != ConnectionState.FALLBACK_POLLING:
                    break

                # Poll for each subscribed project
                for project_id in list(self._subscribed_projects):
                    try:
                        start_time = time.monotonic()
                        url = f"{base_url}/api/v1/projects/{project_id}/status"

                        response = await client.get(url)
                        duration_ms = (time.monotonic() - start_time) * 1000

                        self._log.polling_request(url, "GET", duration_ms, response.status_code)

                        if response.status_code == 200:
                            data = response.json()
                            # Create a synthetic message for handlers
                            message = WebSocketMessage(
                                type="project_update",
                                data={
                                    "event": "polling_update",
                                    "project_id": project_id,
                                    "data": data,
                                },
                                timestamp=time.time(),
                                raw=json.dumps(data),
                            )

                            handlers = self._handlers.get("project_update", [])
                            for handler in handlers:
                                try:
                                    result = handler(message)
                                    if asyncio.iscoroutine(result):
                                        await result
                                except Exception as e:
                                    logger.error(
                                        "Polling handler error",
                                        extra={
                                            "project_id": project_id,
                                            "error_type": type(e).__name__,
                                        },
                                        exc_info=True,
                                    )

                    except Exception as e:
                        self._log.polling_error(f"{base_url}/api/v1/projects/{project_id}/status", e)

                # Periodically try to reconnect WebSocket
                if await self._circuit_breaker.can_execute():
                    logger.info("Attempting WebSocket reconnection from polling mode")
                    if await self.connect():
                        break

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Polling loop error",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

    async def wait_for_message(
        self,
        message_type: str,
        timeout: float | None = None,
    ) -> WebSocketMessage | None:
        """Wait for a specific message type.

        Args:
            message_type: Type of message to wait for
            timeout: Optional timeout in seconds

        Returns:
            Received message or None if timeout
        """
        timeout = timeout or self._config.message_timeout
        event = asyncio.Event()
        received_message: WebSocketMessage | None = None

        def handler(msg: WebSocketMessage) -> None:
            nonlocal received_message
            received_message = msg
            event.set()

        self.on_message(message_type, handler)

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return received_message
        except TimeoutError:
            return None
        finally:
            self.off_message(message_type, handler)


# Singleton instance
_websocket_client: WebSocketClient | None = None


def get_websocket_client(config: WebSocketClientConfig | None = None) -> WebSocketClient:
    """Get or create the global WebSocket client.

    Args:
        config: Optional configuration (required on first call)

    Returns:
        WebSocket client instance

    Raises:
        ValueError: If config is None on first call
    """
    global _websocket_client

    if _websocket_client is None:
        if config is None:
            raise ValueError("WebSocketClientConfig required on first call")
        _websocket_client = WebSocketClient(config)
        logger.info("WebSocket client initialized")

    return _websocket_client


async def close_websocket_client() -> None:
    """Close the global WebSocket client."""
    global _websocket_client

    if _websocket_client is not None:
        await _websocket_client.disconnect()
        _websocket_client = None
        logger.info("WebSocket client closed")
