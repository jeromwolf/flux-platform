"""Circuit Breaker unit tests.

TC-CB01 ~ TC-CB10: CircuitBreaker state machine and behavior tests.
All tests run without external dependencies.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from kg.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    CircuitStats,
)


# =============================================================================
# TC-CB01: Initial state
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerInitialState:
    """Circuit breaker initial state tests."""

    def test_initial_state_is_closed(self) -> None:
        """TC-CB01-a: New circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED

    def test_initial_stats_are_zero(self) -> None:
        """TC-CB01-b: Initial statistics are all zero."""
        cb = CircuitBreaker(name="test")
        assert cb.stats.total_calls == 0
        assert cb.stats.total_successes == 0
        assert cb.stats.total_failures == 0

    def test_custom_config(self) -> None:
        """TC-CB01-c: Custom configuration is stored correctly."""
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=3,
            recovery_timeout=10.0,
            success_threshold=1,
        )
        assert cb.name == "custom"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 10.0
        assert cb.success_threshold == 1


# =============================================================================
# TC-CB02: State transitions
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerTransitions:
    """State transition tests."""

    def test_closes_to_open_after_threshold(self) -> None:
        """TC-CB02-a: Circuit opens after consecutive failures reach threshold."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        for _ in range(3):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN

    def test_open_blocks_calls(self) -> None:
        """TC-CB02-b: OPEN circuit raises CircuitOpenError."""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=60.0)
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        with pytest.raises(CircuitOpenError) as exc_info:
            with cb:
                pass  # pragma: no cover
        assert exc_info.value.breaker_name == "test"
        assert exc_info.value.retry_after > 0

    def test_open_to_half_open_after_timeout(self) -> None:
        """TC-CB02-c: OPEN transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_to_closed_on_success(self) -> None:
        """TC-CB02-d: HALF_OPEN closes after success_threshold successes."""
        cb = CircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.1, success_threshold=1
        )
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        time.sleep(0.15)
        # Now in HALF_OPEN
        with cb:
            pass  # success
        assert cb.state == CircuitState.CLOSED

    def test_half_open_to_open_on_failure(self) -> None:
        """TC-CB02-e: Any failure in HALF_OPEN reopens the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=0.1)
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        try:
            with cb:
                raise RuntimeError("fail again")
        except RuntimeError:
            pass
        assert cb.state == CircuitState.OPEN


# =============================================================================
# TC-CB03: Success resets failures
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerSuccessReset:
    """Success call behavior."""

    def test_success_resets_consecutive_failures(self) -> None:
        """TC-CB03-a: A success resets the consecutive failure counter."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        # 2 failures
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        assert cb.stats.consecutive_failures == 2
        # 1 success
        with cb:
            pass
        assert cb.stats.consecutive_failures == 0
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# TC-CB04: Excluded exceptions
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerExclusions:
    """Excluded exception handling."""

    def test_excluded_exception_not_counted(self) -> None:
        """TC-CB04-a: Excluded exceptions don't count as failures."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )
        for _ in range(5):
            try:
                with cb:
                    raise ValueError("not a failure")
            except ValueError:
                pass
        assert cb.state == CircuitState.CLOSED
        assert cb.stats.total_failures == 0

    def test_non_excluded_exception_counted(self) -> None:
        """TC-CB04-b: Non-excluded exceptions still count as failures."""
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            excluded_exceptions=(ValueError,),
        )
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("real failure")
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN


# =============================================================================
# TC-CB05: Decorator usage
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerDecorator:
    """Decorator pattern tests."""

    def test_sync_decorator(self) -> None:
        """TC-CB05-a: Circuit breaker works as sync function decorator."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        @cb
        def my_func() -> str:
            return "ok"

        assert my_func() == "ok"
        assert cb.stats.total_successes == 1

    def test_async_decorator(self) -> None:
        """TC-CB05-b: Circuit breaker works as async function decorator."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        @cb
        async def my_func() -> str:
            return "ok"

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(my_func())
        finally:
            loop.close()
        assert result == "ok"
        assert cb.stats.total_successes == 1


# =============================================================================
# TC-CB06: Reset
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerReset:
    """Manual reset tests."""

    def test_reset_closes_open_circuit(self) -> None:
        """TC-CB06-a: reset() closes an OPEN circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(2):
            try:
                with cb:
                    raise RuntimeError("fail")
            except RuntimeError:
                pass
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# TC-CB07: Stats tracking
# =============================================================================


@pytest.mark.unit
class TestCircuitBreakerStats:
    """Statistics tracking tests."""

    def test_stats_increment_on_calls(self) -> None:
        """TC-CB07-a: Stats are incremented correctly."""
        cb = CircuitBreaker(name="test", failure_threshold=10)
        with cb:
            pass
        try:
            with cb:
                raise RuntimeError("fail")
        except RuntimeError:
            pass
        with cb:
            pass
        assert cb.stats.total_calls == 3
        assert cb.stats.total_successes == 2
        assert cb.stats.total_failures == 1


# =============================================================================
# TC-CB08: CircuitState enum
# =============================================================================


@pytest.mark.unit
class TestCircuitStateEnum:
    """CircuitState enum tests."""

    def test_state_values(self) -> None:
        """TC-CB08-a: CircuitState has correct string values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_state_is_string(self) -> None:
        """TC-CB08-b: CircuitState members are strings."""
        assert isinstance(CircuitState.CLOSED, str)
