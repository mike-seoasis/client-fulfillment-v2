"""Tests for WebSocket client.

Tests cover:
- Connection management (connect, disconnect, reconnect)
- Heartbeat/ping mechanism
- Message handling and handlers
- Circuit breaker behavior
- Polling fallback
- Error scenarios
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.websocket_client import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    ConnectionState,
    ReconnectConfig,
    WebSocketClient,
    WebSocketClientConfig,
    WebSocketClientLogger,
    WebSocketMessage,
    close_websocket_client,
    get_websocket_client,
)

# Silence unused import warning - these are used
_ = WebSocketClientLogger
_ = WebSocketMessage


# Fixtures


@pytest.fixture
def config():
    """Create a test WebSocket client configuration."""
    return WebSocketClientConfig(
        url="ws://localhost:8000/ws/projects",
        heartbeat_interval=1.0,
        heartbeat_timeout=3.0,
        connect_timeout=5.0,
        message_timeout=10.0,
        reconnect=ReconnectConfig(
            initial_delay_ms=100,
            max_delay_ms=1000,
            backoff_multiplier=2.0,
            max_attempts=3,
        ),
        circuit_breaker=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=5.0,
        ),
        polling_interval=1.0,
        polling_enabled=True,
    )


@pytest.fixture
def client(config):
    """Create a test WebSocket client."""
    return WebSocketClient(config)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    mock = AsyncMock()
    mock.close = AsyncMock()
    mock.send = AsyncMock()
    return mock


# ReconnectConfig Tests


class TestReconnectConfig:
    """Tests for ReconnectConfig."""

    def test_get_delay_first_attempt(self):
        """Test delay calculation for first attempt."""
        config = ReconnectConfig(
            initial_delay_ms=1000,
            max_delay_ms=30000,
            backoff_multiplier=2.0,
        )
        assert config.get_delay(0) == 1.0  # 1000ms = 1s

    def test_get_delay_with_backoff(self):
        """Test delay calculation with exponential backoff."""
        config = ReconnectConfig(
            initial_delay_ms=1000,
            max_delay_ms=30000,
            backoff_multiplier=2.0,
        )
        assert config.get_delay(0) == 1.0   # 1000ms
        assert config.get_delay(1) == 2.0   # 2000ms
        assert config.get_delay(2) == 4.0   # 4000ms
        assert config.get_delay(3) == 8.0   # 8000ms

    def test_get_delay_capped_at_max(self):
        """Test that delay is capped at max_delay_ms."""
        config = ReconnectConfig(
            initial_delay_ms=1000,
            max_delay_ms=5000,
            backoff_multiplier=2.0,
        )
        assert config.get_delay(10) == 5.0  # Capped at 5000ms = 5s


# CircuitBreaker Tests


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a test circuit breaker."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,
        )
        return CircuitBreaker(config)

    async def test_initial_state_is_closed(self, circuit_breaker):
        """Test that circuit breaker starts in closed state."""
        assert circuit_breaker.state == CircuitState.CLOSED
        assert not circuit_breaker.is_open

    async def test_can_execute_when_closed(self, circuit_breaker):
        """Test that operations can execute when circuit is closed."""
        assert await circuit_breaker.can_execute() is True

    async def test_opens_after_failure_threshold(self, circuit_breaker):
        """Test that circuit opens after reaching failure threshold."""
        for _ in range(3):
            await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN
        assert circuit_breaker.is_open
        assert await circuit_breaker.can_execute() is False

    async def test_success_resets_failure_count(self, circuit_breaker):
        """Test that success resets the failure count."""
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()
        await circuit_breaker.record_success()

        # Should be able to have more failures
        await circuit_breaker.record_failure()
        await circuit_breaker.record_failure()

        # Should not be open yet (count reset)
        assert circuit_breaker.state == CircuitState.CLOSED

    async def test_half_open_after_recovery_timeout(self, circuit_breaker):
        """Test that circuit transitions to half-open after recovery timeout."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Should transition to half-open when checked
        assert await circuit_breaker.can_execute() is True
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    async def test_closes_on_success_in_half_open(self, circuit_breaker):
        """Test that circuit closes on success when in half-open state."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        await asyncio.sleep(1.1)
        await circuit_breaker.can_execute()  # Transition to half-open

        await circuit_breaker.record_success()

        assert circuit_breaker.state == CircuitState.CLOSED

    async def test_reopens_on_failure_in_half_open(self, circuit_breaker):
        """Test that circuit reopens on failure when in half-open state."""
        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure()

        await asyncio.sleep(1.1)
        await circuit_breaker.can_execute()  # Transition to half-open

        await circuit_breaker.record_failure()

        assert circuit_breaker.state == CircuitState.OPEN


# WebSocketClientLogger Tests


class TestWebSocketClientLogger:
    """Tests for WebSocketClientLogger."""

    def test_mask_url_with_token(self):
        """Test URL masking for tokens."""
        logger = WebSocketClientLogger()
        url = "ws://localhost:8000/ws/projects?token=secret123"
        masked = logger._mask_url(url)
        assert "secret123" not in masked
        assert "token=***" in masked

    def test_mask_url_with_key(self):
        """Test URL masking for API keys."""
        logger = WebSocketClientLogger()
        url = "ws://localhost:8000/ws?api_key=mysecretkey"
        masked = logger._mask_url(url)
        assert "mysecretkey" not in masked
        assert "api_key=***" in masked

    def test_mask_url_truncation(self):
        """Test URL truncation for long URLs."""
        logger = WebSocketClientLogger()
        url = "ws://localhost:8000/" + "a" * 300
        masked = logger._mask_url(url)
        assert len(masked) <= 200


# WebSocketClient Tests


class TestWebSocketClientInit:
    """Tests for WebSocketClient initialization."""

    def test_initial_state(self, client):
        """Test client initial state."""
        assert client.state == ConnectionState.DISCONNECTED
        assert client.is_connected is False
        assert client.connection_id is None

    def test_config_stored(self, client, config):
        """Test that configuration is stored."""
        assert client._config == config


class TestWebSocketClientConnect:
    """Tests for WebSocketClient connection."""

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_successful_connect(self, mock_connect, client, mock_websocket):
        """Test successful WebSocket connection."""
        # Setup mock as awaitable that returns the mock websocket
        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        # Make the async iterator return nothing (empty message stream)
        async def empty_iter():
            return
            yield  # Make this a generator

        mock_websocket.__aiter__ = lambda _self: empty_iter()
        mock_connect.side_effect = mock_connect_coro

        # Connect
        result = await client.connect()

        assert result is True
        assert client.state == ConnectionState.CONNECTED
        assert client.is_connected is True

        # Cleanup
        await client.disconnect()

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_connect_timeout(self, mock_connect, client):
        """Test connection timeout handling."""
        async def slow_connect(*args, **kwargs):
            await asyncio.sleep(10)

        mock_connect.side_effect = slow_connect

        result = await client.connect()

        assert result is False
        assert client.state == ConnectionState.DISCONNECTED

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_connect_auth_failure(self, mock_connect, client):
        """Test authentication failure handling."""
        from websockets.exceptions import (  # type: ignore[attr-defined]
            InvalidStatusCode,
        )

        mock_connect.side_effect = InvalidStatusCode(403, None)

        result = await client.connect()

        assert result is False
        assert client.state == ConnectionState.DISCONNECTED

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_connect_circuit_breaker_open(self, mock_connect, client):
        """Test that connection fails when circuit breaker is open."""
        # Open the circuit breaker
        for _ in range(3):
            await client._circuit_breaker.record_failure()

        result = await client.connect()

        assert result is False
        mock_connect.assert_not_called()


class TestWebSocketClientDisconnect:
    """Tests for WebSocketClient disconnection."""

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_disconnect_cleans_up(self, mock_connect, client, mock_websocket):
        """Test that disconnect cleans up resources."""
        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        async def empty_iter():
            return
            yield

        mock_websocket.__aiter__ = lambda _self: empty_iter()
        mock_connect.side_effect = mock_connect_coro

        await client.connect()
        await client.disconnect()

        assert client.state == ConnectionState.CLOSED
        assert client.is_connected is False
        assert client._ws is None
        mock_websocket.close.assert_called_once()

    async def test_disconnect_idempotent(self, client):
        """Test that disconnect is safe to call multiple times."""
        await client.disconnect()
        await client.disconnect()

        assert client.state == ConnectionState.CLOSED


class TestWebSocketClientSubscription:
    """Tests for WebSocketClient subscription management."""

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_subscribe_when_connected(self, mock_connect, client, mock_websocket):
        """Test subscribing when connected."""
        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        async def empty_iter():
            return
            yield

        mock_websocket.__aiter__ = lambda _self: empty_iter()
        mock_connect.side_effect = mock_connect_coro

        await client.connect()
        result = await client.subscribe("project-123")

        assert result is True
        assert "project-123" in client._subscribed_projects
        mock_websocket.send.assert_called()

        await client.disconnect()

    async def test_subscribe_when_disconnected(self, client):
        """Test subscribing when disconnected (tracks for reconnect)."""
        result = await client.subscribe("project-123")

        assert result is False
        assert "project-123" in client._subscribed_projects

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_unsubscribe(self, mock_connect, client, mock_websocket):
        """Test unsubscribing."""
        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        async def empty_iter():
            return
            yield

        mock_websocket.__aiter__ = lambda _self: empty_iter()
        mock_connect.side_effect = mock_connect_coro

        await client.connect()
        await client.subscribe("project-123")
        result = await client.unsubscribe("project-123")

        assert result is True
        assert "project-123" not in client._subscribed_projects

        await client.disconnect()


class TestWebSocketClientMessageHandling:
    """Tests for WebSocketClient message handling."""

    def test_register_handler(self, client):
        """Test registering a message handler."""
        handler = MagicMock()
        client.on_message("project_update", handler)

        assert "project_update" in client._handlers
        assert handler in client._handlers["project_update"]

    def test_unregister_handler(self, client):
        """Test unregistering a message handler."""
        handler = MagicMock()
        client.on_message("project_update", handler)
        client.off_message("project_update", handler)

        assert handler not in client._handlers.get("project_update", [])

    async def test_handle_connected_message(self, client):
        """Test handling connected message."""
        message = json.dumps({
            "type": "connected",
            "connection_id": "conn-123",
            "heartbeat_interval": 30,
        })

        await client._handle_message(message)

        assert client._connection_id == "conn-123"

    async def test_handle_ping_message(self, client, mock_websocket):
        """Test handling server ping message."""
        client._ws = mock_websocket
        client._state = ConnectionState.CONNECTED

        message = json.dumps({
            "type": "ping",
            "timestamp": 12345.0,
        })

        await client._handle_message(message)

        # Should send pong response
        mock_websocket.send.assert_called()
        call_args = mock_websocket.send.call_args[0][0]
        assert "pong" in call_args

    async def test_handler_called_on_message(self, client):
        """Test that registered handlers are called."""
        received_messages = []

        def handler(msg: WebSocketMessage):
            received_messages.append(msg)

        client.on_message("project_update", handler)

        message = json.dumps({
            "type": "project_update",
            "event": "status_changed",
            "project_id": "project-123",
            "data": {"status": "completed"},
        })

        await client._handle_message(message)

        assert len(received_messages) == 1
        assert received_messages[0].type == "project_update"
        assert received_messages[0].data["project_id"] == "project-123"

    async def test_async_handler_supported(self, client):
        """Test that async handlers are supported."""
        received_messages = []

        async def handler(msg: WebSocketMessage):
            await asyncio.sleep(0.01)
            received_messages.append(msg)

        client.on_message("project_update", handler)

        message = json.dumps({
            "type": "project_update",
            "data": {},
        })

        await client._handle_message(message)

        assert len(received_messages) == 1


class TestWebSocketClientReconnection:
    """Tests for WebSocketClient reconnection."""

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_reconnect_attempt_count(self, mock_connect, config):
        """Test that reconnection attempts are tracked when connection fails."""
        # Create client with limited reconnect attempts
        config.reconnect.max_attempts = 2
        client = WebSocketClient(config)

        # Make connect fail
        async def fail_connect(*args, **kwargs):
            raise ConnectionRefusedError()

        mock_connect.side_effect = fail_connect

        # First attempt will fail and increment counter, but circuit breaker
        # catches and records failure. The reconnect_attempt is incremented
        # in _schedule_reconnect, not in connect.
        await client.connect()

        # After failed connect, reconnect_attempt is still 0
        # It gets incremented in _schedule_reconnect
        assert client._reconnect_attempt == 0

        # Set should_reconnect and call _schedule_reconnect
        client._should_reconnect = True
        await client._schedule_reconnect()

        # Now it should be incremented
        assert client._reconnect_attempt == 1

        await client.disconnect()

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_reconnect_with_exponential_backoff(self, mock_connect, client):
        """Test that reconnection uses exponential backoff delay."""
        # Just test the delay calculation, not the actual connection
        delay_1 = client._config.reconnect.get_delay(0)
        delay_2 = client._config.reconnect.get_delay(1)

        assert delay_2 > delay_1  # Exponential backoff

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_subscriptions_restored_on_reconnect(self, mock_connect, client, mock_websocket):
        """Test that subscriptions are restored after reconnection."""
        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        async def empty_iter():
            return
            yield

        mock_websocket.__aiter__ = lambda _self: empty_iter()
        mock_connect.side_effect = mock_connect_coro

        # Subscribe while disconnected
        client._subscribed_projects.add("project-123")
        client._subscribed_projects.add("project-456")

        await client.connect()

        # Handle connected message which triggers re-subscription
        await client._handle_message(json.dumps({
            "type": "connected",
            "connection_id": "conn-123",
        }))

        # Should have sent subscribe messages
        assert mock_websocket.send.call_count >= 2

        await client.disconnect()


class TestWebSocketClientPollingFallback:
    """Tests for WebSocketClient polling fallback."""

    async def test_fallback_to_polling_on_circuit_open(self, config):
        """Test fallback to polling when circuit breaker opens."""
        config.polling_enabled = True
        client = WebSocketClient(config)

        # Open the circuit breaker
        for _ in range(3):
            await client._circuit_breaker.record_failure()

        await client.connect()

        # Should start polling
        await asyncio.sleep(0.1)
        assert client.state == ConnectionState.FALLBACK_POLLING

        await client.disconnect()

    async def test_polling_disabled(self, config):
        """Test that polling can be disabled."""
        config.polling_enabled = False
        client = WebSocketClient(config)

        # Open the circuit breaker
        for _ in range(3):
            await client._circuit_breaker.record_failure()

        await client.connect()

        # Should not start polling
        assert client.state != ConnectionState.FALLBACK_POLLING

        await client.disconnect()


class TestWebSocketClientSingleton:
    """Tests for WebSocket client singleton management."""

    async def test_get_websocket_client_requires_config_first_time(self):
        """Test that config is required on first call."""
        # Reset singleton
        import app.clients.websocket_client as module
        module._websocket_client = None

        with pytest.raises(ValueError, match="WebSocketClientConfig required"):
            get_websocket_client()

    async def test_get_websocket_client_returns_same_instance(self, config):
        """Test that singleton returns same instance."""
        # Reset singleton
        import app.clients.websocket_client as module
        module._websocket_client = None

        client1 = get_websocket_client(config)
        client2 = get_websocket_client()

        assert client1 is client2

        await close_websocket_client()

    async def test_close_websocket_client(self, config):
        """Test closing the singleton client."""
        # Reset singleton
        import app.clients.websocket_client as module
        module._websocket_client = None

        get_websocket_client(config)
        await close_websocket_client()

        assert module._websocket_client is None


class TestWebSocketClientWaitForMessage:
    """Tests for WebSocketClient wait_for_message."""

    async def test_wait_for_message_receives(self, client):
        """Test waiting for a specific message type."""
        async def send_message():
            await asyncio.sleep(0.1)
            await client._handle_message(json.dumps({
                "type": "subscribed",
                "project_id": "project-123",
            }))

        asyncio.create_task(send_message())

        message = await client.wait_for_message("subscribed", timeout=1.0)

        assert message is not None
        assert message.type == "subscribed"

    async def test_wait_for_message_timeout(self, client):
        """Test wait_for_message timeout."""
        message = await client.wait_for_message("never_sent", timeout=0.1)

        assert message is None


class TestWebSocketClientHeartbeat:
    """Tests for WebSocketClient heartbeat mechanism."""

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_heartbeat_sends_ping(self, mock_connect, config, mock_websocket):
        """Test that heartbeat sends ping messages."""
        config.heartbeat_interval = 0.05  # 50ms
        config.heartbeat_timeout = 2.0
        client = WebSocketClient(config)

        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        # Use a blocking iterator so receive_loop doesn't complete
        async def blocking_iter():
            while True:
                await asyncio.sleep(10)
                yield "never"

        mock_websocket.__aiter__ = lambda _self: blocking_iter()
        mock_connect.side_effect = mock_connect_coro

        await client.connect()

        # Wait longer to ensure heartbeat loop runs
        await asyncio.sleep(0.1)

        # Should have sent at least one ping
        calls = [str(call) for call in mock_websocket.send.call_args_list]
        assert any("ping" in call for call in calls), f"Expected ping in calls: {calls}"

        await client.disconnect()

    @patch("app.clients.websocket_client.websockets.connect")
    async def test_heartbeat_timeout_closes_connection(self, mock_connect, config, mock_websocket):
        """Test that heartbeat timeout closes connection."""
        config.heartbeat_interval = 0.05  # 50ms
        config.heartbeat_timeout = 0.1  # 100ms timeout
        client = WebSocketClient(config)

        async def mock_connect_coro(*args, **kwargs):
            return mock_websocket

        # Use a blocking iterator so receive_loop doesn't complete
        async def blocking_iter():
            while True:
                await asyncio.sleep(10)
                yield "never"

        mock_websocket.__aiter__ = lambda _self: blocking_iter()
        mock_connect.side_effect = mock_connect_coro

        await client.connect()

        # Set last pong to long ago to trigger timeout (must be > heartbeat_timeout)
        client._last_pong = time.monotonic() - 0.5  # 500ms ago, well past 100ms timeout

        # Wait for heartbeat loop to run
        await asyncio.sleep(0.1)

        # Heartbeat loop should have triggered close
        mock_websocket.close.assert_called()

        await client.disconnect()
