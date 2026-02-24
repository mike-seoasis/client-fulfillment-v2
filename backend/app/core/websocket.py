"""WebSocket connection manager for real-time project status updates.

Railway Deployment Requirements:
- Railway supports WebSocket connections natively
- Implement heartbeat/ping to keep connections alive
- Handle reconnection gracefully (deploys will disconnect clients)
- Fallback to polling is handled client-side

ERROR LOGGING REQUIREMENTS:
- Log all incoming connections with connection_id
- Log connection close with reason
- Log message send/receive at DEBUG level
- Log errors at ERROR level with full context
- Log rate limit hits at WARNING level
"""

import asyncio
import contextlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class WebSocketConnection:
    """Wrapper for WebSocket connection with metadata."""

    websocket: WebSocket
    connection_id: str
    project_ids: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    last_pong: float = field(default_factory=time.time)
    state: ConnectionState = ConnectionState.CONNECTING

    def subscribe(self, project_id: str) -> None:
        """Subscribe to updates for a project."""
        self.project_ids.add(project_id)

    def unsubscribe(self, project_id: str) -> None:
        """Unsubscribe from updates for a project."""
        self.project_ids.discard(project_id)


class WebSocketLogger:
    """Logger for WebSocket operations with required error logging."""

    def __init__(self) -> None:
        self.logger = get_logger("websocket")

    def connection_opened(self, connection_id: str, client_host: str | None) -> None:
        """Log WebSocket connection opened."""
        self.logger.info(
            "WebSocket connection opened",
            extra={
                "connection_id": connection_id,
                "client_host": client_host,
            },
        )

    def connection_closed(
        self, connection_id: str, reason: str | None, code: int | None = None
    ) -> None:
        """Log WebSocket connection closed."""
        self.logger.info(
            "WebSocket connection closed",
            extra={
                "connection_id": connection_id,
                "close_reason": reason,
                "close_code": code,
            },
        )

    def connection_error(
        self, connection_id: str, error: Exception, context: str | None = None
    ) -> None:
        """Log WebSocket connection error."""
        self.logger.error(
            "WebSocket connection error",
            extra={
                "connection_id": connection_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
            },
            exc_info=True,
        )

    def message_received(
        self, connection_id: str, message_type: str, payload_size: int
    ) -> None:
        """Log incoming WebSocket message at DEBUG level."""
        self.logger.debug(
            "WebSocket message received",
            extra={
                "connection_id": connection_id,
                "message_type": message_type,
                "payload_size": payload_size,
            },
        )

    def message_sent(
        self, connection_id: str, message_type: str, payload_size: int
    ) -> None:
        """Log outgoing WebSocket message at DEBUG level."""
        self.logger.debug(
            "WebSocket message sent",
            extra={
                "connection_id": connection_id,
                "message_type": message_type,
                "payload_size": payload_size,
            },
        )

    def subscription_changed(
        self, connection_id: str, project_id: str, action: str
    ) -> None:
        """Log subscription change."""
        self.logger.info(
            f"WebSocket subscription {action}",
            extra={
                "connection_id": connection_id,
                "project_id": project_id,
                "action": action,
            },
        )

    def heartbeat_sent(self, connection_id: str) -> None:
        """Log heartbeat ping sent."""
        self.logger.debug(
            "WebSocket heartbeat sent",
            extra={"connection_id": connection_id},
        )

    def heartbeat_timeout(
        self, connection_id: str, last_pong_seconds_ago: float
    ) -> None:
        """Log heartbeat timeout."""
        self.logger.warning(
            "WebSocket heartbeat timeout",
            extra={
                "connection_id": connection_id,
                "last_pong_seconds_ago": round(last_pong_seconds_ago, 2),
            },
        )

    def broadcast_sent(
        self, project_id: str, message_type: str, connection_count: int
    ) -> None:
        """Log broadcast message sent to project subscribers."""
        self.logger.info(
            "WebSocket broadcast sent",
            extra={
                "project_id": project_id,
                "message_type": message_type,
                "connection_count": connection_count,
            },
        )

    def broadcast_failure(
        self, connection_id: str, project_id: str, message_type: str
    ) -> None:
        """Log broadcast failure for a specific client."""
        self.logger.warning(
            "WebSocket broadcast failed for client",
            extra={
                "connection_id": connection_id,
                "project_id": project_id,
                "message_type": message_type,
            },
        )

    def progress_broadcast_sent(
        self,
        project_id: str,
        crawl_id: str,
        connection_count: int,
        progress: dict[str, Any],
    ) -> None:
        """Log progress broadcast sent to project subscribers."""
        self.logger.info(
            "WebSocket progress broadcast sent",
            extra={
                "project_id": project_id,
                "crawl_id": crawl_id,
                "connection_count": connection_count,
                "pages_crawled": progress.get("pages_crawled", 0),
                "pages_failed": progress.get("pages_failed", 0),
                "status": progress.get("status"),
            },
        )

    def progress_update_no_subscribers(self, project_id: str, crawl_id: str) -> None:
        """Log progress update with no subscribers."""
        self.logger.debug(
            "No subscribers for progress update",
            extra={
                "project_id": project_id,
                "crawl_id": crawl_id,
            },
        )


# Singleton WebSocket logger
ws_logger = WebSocketLogger()


class ConnectionManager:
    """Manages WebSocket connections for real-time project updates.

    Features:
    - Connection tracking by ID and project subscription
    - Heartbeat/ping mechanism for keepalive
    - Broadcast messages to project subscribers
    - Graceful disconnect handling for Railway deploys
    """

    # Heartbeat interval in seconds (Railway idle timeout is typically 60s)
    HEARTBEAT_INTERVAL = 30
    # Timeout before considering connection dead
    HEARTBEAT_TIMEOUT = 90

    def __init__(self) -> None:
        """Initialize connection manager."""
        self._connections: dict[str, WebSocketConnection] = {}
        self._project_connections: dict[str, set[str]] = {}
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._running = False
        logger.debug("ConnectionManager initialized")

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._connections)

    async def start_heartbeat(self) -> None:
        """Start the heartbeat task for connection keepalive."""
        if self._running:
            return
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("WebSocket heartbeat task started")

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat task."""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        logger.info("WebSocket heartbeat task stopped")

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat pings to all connections."""
        while self._running:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                await self._send_heartbeats()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Heartbeat loop error",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                    exc_info=True,
                )

    async def _send_heartbeats(self) -> None:
        """Send heartbeat pings and check for timeouts."""
        current_time = time.time()
        stale_connections: list[str] = []

        for conn_id, conn in list(self._connections.items()):
            if conn.state != ConnectionState.CONNECTED:
                continue

            # Check for heartbeat timeout
            time_since_pong = current_time - conn.last_pong
            if time_since_pong > self.HEARTBEAT_TIMEOUT:
                ws_logger.heartbeat_timeout(conn_id, time_since_pong)
                stale_connections.append(conn_id)
                continue

            # Send ping
            try:
                await conn.websocket.send_json(
                    {
                        "type": "ping",
                        "timestamp": current_time,
                    }
                )
                conn.last_ping = current_time
                ws_logger.heartbeat_sent(conn_id)
            except Exception as e:
                ws_logger.connection_error(conn_id, e, "heartbeat_send")
                stale_connections.append(conn_id)

        # Clean up stale connections
        for conn_id in stale_connections:
            await self.disconnect(conn_id, reason="heartbeat_timeout")

    async def connect(self, websocket: WebSocket) -> WebSocketConnection:
        """Accept a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance

        Returns:
            WebSocketConnection wrapper with metadata
        """
        connection_id = str(uuid.uuid4())
        client_host = websocket.client.host if websocket.client else None

        await websocket.accept()

        conn = WebSocketConnection(
            websocket=websocket,
            connection_id=connection_id,
        )
        conn.state = ConnectionState.CONNECTED

        self._connections[connection_id] = conn
        ws_logger.connection_opened(connection_id, client_host)

        # Send welcome message with reconnection guidance
        await self._send_message(
            conn,
            {
                "type": "connected",
                "connection_id": connection_id,
                "heartbeat_interval": self.HEARTBEAT_INTERVAL,
                "reconnect_advice": {
                    "should_reconnect": True,
                    "initial_delay_ms": 1000,
                    "max_delay_ms": 30000,
                    "backoff_multiplier": 2.0,
                },
            },
        )

        return conn

    async def disconnect(
        self,
        connection_id: str,
        reason: str | None = None,
        code: int = 1000,
    ) -> None:
        """Disconnect and clean up a WebSocket connection.

        Args:
            connection_id: ID of the connection to disconnect
            reason: Reason for disconnection
            code: WebSocket close code
        """
        conn = self._connections.get(connection_id)
        if not conn:
            return

        conn.state = ConnectionState.CLOSING

        # Unsubscribe from all projects
        for project_id in list(conn.project_ids):
            self._unsubscribe_connection(connection_id, project_id)

        # Close the WebSocket (suppress errors if already closed)
        with contextlib.suppress(Exception):
            await conn.websocket.close(code=code, reason=reason)

        conn.state = ConnectionState.CLOSED
        del self._connections[connection_id]
        ws_logger.connection_closed(connection_id, reason, code)

    def _subscribe_connection(self, connection_id: str, project_id: str) -> None:
        """Subscribe a connection to a project's updates."""
        conn = self._connections.get(connection_id)
        if not conn:
            return

        conn.subscribe(project_id)

        if project_id not in self._project_connections:
            self._project_connections[project_id] = set()
        self._project_connections[project_id].add(connection_id)

        ws_logger.subscription_changed(connection_id, project_id, "subscribed")

    def _unsubscribe_connection(self, connection_id: str, project_id: str) -> None:
        """Unsubscribe a connection from a project's updates."""
        conn = self._connections.get(connection_id)
        if conn:
            conn.unsubscribe(project_id)

        if project_id in self._project_connections:
            self._project_connections[project_id].discard(connection_id)
            if not self._project_connections[project_id]:
                del self._project_connections[project_id]

        ws_logger.subscription_changed(connection_id, project_id, "unsubscribed")

    async def _send_message(
        self, conn: WebSocketConnection, message: dict[str, Any]
    ) -> bool:
        """Send a message to a specific connection.

        Args:
            conn: WebSocket connection wrapper
            message: Message dict to send

        Returns:
            True if message was sent successfully
        """
        if conn.state != ConnectionState.CONNECTED:
            return False

        try:
            message_str = json.dumps(message)
            await conn.websocket.send_text(message_str)
            ws_logger.message_sent(
                conn.connection_id,
                message.get("type", "unknown"),
                len(message_str),
            )
            return True
        except Exception as e:
            ws_logger.connection_error(conn.connection_id, e, "send_message")
            return False

    async def handle_message(
        self, conn: WebSocketConnection, raw_message: str
    ) -> dict[str, Any] | None:
        """Handle an incoming WebSocket message.

        Args:
            conn: WebSocket connection wrapper
            raw_message: Raw JSON message string

        Returns:
            Response message dict or None
        """
        ws_logger.message_received(
            conn.connection_id,
            "raw",
            len(raw_message),
        )

        try:
            message = json.loads(raw_message)
        except json.JSONDecodeError as e:
            ws_logger.connection_error(conn.connection_id, e, "parse_message")
            return {
                "type": "error",
                "code": "INVALID_JSON",
                "error": "Invalid JSON message",
            }

        message_type = message.get("type")

        if message_type == "pong":
            # Client responding to heartbeat
            conn.last_pong = time.time()
            return None

        elif message_type == "subscribe":
            project_id = message.get("project_id")
            if not project_id:
                return {
                    "type": "error",
                    "code": "MISSING_PROJECT_ID",
                    "error": "project_id is required for subscribe",
                }
            self._subscribe_connection(conn.connection_id, project_id)
            return {
                "type": "subscribed",
                "project_id": project_id,
            }

        elif message_type == "unsubscribe":
            project_id = message.get("project_id")
            if not project_id:
                return {
                    "type": "error",
                    "code": "MISSING_PROJECT_ID",
                    "error": "project_id is required for unsubscribe",
                }
            self._unsubscribe_connection(conn.connection_id, project_id)
            return {
                "type": "unsubscribed",
                "project_id": project_id,
            }

        elif message_type == "ping":
            # Client-initiated ping
            return {
                "type": "pong",
                "timestamp": time.time(),
            }

        else:
            return {
                "type": "error",
                "code": "UNKNOWN_MESSAGE_TYPE",
                "error": f"Unknown message type: {message_type}",
            }

    async def broadcast_project_update(
        self,
        project_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> int:
        """Broadcast a project update to all subscribed connections.

        Args:
            project_id: ID of the project that was updated
            event_type: Type of update (e.g., "status_changed", "phase_updated")
            data: Update data to send

        Returns:
            Number of connections the message was sent to
        """
        connection_ids = self._project_connections.get(project_id, set())
        if not connection_ids:
            return 0

        message = {
            "type": "project_update",
            "event": event_type,
            "project_id": project_id,
            "data": data,
            "timestamp": time.time(),
        }

        sent_count = 0
        failed_connections: list[str] = []

        for conn_id in connection_ids:
            conn = self._connections.get(conn_id)
            if conn:
                success = await self._send_message(conn, message)
                if success:
                    sent_count += 1
                else:
                    # Log broadcast failure per-client
                    ws_logger.broadcast_failure(conn_id, project_id, event_type)
                    failed_connections.append(conn_id)

        # Clean up failed connections
        for conn_id in failed_connections:
            await self.disconnect(conn_id, reason="send_failed")

        ws_logger.broadcast_sent(project_id, event_type, sent_count)
        return sent_count

    async def broadcast_progress_update(
        self,
        project_id: str,
        crawl_id: str,
        progress: dict[str, Any],
    ) -> int:
        """Broadcast crawl progress update to all subscribed connections.

        Args:
            project_id: ID of the project
            crawl_id: ID of the crawl job
            progress: Progress data to send

        Returns:
            Number of connections the message was sent to

        ERROR LOGGING REQUIREMENTS:
        - Log broadcast failures per-client
        - Include connection_id in all WebSocket logs
        """
        connection_ids = self._project_connections.get(project_id, set())
        if not connection_ids:
            ws_logger.progress_update_no_subscribers(project_id, crawl_id)
            return 0

        message = {
            "type": "progress_update",
            "project_id": project_id,
            "crawl_id": crawl_id,
            "progress": progress,
            "timestamp": time.time(),
        }

        sent_count = 0
        failed_connections: list[str] = []

        for conn_id in connection_ids:
            conn = self._connections.get(conn_id)
            if conn:
                success = await self._send_message(conn, message)
                if success:
                    sent_count += 1
                else:
                    # Log broadcast failure per-client
                    ws_logger.broadcast_failure(conn_id, project_id, "progress_update")
                    failed_connections.append(conn_id)

        # Clean up failed connections
        for conn_id in failed_connections:
            await self.disconnect(conn_id, reason="send_failed")

        ws_logger.progress_broadcast_sent(project_id, crawl_id, sent_count, progress)
        return sent_count

    async def broadcast_shutdown(self, reason: str = "server_shutdown") -> None:
        """Broadcast shutdown notice to all connections.

        Args:
            reason: Reason for shutdown
        """
        message = {
            "type": "shutdown",
            "reason": reason,
            "reconnect_advice": {
                "should_reconnect": True,
                "initial_delay_ms": 1000,
                "max_delay_ms": 30000,
                "backoff_multiplier": 2.0,
            },
        }

        for _conn_id, conn in list(self._connections.items()):
            with contextlib.suppress(Exception):
                await self._send_message(conn, message)

        logger.info(
            "Shutdown broadcast sent",
            extra={"connection_count": len(self._connections)},
        )

    async def run_connection(self, websocket: WebSocket) -> None:
        """Main loop for handling a WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
        """
        conn = await self.connect(websocket)

        try:
            while conn.state == ConnectionState.CONNECTED:
                try:
                    raw_message = await websocket.receive_text()
                    response = await self.handle_message(conn, raw_message)
                    if response:
                        await self._send_message(conn, response)
                except WebSocketDisconnect as e:
                    ws_logger.connection_closed(
                        conn.connection_id,
                        reason="client_disconnect",
                        code=e.code,
                    )
                    break
        except Exception as e:
            ws_logger.connection_error(conn.connection_id, e, "connection_loop")
        finally:
            await self.disconnect(conn.connection_id, reason="connection_ended")


# Singleton connection manager
connection_manager = ConnectionManager()
