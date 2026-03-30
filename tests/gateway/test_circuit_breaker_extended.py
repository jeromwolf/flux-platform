"""Extended unit tests for gateway.middleware.circuit_breaker.

Targets the 16 statements not covered by test_circuit_breaker.py,
specifically:
- CircuitState enum values
- record_failure() below threshold but in HALF_OPEN (elif branch)
- record_success() _success_count not yet at threshold in HALF_OPEN
- state property when NOT in OPEN (short-circuit return paths)
- reset() clears _last_failure_time conceptually
- Custom threshold combinations
- allow_request() return False path explicitly
- Failure count accumulation < threshold
- OPEN → HALF_OPEN auto-transition resets _success_count
- Multiple success/failure interleaving in HALF_OPEN
"""
from __future__ import annotations

import time

import pytest

from gateway.middleware.circuit_breaker import CircuitBreaker, CircuitState


# ---------------------------------------------------------------------------
# CircuitState enum
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_circuit_state_enum_values():
    assert CircuitState.CLOSED.value == "closed"
    assert CircuitState.OPEN.value == "open"
    assert CircuitState.HALF_OPEN.value == "half_open"


@pytest.mark.unit
def test_circuit_state_enum_members():
    members = {s.name for s in CircuitState}
    assert members == {"CLOSED", "OPEN", "HALF_OPEN"}


# ---------------------------------------------------------------------------
# Initial state / defaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_default_thresholds():
    cb = CircuitBreaker()
    assert cb.failure_threshold == 5
    assert cb.recovery_timeout == 30.0
    assert cb.success_threshold == 2


@pytest.mark.unit
def test_initial_internal_counters():
    cb = CircuitBreaker()
    assert cb._failure_count == 0
    assert cb._success_count == 0
    assert cb._last_failure_time == 0.0
    assert cb._state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# state property — non-OPEN paths (direct returns without time check)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_state_property_returns_closed_directly():
    cb = CircuitBreaker()
    # .state should return CLOSED without touching time.monotonic
    assert cb.state == CircuitState.CLOSED


@pytest.mark.unit
def test_state_property_returns_half_open_directly(monkeypatch):
    """When already HALF_OPEN, .state returns HALF_OPEN without time check."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
    cb.record_failure()
    # Force to HALF_OPEN manually
    cb._state = CircuitState.HALF_OPEN
    # Patch monotonic to raise so we detect if it is called
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: (_ for _ in ()).throw(AssertionError("monotonic called in HALF_OPEN")),
    )
    assert cb.state == CircuitState.HALF_OPEN


# ---------------------------------------------------------------------------
# allow_request() — explicit OPEN rejection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_allow_request_false_when_open_explicitly():
    cb = CircuitBreaker(failure_threshold=1)
    cb._state = CircuitState.OPEN
    cb._last_failure_time = time.monotonic()  # just happened
    assert cb.allow_request() is False


# ---------------------------------------------------------------------------
# record_failure() — below threshold, stays CLOSED
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_record_failure_below_threshold_stays_closed():
    cb = CircuitBreaker(failure_threshold=5)
    for i in range(4):
        cb.record_failure()
        assert cb._state == CircuitState.CLOSED, f"should stay CLOSED after {i+1} failure(s)"
    assert cb._failure_count == 4


@pytest.mark.unit
def test_record_failure_updates_last_failure_time():
    cb = CircuitBreaker(failure_threshold=10)
    before = time.monotonic()
    cb.record_failure()
    after = time.monotonic()
    assert before <= cb._last_failure_time <= after


@pytest.mark.unit
def test_record_failure_increments_count():
    cb = CircuitBreaker(failure_threshold=10)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb._failure_count == 3


# ---------------------------------------------------------------------------
# record_failure() in HALF_OPEN — elif branch (count < threshold)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_record_failure_in_half_open_reopens_without_reaching_threshold(monkeypatch):
    """The elif branch: HALF_OPEN + failure_count < failure_threshold → OPEN."""
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1.0)

    # Drive to OPEN via one failure, then manually set to HALF_OPEN
    cb._state = CircuitState.OPEN
    cb._last_failure_time = time.monotonic() - 999  # long ago

    # Trigger HALF_OPEN via .state
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._failure_count < cb.failure_threshold  # not at threshold

    # Now a failure in HALF_OPEN should hit the elif and re-open
    cb.record_failure()
    assert cb._state == CircuitState.OPEN


@pytest.mark.unit
def test_record_failure_in_half_open_increments_count(monkeypatch):
    cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.0)
    cb._state = CircuitState.OPEN
    cb._last_failure_time = 0.0
    _ = cb.state  # trigger HALF_OPEN
    prev_count = cb._failure_count
    cb.record_failure()
    assert cb._failure_count == prev_count + 1


# ---------------------------------------------------------------------------
# record_success() in HALF_OPEN — partial progress (< threshold)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_record_success_in_half_open_increments_success_count(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0, success_threshold=3)
    cb.record_failure()
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()
    assert cb._success_count == 1
    assert cb._state == CircuitState.HALF_OPEN  # not yet closed

    cb.record_success()
    assert cb._success_count == 2
    assert cb._state == CircuitState.HALF_OPEN  # still need one more

    cb.record_success()
    assert cb._state == CircuitState.CLOSED


@pytest.mark.unit
def test_record_success_in_half_open_resets_failure_count_on_close(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0, success_threshold=1)
    cb.record_failure()
    assert cb.state == CircuitState.HALF_OPEN

    cb.record_success()  # closes
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# OPEN → HALF_OPEN transition resets _success_count
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_open_to_half_open_resets_success_count(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1.0, success_threshold=2)
    cb.record_failure()
    assert cb._state == CircuitState.OPEN

    # Manually set _success_count to a non-zero value (simulating prior session)
    cb._success_count = 99

    original = time.monotonic()
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 5.0,
    )
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._success_count == 0


# ---------------------------------------------------------------------------
# reset() — full reset including last_failure_time
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_reset_from_open_clears_all_state():
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_failure()
    cb.record_failure()
    assert cb._state == CircuitState.OPEN

    cb.reset()
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0
    assert cb._success_count == 0


@pytest.mark.unit
def test_reset_from_half_open():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0)
    cb.record_failure()
    _ = cb.state  # HALF_OPEN
    cb.reset()
    assert cb._state == CircuitState.CLOSED
    assert cb.allow_request() is True


@pytest.mark.unit
def test_reset_from_closed_is_idempotent():
    cb = CircuitBreaker()
    cb.reset()
    assert cb._state == CircuitState.CLOSED
    assert cb._failure_count == 0


# ---------------------------------------------------------------------------
# Custom threshold combinations
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_custom_failure_threshold_1():
    cb = CircuitBreaker(failure_threshold=1)
    cb.record_failure()
    assert cb._state == CircuitState.OPEN


@pytest.mark.unit
def test_custom_success_threshold_1(monkeypatch):
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0, success_threshold=1)
    cb.record_failure()
    _ = cb.state  # HALF_OPEN
    cb.record_success()
    assert cb._state == CircuitState.CLOSED


@pytest.mark.unit
def test_custom_recovery_timeout_large(monkeypatch):
    """With a very large recovery_timeout, OPEN does NOT transition to HALF_OPEN."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999.0)
    cb.record_failure()
    # Only 1 second has passed
    original = time.monotonic()
    monkeypatch.setattr(
        "gateway.middleware.circuit_breaker.time.monotonic",
        lambda: original + 1.0,
    )
    assert cb.state == CircuitState.OPEN


# ---------------------------------------------------------------------------
# Multiple full cycles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_three_open_close_cycles():
    """Circuit reliably opens and closes across multiple cycles."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.0, success_threshold=1)

    for cycle in range(3):
        # Open
        cb.record_failure()
        cb.record_failure()
        assert cb._state == CircuitState.OPEN, f"cycle {cycle}: should be OPEN"

        # Recover
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb._state == CircuitState.CLOSED, f"cycle {cycle}: should be CLOSED"


@pytest.mark.unit
def test_interleaved_success_failure_in_half_open(monkeypatch):
    """Failure in HALF_OPEN after partial successes re-opens; successes don't carry over."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.0, success_threshold=3)
    cb.record_failure()
    _ = cb.state  # HALF_OPEN

    cb.record_success()  # success_count=1
    cb.record_success()  # success_count=2
    assert cb._state == CircuitState.HALF_OPEN

    cb.record_failure()  # reopens
    assert cb._state == CircuitState.OPEN

    # Recover again — success_count should have been reset to 0 by transition
    cb._last_failure_time = 0.0  # force immediate timeout
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._success_count == 0
