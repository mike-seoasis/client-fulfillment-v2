"""Tests for shared CircuitBreaker module.

Tests the circuit breaker pattern implementation:
- Initial state is CLOSED (normal operation)
- Opens after failure_threshold failures
- Transitions to HALF_OPEN after recovery_timeout
- Closes on success in HALF_OPEN state
- Reopens on failure in HALF_OPEN state
"""

from unittest.mock import patch

import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState


class TestCircuitBreakerInitialState:
    """Test initial state of CircuitBreaker."""

    def test_initial_state_is_closed(self) -> None:
        """CircuitBreaker should start in CLOSED state."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.is_half_open is False

    def test_initial_failure_count_is_zero(self) -> None:
        """CircuitBreaker should start with zero failures."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        assert cb.failure_count == 0

    def test_name_property(self) -> None:
        """CircuitBreaker should expose its name."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="my_service")

        assert cb.name == "my_service"


class TestCircuitBreakerOpensAfterThreshold:
    """Test that circuit opens after failure_threshold failures."""

    @pytest.mark.asyncio
    async def test_opens_after_reaching_threshold(self) -> None:
        """Circuit should open after failure_threshold consecutive failures."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Record failures up to threshold
        await cb.record_failure()
        assert cb.is_closed is True  # Not open yet (1 failure)

        await cb.record_failure()
        assert cb.is_closed is True  # Not open yet (2 failures)

        await cb.record_failure()
        assert cb.is_open is True  # Now open (3 failures = threshold)
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_failure_count_increments(self) -> None:
        """Failure count should increment on each failure."""
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        await cb.record_failure()
        assert cb.failure_count == 1

        await cb.record_failure()
        assert cb.failure_count == 2

        await cb.record_failure()
        assert cb.failure_count == 3

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Success in CLOSED state should reset failure count."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        await cb.record_failure()
        await cb.record_failure()
        assert cb.failure_count == 2

        await cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_closed is True


class TestCircuitBreakerCanExecute:
    """Test can_execute behavior in different states."""

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self) -> None:
        """Should allow execution when circuit is closed."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        assert await cb.can_execute() is True

    @pytest.mark.asyncio
    async def test_cannot_execute_when_open_before_timeout(self) -> None:
        """Should block execution when circuit is open and timeout not reached."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        cb = CircuitBreaker(config, name="test")

        # Open the circuit
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # Should not allow execution (timeout hasn't passed)
        assert await cb.can_execute() is False


class TestCircuitBreakerTransitionsToHalfOpen:
    """Test transition to HALF_OPEN state after recovery_timeout."""

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_timeout(self) -> None:
        """Circuit should transition to HALF_OPEN after recovery_timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Open the circuit
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # Mock time to simulate timeout elapsed
        with patch("time.monotonic") as mock_time:
            # Set initial time when failure was recorded
            initial_time = 1000.0
            mock_time.return_value = initial_time

            # Re-record failure to update _last_failure_time with mocked time
            cb._last_failure_time = initial_time

            # Advance time past recovery_timeout
            mock_time.return_value = initial_time + 31.0  # 31 seconds > 30 second timeout

            # Now can_execute should transition to HALF_OPEN and return True
            result = await cb.can_execute()
            assert result is True
            assert cb.is_half_open is True
            assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_allows_test_request_in_half_open(self) -> None:
        """Should allow a test request when in HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Manually set to HALF_OPEN state
        cb._state = CircuitState.HALF_OPEN

        assert await cb.can_execute() is True


class TestCircuitBreakerClosesOnSuccessInHalfOpen:
    """Test that circuit closes on success in HALF_OPEN state."""

    @pytest.mark.asyncio
    async def test_closes_on_success_in_half_open(self) -> None:
        """Circuit should close when success recorded in HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Set to HALF_OPEN state
        cb._state = CircuitState.HALF_OPEN
        cb._failure_count = 2

        # Record success
        await cb.record_success()

        assert cb.is_closed is True
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_resets_failure_time_on_close(self) -> None:
        """Should reset last_failure_time when closing from HALF_OPEN."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Set to HALF_OPEN state with a failure time
        cb._state = CircuitState.HALF_OPEN
        cb._last_failure_time = 1000.0

        await cb.record_success()

        assert cb._last_failure_time is None


class TestCircuitBreakerReopensOnFailureInHalfOpen:
    """Test that circuit reopens on failure in HALF_OPEN state."""

    @pytest.mark.asyncio
    async def test_reopens_on_failure_in_half_open(self) -> None:
        """Circuit should reopen when failure recorded in HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test")

        # Set to HALF_OPEN state
        cb._state = CircuitState.HALF_OPEN

        # Record failure
        await cb.record_failure()

        assert cb.is_open is True
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerLogging:
    """Test logging behavior."""

    @pytest.mark.asyncio
    async def test_logs_state_change_to_open(self) -> None:
        """Should log when transitioning to OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test_service")

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            await cb.record_failure()
            await cb.record_failure()

            # Should have logged the state change and circuit open
            assert mock_logger.info.called
            assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_logs_recovery_attempt(self) -> None:
        """Should log when attempting recovery in HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test_service")

        # Open the circuit
        cb._state = CircuitState.OPEN
        cb._last_failure_time = 0.0

        with (
            patch("time.monotonic", return_value=100.0),  # Well past timeout
            patch("app.core.circuit_breaker.logger") as mock_logger,
        ):
            await cb.can_execute()

            # Should have logged recovery attempt
            assert mock_logger.info.called

    @pytest.mark.asyncio
    async def test_logs_circuit_closed_on_recovery(self) -> None:
        """Should log when circuit closes after successful recovery."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=30.0)
        cb = CircuitBreaker(config, name="test_service")

        cb._state = CircuitState.HALF_OPEN

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            await cb.record_success()

            # Should have logged circuit closed
            assert mock_logger.info.called


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig dataclass."""

    def test_config_stores_values(self) -> None:
        """Config should store failure_threshold and recovery_timeout."""
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0


class TestCircuitStateEnum:
    """Test CircuitState enum."""

    def test_circuit_states(self) -> None:
        """CircuitState should have CLOSED, OPEN, and HALF_OPEN values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerFullCycle:
    """Integration test for full circuit breaker cycle."""

    @pytest.mark.asyncio
    async def test_full_cycle_closed_open_half_open_closed(self) -> None:
        """Test complete lifecycle: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=10.0)
        cb = CircuitBreaker(config, name="integration_test")

        # 1. Start CLOSED
        assert cb.is_closed is True

        # 2. Failures open the circuit
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # 3. After timeout, transitions to HALF_OPEN
        cb._last_failure_time = 0.0  # Set to past time
        with patch("time.monotonic", return_value=100.0):
            await cb.can_execute()
        assert cb.is_half_open is True

        # 4. Success in HALF_OPEN closes the circuit
        await cb.record_success()
        assert cb.is_closed is True
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_full_cycle_with_failed_recovery(self) -> None:
        """Test lifecycle where recovery fails: CLOSED -> OPEN -> HALF_OPEN -> OPEN."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=10.0)
        cb = CircuitBreaker(config, name="integration_test")

        # 1. Start CLOSED
        assert cb.is_closed is True

        # 2. Failures open the circuit
        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_open is True

        # 3. After timeout, transitions to HALF_OPEN
        cb._last_failure_time = 0.0
        with patch("time.monotonic", return_value=100.0):
            await cb.can_execute()
        assert cb.is_half_open is True

        # 4. Failure in HALF_OPEN reopens the circuit
        await cb.record_failure()
        assert cb.is_open is True
