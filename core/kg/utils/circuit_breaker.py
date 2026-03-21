"""Circuit Breaker pattern for external service calls.

Implements the classic three-state circuit breaker (CLOSED → OPEN → HALF_OPEN)
to prevent cascading failures when external services (Neo4j, LLM providers,
embedding services) become unresponsive.

Usage::

    from kg.utils.circuit_breaker import CircuitBreaker

    neo4j_breaker = CircuitBreaker(
        name="neo4j",
        failure_threshold=5,
        recovery_timeout=30.0,
    )

    # Synchronous usage
    with neo4j_breaker:
        result = session.run("RETURN 1")

    # Async usage
    async with neo4j_breaker:
        result = await async_session.run("RETURN 1")

    # Decorator usage
    @neo4j_breaker
    def query_neo4j():
        return session.run("RETURN 1")
"""
from __future__ import annotations

import enum
import functools
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, enum.Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation, requests pass through
    OPEN = "open"              # Failures exceeded threshold, requests blocked
    HALF_OPEN = "half_open"    # Testing if service has recovered


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is OPEN.

    Attributes:
        breaker_name: Name of the circuit breaker that blocked the call.
        retry_after: Seconds until the circuit will transition to HALF_OPEN.
    """

    def __init__(self, breaker_name: str, retry_after: float) -> None:
        self.breaker_name = breaker_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{breaker_name}' is OPEN. Retry after {retry_after:.1f}s"
        )


@dataclass
class CircuitStats:
    """Mutable statistics for a circuit breaker (not frozen - updated in place)."""
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    last_state_change: float = field(default_factory=time.monotonic)


class CircuitBreaker:
    """Three-state circuit breaker for protecting external service calls.

    Thread-safe implementation using a reentrant lock.

    Args:
        name: Human-readable name for logging and error messages.
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout: Seconds to wait in OPEN state before trying HALF_OPEN.
        success_threshold: Successes needed in HALF_OPEN to close the circuit.
        excluded_exceptions: Exception types that should NOT count as failures.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        success_threshold: int = 2,
        excluded_exceptions: tuple[type[Exception], ...] = (),
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.excluded_exceptions = excluded_exceptions

        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current circuit state (may auto-transition OPEN → HALF_OPEN)."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._recovery_timeout_elapsed():
                    self._transition(CircuitState.HALF_OPEN)
            return self._state

    @property
    def stats(self) -> CircuitStats:
        """Current circuit statistics snapshot."""
        return self._stats

    # ------------------------------------------------------------------
    # Sync context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> CircuitBreaker:
        self._before_call()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is None:
            self._on_success()
        elif self.excluded_exceptions and isinstance(exc_val, self.excluded_exceptions):
            self._on_success()  # Don't count excluded exceptions as failures
        else:
            self._on_failure()
        return False  # Don't suppress exceptions

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> CircuitBreaker:
        self._before_call()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is None:
            self._on_success()
        elif self.excluded_exceptions and isinstance(exc_val, self.excluded_exceptions):
            self._on_success()
        else:
            self._on_failure()
        return False

    # ------------------------------------------------------------------
    # Decorator
    # ------------------------------------------------------------------

    def __call__(self, func: F) -> F:
        """Use the circuit breaker as a decorator."""
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with self:
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            async with self:
                return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Manual control
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Force-reset the circuit to CLOSED state."""
        with self._lock:
            self._transition(CircuitState.CLOSED)
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _before_call(self) -> None:
        """Check if the call should proceed. Raises CircuitOpenError if OPEN."""
        with self._lock:
            current = self.state  # triggers OPEN → HALF_OPEN if timeout elapsed
            if current == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (
                    time.monotonic() - self._stats.last_state_change
                )
                raise CircuitOpenError(self.name, max(0.0, retry_after))
            self._stats.total_calls += 1

    def _on_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._stats.total_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes += 1
            self._stats.last_success_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.success_threshold:
                    self._transition(CircuitState.CLOSED)

    def _on_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._stats.total_failures += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in HALF_OPEN immediately reopens
                self._transition(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._stats.consecutive_failures >= self.failure_threshold:
                    self._transition(CircuitState.OPEN)

    def _recovery_timeout_elapsed(self) -> bool:
        """Check if enough time has passed since opening."""
        return (
            time.monotonic() - self._stats.last_state_change
        ) >= self.recovery_timeout

    def _transition(self, new_state: CircuitState) -> None:
        """Transition to a new state with logging."""
        old = self._state
        self._state = new_state
        self._stats.last_state_change = time.monotonic()
        if new_state == CircuitState.CLOSED:
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0
        logger.info(
            "Circuit '%s' transitioned %s → %s",
            self.name,
            old.value,
            new_state.value,
        )
