## ADDED Requirements

### Requirement: Shared CircuitBreaker module
The system SHALL provide a single, shared CircuitBreaker implementation at `backend/app/core/circuit_breaker.py` that all integration clients use.

#### Scenario: Module exports required components
- **WHEN** an integration client imports from `app.core.circuit_breaker`
- **THEN** `CircuitState`, `CircuitBreakerConfig`, and `CircuitBreaker` are available

#### Scenario: No duplicate implementations
- **WHEN** searching the codebase for `class CircuitBreaker`
- **THEN** only one definition exists (in `core/circuit_breaker.py`)

### Requirement: CircuitBreaker state machine
The CircuitBreaker SHALL implement a three-state machine: CLOSED (normal), OPEN (failing), and HALF_OPEN (testing recovery).

#### Scenario: Initial state is CLOSED
- **WHEN** a new CircuitBreaker is instantiated
- **THEN** its state is CLOSED

#### Scenario: Opens after failure threshold
- **WHEN** consecutive failures reach `failure_threshold`
- **THEN** state transitions to OPEN

#### Scenario: Transitions to HALF_OPEN after recovery timeout
- **WHEN** state is OPEN and `recovery_timeout` seconds have elapsed
- **THEN** state transitions to HALF_OPEN on next `can_execute()` call

#### Scenario: Closes on success in HALF_OPEN
- **WHEN** state is HALF_OPEN and `record_success()` is called
- **THEN** state transitions to CLOSED and failure count resets

#### Scenario: Reopens on failure in HALF_OPEN
- **WHEN** state is HALF_OPEN and `record_failure()` is called
- **THEN** state transitions to OPEN

### Requirement: CircuitBreaker configuration
The CircuitBreaker SHALL accept configuration via `CircuitBreakerConfig` dataclass with `failure_threshold` and `recovery_timeout` parameters.

#### Scenario: Custom thresholds
- **WHEN** CircuitBreaker is created with `CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30.0)`
- **THEN** circuit opens after 5 failures and recovers after 30 seconds

### Requirement: CircuitBreaker naming for logging
The CircuitBreaker SHALL accept a `name` parameter for logging context, identifying which service the circuit protects.

#### Scenario: Named circuit breaker
- **WHEN** CircuitBreaker is created with `name="pop_api"`
- **THEN** log messages include "pop_api" as the circuit identifier

### Requirement: Thread-safe async operations
The CircuitBreaker SHALL use `asyncio.Lock` to ensure thread-safe state transitions in async contexts.

#### Scenario: Concurrent access
- **WHEN** multiple coroutines call `can_execute()` simultaneously
- **THEN** state transitions are atomic and consistent

### Requirement: Integration client refactoring
All integration clients SHALL import CircuitBreaker from the shared module and remove local implementations.

#### Scenario: Redis client uses shared module
- **WHEN** examining `backend/app/core/redis.py`
- **THEN** it imports from `app.core.circuit_breaker` and has no local CircuitBreaker class

#### Scenario: POP client uses shared module
- **WHEN** examining `backend/app/integrations/pop.py`
- **THEN** it imports from `app.core.circuit_breaker` and has no local CircuitBreaker class

#### Scenario: All 11 clients refactored
- **WHEN** examining redis.py and all 10 integration files
- **THEN** each imports from `app.core.circuit_breaker` with no local implementations
