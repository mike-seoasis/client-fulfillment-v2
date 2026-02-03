"""Shared circuit breaker implementation.

Circuit breaker pattern prevents cascading failures by stopping requests
to a failing service. After recovery_timeout, allows a test request through
(half-open state). If test succeeds, circuit closes. If fails, circuit opens again.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject all requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int
    recovery_timeout: float


class CircuitBreaker:
    """Circuit breaker implementation for service operations.

    Prevents cascading failures by stopping requests to a failing service.
    After recovery_timeout, allows a test request through (half-open state).
    If test succeeds, circuit closes. If fails, circuit opens again.
    """

    def __init__(self, config: CircuitBreakerConfig, name: str = "default") -> None:
        self._config = config
        self._name = name
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        """Get circuit breaker name."""
        return self._name

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    async def _check_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = time.monotonic() - self._last_failure_time
        return elapsed >= self._config.recovery_timeout

    def _log_state_change(self, previous_state: str, new_state: str) -> None:
        """Log circuit state transition."""
        logger.info(
            "Circuit breaker state change",
            extra={
                "circuit_name": self._name,
                "previous_state": previous_state,
                "new_state": new_state,
                "failure_count": self._failure_count,
            },
        )

    def _log_circuit_open(self) -> None:
        """Log circuit opened event."""
        logger.warning(
            "Circuit breaker opened",
            extra={
                "circuit_name": self._name,
                "failure_count": self._failure_count,
                "recovery_timeout": self._config.recovery_timeout,
            },
        )

    def _log_recovery_attempt(self) -> None:
        """Log recovery attempt."""
        logger.info(
            "Circuit breaker attempting recovery",
            extra={"circuit_name": self._name},
        )

    def _log_circuit_closed(self) -> None:
        """Log circuit closed (recovered)."""
        logger.info(
            "Circuit breaker closed (recovered)",
            extra={"circuit_name": self._name},
        )

    async def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit state."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if await self._check_recovery():
                    # Transition to half-open for testing
                    previous_state = self._state.value
                    self._state = CircuitState.HALF_OPEN
                    self._log_state_change(previous_state, self._state.value)
                    self._log_recovery_attempt()
                    return True
                return False

            # HALF_OPEN state - allow single test request
            return True

    async def record_success(self) -> None:
        """Record successful operation."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Recovery successful, close circuit
                previous_state = self._state.value
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._last_failure_time = None
                self._log_state_change(previous_state, self._state.value)
                self._log_circuit_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record failed operation."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Recovery failed, open circuit again
                previous_state = self._state.value
                self._state = CircuitState.OPEN
                self._log_state_change(previous_state, self._state.value)
                self._log_circuit_open()
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self._config.failure_threshold
            ):
                # Too many failures, open circuit
                previous_state = self._state.value
                self._state = CircuitState.OPEN
                self._log_state_change(previous_state, self._state.value)
                self._log_circuit_open()
