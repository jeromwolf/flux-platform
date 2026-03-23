"""Unit tests for gateway.middleware.circuit_breaker."""
from __future__ import annotations

import time

import pytest

from gateway.middleware.circuit_breaker import CircuitBreaker, CircuitState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_circuit(cb: CircuitBreaker) -> None:
    """Drive *cb* into OPEN state by exhausting the failure threshold."""
    for _ in range(cb.failure_threshold):
        cb.record_failure()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_initial_state_is_closed():
    cb = CircuitBreaker()
    assert cb.state == CircuitState.CLOSED


def test_allows_requests_when_closed():
    cb = CircuitBreaker()
    assert cb.allow_request() is True


def test_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3)
    for i in range(2):
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED, f"should still be CLOSED after {i + 1} failures"

    cb.record_failure()  # 3rd failure → threshold reached
    assert cb.state == CircuitState.OPEN


def test_rejects_when_open():
    cb = CircuitBreaker(failure_threshold=2)
    _open_circuit(cb)
    assert cb.allow_request() is False


def test_transitions_to_half_open_after_timeout(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Simulate time passing beyond recovery_timeout
    original = time.monotonic()
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 2.0,
    )

    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True


def test_closes_after_success_threshold_in_half_open(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0, success_threshold=2)
    cb.record_failure()

    original = time.monotonic()
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 2.0,
    )

    # Trigger transition to HALF_OPEN via .state
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN  # still need one more

    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_reopens_on_failure_in_half_open(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0)
    cb.record_failure()

    original = time.monotonic()
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 2.0,
    )

    assert cb.state == CircuitState.HALF_OPEN

    cb.record_failure()  # failure in HALF_OPEN → back to OPEN
    # Reset the monotonic mock to avoid the recovery timeout kicking in immediately
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 2.0,  # same frozen time — won't retrigger timeout
    )
    # The state should be OPEN — but because time is still frozen at +2s and
    # _last_failure_time was recorded at +2s, recovery_timeout has NOT elapsed.
    # We need to check the raw internal state instead.
    assert cb._state == CircuitState.OPEN


def test_reset():
    cb = CircuitBreaker(failure_threshold=2)
    _open_circuit(cb)
    assert cb._state == CircuitState.OPEN

    cb.reset()
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0
    assert cb._success_count == 0
    assert cb.allow_request() is True


def test_success_in_closed_resets_failure_count():
    """record_success() in CLOSED state resets the failure counter."""
    cb = CircuitBreaker(failure_threshold=5)
    cb.record_failure()
    cb.record_failure()
    assert cb._failure_count == 2

    cb.record_success()
    assert cb._failure_count == 0


def test_multiple_cycles():
    """Circuit can open, recover, and open again."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.0, success_threshold=1)

    # First open
    _open_circuit(cb)
    assert cb._state == CircuitState.OPEN

    # Recovery (timeout=0 → immediately HALF_OPEN on next .state access)
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # Second open
    _open_circuit(cb)
    assert cb._state == CircuitState.OPEN
