"""WebSocket endpoint for real-time project status updates.

Railway Deployment Requirements:
- Railway supports WebSocket connections
- Heartbeat/ping keeps connections alive
- Handle reconnection gracefully (deploys will disconnect clients)
- Fallback to polling handled client-side

ERROR LOGGING REQUIREMENTS:
- Log all incoming requests with method, path, request_id
- Log request body at DEBUG level (sanitize sensitive fields)
- Log response status and timing for every request
- Return structured error responses: {"error": str, "code": str, "request_id": str}
- Log 4xx errors at WARNING, 5xx at ERROR
- Include user context if available
- Log rate limit hits at WARNING level
"""

from fastapi import APIRouter, WebSocket

from app.core.logging import get_logger
from app.core.websocket import connection_manager

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/projects")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time project status updates.

    Connect to this endpoint to receive real-time updates for projects.
    Send subscription messages to receive updates for specific projects.

    Message Protocol:
    -----------------

    **Client -> Server Messages:**

    Subscribe to a project:
    ```json
    {"type": "subscribe", "project_id": "uuid"}
    ```

    Unsubscribe from a project:
    ```json
    {"type": "unsubscribe", "project_id": "uuid"}
    ```

    Ping (client-initiated keepalive):
    ```json
    {"type": "ping"}
    ```

    Pong (response to server ping):
    ```json
    {"type": "pong"}
    ```

    **Server -> Client Messages:**

    Connection established:
    ```json
    {
        "type": "connected",
        "connection_id": "uuid",
        "heartbeat_interval": 30,
        "reconnect_advice": {
            "should_reconnect": true,
            "initial_delay_ms": 1000,
            "max_delay_ms": 30000,
            "backoff_multiplier": 2.0
        }
    }
    ```

    Subscription confirmed:
    ```json
    {"type": "subscribed", "project_id": "uuid"}
    ```

    Unsubscription confirmed:
    ```json
    {"type": "unsubscribed", "project_id": "uuid"}
    ```

    Project update:
    ```json
    {
        "type": "project_update",
        "event": "status_changed",
        "project_id": "uuid",
        "data": {...},
        "timestamp": 1234567890.123
    }
    ```

    Server heartbeat ping:
    ```json
    {"type": "ping", "timestamp": 1234567890.123}
    ```

    Server shutdown notice:
    ```json
    {
        "type": "shutdown",
        "reason": "server_shutdown",
        "reconnect_advice": {
            "should_reconnect": true,
            "initial_delay_ms": 1000,
            "max_delay_ms": 30000,
            "backoff_multiplier": 2.0
        }
    }
    ```

    Error response:
    ```json
    {"type": "error", "code": "ERROR_CODE", "error": "Error description"}
    ```

    **Reconnection:**

    When the connection is closed (e.g., during Railway deploys),
    clients should implement exponential backoff reconnection:
    1. Wait initial_delay_ms (1 second)
    2. If reconnection fails, multiply delay by backoff_multiplier
    3. Cap delay at max_delay_ms (30 seconds)
    4. Continue attempting until reconnected
    """
    await connection_manager.run_connection(websocket)


@router.get("/ws/health")
async def websocket_health() -> dict[str, str | int | bool]:
    """Health check endpoint for WebSocket service.

    Returns information about the WebSocket connection manager,
    including the number of active connections and heartbeat status.
    """
    return {
        "status": "ok",
        "active_connections": connection_manager.connection_count,
        "heartbeat_enabled": connection_manager._running,
    }
