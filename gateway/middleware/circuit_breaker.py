"""Circuit breaker for upstream API proxy."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


@dataclass
class CircuitBreaker:
    """Circuit breaker that protects upstream calls from cascading failures.

    State transitions:
        CLOSED  → OPEN      : failure_count reaches failure_threshold
        OPEN    → HALF_OPEN : recovery_timeout seconds have elapsed
        HALF_OPEN → CLOSED  : success_count reaches success_threshold
        HALF_OPEN → OPEN    : any single failure

    Attributes:
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout: Seconds to wait in OPEN state before probing.
        success_threshold: Consecutive successes in HALF_OPEN to close.
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)

    @property
    def state(self) -> CircuitState:
        """Return the current state, auto-transitioning OPEN → HALF_OPEN on timeout."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
        return self._state

    def allow_request(self) -> bool:
        """Return True if the circuit allows a request to proceed.

        Returns:
            True for CLOSED or HALF_OPEN (probe), False for OPEN.
        """
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow one test request through
        return False  # OPEN — reject

    def record_success(self) -> None:
        """Record a successful upstream call.

        In HALF_OPEN: increments success counter; closes circuit when threshold met.
        In CLOSED: resets failure counter.
        """
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        else:
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed upstream call.

        Increments failure counter and opens the circuit when threshold is met.
        Any failure in HALF_OPEN immediately re-opens the circuit.
        """
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Fully reset the circuit breaker to the initial CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
