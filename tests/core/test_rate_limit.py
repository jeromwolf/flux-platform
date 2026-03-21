"""Unit tests for the rate limiting middleware."""
from __future__ import annotations

import pytest

from kg.api.middleware.rate_limit import (
    DEFAULT_LIMIT,
    ROLE_LIMITS,
    TokenBucket,
    RateLimitMiddleware,
)


@pytest.mark.unit
class TestTokenBucket:
    """Tests for TokenBucket rate limiter."""

    def test_initial_capacity(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.remaining == 10

    def test_consume_decrements(self):
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket.consume() is True
        assert bucket.remaining == 9

    def test_consume_until_empty(self):
        bucket = TokenBucket(capacity=3, refill_rate=0.0)  # no refill
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False  # empty

    def test_remaining_never_negative(self):
        bucket = TokenBucket(capacity=1, refill_rate=0.0)
        bucket.consume()
        bucket.consume()  # try even though empty
        assert bucket.remaining >= 0

    def test_refill_adds_tokens(self):
        import time
        bucket = TokenBucket(capacity=10, refill_rate=100.0)  # 100/sec
        bucket.consume()
        bucket.consume()
        time.sleep(0.05)  # wait 50ms -> ~5 tokens refilled
        assert bucket.remaining >= 5  # should have refilled some

    def test_capacity_is_max(self):
        import time
        bucket = TokenBucket(capacity=5, refill_rate=1000.0)  # very fast refill
        time.sleep(0.01)
        assert bucket.remaining <= 5  # capped at capacity


@pytest.mark.unit
class TestRoleLimits:
    """Tests for role-based rate limit configuration."""

    def test_admin_has_highest_limit(self):
        assert ROLE_LIMITS["admin"] >= ROLE_LIMITS["viewer"]

    def test_all_roles_have_positive_limits(self):
        for role, limit in ROLE_LIMITS.items():
            assert limit > 0, f"Role {role} has non-positive limit"

    def test_default_limit_positive(self):
        assert DEFAULT_LIMIT > 0

    def test_known_roles_exist(self):
        assert "admin" in ROLE_LIMITS
        assert "researcher" in ROLE_LIMITS
        assert "viewer" in ROLE_LIMITS
